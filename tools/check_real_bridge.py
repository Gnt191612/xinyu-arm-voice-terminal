"""用合成语音接入正在运行的真实心语；不改原模型，不冒充实机。"""
import base64
import json
import sys
import threading
import urllib.request
import uuid
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from audio_core import read_wav
from board_client import send_turn
from pc_server import Pipeline, make_handler


def main():
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(config['xinyu_url'].rstrip('/') + '/health', timeout=5) as response:
        health = json.load(response)
    source = ROOT / 'records/合成语音识别冒烟/input.wav'
    audio = source.read_bytes()
    read_wav(audio)
    output = ROOT / 'records/真实心语桥接联调' / uuid.uuid4().hex
    output.mkdir(parents=True)
    (output / 'input.wav').write_bytes(audio)
    pipeline = Pipeline(config, simulate=False)
    server = HTTPServer(('127.0.0.1', 0), make_handler(pipeline, config['token']))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    record = {'scope': '合成语音输入→Vosk实际识别→真实心语→中文TTS；非真人麦克风、非ARM实机',
              'health': health, 'input_source': str(source), 'status': '未完成'}
    try:
        result = send_turn(f'http://127.0.0.1:{server.server_port}', config['token'], audio, [])
        spoken = base64.b64decode(result.pop('audio_wav'), validate=True)
        read_wav(spoken, max_seconds=120)
        (output / 'reply.wav').write_bytes(spoken)
        record.update(status='成功', response=result)
        print(json.dumps(record, ensure_ascii=False, indent=2), flush=True)
        print('回复音频：' + str(output / 'reply.wav'), flush=True)
    except Exception as exc:
        record.update(status='失败', error=str(exc))
        raise
    finally:
        (output / 'result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        server.shutdown()
        server.server_close()
        thread.join(3)


if __name__ == '__main__':
    main()
