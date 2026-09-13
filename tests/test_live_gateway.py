import http.client
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from silta.cnc.live_gateway import Gateway, make_handler


@pytest.fixture
def gateway(tmp_path):
    calls = []

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            calls.append((self.path, self.headers.get("Origin"), body))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "11")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def do_GET(self):
            self.send_response(206)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", "4")
            self.send_header("Content-Range", "bytes 2-5/10")
            self.end_headers()
            self.wfile.write(b"2345")

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    state = Gateway(tmp_path, upstream=upstream.server_port)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    state.port = server.server_port
    state.hosts = {f"127.0.0.1:{state.port}"}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield state, calls
    server.shutdown()
    upstream.shutdown()
    server.server_close()
    upstream.server_close()


def request(gateway, method, path, data=None, cookie=None, origin=True, host=None):
    state, _ = gateway
    client = http.client.HTTPConnection("127.0.0.1", state.port, timeout=3)
    headers = {"Host": host or f"127.0.0.1:{state.port}"}
    if origin:
        headers["Origin"] = f"http://127.0.0.1:{state.port}"
    if cookie:
        headers["Cookie"] = cookie
    if data is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    client.request(method, path, body=data, headers=headers)
    response = client.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    client.close()
    return result


def pair(gateway):
    state, _ = gateway
    code, headers, _ = request(gateway, "POST", "/live/pair", {"token": state.token})
    assert code == 200
    assert "HttpOnly" in headers["Set-Cookie"]
    assert "SameSite=Strict" in headers["Set-Cookie"]
    return headers["Set-Cookie"].split(";", 1)[0]


def test_unpaired_clients_cannot_read_frames_or_submit_jobs(gateway):
    assert request(gateway, "GET", "/live/frame.jpg")[0] == 401
    assert request(gateway, "GET", "/api/state")[0] == 401
    assert request(gateway, "POST", "/api/start", {"id": "test"})[0] == 401
    assert gateway[1] == []


def test_pairing_rejects_wrong_secret_and_wrong_origin(gateway):
    assert request(gateway, "POST", "/live/pair", {"token": "wrong"})[0] == 403
    assert request(gateway, "POST", "/live/pair", {"token": gateway[0].token}, origin=False)[0] == 403
    assert not gateway[0].sessions


def test_authenticated_start_forwards_once_with_local_origin(gateway):
    cookie = pair(gateway)
    assert request(gateway, "POST", "/api/start", {"id": "prepared"}, cookie=cookie)[0] == 200
    assert gateway[1] == [("/api/start", f"http://127.0.0.1:{gateway[0].upstream}", b'{"id": "prepared"}')]


def test_paired_cookie_does_not_allow_cross_origin_or_arbitrary_actions(gateway):
    cookie = pair(gateway)
    assert request(gateway, "POST", "/api/start", {"id": "x"}, cookie=cookie, origin=False)[0] == 403
    assert request(gateway, "POST", "/execute", {"code": "x"}, cookie=cookie)[0] == 404
    assert request(gateway, "GET", "/live/status", cookie=cookie, host="attacker.example")[0] == 403
    assert gateway[1] == []


def test_video_response_range_is_preserved(gateway):
    cookie = pair(gateway)
    status, headers, body = request(gateway, "GET", "/artifact/test.mp4", cookie=cookie)
    assert (status, body) == (206, b"2345")
    assert headers["Content-Range"] == "bytes 2-5/10"


def test_stale_capture_never_serves_old_frame_as_live(gateway):
    state, _ = gateway
    cookie = pair(gateway)
    (state.directory / "frame.jpg").write_bytes(b"old frame")
    (state.directory / "status.json").write_text(json.dumps({"status": "live", "heartbeat": time.time() - 60}))
    assert request(gateway, "GET", "/live/frame.jpg", cookie=cookie)[0] == 503


def test_expired_connection_disables_existing_sessions(gateway):
    cookie = pair(gateway)
    gateway[0].deadline = time.time() - 1
    assert request(gateway, "GET", "/api/state", cookie=cookie)[0] == 403
    assert request(gateway, "POST", "/live/pair", {"token": gateway[0].token})[0] == 403
