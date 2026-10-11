import asyncio
import io
import struct
import zlib

import httpx
import pytest
from PIL import Image
from rm_worker import images as imgmod
from rm_worker.images import (
    ImageRejectedError,
    PreparedImage,
    download_image,
    drop_near_duplicates,
    fetch_prepared,
    prepare_image,
    select_media,
    validate_image_url,
)

HOSTS = ("olxcdn.com", "otodom.pl")
GOOD = "https://ireland.apollo.olxcdn.com/v1/files/abc/image;s=1280x1024"


def encode(img: Image.Image, fmt: str = "JPEG", **kw: object) -> bytes:
    out = io.BytesIO()
    img.save(out, format=fmt, **kw)
    return out.getvalue()


def gradient(w: int, h: int, seed: int = 0) -> Image.Image:
    img = Image.new("RGB", (w, h))
    px = img.load()
    assert px is not None
    for x in range(w):
        for y in range(h):
            px[x, y] = ((x * 255 // w + seed * 40) % 256, (y * 255 // h) % 256, ((x + y) * seed) % 256)
    return img


# ---- URL validation ----
@pytest.mark.parametrize(
    "url",
    [
        GOOD,
        "https://olxcdn.com/x.jpg",
        "https://media.otodom.pl/x.jpg",
        "https://IRELAND.APOLLO.OLXCDN.COM/x.jpg",
        "https://ireland.apollo.olxcdn.com:443/x.jpg",
    ],
)
def test_allow_listed_https_urls_pass(url: str) -> None:
    assert validate_image_url(url, HOSTS).startswith("https://")


@pytest.mark.parametrize(
    "url",
    [
        "http://olxcdn.com/x.jpg",
        "https://evil.example/x.jpg",
        "https://olxcdn.com.evil.example/x.jpg",
        "https://notolxcdn.com/x.jpg",
        "https://olxcdn.com@evil.example/x.jpg",
        "https://user:pw@olxcdn.com/x.jpg",
        "https://olxcdn.com:8443/x.jpg",
        "https://127.0.0.1/x.jpg",
        "https://169.254.169.254/latest/meta-data",
        "https://localhost/x.jpg",
        "file:///etc/passwd",
        "data:image/png;base64,AAAA",
        "//olxcdn.com/x.jpg",
        "",
        "https://[::1/x",
    ],
)
def test_everything_else_is_rejected(url: str) -> None:
    with pytest.raises(ImageRejectedError):
        validate_image_url(url, HOSTS)


def test_an_empty_allowlist_rejects_everything() -> None:
    with pytest.raises(ImageRejectedError):
        validate_image_url(GOOD, ())


# ---- processing ----
def test_large_photo_is_downscaled_to_1600_long_edge_as_jpeg() -> None:
    out = prepare_image(encode(gradient(3200, 2400)))
    assert (out.width, out.height) == (1600, 1200)
    assert Image.open(io.BytesIO(out.jpeg)).format == "JPEG"


def test_small_photo_is_not_upscaled() -> None:
    out = prepare_image(encode(gradient(400, 300)))
    assert (out.width, out.height) == (400, 300)


def test_exif_including_gps_is_stripped_and_orientation_applied() -> None:
    img = gradient(300, 200)
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    exif[0x010F] = "SecretCameraMaker"
    gps = exif.get_ifd(0x8825)
    gps[2] = (52.0, 13.0, 0.0)
    out = prepare_image(encode(img, exif=exif))
    result = Image.open(io.BytesIO(out.jpeg))
    assert (result.width, result.height) == (200, 300)  # rotated
    assert len(result.getexif()) == 0
    assert b"SecretCameraMaker" not in out.jpeg
    assert b"Exif" not in out.jpeg[:64]


@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_other_allowed_formats_are_converted(fmt: str) -> None:
    out = prepare_image(encode(gradient(200, 100), fmt))
    assert Image.open(io.BytesIO(out.jpeg)).format == "JPEG"


def test_transparency_is_flattened_on_white() -> None:
    rgba = Image.new("RGBA", (50, 50), (255, 0, 0, 0))
    result = Image.open(io.BytesIO(prepare_image(encode(rgba, "PNG")).jpeg)).convert("RGB")
    r, g, b = result.getpixel((10, 10))  # pyright: ignore[reportGeneralTypeIssues]
    assert min(r, g, b) > 240


def png_header(width: int, height: int) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


def test_decompression_bomb_is_rejected_before_decoding() -> None:
    with pytest.raises(ImageRejectedError, match=r"too many pixels|unreadable"):
        prepare_image(png_header(30_000, 30_000))


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not an image",
        b"GIF89a" + b"\x00" * 20,
        encode(gradient(10, 10), "GIF"),
        encode(gradient(10, 10), "BMP"),
    ],
)
def test_garbage_and_unsupported_formats_are_rejected(data: bytes) -> None:
    with pytest.raises(ImageRejectedError):
        prepare_image(data)


def test_truncated_jpeg_is_rejected() -> None:
    with pytest.raises(ImageRejectedError):
        prepare_image(encode(gradient(300, 300))[:200])


def test_oversized_input_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imgmod, "MAX_DOWNLOAD_BYTES", 100)
    with pytest.raises(ImageRejectedError, match="cap"):
        prepare_image(encode(gradient(300, 300)))


# ---- limits and de-duplication ----
def test_near_duplicates_are_dropped_and_distinct_photos_kept() -> None:
    a = prepare_image(encode(gradient(400, 300, 1)), "a")
    a_resized = prepare_image(encode(gradient(400, 300, 1).resize((380, 285))), "a2")
    b = prepare_image(encode(Image.new("RGB", (400, 300), (10, 200, 30))), "b")
    kept = drop_near_duplicates([a, a_resized, b])
    assert [k.source_url for k in kept] == ["a", "b"]


def test_media_limits_cap_photos_and_plans_and_remove_repeats() -> None:
    photos, plans = select_media([f"p{i}" for i in range(40)] + ["p0"], ["f1", "f1", "f2", "f3"])
    assert len(photos) == 25
    assert photos[0] == "p0"
    assert plans == ["f1", "f2"]


# ---- download ----
def client(transport: httpx.MockTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=transport or httpx.MockTransport(lambda _r: httpx.Response(200, content=b"ok"))
    )


async def test_download_returns_bytes_for_an_allowed_host() -> None:
    async with client(httpx.MockTransport(lambda r: httpx.Response(200, content=b"data"))) as c:
        assert await download_image(c, GOOD, HOSTS) == b"data"


async def test_download_never_contacts_a_disallowed_host() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=b"x")

    async with client(httpx.MockTransport(handler)) as c:
        for bad in ("https://evil.example/x.jpg", "http://olxcdn.com/x.jpg", "https://169.254.169.254/"):
            with pytest.raises(ImageRejectedError):
                await download_image(c, bad, HOSTS)
    assert calls == []


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404),
        httpx.Response(302, headers={"location": "https://evil.example/x"}),
        httpx.Response(200, headers={"content-length": str(50 * 1024 * 1024)}, content=b"x"),
    ],
)
async def test_download_rejects_errors_redirects_and_declared_oversize(response: httpx.Response) -> None:
    async with client(httpx.MockTransport(lambda r: response)) as c:
        with pytest.raises(ImageRejectedError):
            await download_image(c, GOOD, HOSTS)


async def test_download_aborts_streams_that_exceed_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imgmod, "MAX_DOWNLOAD_BYTES", 1000)

    async def body() -> object:
        for _ in range(100):
            yield b"x" * 100

    async with client(httpx.MockTransport(lambda r: httpx.Response(200, content=body()))) as c:  # pyright: ignore[reportArgumentType]
        with pytest.raises(ImageRejectedError, match="cap"):
            await download_image(c, GOOD, HOSTS)


async def test_download_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(imgmod, "DOWNLOAD_TIMEOUT_S", 0.1)

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(2)
        return httpx.Response(200, content=b"x")

    async with client(httpx.MockTransport(slow)) as c:
        with pytest.raises(ImageRejectedError, match=r"Timeout"):
            await download_image(c, GOOD, HOSTS)


async def test_fetch_prepared_skips_bad_images_counts_them_and_bounds_concurrency() -> None:
    good = encode(gradient(200, 100, 2))
    active = 0
    peak = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return httpx.Response(200, content=b"junk" if "bad" in request.url.path else good)

    urls = [f"https://olxcdn.com/ok{i}.jpg" for i in range(10)] + [
        "https://olxcdn.com/bad.jpg",
        "https://evil.example/x",
    ]
    async with client(httpx.MockTransport(handler)) as c:
        images, skipped = await fetch_prepared(c, urls, HOSTS)
    assert len(images) == 10
    assert skipped == 2
    assert peak <= 4
    assert all(isinstance(i, PreparedImage) for i in images)
