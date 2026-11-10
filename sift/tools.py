"""Werkzeuge, die das Modell in Schritt 5 selbst aufrufen darf.

Ein Werkzeug ist eine normale Python-Funktion plus eine Beschreibung mit JSON-Schema.
Das Modell entscheidet, ob und mit welchen Argumenten es sie aufruft; wir führen sie aus
und geben das Ergebnis als Text zurück. Keine Agenten-Bibliothek nötig.
"""

from __future__ import annotations

import re
from pathlib import Path

import requests
import yaml

from sift.sources.base import USER_AGENT

CLOSED_MARKERS = (
    "position has been filled",
    "no longer available",
    "job not found",
    "stelle wurde besetzt",
    "nicht mehr verfügbar",
    "nicht gefunden",
    "page not found",
    "this job is no longer accepting applications",
)


def check_posting_live(url: str, *, timeout: int = 20, _get=None) -> dict:
    """Ist die Anzeige noch online? HTTP-Status plus Suche nach typischen 'geschlossen'-Texten.
    `_get` erlaubt Tests, den HTTP-Aufruf zu ersetzen."""
    getter = _get or (lambda u: requests.get(u, timeout=timeout, headers={"User-Agent": USER_AGENT}, allow_redirects=True))
    try:
        response = getter(url)
    except Exception as exc:  # Netzfehler sind ein Ergebnis, kein Absturz
        return {"url": url, "live": None, "status": None, "note": f"request failed: {exc}"}
    text = (response.text or "")[:200000].lower()
    marker = next((m for m in CLOSED_MARKERS if m in text), None)
    redirected = getattr(response, "url", url).rstrip("/") != url.rstrip("/")
    live = response.status_code == 200 and marker is None and not redirected
    note = []
    if marker:
        note.append(f"page says: '{marker}'")
    if redirected:
        note.append(f"redirected to {getattr(response, 'url', '?')}")
    return {"url": url, "live": live, "status": response.status_code, "note": "; ".join(note) or "ok"}


def lookup_watchlist(company: str, path: str | Path = "watchlist.yaml") -> dict:
    """Eigene Notizen zu einer Firma aus watchlist.yaml, unscharfer Namensvergleich."""
    p = Path(path)
    if not p.exists():
        return {"company": company, "note": None}
    notes = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    key = re.sub(r"[^a-z0-9]", "", company.lower())
    for name, note in notes.items():
        if re.sub(r"[^a-z0-9]", "", str(name).lower()) in key or key in re.sub(r"[^a-z0-9]", "", str(name).lower()):
            return {"company": name, "note": note}
    return {"company": company, "note": None}


TOOL_DEFINITIONS = [
    {
        "name": "check_posting_live",
        "description": "Check whether a job posting URL is still online. Returns live true/false, HTTP status and a note.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The posting URL"}},
            "required": ["url"],
        },
    },
    {
        "name": "lookup_watchlist",
        "description": "Look up my own notes about a company (previous applications, outcomes, impressions).",
        "input_schema": {
            "type": "object",
            "properties": {"company": {"type": "string"}},
            "required": ["company"],
        },
    },
]


def run_tool(name: str, arguments: dict) -> dict:
    """Werkzeugaufruf des Modells ausführen."""
    if name == "check_posting_live":
        return check_posting_live(arguments["url"])
    if name == "lookup_watchlist":
        return lookup_watchlist(arguments["company"])
    return {"error": f"unknown tool {name}"}
