"""Inspectable story views and a QR link to the public application."""

from __future__ import annotations

import html
import ipaddress
import os
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

import qrcode

# Verified Cloud Run service; override for another deployment, never a session URL.
DEFAULT_DEMO_URL = "https://silta-1020247549062.us-central1.run.app"


def public_demo_url(value: str | None = None) -> str:
    value = value if value is not None else os.environ.get("SILTA_PUBLIC_URL", DEFAULT_DEMO_URL)
    parsed = urlsplit(value.strip())
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError("Share a public HTTPS application URL without credentials.")
    if (
        host == "localhost"
        or host.endswith((".localhost", ".local", ".internal"))
        or "." not in host
    ):
        raise ValueError("A phone needs the deployed application URL, not localhost.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not address.is_global:
            raise ValueError("The demo URL must be publicly reachable.")
    # Query strings and fragments can contain session/access tokens. Share app only.
    return urlunsplit(("https", parsed.netloc, parsed.path or "/", "", ""))


@lru_cache(maxsize=8)
def qr_svg(url: str) -> str:
    url = public_demo_url(url)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    size = len(matrix)
    path = " ".join(
        f"M{x},{y}h1v1h-1z" for y, row in enumerate(matrix) for x, dark in enumerate(row) if dark
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        'width="184" height="184" role="img" aria-label="Scan to try SILTA CAD" '
        'shape-rendering="crispEdges">'
        f'<rect width="{size}" height="{size}" fill="white"/>'
        f'<path d="{path}" fill="black"/></svg>'
    )


def share_panel() -> str:
    try:
        url = public_demo_url()
    except ValueError as exc:
        return f'<div class="sx-note">Sharing unavailable: {html.escape(str(exc))}</div>'
    escaped = html.escape(url, quote=True)
    return (
        '<div class="sx-share"><div>'
        '<span class="sx-k">OPEN THE PRODUCT</span><h2>Share SILTA CAD.</h2>'
        "<p>Rotate the part, inspect each attempt, and try the planning controls. "
        "Drag with one finger; pinch to zoom. Each visitor gets a separate session.</p>"
        f'<a href="{escaped}" target="_blank" rel="noopener noreferrer">Open live demo ↗</a>'
        f'<p class="sx-share-url">{escaped}</p></div><div class="sx-qr">{qr_svg(url)}</div></div>'
    )


def story_card(mode: str, outcome, spec) -> str:
    if mode == "Inspect":
        return (
            '<div class="sx-note"><b>Inspect the actual run.</b> Select an attempt, rotate '
            "the model, and compare its checks and recipe. "
            "View controls do not rerun the agent.</div>"
        )
    if mode == "Story 1: the part":
        return (
            '<article class="sx-story"><span class="sx-k">Story 1 of 2</span>'
            "<h2>One fixed part. Many ways to make it.</h2>"
            f"<p>This {spec.stock_x_mm:g} × {spec.stock_y_mm:g} × {spec.stock_z_mm:g} mm "
            f"block has {len(spec.features)} features. The drawing becomes a STEP solid; "
            "the planner must work with the available tools and fixtures.</p>"
            "<p><b>Try it:</b> choose Top and Target design below, "
            "then inspect the fixed geometry. "
            "Rotating the view never changes the engineering coordinates.</p></article>"
        )
    failures = sum(a.disposition.value != "passed" for a in outcome.attempts)
    best = outcome.best_attempt
    result = (
        f"Attempt {best.index:02d} is the selected verified plan."
        if best
        else "No verified plan was found in this run; inspect the failure evidence."
    )
    guidance = (
        "Then select the verified attempt and compare its checks and recipe below. "
        if best
        else "Compare the other attempts and their remaining failures below. "
    )
    return (
        '<article class="sx-story"><span class="sx-k">Story 2 of 2</span>'
        "<h2>Watch the repair. Inspect the proof.</h2>"
        f"<p>{len(outcome.attempts)} attempts, {failures} non-passing. {result}</p>"
        "<p><b>Try it:</b> select a collision attempt, if present, and press Play. "
        f"{guidance}Geometry checks decide "
        "the outcome; the animation replays their trajectory.</p></article>"
    )
