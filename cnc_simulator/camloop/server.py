"""Loopback-only viewer; serves only viewer assets and run artifacts."""

import json
import mimetypes
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

VIEWER = Path(__file__).resolve().parents[1] / "viewer/dist"


def serve(workspace, port):
    root = Path(workspace).resolve()
    origin = f"http://127.0.0.1:{port}"
    lock = threading.Lock()
    active = {"process": None}

    class Handler(BaseHTTPRequestHandler):
        def payload(self, value, status=200):
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/api/jobs":
                self.payload([dict(id=p.parent.name) for p in sorted((root / "jobs").glob("*/job.json"))])
                return
            if path == "/api/benchmark":
                result = root / "results.json"
                self.payload(json.loads(result.read_text()) if result.exists() else dict(parts=[]))
                return
            if path == "/api/runs":
                runs = []
                for manifest in (root / "runs").glob("*/manifest.json"):
                    value = json.loads(manifest.read_text())
                    runs.append(value)
                self.payload(sorted(runs, key=lambda r: r["started_at"], reverse=True))
                return
            if path == "/api/videos":
                self.payload([dict(name=p.stem, url="/videos/" + p.name) for p in sorted((root / "videos").glob("*.mp4")) if not p.stem.endswith(".rendering")])
                return
            if path.startswith("/videos/"):
                base, relative = root / "videos", path[len("/videos/"):]
                allowed = {".mp4", ".json"}
            elif path.startswith("/runs/"):
                base, relative = root / "runs", path[len("/runs/") :]
                allowed = {".json", ".ply", ".bin"}
            else:
                base, relative = VIEWER, path.lstrip("/") or "index.html"
                allowed = {".html", ".js", ".css", ".json"}
            target = (base / relative).resolve()
            if (
                not target.is_relative_to(base.resolve())
                or target.suffix not in allowed
                or not target.is_file()
            ):
                self.send_error(404)
                return
            data = target.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type", mimetypes.guess_type(target)[0] or "application/octet-stream"
            )
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if (
                self.path != "/api/start"
                or self.headers.get("Origin") != origin
                or self.headers.get("Host") != f"127.0.0.1:{port}"
            ):
                self.payload(dict(error="Only same-origin local run requests are accepted"), 403)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length < 1024 or self.headers.get("Content-Type") != "application/json":
                    raise ValueError("Expected small JSON request")
                request = json.loads(self.rfile.read(length))
                if set(request) != {"job"} or request["job"] not in {p.parent.name for p in (root / "jobs").glob("*/job.json")}:
                    raise ValueError("Select a prepared job")
                if not (root / "corpus/index.json").exists():
                    raise ValueError("Prepare the simulator-labelled corpus first")
                with lock:
                    if active["process"] is not None and active["process"].poll() is None:
                        self.payload(dict(error="An Astra run is already active"), 409)
                        return
                    run_id = f"astra-{request['job']}-{time.time_ns()}"
                    (root / "logs").mkdir(parents=True, exist_ok=True)
                    with (root / "logs" / f"{run_id}.log").open("w") as log:
                        active["process"] = subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "camloop",
                                "run",
                                str(root / "jobs" / request["job"] / "job.json"),
                                "--workspace",
                                str(root),
                                "--mode",
                                "astra",
                                "--id",
                                run_id,
                            ],
                            stdout=log,
                            stderr=log,
                            start_new_session=True,
                        )
                self.payload(dict(id=run_id), 202)
            except (ValueError, TypeError) as error:
                self.payload(dict(error=str(error)), 400)

        def log_message(self, format, *args):
            pass

    print(f"Silta local viewer: {origin}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
