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

from pydantic import BaseModel

from sift.models import Posting, Requirements

DEFAULT_MODEL = os.environ.get("SIFT_MODEL", "claude-haiku-5-5")
MAX_CHARS = 12000  # längere Anzeigen abschneiden, der Rest ist fast immer Firmenprosa

PROMPT_VERSION = "v3"  # bei jeder Änderung am Prompt hochzählen, damit Schritt 4 Varianten vergleichen kann

SYSTEM_PROMPT = """You extract structured hiring requirements from job postings.
Rules:
- Use only the requirements and responsibilities of the role. Ignore company descriptions, "about us" sections, founder biographies and benefits. A sentence like "founded by four PhDs" is NOT a requirement.
- Use only what the posting says. Do not guess. If something is not stated, use null, an empty list or "unclear".
- min_years_experience: only an explicitly stated minimum number of years of professional experience, else null.
- seniority, decide in this order: (1) a title word wins: "Senior" without parentheses -> senior; Lead/Principal/Head/Director/Expert/Chief/Staff -> lead; "(Junior)" or Intern/Praktikum/Werkstudent/Working Student -> junior; "(Senior)" with Senior in parentheses means open to both levels -> mid, never senior. (2) Otherwise use the text: if internships, working-student jobs or course projects are accepted as the required experience, or the posting addresses graduates -> junior; if 2-5 years or "some professional experience" are expected -> mid; if 5+ years -> senior. (3) If the posting explicitly addresses both graduates and experienced professionals, or says nothing about level -> unclear.
- phd_mentioned: true only if a doctorate is listed as required, preferred or welcome for the candidate.
- llm_experience_required: true if hands-on experience with LLM / GenAI applications is a requirement of the role, including building with LLM or "frontier lab" APIs (OpenAI, Anthropic, Gemini), RAG, agents, prompt engineering, fine-tuning or serving language models (e.g. HuggingFace). False if it is only a plus or nice-to-have, or not mentioned.
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


class ExtractionRecord(BaseModel):
    """Ein Extraktionsergebnis samt Herkunft, damit Schritt 4 Prompt- und Modellvarianten vergleichen kann."""

    prompt_version: str
    model: str
    requirements: Requirements


def load_requirements(path: Path = REQ_FILE) -> dict[str, ExtractionRecord]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    records = {}
    for key, value in raw.items():
        if "requirements" in value:  # neues Format
            records[key] = ExtractionRecord.model_validate(value)
        else:  # altes Format ohne Herkunft (Lauf vom 10.11.)
            records[key] = ExtractionRecord(prompt_version="v1", model="claude-haiku-5-5", requirements=Requirements.model_validate(value))
    return records


def save_requirements(records: dict[str, ExtractionRecord], path: Path = REQ_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: v.model_dump(mode="json") for k, v in records.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_missing(
    postings: list[Posting],
    extractor: Extractor,
    cache: dict[str, ExtractionRecord],
    *,
    limit: int | None = None,
    force: bool = False,
    log=print,
) -> dict[str, ExtractionRecord]:
    """Für alle Postings ohne Eintrag im Cache (oder mit veralteter Prompt-Version bei --force) extrahieren."""
    todo = [p for p in postings if force or p.key not in cache]
    if limit is not None:
        todo = todo[:limit]
    model = getattr(extractor, "model", "unknown")
    for i, posting in enumerate(todo, start=1):
        try:
            cache[posting.key] = ExtractionRecord(
                prompt_version=PROMPT_VERSION, model=model, requirements=extractor.extract(posting)
            )
            log(f"[ok] {i}/{len(todo)} {posting.company}: {posting.title}")
        except Exception as exc:  # eine Anzeige soll den Lauf nicht stoppen
            log(f"[warn] {i}/{len(todo)} {posting.company}: {posting.title}: {exc}")
    return cache
