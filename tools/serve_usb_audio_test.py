"""仅在USB链路本地地址提供一份测试录音，不公开其他文件。"""
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path('/mnt/UDISK/xinyu-arm-check')


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/audio.wav':
            self.send_error(404)
            return
        data = (ROOT / 'usb-mic-second.wav').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'audio/wav')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == '__main__':
    if '--start' in sys.argv:
        log = open(str(ROOT / 'audio-http.log'), 'w')
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve())],
                                   stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        print('USB录音传输检查进程：' + str(process.pid), flush=True)
    else:
        HTTPServer(('169.254.113.2', 18769), Handler).serve_forever()
