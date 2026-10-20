"""Interior upload normalisation: format sniffing, bounds, metadata stripping, orientation (RM-448)."""

import io
import zlib

import pytest
from PIL import Image
from rm_core.interior_images import (
    MAX_SIDE_OUT,
    MAX_UPLOAD_BYTES,
    ImageRejectedError,
    normalize_image,
)


def _encode(fmt: str, size: tuple[int, int] = (400, 300), mode: str = "RGB", **kwargs: object) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else (200, 30, 30, 128)).save(
        buf, format=fmt, **kwargs
    )
    return buf.getvalue()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_supported_formats_become_a_jpeg(fmt: str) -> None:
    out = normalize_image(_encode(fmt))
    assert out.mime == "image/jpeg"
    assert (out.width, out.height) == (400, 300)
    assert len(out.sha256) == 64
    with Image.open(io.BytesIO(out.data)) as im:
        assert im.format == "JPEG"


def test_large_images_are_bounded_and_deterministic() -> None:
    raw = _encode("JPEG", (4000, 2000))
    a, b = normalize_image(raw), normalize_image(raw)
    assert max(a.width, a.height) == MAX_SIDE_OUT
    assert a.sha256 == b.sha256


def test_exif_gps_and_other_metadata_are_dropped() -> None:
    exif = Image.Exif()
    exif[0x010F] = "CameraMaker"
    exif[0x8825] = {1: "N", 2: (52.0, 13.0, 0.0)}  # GPS IFD
    raw = _encode("JPEG", exif=exif.tobytes())
    with Image.open(io.BytesIO(raw)) as src:
        assert src.getexif().get(0x010F) == "CameraMaker"
    out = normalize_image(raw)
    with Image.open(io.BytesIO(out.data)) as dst:
        assert not dst.getexif()
        assert b"CameraMaker" not in out.data
        assert "icc_profile" not in dst.info


def test_orientation_is_applied_not_just_removed() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise on display
    out = normalize_image(_encode("JPEG", (400, 300), exif=exif.tobytes()))
    assert (out.width, out.height) == (300, 400)


def test_transparency_is_flattened_on_white() -> None:
    out = normalize_image(_encode("PNG", mode="RGBA"))
    with Image.open(io.BytesIO(out.data)) as im:
        assert im.mode == "RGB"
        pixel = im.getpixel((5, 5))
        assert isinstance(pixel, tuple)
        assert min(pixel) > 100  # blended towards white, not black


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (b"", "empty"),
        (b"x" * (MAX_UPLOAD_BYTES + 1), "too_large"),
        (b"GIF89a not really an image", "malformed"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "malformed"),
        (_encode("GIF", (400, 300)), "unsupported_type"),
        (_encode("JPEG", (100, 100)), "too_small"),
        (_encode("JPEG")[:200], "malformed"),
    ],
)
def test_rejections(raw: bytes, code: str) -> None:
    with pytest.raises(ImageRejectedError) as err:
        normalize_image(raw)
    assert err.value.code == code


def test_declared_huge_pixel_count_is_refused_before_decoding() -> None:
    # A tiny PNG whose header claims 30000 x 30000: refused from the header, nothing is allocated.
    raw = bytearray(_encode("PNG", (400, 300)))
    raw[16:24] = (30000).to_bytes(4, "big") * 2
    raw[29:33] = zlib.crc32(bytes(raw[12:29])).to_bytes(4, "big")  # keep the IHDR chunk valid
    with pytest.raises(ImageRejectedError) as err:
        normalize_image(bytes(raw))
    assert err.value.code == "too_many_pixels"


def test_animated_images_are_refused() -> None:
    buf = io.BytesIO()
    frames = [Image.new("RGB", (400, 300), c) for c in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:], duration=100)
    with pytest.raises(ImageRejectedError) as err:
        normalize_image(buf.getvalue())
    assert err.value.code == "animated"
