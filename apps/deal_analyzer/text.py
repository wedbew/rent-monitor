"""Folding of seller free text so patterns match regardless of HTML, accents, case and whitespace."""

import html
import re
import unicodedata

_TAGS = re.compile(r"<[^>]{0,500}>")
_SPACES = re.compile(r"\s+")
_EXTRA = str.maketrans({"ł": "l", "Ł": "l", "ø": "o", "đ": "d"})  # NFKD does not decompose these


def fold(text: str) -> str:
    """Unescape HTML, drop tags and accents (`ł`→`l`), casefold, collapse whitespace."""
    cleaned = _TAGS.sub(" ", html.unescape(text)).translate(_EXTRA)
    decomposed = unicodedata.normalize("NFKD", cleaned)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _SPACES.sub(" ", stripped.casefold()).strip()


def snippet(text: str, start: int, end: int, width: int = 40) -> str:
    """A short evidence excerpt around a match, bounded so results stay small."""
    return text[max(0, start - width) : min(len(text), end + width)].strip()[:120]
