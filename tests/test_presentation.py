import xml.etree.ElementTree as ET

import pytest
import traitlets

from silta.presentation import DEFAULT_DEMO_URL, public_demo_url, qr_svg, share_panel
from silta.viewer import PartViewer, build_scene


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://localhost",
        "https://192.168.1.8",
        "https://127.0.0.1",
        "https://user:secret@example.com",
        "https://app.internal",
    ],
)
def test_qr_rejects_nonpublic_or_credential_urls(url):
    with pytest.raises(ValueError):
        public_demo_url(url)


def test_qr_strips_session_tokens_and_has_quiet_zone():
    assert public_demo_url("https://example.com/?token=secret#session") == "https://example.com/"
    root = ET.fromstring(qr_svg(DEFAULT_DEMO_URL))
    assert root.attrib["viewBox"].startswith("0 0 ")
    path = root.find("{http://www.w3.org/2000/svg}path").attrib["d"]
    for command in path.split():
        x, y = map(int, command[1:].split("h", 1)[0].split(","))
        assert x >= 4 and y >= 4
    assert "secret" not in qr_svg("https://example.com/?token=secret")


def test_invalid_share_configuration_does_not_break_notebook(monkeypatch):
    monkeypatch.setenv("SILTA_PUBLIC_URL", "http://localhost:2720")
    assert "Sharing unavailable" in share_panel()


def test_camera_commands_leave_engineering_and_other_widgets_unchanged():
    first = PartViewer(scene={"stock": {"x_mm": 120}}, playhead=0.4)
    second = PartViewer()
    try:
        first.set_camera("top")
        first.set_camera("top")
        assert first.camera_command == {"preset": "top", "revision": 2}
        assert second.camera_command == {"preset": "isometric", "revision": 0}
        assert first.scene == {"stock": {"x_mm": 120}}
        assert first.playhead == 0.4
        with pytest.raises(ValueError):
            first.set_camera("invalid")
        with pytest.raises(traitlets.TraitError):
            first.view_mode = "invalid"
    finally:
        first.close()
        second.close()


def test_mesh_sampling_retains_complete_xyz_triangles():
    positions = list(range(450_000))
    mesh = build_scene(mesh={"positions": positions})["target_mesh"]
    assert len(mesh["positions"]) % 9 == 0
    assert mesh["positions"][:18] == list(range(9)) + list(range(18, 27))
    assert mesh["count"] * 9 == len(mesh["positions"])


def test_heightfield_sampling_preserves_rows_and_dimensions():
    frame = {"nx": 200, "ny": 200, "height": list(range(40_000)), "grid_mm": 0.5}
    result = build_scene(simulation_replay={"frames": [frame]})["replay_frames"][0]
    assert result["nx"] == result["ny"] == 100
    assert len(result["height"]) == 10_000
    assert result["height"][:3] == [0, 2, 4]
    assert result["height"][100] == 400
    assert result["grid_mm"] == 1
    assert result["origin_mm"] == 0.25
