"""Paired LAN access to the local control center and a read-only Fusion preview.

The control center remains loopback-only. This gateway authenticates remote
requests before forwarding its existing, bounded routes. It never executes code
itself and does not alter Fusion's window or simulation state.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import os
import secrets
import subprocess
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "applications/fusion-live/index.html"
PAIR_PAGE = b"""<!doctype html><meta name="viewport" content="width=device-width">
<title>Connect to SILTA</title>
<style>body{font:18px system-ui;max-width:650px;margin:15vh auto;padding:30px;
background:#f6f6f2;color:#252722}a{color:inherit}</style>
<h1>Connect to the Fusion computer</h1>
<p id="status">Use the private connection link shown on the Fusion computer.</p>
<script>const token=location.hash.slice(1);history.replaceState(null,'','/pair');
if(token)fetch('/live/pair',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})})
.then(r=>{if(!r.ok)throw Error(
'This connection link has expired. Get a new link from the Fusion computer.');
location.replace('/')})
.catch(e=>document.getElementById('status').textContent=e.message);</script>"""


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


class Gateway:
    def __init__(self, directory, port=8810, upstream=8768, lan_host="127.0.0.1"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.port, self.upstream, self.lan_host = port, upstream, lan_host
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"{lan_host}:{port}"}
        self.token = secrets.token_urlsafe(32)
        self.deadline = time.time() + 4 * 3600
        self.sessions = {}
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.capture = None
        self.capture_started = 0.0
        self.worker_cache = (0.0, {})
        self.connection = f"http://{lan_host}:{port}/pair#{self.token}"
        fd = os.open(
            self.directory / "connection.json", os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600
        )
        with os.fdopen(fd, "w") as stream:
            json.dump({"connection_url": self.connection, "expires_at": self.deadline}, stream)

    def new_session(self):
        with self.lock:
            self.sessions = {k: v for k, v in self.sessions.items() if v > time.time()}
            key = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(key.encode()).hexdigest()] = self.deadline
            return key

    def authorized(self, cookie):
        try:
            parsed = SimpleCookie(cookie or "")
            key = parsed["silta_live"].value
        except (KeyError, ValueError):
            return False
        with self.lock:
            return self.sessions.get(hashlib.sha256(key.encode()).hexdigest(), 0) > time.time()

    def capture_status(self):
        status = read_json(self.directory / "status.json")
        age = time.time() - status.get("heartbeat", 0)
        process = self.capture
        if (
            age > 5
            or status.get("heartbeat", 0) < self.capture_started
            or process is None
            or process.poll() is not None
        ):
            return {
                "status": "unavailable",
                "error": status.get("error", "Fusion preview is starting or disconnected"),
            }
        return {**status, "heartbeat_age_seconds": max(0, age)}

    def worker(self):
        with self.lock:
            if time.monotonic() - self.worker_cache[0] < 1:
                return self.worker_cache[1]
            connection = http.client.HTTPConnection("127.0.0.1", self.upstream, timeout=2)
            try:
                connection.request("GET", "/api/state")
                response = connection.getresponse()
                result = json.loads(response.read())
                worker = result.get("worker", {}) if response.status == 200 else {}
            except (OSError, ValueError, http.client.HTTPException):
                worker = {"label": "Control center is restarting", "running": False}
            finally:
                connection.close()
            self.worker_cache = (time.monotonic(), worker)
            return worker

    def supervise_capture(self):
        binary = self.directory / "live-window"
        (self.directory / "stop").unlink(missing_ok=True)
        while not self.stop.is_set() and time.time() < self.deadline:
            if self.capture is None or self.capture.poll() is not None:
                self.capture_started = time.time()
                with (self.directory / "capture.log").open("ab") as log:
                    self.capture = subprocess.Popen(
                        [str(binary), str(self.directory)], stdout=log, stderr=log
                    )
            self.stop.wait(5)
        (self.directory / "stop").touch()


def make_handler(gateway):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Pairing secrets, session cookies and source filenames are not logged.

        def send(self, body, kind="application/json", status=200, cookie=None):
            if isinstance(body, dict):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if kind.startswith("text/html"):
                self.send_header("Content-Security-Policy", "frame-ancestors 'self'")
            if cookie:
                self.send_header(
                    "Set-Cookie",
                    f"silta_live={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=14400",
                )
            self.end_headers()
            if self.command != "HEAD":
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def valid_host(self):
            return self.headers.get("Host") in gateway.hosts

        def local(self):
            return self.client_address[0] == "127.0.0.1"

        def access(self):
            if not self.valid_host() or time.time() >= gateway.deadline:
                self.send({"error": "Connection unavailable"}, status=403)
                return False
            if not gateway.authorized(self.headers.get("Cookie")):
                self.send(PAIR_PAGE, "text/html; charset=utf-8", status=401)
                return False
            return True

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self.valid_host():
                self.send({"error": "Unexpected host"}, status=403)
                return
            if path == "/pair":
                self.send(PAIR_PAGE, "text/html; charset=utf-8")
                return
            if (
                self.local()
                and path in {"/", "/live"}
                and not gateway.authorized(self.headers.get("Cookie"))
            ):
                # A local top-level visit pairs this browser. Remote visitors need the private link.
                if time.time() >= gateway.deadline:
                    self.send({"error": "Connection expired"}, status=403)
                    return
                self.send(
                    b"<script>location.reload()</script>", "text/html", cookie=gateway.new_session()
                )
                return
            if not self.access():
                return
            if path == "/live":
                self.send(PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/live/connection":
                if not self.local():
                    self.send(
                        {"error": "Open connection details on the Fusion computer"}, status=403
                    )
                else:
                    self.send({"url": gateway.connection, "expires_at": gateway.deadline})
            elif path == "/live/status":
                self.send(
                    {
                        **gateway.capture_status(),
                        "worker": gateway.worker(),
                        "expires_at": gateway.deadline,
                    }
                )
            elif path == "/live/frame.jpg":
                frame = gateway.directory / "frame.jpg"
                if gateway.capture_status().get("status") != "live" or not frame.is_file():
                    self.send({"error": "No current Fusion frame"}, status=503)
                else:
                    self.send(frame.read_bytes(), "image/jpeg")
            else:
                self.proxy()

        def do_POST(self):
            if not self.valid_host() or self.headers.get("Origin") != "http://" + self.headers.get(
                "Host", ""
            ):
                self.send({"error": "Use the connected application"}, status=403)
                return
            if self.headers.get("Transfer-Encoding"):
                self.send({"error": "Chunked requests are not supported"}, status=400)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if not 0 <= length <= 25_000_000:
                self.send({"error": "Invalid request size"}, status=413)
                return
            path = urlsplit(self.path).path
            if path == "/live/pair":
                if length > 2048:
                    self.send({"error": "Invalid connection link"}, status=400)
                    return
                try:
                    token = json.loads(self.rfile.read(length)).get("token", "")
                    valid = isinstance(token, str) and hmac.compare_digest(token, gateway.token)
                except (ValueError, AttributeError):
                    valid = False
                if not valid or time.time() >= gateway.deadline:
                    self.send({"error": "Invalid or expired connection link"}, status=403)
                    return
                self.send({"connected": True}, cookie=gateway.new_session())
                return
            if not self.access():
                return
            if path not in {
                "/api/upload",
                "/api/start",
                "/api/worker/check",
                "/api/evaluations/refresh",
            }:
                self.send({"error": "Unknown application action"}, status=404)
                return
            self.proxy(self.rfile.read(length))

        def proxy(self, body=None):
            # One fixed loopback destination; this is not an arbitrary URL proxy.
            if not self.path.startswith("/") or urlsplit(self.path).netloc:
                self.send({"error": "Invalid path"}, status=400)
                return
            connection = http.client.HTTPConnection("127.0.0.1", gateway.upstream, timeout=65)
            headers = {
                k: self.headers[k]
                for k in ("Content-Type", "X-Filename", "Range")
                if k in self.headers
            }
            headers["Host"] = f"127.0.0.1:{gateway.upstream}"
            if self.command == "POST":
                headers["Origin"] = f"http://127.0.0.1:{gateway.upstream}"
            try:
                connection.request(self.command, self.path, body=body, headers=headers)
                response = connection.getresponse()
                kind = response.getheader("Content-Type", "application/octet-stream")
                if (
                    self.command == "GET"
                    and urlsplit(self.path).path in {"/", "/index.html"}
                    and response.status == 200
                ):
                    data = response.read().replace(
                        b"</body>",
                        b"""<a href="/live" target="_blank" rel="noopener" style="position:fixed;
right:24px;bottom:24px;z-index:100;background:#252722;
color:white;border:1px solid #626853;border-radius:7px;
padding:13px 20px;font:13px system-ui;box-shadow:0 4px 20px #0002">
Open live Fusion \xe2\x86\x97</a></body>""",
                    )
                    self.send(data, kind)
                    return
                self.send_response(response.status)
                for key in (
                    "Content-Type",
                    "Content-Length",
                    "Content-Range",
                    "Accept-Ranges",
                    "X-Content-Type-Options",
                ):
                    value = response.getheader(key)
                    if value is not None:
                        self.send_header(key, value)
                self.send_header("Cache-Control", "private, no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                if self.command != "HEAD":
                    while chunk := response.read(262144):
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (OSError, http.client.HTTPException):
                self.send(
                    {
                        "error": (
                            "Control center is starting or reconnecting; live view remains at /live"
                        )
                    },
                    status=502,
                )
            finally:
                connection.close()

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8810)
    parser.add_argument("--upstream", type=int, default=8768)
    parser.add_argument("--lan-host", default="127.0.0.1")
    args = parser.parse_args()
    directory = ROOT / ".private/fusion-live-gateway"
    gateway = Gateway(directory, args.port, args.upstream, args.lan_host)
    source = ROOT / "scripts/fusion/live_window.swift"
    binary = directory / "live-window"
    if not binary.exists() or source.stat().st_mtime > binary.stat().st_mtime:
        subprocess.run(["swiftc", "-parse-as-library", str(source), "-o", str(binary)], check=True)
    threading.Thread(target=gateway.supervise_capture, daemon=True).start()
    server = ThreadingHTTPServer(
        ("127.0.0.1" if args.lan_host == "127.0.0.1" else "0.0.0.0", args.port),
        make_handler(gateway),
    )
    print(
        f"SILTA live connection: http://127.0.0.1:{args.port}/live "
        "(private connection link available there)",
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        gateway.stop.set()
        (directory / "stop").touch()
        server.server_close()


if __name__ == "__main__":
    main()
