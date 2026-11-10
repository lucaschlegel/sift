"""Schritt 5: Begründete Einschätzung einer Stelle durch das Modell, mit Werkzeugaufrufen.

Ablauf pro Stelle (die klassische Werkzeug-Schleife):
  1. Wir schicken Profil, Anzeige, extrahierte Anforderungen und das Regelergebnis aus Schritt 3.
  2. Das Modell darf Werkzeuge aufrufen (ist die Anzeige noch online? was weiß ich über die Firma?).
     Wir führen sie aus und geben die Ergebnisse zurück. Das wiederholt sich, bis das Modell fertig ist.
  3. Am Ende muss es record_assessment aufrufen, ein Werkzeug, dessen Schema unser Pydantic-Modell
     Assessment ist. So bleibt auch die Begründung strukturiert.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from jobradar.extract import DEFAULT_MODEL
from jobradar.models import Match, Posting, Requirements
from jobradar.tools import TOOL_DEFINITIONS, run_tool

MAX_TOOL_ROUNDS = 6


class Assessment(BaseModel):
    verdict: Literal["apply", "maybe", "skip", "applied"]
    fit_score: float = Field(ge=0, le=1, description="0 = passt gar nicht, 1 = passt sehr gut (content fit, independent of the verdict)")
    rationale: str = Field(description="Two or three plain sentences, no marketing language")
    main_gap: str = Field(default="", description="The single biggest gap between profile and posting, or empty")
    still_live: bool | None = Field(default=None, description="Result of check_posting_live if used")


class AssessmentRecord(BaseModel):
    prompt_version: str
    model: str
    tool_calls: list[str]
    assessment: Assessment


PROMPT_VERSION = "a2"

# Reihenfolge für Tabellen und API: erst, was zu tun ist.
VERDICT_ORDER = {"apply": 0, "maybe": 1, "applied": 2, "skip": 3}

SYSTEM_PROMPT = """You are helping one specific candidate decide whether to apply to a job posting.
You get the candidate profile, the posting, the requirements extracted earlier and the result of simple rule-based filters.
You may call tools: check_posting_live to see whether the posting is still online, lookup_watchlist to read the candidate's own notes about the company (previous applications, rejections, impressions). Use lookup_watchlist for every posting; use check_posting_live when the posting is older than a few months or the rules say it fits.
Judge the actual work: a "Software Developer / Consultant" role is software engineering even if it says consultant; the candidate wants data analysis, statistics, modelling or quantitative consulting, not pure software engineering.
Posting dates from the feed are often the date the ad was first created and can be years old for evergreen postings; do not treat an old date as a reason against applying if the posting is live.
An earlier application to the same company for a different role is not a reason against applying to this one. Only an application to this same role counts as a duplicate.
Be blunt and concrete. Then call record_assessment exactly once with your final judgement.
verdict: apply = worth an application now; maybe = borderline, say what would need to be true; skip = do not apply; applied = the watchlist shows the candidate already applied to this same role, so follow up instead of applying again.
fit_score always rates the content fit between profile and role, independent of the verdict (an "applied" posting with a good fit keeps a high score)."""

RECORD_TOOL = {
    "name": "record_assessment",
    "description": "Record the final assessment of this posting for the candidate.",
    "input_schema": Assessment.model_json_schema(),
}


def build_user_message(posting: Posting, req: Requirements, match: Match, profile: dict) -> str:
    return (
        "CANDIDATE PROFILE (yaml):\n" + json.dumps(profile, ensure_ascii=False, indent=1) + "\n\n"
        f"POSTING: {posting.company} | {posting.title} | {posting.location} | {posting.employment_type} | posted {posting.posted_at}\n"
        f"URL: {posting.url}\n\n"
        "EXTRACTED REQUIREMENTS (json):\n" + req.model_dump_json(indent=1) + "\n\n"
        f"RULE-BASED RESULT: hard_filter_passed={match.hard_filter_passed}, score={match.score}, reasons={match.reasons}\n\n"
        "POSTING TEXT (truncated):\n" + posting.description_text[:6000]
    )


class AnthropicAssessor:
    def __init__(self, model: str | None = None, client=None, tool_runner=run_tool):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model or DEFAULT_MODEL
        self.tool_runner = tool_runner

    def assess(self, posting: Posting, req: Requirements, match: Match, profile: dict) -> AssessmentRecord:
        messages = [{"role": "user", "content": build_user_message(posting, req, match, profile)}]
        tools = TOOL_DEFINITIONS + [RECORD_TOOL]
        tool_calls: list[str] = []
        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.messages.create(
                model=self.model, max_tokens=1500, system=SYSTEM_PROMPT, tools=tools, messages=messages
            )
            tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
            final = next((b for b in tool_uses if b.name == "record_assessment"), None)
            if final is not None:
                return AssessmentRecord(
                    prompt_version=PROMPT_VERSION, model=self.model, tool_calls=tool_calls,
                    assessment=Assessment.model_validate(final.input),
                )
            if not tool_uses:
                break  # Modell hat nur Text geschrieben, wir zwingen unten das Ergebnis
            # Werkzeuge ausführen und Ergebnisse zurückgeben
            messages.append({"role": "assistant", "content": _serialize_content(response.content)})
            results = []
            for tu in tool_uses:
                tool_calls.append(f"{tu.name}({json.dumps(tu.input, ensure_ascii=False)})")
                out = self.tool_runner(tu.name, tu.input)
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(out, ensure_ascii=False)})
            messages.append({"role": "user", "content": results})
        # Letzte Runde: Ergebnis erzwingen
        messages.append({"role": "user", "content": "Now call record_assessment with your final judgement."})
        response = self.client.messages.create(
            model=self.model, max_tokens=800, system=SYSTEM_PROMPT, tools=tools,
            tool_choice={"type": "tool", "name": "record_assessment"}, messages=messages,
        )
        final = next(b for b in response.content if getattr(b, "type", None) == "tool_use")
        return AssessmentRecord(
            prompt_version=PROMPT_VERSION, model=self.model, tool_calls=tool_calls,
            assessment=Assessment.model_validate(final.input),
        )


def _serialize_content(blocks) -> list[dict]:
    """Antwortblöcke des Modells so zurückgeben, wie die API sie als Verlauf erwartet."""
    out = []
    for b in blocks:
        t = getattr(b, "type", None)
        if t == "text":
            out.append({"type": "text", "text": b.text})
        elif t == "tool_use":
            out.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
    return out


ASSESS_FILE = Path("data") / "assessments.json"


def load_assessments(path: Path = ASSESS_FILE) -> dict[str, AssessmentRecord]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: AssessmentRecord.model_validate(v) for k, v in raw.items()}


def save_assessments(records: dict[str, AssessmentRecord], path: Path = ASSESS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: v.model_dump(mode="json") for k, v in records.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
