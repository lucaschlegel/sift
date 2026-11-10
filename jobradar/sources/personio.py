"""Personio-Karriereseiten (z. B. Staburo, Coriolis, TNG, appliedAI).

Jede Personio-Karriereseite hat einen öffentlichen XML-Feed:
    https://<firma>.jobs.personio.com/xml
Der Firmen-Slug ist der erste Teil der Karriere-URL, bei Staburo "staburo".
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime

from jobradar.models import Posting
from jobradar.sources.base import get, strip_html


class PersonioSource:
    def __init__(self, slug: str, company: str | None = None):
        self.slug = slug
        self.company = company or slug.capitalize()
        self.name = f"personio:{slug}"

    def fetch(self) -> list[Posting]:
        xml_bytes = get(f"https://{self.slug}.jobs.personio.com/xml").content
        return self.parse(xml_bytes)

    def parse(self, xml_text: str | bytes) -> list[Posting]:
        """XML zu Postings. Bytes bevorzugt, dann liest der Parser die Kodierung selbst aus der XML-Deklaration."""
        root = ET.fromstring(xml_text)
        postings = []
        for pos in root.iter("position"):
            def text(tag: str) -> str:
                node = pos.find(tag)
                return (node.text or "").strip() if node is not None else ""

            job_id = text("id")
            created = text("createdAt")
            posted = None
            if created:
                try:
                    posted = datetime.fromisoformat(created.replace("Z", "+00:00")).date()
                except ValueError:
                    posted = None
            sections = []
            for desc in pos.iter("jobDescription"):
                name = desc.findtext("name", default="").strip()
                value = strip_html(desc.findtext("value", default=""))
                sections.append(f"{name}\n{value}".strip())
            postings.append(
                Posting(
                    source=self.name,
                    company=self.company,
                    external_id=job_id,
                    title=text("name"),
                    location=text("office"),
                    url=f"https://{self.slug}.jobs.personio.com/job/{job_id}",
                    posted_at=posted,
                    employment_type=" / ".join(filter(None, [text("employmentType"), text("schedule")])),
                    description_text="\n\n".join(sections),
                )
            )
        return postings
