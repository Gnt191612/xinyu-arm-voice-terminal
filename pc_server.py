"""电脑侧语音桥接；不修改、不重复加载心语模型。"""
import argparse
import base64
import hashlib
import hmac
import io
import json
import math
import os
import struct
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from audio_core import Gate, read_wav

ROOT = Path(__file__).resolve().parent
MAX_REQUEST = 2000000


def play_on_pc(path):
    """同步播放；返回后才允许下一轮录音，实际出声仍需人工确认。"""
    import winsound
    winsound.PlaySound(str(path), winsound.SND_FILENAME)


def json_post(url, data, timeout):
    # 本机模型及板端专网请求不通过系统代理。
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, json.dumps(data, ensure_ascii=False).encode('utf-8'),
                                     {'Content-Type': 'application/json'}, method='POST')
    with opener.open(request, timeout=timeout) as response:
        return json.load(response)


def validate_history(history):
    if not isinstance(history, list) or len(history) > 38 or len(history) % 2:
        raise ValueError('历史必须为最多19轮的完整对话；20轮后请重新开始')
    for i, turn in enumerate(history):
        if not isinstance(turn, dict) or turn.get('role') != ('user' if i % 2 == 0 else 'assistant'):
            raise ValueError('历史角色必须按user、assistant交替')
        content = turn.get('content')
        if not isinstance(content, str) or not content.strip() or len(content) > 4000:
            raise ValueError('历史正文不能为空或超过4000字符')


def test_tone():
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as target:
        target.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        target.writeframes(b''.join(struct.pack('<h', int(1000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(3200)))
    return buffer.getvalue()


class Pipeline:
    def __init__(self, config, simulate=False):
        self.config = config
        self.simulate = simulate
        self.playback_target = config.get('playback_target', 'pc')
        if self.playback_target not in ('pc', 'board'):
            raise ValueError('playback_target只能是pc或board')
        self.recognizer_model = None
        self.records = ROOT / 'records' / ('模拟联调' if simulate else '真实语音')
        self.records.mkdir(parents=True, exist_ok=True)

    def process(self, request):
        started = time.perf_counter()
        history = request.get('history', [])
        validate_history(history)
        try:
            audio = base64.b64decode(request['audio_wav'], validate=True)
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError('audio_wav必须是有效Base64 WAV') from exc
        samples, pcm = read_wav(audio)
        # 电脑重复校验输入，记录中明确标为参考实现而非板侧汇编。
        gate = Gate(threshold=self.config['threshold']).analyze(samples)
        identifier = uuid.uuid4().hex
        directory = self.records / identifier
        directory.mkdir()
        (directory / 'input.wav').write_bytes(audio)
        record = {'id': identifier, 'mode': '模拟 非真实模型与语音' if self.simulate else '真实模式',
                  'input_sha256': hashlib.sha256(audio).hexdigest(), 'gate': gate}
        try:
            if not gate['accepted']:
                raise ValueError(gate['reason'])
            asr_start = time.perf_counter()
            if self.simulate:
                text = '模拟识别：我今天想和你聊聊天。'
            else:
                from vosk import Model, KaldiRecognizer
                model_dir = Path(self.config['vosk_model'])
                if not model_dir.is_absolute():
                    model_dir = ROOT / model_dir
                if not model_dir.is_dir():
                    raise ValueError('缺少Vosk中文模型，见运行说明')
                if self.recognizer_model is None:
                    # Vosk的Windows底层对中文绝对路径兼容不佳，使用ASCII相对路径。
                    model_name = os.path.relpath(model_dir)
                    if os.name == 'nt' and not model_name.isascii():
                        raise ValueError('请在本项目目录运行，并将Vosk模型放在models目录下')
                    self.recognizer_model = Model(model_name)
                recognizer = KaldiRecognizer(self.recognizer_model, 16000)
                texts = []
                for offset in range(0, len(pcm), 8000):
                    if recognizer.AcceptWaveform(pcm[offset:offset + 8000]):
                        texts.append(json.loads(recognizer.Result()).get('text', ''))
                texts.append(json.loads(recognizer.FinalResult()).get('text', ''))
                text = ''.join(texts).replace(' ', '').strip()
            record['asr_seconds'] = time.perf_counter() - asr_start
            record['recognized_text'] = text
            if not text:
                raise ValueError('没有识别到文字，请检查麦克风或重新清晰说话')
            model_start = time.perf_counter()
            if self.simulate:
                answer = {'response_text': '模拟回复：这是接口联调，不是心语模型的实际输出。'}
            else:
                answer = json_post(self.config['xinyu_url'].rstrip('/') + '/chat',
                                   {'history': history + [{'role': 'user', 'content': text}]}, 180)
            reply = answer.get('response_text')
            if not isinstance(reply, str) or not reply.strip() or len(reply) > 4000:
                raise ValueError('心语未返回有效response_text')
            record['model_seconds'] = time.perf_counter() - model_start
            record['reply_text'] = reply
            record['model_result'] = answer
            tts_start = time.perf_counter()
            if self.simulate:
                spoken = test_tone()
            else:
                with tempfile.TemporaryDirectory(prefix='xinyu_tts_') as temp:
                    text_file = Path(temp) / 'text.json'
                    wave_file = Path(temp) / 'reply.wav'
                    # 正文作为JSON数据，不拼入PowerShell命令，避免引号与命令注入。
                    text_file.write_text(json.dumps({'text': reply[:800]}, ensure_ascii=False), encoding='utf-8')
                    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'tts.ps1'),
                                    '-RequestFile', str(text_file), '-OutputFile', str(wave_file)],
                                   check=True, timeout=90, capture_output=True)
                    spoken = wave_file.read_bytes()
                if len(spoken) > 4000000:
                    raise ValueError('合成音频超过4MB限制')
            record['tts_seconds'] = time.perf_counter() - tts_start
            record['spoken_truncated'] = len(reply) > 800
            (directory / 'reply.wav').write_bytes(spoken)
            record['reply_sha256'] = hashlib.sha256(spoken).hexdigest()
            record['playback_target'] = self.playback_target
            record['playback_command_completed'] = False
            record['audible_output_verified'] = False
            if self.playback_target == 'pc' and not self.simulate:
                play_on_pc(directory / 'reply.wav')
                record['playback_command_completed'] = True
            record['status'] = '成功'
            result = {'id': identifier, 'mode': record['mode'], 'recognized_text': text,
                    'reply_text': reply, 'playback_target': self.playback_target,
                    'playback_command_completed': record['playback_command_completed'],
                    'spoken_truncated': record['spoken_truncated']}
            if self.playback_target == 'board':
                result['audio_wav'] = base64.b64encode(spoken).decode('ascii')
            return result
        except Exception as exc:
            record['status'] = '失败'
            record['error'] = str(exc)
            raise
        finally:
            record['total_seconds'] = time.perf_counter() - started
            (directory / 'result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')


def make_handler(pipeline, token):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self, code, payload):
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def authenticated(self):
            return hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)

        def do_GET(self):
            if not self.authenticated():
                self.send_json(401, {'error': '访问令牌错误'})
            elif self.path == '/health':
                self.send_json(200, {'service': '心语语音桥接', 'simulate': pipeline.simulate,
                                     'playback_target': pipeline.playback_target})
            else:
                self.send_json(404, {'error': '接口不存在'})

        def do_POST(self):
            if not self.authenticated():
                self.send_json(401, {'error': '访问令牌错误'})
                return
            if self.path != '/turn':
                self.send_json(404, {'error': '接口不存在'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_REQUEST:
                    raise ValueError('请求为空或超过2MB限制')
                self.connection.settimeout(15)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('请求数据不完整')
                request = json.loads(raw)
                if not isinstance(request, dict):
                    raise ValueError('请求必须是JSON对象')
                self.send_json(200, pipeline.process(request))
            except (ValueError, KeyError, TypeError) as exc:
                self.send_json(400, {'error': str(exc)})
            except (OSError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
                self.send_json(503, {'error': '识别、模型或合成服务不可用：' + str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description='心语电脑侧语音桥接')
    parser.add_argument('--config', default=str(ROOT / 'config.json'))
    parser.add_argument('--playback-target', choices=('pc', 'board'),
                        help='默认电脑外放；board为原有板端播放兼容模式')
    parser.add_argument('--simulate', action='store_true', help='明确使用模拟识别、模拟回复和测试音')
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
    if args.playback_target:
        config['playback_target'] = args.playback_target
    if len(config.get('token', '')) < 24 or not config['token'].isascii() or config['token'].startswith('请替换'):
        raise SystemExit('请先设置至少24字符的ASCII随机访问令牌')
    server = HTTPServer((config['listen_host'], config['port']), make_handler(Pipeline(config, args.simulate), config['token']))
    print(f"模式：{'模拟 非实机' if args.simulate else '真实语音'}；监听{config['listen_host']}:{config['port']}；Ctrl+C停止", flush=True)
    if config['listen_host'] not in ('127.0.0.1', 'localhost'):
        print('仅供可信局域网；HTTP不加密，不要开放公网端口。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
