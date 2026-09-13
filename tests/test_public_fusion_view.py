import http.client
import json
import threading
import time
from http.server import ThreadingHTTPServer

import pytest

from silta.cnc.public_fusion_view import make_handler


@pytest.fixture
def server(tmp_path):
    (tmp_path / "frame.jpg").write_bytes(b"jpeg")
    (tmp_path / "index.html").write_text("view only")
    (tmp_path / "status.json").write_text(
        json.dumps(
            {
                "status": "live",
                "heartbeat": time.time(),
                "frames": 12,
                "connection_url": "must never leak",
                "window_title": "private metadata",
            }
        )
    )
    app = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(tmp_path, tmp_path / "index.html", time.time() + 100)
    )
    threading.Thread(target=app.serve_forever, daemon=True).start()
    yield app.server_port, tmp_path
    app.shutdown()
    app.server_close()


def get(server, path, method="GET"):
    connection = http.client.HTTPConnection("127.0.0.1", server[0])
    connection.request(method, path)
    response = connection.getresponse()
    result = response.status, response.read()
    connection.close()
    return result


def test_public_surface_has_only_page_status_and_frame(server):
    assert get(server, "/")[0] == 200
    assert get(server, "/frame.jpg") == (200, b"jpeg")
    code, value = get(server, "/status")
    assert code == 200
    assert json.loads(value)["view_only"] is True
    assert b"must never leak" not in value
    assert b"private metadata" not in value


@pytest.mark.parametrize(
    "path",
    [
        "/api/state",
        "/api/start",
        "/artifact/file.nc",
        "/live/connection",
        "/../.private/connection.json",
    ],
)
def test_no_control_or_artifact_route(server, path):
    assert get(server, path)[0] == 404


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_public_connection_cannot_mutate(server, method):
    assert get(server, "/api/start", method)[0] == 405


def test_stale_frame_is_not_published(server):
    (server[1] / "status.json").write_text(json.dumps({"status": "live", "heartbeat": 0}))
    assert get(server, "/frame.jpg")[0] == 503
