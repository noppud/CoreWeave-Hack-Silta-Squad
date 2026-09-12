"""Start or reuse the local presentation. Never terminate an unrelated server."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import html
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = (
    (
        "Slides",
        "http://127.0.0.1:8010/slides.html",
        "Silta CNC · Three-minute demo",
        [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "http.server",
            "8010",
            "--bind",
            "127.0.0.1",
            "--directory",
            str(ROOT / "demo"),
        ],
    ),
    (
        "Notebook",
        "http://127.0.0.1:2732/",
        "Silta CNC · 3 minute demo",
        [
            str(ROOT / ".venv/bin/marimo"),
            "run",
            str(ROOT / "notebooks/demo.py"),
            "--host",
            "127.0.0.1",
            "--port",
            "2732",
            "--headless",
        ],
    ),
    (
        "Evals",
        "http://127.0.0.1:2733/",
        "Silta CNC Evaluations",
        [
            str(ROOT / ".venv/bin/marimo"),
            "run",
            str(ROOT / "notebooks/evaluations.py"),
            "--host",
            "127.0.0.1",
            "--port",
            "2733",
            "--headless",
        ],
    ),
)


def build_pitch_guide():
    """Serve the Markdown runbook as a readable page alongside the deck."""
    import markdown

    content = markdown.markdown(
        (ROOT / "docs/demo-3min.md").read_text(), extensions=["tables", "fenced_code"]
    )
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Silta CNC · Pitch guide</title><style>
body{font:18px/1.6 system-ui,sans-serif;max-width:1100px;margin:40px auto;
padding:0 24px;color:#163449;background:#f6f9fb}a{color:#075e9b}
nav{display:flex;gap:24px;flex-wrap:wrap}h1,h2{line-height:1.2}
table{display:block;overflow-x:auto;border-collapse:collapse;background:white}
th,td{padding:12px;border:1px solid #ccd9e2;text-align:left;min-width:100px}
td:last-child{min-width:300px}pre{background:#e5edf3;padding:16px;overflow:auto}
code{font-size:.9em}blockquote{border-left:4px solid #075e9b;padding-left:16px}
</style><nav><a href="slides.html">Open slides</a>
<a href="http://localhost:2732/" target="silta-demo">Open interactive demo</a></nav>
<main>CONTENT</main></html>"""
    (ROOT / "demo/guide.html").write_text(page.replace("CONTENT", content))


def probe(url: str, expected_title: str) -> bool:
    """Return False only for a refused connection. Wrong/busy servers are errors."""
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            content = response.read(2_000_000).decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, OSError) and reason.errno in (errno.ECONNREFUSED,):
            return False
        raise RuntimeError(f"{url} is occupied or unresponsive; no process was stopped.") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"{url} did not respond; no process was stopped.") from exc
    match = re.search(r"<title[^>]*>(.*?)</title>", content, re.I | re.S)
    if not match or html.unescape(match.group(1)).strip() != expected_title:
        raise RuntimeError(
            f"{url} serves another page; close that server before running make present."
        )
    return True


def launch(services=SERVICES):
    # Check every port before launching anything; handle partially running services.
    running = [probe(url, title) for _, url, title, _ in services]
    started = []
    log_dir = None
    try:
        for (name, url, title, command), already_running in zip(services, running, strict=True):
            if already_running:
                print(f"Reusing {name.lower()}: {url}", flush=True)
                continue
            if log_dir is None:
                log_dir = Path(tempfile.mkdtemp(prefix="silta-presenter-logs-"))
            log_path = log_dir / f"{name.lower()}.log"
            with log_path.open("w") as log:
                process = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            started.append(process)
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"{name} failed to start. Details: {log_path}")
                if probe(url, title):
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError(f"{name} did not become ready. Details: {log_path}")
                time.sleep(0.2)
            print(f"Started {name.lower()}: {url}", flush=True)
    except BaseException:
        for process in started:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        raise
    print("\nReady. Preload the demo and eval notebooks before presenting:", flush=True)
    print("Slides:   http://localhost:8010/slides.html")
    print("Notebook: http://localhost:2732")
    print("Pitch guide: http://localhost:8010/guide.html")
    print("Eval report: http://localhost:8010/evals.html")
    print("Eval notebook: http://localhost:2733")
    print("Servers keep running. Repeating make present safely reuses them.")
    if log_dir:
        print(f"Server logs: {log_dir}")


def main():
    key = hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]
    # Serialize concurrent launches from this checkout.
    with (Path(tempfile.gettempdir()) / f"silta-presenter-{key}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            build_pitch_guide()
            launch()
        except RuntimeError as exc:
            print(f"Presentation not ready: {exc}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
