"""Datenmodelle des Job-Radars.

Ein Posting ist das, was eine Karriereseite liefert. Die Extraktion (Schritt 2)
füllt später aus dem Volltext ein Requirements-Objekt.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Posting(BaseModel):
    """Eine Stellenanzeige, so wie die Quelle sie liefert."""

    source: str = Field(description="Name der Quelle, z. B. 'lever:quantco-'")
    company: str
    external_id: str = Field(description="ID der Anzeige bei der Quelle")
    title: str
    location: str = ""
    url: str
    posted_at: date | None = None
    employment_type: str = ""
    description_text: str = Field(default="", description="Volltext ohne HTML")
    fetched_at: datetime = Field(default_factory=datetime.now)

    @property
    def key(self) -> str:
        """Eindeutiger Schlüssel für den Abgleich zwischen zwei Läufen."""
        return f"{self.source}:{self.external_id}"


Seniority = Literal["junior", "mid", "senior", "lead", "unclear"]


class Requirements(BaseModel):
    """Was das Modell in Schritt 2 aus dem Volltext zieht."""

    role_family: str = Field(description="z. B. Data Scientist, Biostatistician, Consultant")
    seniority: Seniority
    min_years_experience: int | None = Field(
        default=None, description="explizit geforderte Mindestjahre, sonst None"
    )
    phd_mentioned: bool = Field(description="Promotion erwähnt oder erwünscht")
    llm_experience_required: bool = Field(
        description="praktische Erfahrung mit LLM-/GenAI-Anwendungen ist Pflicht (nicht nur Plus)"
    )
    languages: list[str] = Field(default_factory=list, description="z. B. ['German C1', 'English']")
    remote_policy: str = Field(default="", description="onsite / hybrid / remote / unclear, mit Zusatz")
    permanent: bool | None = Field(default=None, description="unbefristet, wenn bekannt")
    salary_text: str = ""
    must_haves: list[str] = Field(default_factory=list, description="max. 8 Kernanforderungen")
    nice_to_haves: list[str] = Field(default_factory=list)


class Match(BaseModel):
    """Ergebnis der Bewertung gegen das Profil (Schritt 3)."""

    posting_key: str
    hard_filter_passed: bool
    score: float = Field(ge=0, le=1)
    reasons: list[str]
