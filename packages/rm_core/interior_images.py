"""Upload normalisation for interior photos: sniff, bound, orient, strip metadata, re-encode (RM-448).

Nothing the client says about the file is trusted: the format comes from decoding the header, the pixel
count is checked before any pixel is decoded, animated files are refused, EXIF (GPS, device, time) is dropped
by re-encoding from raw pixels, and the result is always a bounded JPEG. CPU-bound: call through
`asyncio.to_thread`.

LEGAL[images]: processes images supplied by the user and, later, product references (RM-448)
GDPR[personal-data]: photos can contain people and location metadata; metadata is stripped here (RM-448)
"""

import hashlib
import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 40_000_000  # decoded; checked from the header before decoding
MAX_SIDE_IN = 12_000
MIN_SIDE_IN = 200
MAX_SIDE_OUT = 1600
JPEG_QUALITY = 88
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class ImageRejectedError(Exception):
    """The upload cannot be used. `code` is stable and never carries file content."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class NormalizedImage:
    data: bytes
    mime: str
    width: int
    height: int
    sha256: str


def normalize_image(raw: bytes) -> NormalizedImage:
    if not raw:
        raise ImageRejectedError("empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ImageRejectedError("too_large")
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            width, height = probe.size
            frames = getattr(probe, "n_frames", 1)
            if fmt not in ALLOWED_FORMATS:
                raise ImageRejectedError("unsupported_type")
            if width > MAX_SIDE_IN or height > MAX_SIDE_IN or width * height > MAX_PIXELS:
                raise ImageRejectedError("too_many_pixels")
            if min(width, height) < MIN_SIDE_IN:
                raise ImageRejectedError("too_small")
            if frames > 1:
                raise ImageRejectedError("animated")
            probe.load()  # decode once so a truncated or corrupt body fails here, not later
            image = ImageOps.exif_transpose(probe)  # applies the orientation, then the tag is gone
            if image.mode in ("RGBA", "LA", "P"):
                rgba = image.convert("RGBA")
                flat = Image.new("RGB", rgba.size, (255, 255, 255))
                flat.paste(rgba, mask=rgba.getchannel("A"))
                image = flat
            else:
                image = image.convert("RGB")
            image.thumbnail((MAX_SIDE_OUT, MAX_SIDE_OUT), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            image.save(
                out, format="JPEG", quality=JPEG_QUALITY, optimize=True
            )  # no exif= argument: none kept
    except ImageRejectedError:
        raise
    except Image.DecompressionBombError:
        raise ImageRejectedError("too_many_pixels") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        raise ImageRejectedError("malformed") from None
    data = out.getvalue()
    return NormalizedImage(data, "image/jpeg", image.width, image.height, hashlib.sha256(data).hexdigest())
