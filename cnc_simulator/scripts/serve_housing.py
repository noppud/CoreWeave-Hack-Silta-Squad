"""Local-only presentation server with bounded same-origin video capture."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path!='/api/housing-video' or self.headers.get('Origin')!='http://127.0.0.1:2740':
            self.send_error(403);return
        try:size=int(self.headers.get('Content-Length','0'))
        except ValueError:self.send_error(400);return
        if not 0<size<200_000_000:self.send_error(413);return
        payload=self.rfile.read(size)
        if not payload.startswith(bytes.fromhex('1a45dfa3')):self.send_error(400);return
        out=ROOT/'workspace-housing/housing-machining.webm';out.parent.mkdir(exist_ok=True)
        out.write_bytes(payload);self.send_response(200);self.end_headers();self.wfile.write(b'Saved')
ThreadingHTTPServer(('127.0.0.1',2740),partial(Handler,directory=str(ROOT/'viewer/dist'))).serve_forever()
