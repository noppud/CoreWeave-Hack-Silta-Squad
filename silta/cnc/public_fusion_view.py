"""Public visual-only surface: a page, capture status, and the current Fusion JPEG.

This server has no control-center proxy, job API, arbitrary file route, pairing
route, or write operation. Only this loopback port should enter the public tunnel.
"""

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]


def capture_status(directory):
    try:
        data = json.loads((Path(directory) / "status.json").read_text())
    except (OSError, ValueError):
        return {"status": "unavailable"}
    if (data.get("status") != "live" or not data.get("viewport_only")
            or time.time() - data.get("heartbeat", 0) > 5
            or time.time() - data.get("captured_at", 0) > 5):
        return {"status": "unavailable"}
    return {key: data[key] for key in (
        "status", "heartbeat", "captured_at", "width", "height", "frames"
    ) if key in data}


def make_handler(directory, page, deadline):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, data, kind="application/json", status=200):
            if isinstance(data, dict):
                data = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Robots-Tag", "noindex, nofollow")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if self.command != "HEAD":
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in {"/", "/index.html"}:
                self.send(Path(page).read_bytes(), "text/html; charset=utf-8")
                return
            if path not in {"/status", "/frame.jpg", "/stream.mjpg"}:
                self.send({"error": "Not found"}, status=404)
                return
            current = capture_status(directory) if time.time() < deadline else {"status": "ended"}
            if path == "/status":
                self.send({**current, "view_only": True, "expires_at": deadline})
                return
            image = Path(directory) / "frame.jpg"
            if current["status"] != "live" or not image.is_file():
                self.send({"error": "Live picture unavailable"}, status=503)
                return
            if path == "/stream.mjpg":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store, no-transform")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Robots-Tag", "noindex, nofollow")
                self.end_headers()
                if self.command == "HEAD":
                    return
                self.connection.settimeout(5)
                previous = None
                try:
                    while time.time() < deadline:
                        current = capture_status(directory)
                        if current["status"] != "live":
                            break
                        marker = image.stat().st_mtime_ns
                        if marker != previous:
                            data = image.read_bytes()
                            self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                             + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
                            self.wfile.flush()
                            previous = marker
                        time.sleep(0.04)
                except (OSError, TimeoutError):
                    pass
                self.close_connection = True
                return
            self.send(image.read_bytes(), "image/jpeg")

        def do_POST(self):
            self.send({"error": "This connection is visual only"}, status=405)

        do_PUT = do_POST
        do_PATCH = do_POST
        do_DELETE = do_POST

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8811)
    args = parser.parse_args()
    directory = ROOT / ".private/fusion-live-gateway"
    connection = json.loads((directory / "connection.json").read_text())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(
        directory, ROOT / "applications/fusion-live/public.html", connection["expires_at"]
    ))
    print(f"Visual-only origin: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
