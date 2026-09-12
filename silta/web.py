"""Public application and presentation routes for Cloud Run."""

import os
from pathlib import Path

import marimo
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.routing import Mount, Route

ROOT = Path(__file__).resolve().parents[1]
os.environ["SILTA_HOSTED"] = "1"


async def health(request: Request):
    return JSONResponse({"status": "ok", "commit": os.getenv("SILTA_COMMIT", "unknown")})


async def report(request: Request):
    # Explicit public artifacts only; never mount the repository or runtime storage.
    name = request.path_params["name"]
    if name not in {"guide.html", "evals.html", "evals.json", "slides.html"}:
        return JSONResponse({"error": "not found"}, status_code=404)
    path = ROOT / "demo" / name
    if path.suffix == ".json":
        return FileResponse(path, media_type="application/json")
    content = path.read_text()
    for local, hosted in {
        "http://localhost:2734": "/slides",
        "http://localhost:2732": "/demo",
        "http://localhost:2733": "/presentation/evals.html",
        "http://localhost:8010": "/presentation",
    }.items():
        content = content.replace(local, hosted)
    return HTMLResponse(content)


notebooks = (
    marimo.create_asgi_app(quiet=True, include_code=False, session_ttl=120)
    .with_app(path="/slides", root=str(ROOT / "notebooks/demo_slides.py"))
    .with_app(path="/demo", root=str(ROOT / "notebooks/demo.py"))
    .with_app(path="/", root=str(ROOT / "notebooks/workbench.py"))
    .build()
)
app = Starlette(
    routes=[
        Route("/health", health),
        Route("/presentation/{name}", report),
        Mount("/", app=notebooks),
    ]
)
