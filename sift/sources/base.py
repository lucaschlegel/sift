"""Gemeinsame Hilfen für alle Quellen."""

from __future__ import annotations

import html
import re
import time
from typing import Protocol

import requests

from jobradar.models import Posting

USER_AGENT = "jobradar/0.1 (personal job search tool; contact via GitHub)"
REQUEST_PAUSE_SECONDS = 1.0


class Source(Protocol):
    """Jede Quelle liefert eine Liste von Postings."""

    name: str

    def fetch(self) -> list[Posting]: ...


def get(url: str, *, params: dict | None = None, timeout: int = 30) -> requests.Response:
    """GET mit ehrlichem User-Agent und kurzer Pause, damit wir niemanden belästigen."""
    time.sleep(REQUEST_PAUSE_SECONDS)
    response = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


def strip_html(text: str) -> str:
    """HTML grob zu lesbarem Text machen. Reicht für die Extraktion, kein Parser nötig."""
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _NL_RE.sub("\n\n", text).strip()
