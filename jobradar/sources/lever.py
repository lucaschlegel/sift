"""Lever-Karriereseiten (z. B. QuantCo).

Lever bietet ein öffentliches JSON-Verzeichnis pro Firma:
    https://api.lever.co/v0/postings/<firma>?mode=json
Der Firmen-Slug steht in der URL der Karriereseite, bei QuantCo "quantco-".
"""

from __future__ import annotations

from datetime import date, datetime

from jobradar.models import Posting
from jobradar.sources.base import get, strip_html


class LeverSource:
    def __init__(self, slug: str, company: str | None = None):
        self.slug = slug
        self.company = company or slug.strip("-").capitalize()
        self.name = f"lever:{slug}"

    def fetch(self) -> list[Posting]:
        data = get(f"https://api.lever.co/v0/postings/{self.slug}", params={"mode": "json"}).json()
        return [self.parse(item) for item in data]

    def parse(self, item: dict) -> Posting:
        """Ein Lever-Eintrag zu einem Posting. Öffentlich, damit Tests Fixtures nutzen können."""
        categories = item.get("categories") or {}
        created = item.get("createdAt")
        posted = date.fromtimestamp(created / 1000) if created else None
        parts = [item.get("descriptionPlain") or strip_html(item.get("description", ""))]
        for block in item.get("lists") or []:
            parts.append(block.get("text", ""))
            parts.append(strip_html(block.get("content", "")))
        parts.append(item.get("additionalPlain") or strip_html(item.get("additional", "")))
        locations = categories.get("allLocations") or (
            [categories["location"]] if categories.get("location") else []
        )
        return Posting(
            source=self.name,
            company=self.company,
            external_id=item["id"],
            title=item.get("text", "").strip(),
            location=", ".join(locations),
            url=item.get("hostedUrl", ""),
            posted_at=posted,
            employment_type=categories.get("commitment", ""),
            description_text="\n\n".join(p for p in parts if p).strip(),
        )
