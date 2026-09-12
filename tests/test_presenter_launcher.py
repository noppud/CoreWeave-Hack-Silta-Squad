import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "presenter_launcher", Path(__file__).resolve().parents[1] / "scripts/start_presenter.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_existing_presentation_is_reused_without_spawning(monkeypatch):
    monkeypatch.setattr(launcher, "probe", lambda *args: True)

    def unexpected(*args, **kwargs):
        pytest.fail("An existing presentation must not start another process")

    monkeypatch.setattr(launcher.subprocess, "Popen", unexpected)
    launcher.launch()


def test_conflicting_second_port_prevents_partial_start(monkeypatch):
    def probe(url, title):
        if "2732" in url:
            raise RuntimeError("occupied by another app")
        return False

    monkeypatch.setattr(launcher, "probe", probe)

    def unexpected(*args, **kwargs):
        pytest.fail("No new server should start if either port conflicts")

    monkeypatch.setattr(launcher.subprocess, "Popen", unexpected)
    with pytest.raises(RuntimeError, match="another app"):
        launcher.launch()


def test_other_page_is_not_mistaken_for_presenter(monkeypatch):
    import io

    monkeypatch.setattr(
        launcher.urllib.request,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(b"<title>Another app</title>"),
    )
    with pytest.raises(RuntimeError, match="another page"):
        launcher.probe("http://127.0.0.1:2732", "Silta CNC · 3 minute demo")
