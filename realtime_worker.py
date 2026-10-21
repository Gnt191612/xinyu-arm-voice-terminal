"""本次会话专属的单句识别、心语与合成任务；不自行播放。"""
import base64
import json
import hashlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / '.deps'))
sys.path.insert(0, str(Path(__file__).resolve().parent / '.realtime-deps'))
from pc_server import Pipeline, ROOT
from voice_activity import analyze_realtime_audio
from speech_text import select_voice_text


def main():
    directory = Path(sys.argv[1])
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8-sig'))
    config['playback_target'] = 'board'
    config['interaction_mode'] = 'voice'
    try:
        audio = (directory / 'clean.wav').read_bytes()
        endpoint_path = directory / 'endpoint.json'
        endpoint_confirmed = False
        if endpoint_path.exists():
            evidence = json.loads(endpoint_path.read_text(encoding='utf-8'))
            endpoint_confirmed = (evidence.get('onset_frames', 0) >= 3 and
                evidence.get('sha256') == hashlib.sha256(audio).hexdigest())
        settings = json.loads((ROOT / 'asr-settings.json').read_text(encoding='utf-8'))
        transcriber = None
        if settings['backend'] == 'sensevoice':
            from sensevoice_asr import SenseVoice
            transcriber = SenseVoice()
        elif settings['backend'] != 'vosk':
            raise ValueError('未知本地识别后端，未启动在线识别')
        result = Pipeline(config, voice_gate=lambda samples: analyze_realtime_audio(samples, endpoint_confirmed),
                          asr_selector=select_voice_text if transcriber is None else None,
                          transcriber=transcriber).process({
            'audio_wav': base64.b64encode(audio).decode(),
            'history': json.loads((directory / 'history.json').read_text(encoding='utf-8'))})
        payload = {'ok': True, 'result': result}
    except Exception as exc:
        payload = {'ok': False, 'error': str(exc)}
    (directory / 'worker-result.json').write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
