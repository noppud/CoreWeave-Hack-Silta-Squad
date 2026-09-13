"""Read-only benchmark explorer and explicit same-origin local video capture."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import json,argparse
from camloop.indexed.report import report
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=ROOT/'workspace-indexed-five');p.add_argument('--port',type=int,default=2742);args=p.parse_args()
WORK=args.workspace.resolve();ORIGIN=f'http://127.0.0.1:{args.port}'
IDS={p['id'] for p in json.loads((WORK/'catalog.json').read_text())['parts']}
class Handler(SimpleHTTPRequestHandler):
    def payload(self,data):
        body=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def do_GET(self):
        url=urlsplit(self.path);part=parse_qs(url.query).get('part',[''])[0]
        if url.path=='/api/study-results':
            data=report(WORK);data['catalog']=json.loads((WORK/'catalog.json').read_text())['parts'];data['memory']=json.loads((WORK/'memory.json').read_text()) if (WORK/'memory.json').exists() else None
            namespace=ROOT/'viewer/dist/assets/study'/WORK.name
            data['asset_namespace']=WORK.name if namespace.exists() else ''
            for r in data['parts']:
                r['playback_variants']=[p.name.split('--',1)[1] for p in namespace.glob(r['id']+'--*') if (p/'receipt.json').exists()]
                r['playback_ready']=((namespace if namespace.exists() else ROOT/'viewer/dist/assets/study')/r['id']/'receipt.json').exists();r['video_ready']=(WORK/'videos'/f"{r['id']}.mp4").exists();r['video_captured']=(WORK/'videos'/f"{r['id']}.webm").exists()
            return self.payload(data)
        if url.path=='/api/study-run' and part in IDS:
            p=WORK/'runs'/part/'manifest.json'
            return self.payload(json.loads(p.read_text()) if p.exists() else {})
        if url.path=='/api/learned-check-audit':
            p=WORK/'learning-check-audit/receipt.json';return self.payload(json.loads(p.read_text()) if p.exists() else {})
        if url.path=='/api/study-learning':
            p=WORK/'memory.json';return self.payload(json.loads(p.read_text()) if p.exists() else {})
        if url.path.startswith('/study-videos/'):
            name=url.path.split('/')[-1]
            if not any(name==part+ext for part in IDS for ext in ['.mp4','.png']):self.send_error(404);return
            p=WORK/'videos'/name
            if not p.exists():self.send_error(404);return
            body=p.read_bytes();self.send_response(200);self.send_header('Content-Type','video/mp4' if p.suffix=='.mp4' else 'image/png');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        super().do_GET()
    def do_POST(self):
        url=urlsplit(self.path);part=parse_qs(url.query).get('part',[''])[0]
        if url.path!='/api/study-video' or part not in IDS or self.headers.get('Origin')!=ORIGIN:self.send_error(403);return
        try:size=int(self.headers.get('Content-Length','0'))
        except ValueError:self.send_error(400);return
        if not 0<size<200_000_000:self.send_error(413);return
        data=self.rfile.read(size)
        if not data.startswith(bytes.fromhex('1a45dfa3')):self.send_error(400);return
        p=WORK/'videos'/f'{part}.webm';p.parent.mkdir(exist_ok=True);temporary=p.with_suffix('.upload');temporary.write_bytes(data);temporary.replace(p)
        self.send_response(200);self.end_headers();self.wfile.write(b'Saved')
ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(ROOT/'viewer/dist'))).serve_forever()
