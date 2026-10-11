"""Listing photo pipeline: allow-listed bounded download, bomb guard, EXIF strip, downscale, de-duplication.

LEGAL[images]: downloads, resizes and caches third-party listing photos and floor plans (RM-23).
GDPR[personal-data]: photos can contain people and EXIF GPS data; EXIF is stripped before anything is stored
or sent to a processor (OpenRouter, see `openrouter.py`).
Security: URLs come from third-party payloads, so only https URLs on allow-listed host suffixes are fetched,
redirects are not followed, and size, pixel and time are all capped.
"""

import asyncio
import io
import warnings
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
import structlog
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PHOTOS = 25
MAX_FLOOR_PLANS = 2
LONG_EDGE_PX = 1600
MAX_PIXELS = 40_000_000
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
DOWNLOAD_TIMEOUT_S = 20.0
DOWNLOAD_CONCURRENCY = 4
DUPLICATE_HAMMING_MAX = 4
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

Image.MAX_IMAGE_PIXELS = MAX_PIXELS  # refuse decompression bombs (blueprint §6)
log = structlog.get_logger(__name__)


class ImageRejectedError(ValueError):
    """The bytes are not a usable photo (wrong type, too large, too many pixels, corrupt)."""


@dataclass(frozen=True)
class PreparedImage:
    source_url: str
    jpeg: bytes
    width: int
    height: int
    dhash: int


def validate_image_url(url: str, allowed_suffixes: tuple[str, ...]) -> str:
    """Return `url` if it is https on an allow-listed host; raise `ImageRejectedError` otherwise."""
    try:
        parts = urlsplit(url.strip())
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError as exc:
        raise ImageRejectedError("malformed image URL") from exc
    allowed = any(host == s or host.endswith("." + s) for s in allowed_suffixes)
    if parts.scheme != "https" or not allowed or parts.username or parts.password or port not in {None, 443}:
        raise ImageRejectedError("image URL is not an allow-listed https host")
    return parts.geturl()


def _dhash(img: Image.Image) -> int:
    small = img.convert("L").resize((9, 8), Image.Resampling.LANCZOS)  # pyright: ignore[reportUnknownMemberType]
    pixels = small.tobytes()  # mode L: one byte per pixel, row-major
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | int(pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def prepare_image(data: bytes, source_url: str = "") -> PreparedImage:
    """CPU-bound: validate, orient, strip metadata, downscale to a 1,600 px long edge, re-encode as JPEG."""
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ImageRejectedError("image is larger than the download cap")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data))
            if img.format not in ALLOWED_FORMATS:
                raise ImageRejectedError(f"unsupported image format {img.format}")
            if img.width * img.height > MAX_PIXELS:
                raise ImageRejectedError("image has too many pixels")
            img.draft("RGB", (LONG_EDGE_PX, LONG_EDGE_PX))  # JPEG: decode at reduced size
            img = ImageOps.exif_transpose(img)
            img.load()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ImageRejectedError(f"unreadable image: {type(exc).__name__}") from exc
    if img.mode in {"RGBA", "LA", "P"}:
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        img = background
    else:
        img = img.convert("RGB")
    img.thumbnail((LONG_EDGE_PX, LONG_EDGE_PX), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)  # no exif= argument: metadata is dropped
    return PreparedImage(source_url, out.getvalue(), img.width, img.height, _dhash(img))


def drop_near_duplicates(images: list[PreparedImage]) -> list[PreparedImage]:
    kept: list[PreparedImage] = []
    for img in images:
        if all((img.dhash ^ k.dhash).bit_count() > DUPLICATE_HAMMING_MAX for k in kept):
            kept.append(img)
    return kept


def select_media(photo_urls: list[str], plan_urls: list[str]) -> tuple[list[str], list[str]]:
    """Apply the per-audit limits: at most 25 photos and 2 floor plans, in listing order, without repeats."""
    photos = list(dict.fromkeys(photo_urls))[:MAX_PHOTOS]
    plans = list(dict.fromkeys(plan_urls))[:MAX_FLOOR_PLANS]
    return photos, plans


async def download_image(client: httpx.AsyncClient, url: str, allowed_suffixes: tuple[str, ...]) -> bytes:
    """Bounded streaming download of one allow-listed image; never follows redirects."""
    safe = validate_image_url(url, allowed_suffixes)
    try:
        async with asyncio.timeout(DOWNLOAD_TIMEOUT_S):
            async with client.stream("GET", safe, follow_redirects=False) as response:
                if response.status_code != 200:
                    raise ImageRejectedError(f"image host answered HTTP {response.status_code}")
                declared = int(response.headers.get("content-length", "0") or 0)
                if declared > MAX_DOWNLOAD_BYTES:
                    raise ImageRejectedError("image is larger than the download cap")
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise ImageRejectedError("image is larger than the download cap")
                    chunks.append(chunk)
                return b"".join(chunks)
    except (httpx.HTTPError, TimeoutError) as exc:
        raise ImageRejectedError(f"image download failed: {type(exc).__name__}") from exc


async def fetch_prepared(
    client: httpx.AsyncClient, urls: list[str], allowed_suffixes: tuple[str, ...]
) -> tuple[list[PreparedImage], int]:
    """Download and prepare many images with bounded concurrency. Returns (images, number skipped)."""
    gate = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)

    async def one(url: str) -> PreparedImage | None:
        async with gate:
            try:
                data = await download_image(client, url, allowed_suffixes)
                return await asyncio.to_thread(prepare_image, data, url)
            except ImageRejectedError as exc:
                log.warning("image_skipped", reason=str(exc))  # never log the URL query (may carry tokens)
                return None

    results = await asyncio.gather(*(one(u) for u in urls))
    images = [r for r in results if r is not None]
    return images, len(results) - len(images)
