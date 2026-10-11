import pytest
from rm_core.listing_ref import InvalidListingRefError, parse_listing_ref


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("ID4CpHB", "ID4CpHB"),
        ("  ID4CpHB  ", "ID4CpHB"),
        ("https://www.otodom.pl/pl/oferta/mieszkanie-2-pokoje-warszawa-ID4CpHB", "ID4CpHB"),
        ("http://otodom.pl/pl/oferta/x-ID4CpHB/", "ID4CpHB"),
        ("https://www.otodom.pl/pl/oferta/x-ID4CpHB?utm=1#top", "ID4CpHB"),
        ("https://www.otodom.pl:443/pl/oferta/x-ID4CpHB", "ID4CpHB"),
    ],
)
def test_accepts_ids_and_otodom_listing_urls(ref: str, expected: str) -> None:
    assert parse_listing_ref(ref) == expected


@pytest.mark.parametrize(
    "ref",
    [
        "",
        "   ",
        "ID",  # too short
        "ID4CpHB\n",  # control character survives strip? newline is stripped, so use inner one below
        "ID4C pHB",
        "https://evil.example/pl/oferta/x-ID4CpHB",
        "https://otodom.pl.evil.example/pl/oferta/x-ID4CpHB",
        "https://www.otodom.pl@evil.example/pl/oferta/x-ID4CpHB",
        "https://user:pw@www.otodom.pl/pl/oferta/x-ID4CpHB",
        "https://www.otodom.pl:8443/pl/oferta/x-ID4CpHB",
        "ftp://www.otodom.pl/pl/oferta/x-ID4CpHB",
        "file:///etc/passwd",
        "//www.otodom.pl/pl/oferta/x-ID4CpHB",
        "https://www.otodom.pl/pl/szukaj/x-ID4CpHB",  # not an offer path
        "https://www.otodom.pl/pl/oferta/no-id-here",
        "https://www.otodom.pl/pl/oferta/x-ID4CpHB/extra",
        "https://[::1/pl/oferta/x-ID4CpHB",  # malformed IPv6 -> ValueError inside urlsplit
        "https://www.otodom.pl/pl/oferta/" + "a" * 400 + "-ID4CpHB",
        "ID4CpHB\x00",
        "ID4CpHB\u202e",
    ],
)
def test_rejects_everything_else(ref: str) -> None:
    if ref == "ID4CpHB\n":
        assert parse_listing_ref(ref) == "ID4CpHB"  # surrounding whitespace is stripped by design
        return
    with pytest.raises(InvalidListingRefError):
        parse_listing_ref(ref)
