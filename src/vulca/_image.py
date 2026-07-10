"""Image loading utilities -- file, URL, or base64."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import httpx


def resolve_image_input(value: str) -> str:
    """Resolve image input to base64 string.

    Accepts file path (starts with /, ~, or drive letter) or raw base64.
    Returns empty string for empty input.
    """
    if not value:
        return ""

    # Check if it looks like a file path (absolute, relative, or home-relative)
    path = Path(value).expanduser()
    if path.exists():
        return base64.b64encode(path.resolve().read_bytes()).decode()

    # Check common path patterns that might not exist yet
    if value.startswith(("/", "~", ".")) or (len(value) >= 3 and value[1] == ":"):
        raise FileNotFoundError(f"Image not found: {path.resolve()}")

    # Assume base64
    return value


async def load_image_base64(image: str) -> tuple[str, str]:
    """Load an image and return ``(base64_string, mime_type)``.

    Accepts:
    - Local file path: ``"/tmp/art.jpg"``
    - HTTP(S) URL: ``"https://example.com/image.png"``
    - Already-encoded base64: ``"data:image/jpeg;base64,..."`` or raw b64 string
    """
    # Already base64 data URI
    if image.startswith("data:"):
        mime, _, b64 = image.partition(";base64,")
        return b64, mime.replace("data:", "")

    # URL
    if image.startswith(("http://", "https://")):
        headers = {"User-Agent": "VULCA/0.3 (https://github.com/vulca-org/vulca-visual-control-sdk)"}
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
            resp = await client.get(image)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            mime = content_type.split(";")[0].strip()
            b64 = base64.b64encode(resp.content).decode()
            return b64, mime

    # Local file
    path = Path(image).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return b64, mime
