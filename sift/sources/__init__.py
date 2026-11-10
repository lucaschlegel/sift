"""Quellen. Neue Quelle = neue Klasse mit fetch() -> list[Posting]."""

from sift.sources.lever import LeverSource
from sift.sources.personio import PersonioSource

__all__ = ["LeverSource", "PersonioSource", "build_sources"]


def build_sources(config: dict) -> list:
    """Aus dem Abschnitt `sources` der sources.yaml die Quellobjekte bauen."""
    sources = []
    for entry in config.get("lever", []):
        sources.append(LeverSource(entry["slug"], entry.get("company"), entry.get("location_hint")))
    for entry in config.get("personio", []):
        sources.append(PersonioSource(entry["slug"], entry.get("company"), entry.get("location_hint")))
    return sources
