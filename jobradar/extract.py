"""Schritt 2: Anforderungen aus dem Stellentext ziehen, mit festem Schema.

Wie es funktioniert
-------------------
Das Modell bekommt den Stellentext und ein "Werkzeug" namens record_requirements,
dessen Eingabeschema das JSON-Schema unseres Pydantic-Modells Requirements ist.
Mit tool_choice zwingen wir das Modell, genau dieses Werkzeug aufzurufen. Die
Antwort ist dann kein freier Text, sondern ein JSON-Objekt, das zum Schema passt
("schema-constrained output"). Pydantic prüft es noch einmal nach.

Der Anbieter steckt hinter einer kleinen Schnittstelle (Extractor), damit sich
später ein lokales Modell (Ollama) oder OpenAI einhängen lässt.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from jobradar.models import Posting, Requirements

DEFAULT_MODEL = os.environ.get("JOBRADAR_MODEL", "claude-haiku-5-5")
MAX_CHARS = 12000  # längere Anzeigen abschneiden, der Rest ist fast immer Firmenprosa

SYSTEM_PROMPT = """You extract structured hiring requirements from job postings.
Rules:
- Use only what the posting says. Do not guess. If something is not stated, use null, an empty list or "unclear".
- min_years_experience: only an explicitly stated minimum number of years of professional experience, else null.
- seniority: junior = entry level / graduate / "(Junior)" / "(Senior)" in parentheses meaning either level; mid = 2-5 years or no explicit level but professional experience expected; senior = "Senior" or 5+ years; lead = Lead/Principal/Head/Director/Expert/Chief.
- llm_experience_required: true only if hands-on experience with LLM / GenAI applications (building with LLM APIs, RAG, agents, prompt engineering) is listed as a requirement, not as a plus or nice-to-have.
- must_haves: at most 8 short items, in the posting's own words, trimmed.
- languages: list language requirements with level if given, e.g. "German C1", "English fluent".
- remote_policy: one of onsite / hybrid / remote / unclear, optionally with a short detail, e.g. "hybrid, 2-3 days office".
- permanent: true if permanent/unbefristet is stated, false if fixed-term/befristet, null if not stated.
"""

TOOL_NAME = "record_requirements"


def build_tool() -> dict:
    """Das Werkzeug, das das Modell aufrufen muss. Schema kommt direkt aus Pydantic."""
    schema = Requirements.model_json_schema()
    return {
        "name": TOOL_NAME,
        "description": "Record the structured requirements of one job posting.",
        "input_schema": schema,
    }


def build_user_message(posting: Posting) -> str:
    text = posting.description_text[:MAX_CHARS]
    return (
        f"Company: {posting.company}\n"
        f"Title: {posting.title}\n"
        f"Location: {posting.location}\n"
        f"Employment type: {posting.employment_type}\n\n"
        f"Posting text:\n{text}"
    )


class Extractor(Protocol):
    def extract(self, posting: Posting) -> Requirements: ...


class AnthropicExtractor:
    """Extraktion über die Anthropic-API. Braucht ANTHROPIC_API_KEY in der Umgebung."""

    def __init__(self, model: str | None = None, client=None):
        if client is None:
            import anthropic  # erst hier importieren, damit Tests ohne SDK laufen

            client = anthropic.Anthropic()
        self.client = client
        self.model = model or DEFAULT_MODEL
        self.tool = build_tool()

    def extract(self, posting: Posting) -> Requirements:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[self.tool],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[{"role": "user", "content": build_user_message(posting)}],
        )
        return parse_tool_response(response)


def parse_tool_response(response) -> Requirements:
    """Aus der API-Antwort den Werkzeugaufruf herausholen und gegen das Schema prüfen."""
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
            return Requirements.model_validate(block.input)
    raise ValueError("model did not call the extraction tool")


# ---------------------------------------------------------------------------
# Zwischenspeicher: einmal extrahiert, nicht noch einmal bezahlen
# ---------------------------------------------------------------------------

REQ_FILE = Path("data") / "requirements.json"


def load_requirements(path: Path = REQ_FILE) -> dict[str, Requirements]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: Requirements.model_validate(v) for k, v in raw.items()}


def save_requirements(reqs: dict[str, Requirements], path: Path = REQ_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: v.model_dump(mode="json") for k, v in reqs.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_missing(
    postings: list[Posting],
    extractor: Extractor,
    cache: dict[str, Requirements],
    *,
    limit: int | None = None,
    force: bool = False,
    log=print,
) -> dict[str, Requirements]:
    """Für alle Postings ohne Eintrag im Cache die Extraktion aufrufen."""
    todo = [p for p in postings if force or p.key not in cache]
    if limit is not None:
        todo = todo[:limit]
    for i, posting in enumerate(todo, start=1):
        try:
            cache[posting.key] = extractor.extract(posting)
            log(f"[ok] {i}/{len(todo)} {posting.company}: {posting.title}")
        except Exception as exc:  # eine Anzeige soll den Lauf nicht stoppen
            log(f"[warn] {i}/{len(todo)} {posting.company}: {posting.title}: {exc}")
    return cache
