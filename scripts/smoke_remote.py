#!/usr/bin/env python3
"""
Remote smoke test for deployed Silta service.
Verifies production deployment without authentication.

Usage:
    python scripts/smoke_remote.py https://silta-abc123-uc.a.run.app
"""

import re
import sys
from urllib.parse import urljoin

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: uv pip install httpx", file=sys.stderr)
    sys.exit(1)


def check_html_response(client: httpx.Client, url: str, description: str) -> tuple[bool, str]:
    """Verify endpoint returns HTML without auth."""
    try:
        response = client.get(url, timeout=30.0)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"

        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return False, f"Not HTML: {content_type}"

        html = response.text
        if not html.strip():
            return False, "Empty response"

        # Verify it's not the marimo editor
        if "marimo-editor" in html.lower() or "monaco-editor" in html.lower():
            return False, "Editor UI detected (should be headless app)"

        return True, f"OK ({len(html)} bytes)"
    except httpx.TimeoutException:
        return False, "Timeout"
    except httpx.RequestError as e:
        return False, f"Request failed: {e}"


def check_static_asset(client: httpx.Client, base_url: str, path: str) -> tuple[bool, str]:
    """Verify static asset is served from app origin."""
    url = urljoin(base_url, path)
    try:
        response = client.get(url, timeout=15.0)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"

        size = len(response.content)
        if size == 0:
            return False, "Empty file"

        # Verify it's actually JavaScript
        if "three.min.js" in path:
            content = response.text
            if "THREE" not in content and "three" not in content.lower():
                return False, "Not Three.js content"

        return True, f"OK ({size:,} bytes)"
    except httpx.RequestError as e:
        return False, f"Request failed: {e}"


def check_health(client: httpx.Client, base_url: str) -> tuple[bool, str]:
    """Liveness only. marimo answers /health with JSON, so do not demand HTML."""
    try:
        response = client.get(urljoin(base_url, "/health"), timeout=15.0)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        return True, f"HTTP 200 ({response.headers.get('content-type', 'unknown')})"
    except httpx.RequestError as exc:
        return False, f"Request failed: {exc}"


# Hosts that would mean judging depends on someone else's uptime. Fonts are a
# deliberate, documented exception: they are cosmetic and degrade to a local stack.
_CODE_CDN_HOSTS = (
    "cdn.jsdelivr.net",
    "cdnjs.cloudflare.com",
    "unpkg.com",
    "esm.sh",
    "code.jquery.com",
    "ajax.googleapis.com",
    "cdn.skypack.dev",
)


def check_no_cdn_dependency(client: httpx.Client, base_url: str) -> tuple[bool, str]:
    """No script or stylesheet may be fetched from a third-party code CDN.

    The viewer's Three.js bundle is inlined into the anywidget module rather than
    served as a separate asset, so there is no fixed asset URL to probe; what must
    hold is that the served page pulls no code from anyone else's origin.
    """
    try:
        body = client.get(base_url, timeout=20.0).text
    except httpx.RequestError as exc:
        return False, f"Request failed: {exc}"
    found = [host for host in _CODE_CDN_HOSTS if host in body]
    if found:
        return False, f"References third-party code host(s): {', '.join(found)}"
    scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', body, re.IGNORECASE)
    offsite = [
        src
        for src in scripts
        if src.startswith(("http://", "https://")) and not src.startswith(base_url)
    ]
    if offsite:
        return False, f"Off-origin script(s): {', '.join(offsite[:3])}"
    return True, f"All {len(scripts)} scripts same-origin"


def check_no_api_key_leak(client: httpx.Client, url: str) -> tuple[bool, str]:
    """Verify no API keys are exposed in responses or headers."""
    try:
        response = client.get(url, timeout=20.0)

        # Check headers
        for header, value in response.headers.items():
            if re.search(r"(api[_-]?key|token|secret|bearer)", header, re.IGNORECASE):
                if re.search(r"[a-zA-Z0-9_-]{32,}", value):
                    return False, f"Possible key in header: {header}"

        # Check body for common key patterns
        body = response.text

        # W&B keys start with "wb_" or "wandb_"
        if re.search(r"(wb_|wandb_)[a-zA-Z0-9]{32,}", body):
            return False, "W&B key pattern in HTML"

        # Generic API key patterns (long alphanumeric strings)
        if re.search(r"['\"]api[_-]?key['\"]:\s*['\"][a-zA-Z0-9_-]{32,}['\"]", body, re.IGNORECASE):
            return False, "API key pattern in HTML"

        return True, "No leaks detected"
    except httpx.RequestError as e:
        return False, f"Request failed: {e}"


def check_websocket_endpoint(client: httpx.Client, base_url: str) -> tuple[bool, str]:
    """Open a real WebSocket to marimo's kernel endpoint and read one frame.

    A status-code guess proves nothing: the application only works if the socket
    actually upgrades and the kernel speaks first.
    """
    import asyncio

    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = ws_url.rstrip("/") + "/ws?session_id=smoke-remote-check"

    async def handshake() -> tuple[bool, str]:
        try:
            import websockets
        except ImportError:
            return False, "websockets library unavailable"
        try:
            async with websockets.connect(ws_url, open_timeout=20, close_timeout=5) as socket:
                frame = await asyncio.wait_for(socket.recv(), timeout=20)
                size = len(frame)
                return True, f"Upgraded and received {size} bytes"
        except Exception as exc:  # noqa: BLE001 - any failure is a failed check
            return False, f"{type(exc).__name__}: {exc}"

    return asyncio.run(handshake())


def check_editor_routes_blocked(client: httpx.Client, base_url: str) -> tuple[bool, str]:
    """Verify marimo editor routes are not accessible."""
    editor_paths = ["/edit", "/@file", "/api/kernel"]
    blocked_count = 0

    for path in editor_paths:
        url = urljoin(base_url, path)
        try:
            response = client.get(url, timeout=10.0)
            # We want these to be 404 or 403, not 200
            if response.status_code == 200:
                return False, f"Editor route accessible: {path}"
            blocked_count += 1
        except httpx.RequestError:
            blocked_count += 1

    return True, f"Editor routes blocked ({blocked_count}/{len(editor_paths)})"


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/smoke_remote.py <SERVICE_URL>")
        print("Example: python scripts/smoke_remote.py https://silta-abc123-uc.a.run.app")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Silta Remote Smoke Test")
    print(f"Target: {base_url}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    results = []
    client = httpx.Client(follow_redirects=True)

    try:
        # Test 1: Root endpoint serves HTML
        print("1. Root endpoint (HTML)...", end=" ")
        passed, message = check_html_response(client, base_url, "root")
        results.append(("Root HTML", passed, message))
        print(f"{'✓' if passed else '✗'} {message}")

        # Test 2: Health endpoint (if exists)
        print("2. Health endpoint...", end=" ")
        passed, message = check_health(client, base_url)
        results.append(("Health check", passed, message))
        print(f"{'✓' if passed else '✗'} {message}")

        # Test 3: Static asset (Three.js)
        print("3. No third-party code hosts...", end=" ")
        passed, message = check_no_cdn_dependency(client, base_url)
        results.append(("No CDN for code", passed, message))
        print(f"{'✓' if passed else '✗'} {message}")

        # Test 4: WebSocket endpoint exists
        print("4. WebSocket endpoint...", end=" ")
        passed, message = check_websocket_endpoint(client, base_url)
        results.append(("WebSocket", passed, message))
        print(f"{'✓' if passed else '✗'} {message}")

        # Test 5: No API key leaks
        print("5. API key leak check...", end=" ")
        passed, message = check_no_api_key_leak(client, base_url)
        results.append(("No API leaks", passed, message))
        print(f"{'✓' if passed else '✗'} {message}")

        # Test 6: Editor routes blocked
        print("6. Editor routes blocked...", end=" ")
        passed, message = check_editor_routes_blocked(client, base_url)
        results.append(("Editor blocked", passed, message))
        print(f"{'✓' if passed else '✗'} {message}")

    finally:
        client.close()

    # Summary
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("Summary")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)

    for name, passed, message in results:
        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {name:20s} {status:6s} {message}")

    print()
    print(f"Result: {passed_count}/{total_count} checks passed")
    print()

    if passed_count == total_count:
        print("✅ ALL CHECKS PASSED - Deployment verified")
        sys.exit(0)
    else:
        print("❌ SOME CHECKS FAILED - Review issues above")
        sys.exit(1)


if __name__ == "__main__":
    main()
