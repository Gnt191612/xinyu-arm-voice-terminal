"""既有真人录音经新任务入口的真实模型检查；不播放，不冒充本轮真人发声。"""
import json
import argparse
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from supervise_bridge import stop_owned_process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--story', action='store_true', help='复核已保存的睡前故事请求')
    parser.add_argument('--task', action='store_true', help='复核已保存的早餐任务请求')
    args = parser.parse_args()
    output = ROOT / 'records/实时交互' / ('早餐任务完整链路复核' if args.task else
             ('故事完整链路复核' if args.story else '真实任务入口复核'))
    output.mkdir(exist_ok=True)
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def healthy():
        try:
            with opener.open(config['xinyu_url'].rstrip('/') + '/health', timeout=1) as response:
                return response.status == 200
        except OSError:
            return False
    model = worker = None
    model_log = open(output / 'model.log', 'wb')
    worker_log = open(output / 'worker.log', 'wb')
    started = time.monotonic()
    try:
        if not healthy():
            project = ROOT.parents[1] / '机器学习/情感陪伴参赛作业'
            model = subprocess.Popen([str(project / '.venv/Scripts/python.exe'), '-u',
                str(project / '体验/chat_app.py')], cwd=str(project), stdout=model_log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            deadline = time.monotonic() + 120
            while not healthy():
                if model.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('本次模型加载失败，见model.log')
                time.sleep(0.2)
        source = (ROOT / 'records/实时交互/4cfe8090d3274a15a7e4ad00245ce4b4/turn-1/clean.wav'
                  if args.story else ROOT / 'records/T113真实ARM对照/usb-mic-second.wav')
        if args.task:
            source = ROOT / 'records/实时交互/69dd46615ec44e059391368f74ae3396/turn-2/clean.wav'
        shutil.copyfile(source, output / 'clean.wav')
        if (source.parent / 'endpoint.json').exists():
            shutil.copyfile(source.parent / 'endpoint.json', output / 'endpoint.json')
        (output / 'history.json').write_text('[]', encoding='utf-8')
        worker = subprocess.Popen([sys.executable, '-u', str(ROOT / 'realtime_worker.py'), str(output)],
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                  cwd=str(ROOT), stdout=worker_log, stderr=subprocess.STDOUT)
        worker.wait(timeout=200)
        result = json.loads((output / 'worker-result.json').read_text(encoding='utf-8'))
        summary = {'通过': result['ok'], 'seconds': time.monotonic() - started,
                   '边界': '既有真人录音文件经真实ASR/心语/TTS；未外放，不是当前实时对话'}
        if result['ok']:
            summary.update({key: result['result'].get(key) for key in
                            ('recognized_text', 'reply_text', 'playback_target', 'mode')})
            if args.story:
                record = json.loads((ROOT / 'records/真实语音' / result['result']['id'] / 'result.json').read_text(encoding='utf-8'))
                summary['原始识别'] = record.get('recognized_text_raw')
                summary['故事模式'] = record['model_result'].get('story_mode')
                summary['回复字数'] = len(result['result']['reply_text'])
                # 用户已明确接受简短故事，不再把150字当作通过条件。
                summary['通过'] = bool(summary['故事模式'] and result['result']['reply_text'].strip())
            if args.task:
                record = json.loads((ROOT / 'records/真实语音' / result['result']['id'] / 'result.json').read_text(encoding='utf-8'))
                summary['语音任务模式'] = record['model_result'].get('voice_task_mode')
                summary['有具体早餐内容'] = bool(re.search(r'鸡蛋|牛奶|豆浆|燕麦|面包|粥|馒头|包子|水果|玉米|酸奶|饺', summary['reply_text']))
                summary['通过'] = bool(summary['语音任务模式'] and summary['有具体早餐内容'])
        else:
            summary['error'] = result['error']
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        if not summary['通过']:
            raise RuntimeError('任务入口验证未通过')
    finally:
        for process in (worker, model):
            if process:
                stop_owned_process(process)
        model_log.close()
        worker_log.close()


if __name__ == '__main__':
    main()
