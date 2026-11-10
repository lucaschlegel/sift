"""Schritt 3: Stellen gegen das eigene Profil bewerten.

Zwei Stufen, bewusst ohne Modell:
1. Harte Filter aus profile.yaml (Seniorität, Jahre, LLM-Pflicht, Befristung, Praktikum,
   Ort, Arbeitgebertyp). Wer durchfällt, bekommt den Grund gesagt.
2. Ein einfacher Score aus weichen Vorlieben (Fachrichtung, Promotion erwünscht,
   Ort klar passend, Einstiegsniveau). Regeln sind nachvollziehbar und testbar,
   das Modell kommt in Schritt 5 für die Begründung in Prosa dazu.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from jobradar.models import Match, Posting, Requirements

INTERN_RE = re.compile(r"intern|praktik|werkstud|working student|student|thesis|abschlussarbeit", re.I)


def load_profile(path: str | Path = "profile.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _contains_any(text: str, needles: list[str]) -> str | None:
    low = text.lower()
    for n in needles:
        if n.lower() in low:
            return n
    return None


def location_status(posting: Posting, req: Requirements, profile: dict) -> str:
    """'ok', 'remote', 'unclear' oder 'bad'."""
    hard = profile["hard"]
    loc_text = f"{posting.location} {req.remote_policy}"
    if _contains_any(posting.location, hard.get("locations_ok", [])):
        return "ok"
    if re.search(r"\bremote\b", req.remote_policy, re.I) and re.search(r"german|deutschland|europe", loc_text, re.I):
        return "remote"
    if _contains_any(posting.location, hard.get("locations_bad", [])):
        return "bad"
    return "unclear"


def evaluate(posting: Posting, req: Requirements, profile: dict) -> Match:
    hard = profile["hard"]
    soft = profile.get("soft", {})
    reasons: list[str] = []
    passed = True

    # --- harte Filter -------------------------------------------------------
    if INTERN_RE.search(posting.title) or INTERN_RE.search(posting.employment_type):
        passed = False
        reasons.append("Praktikum/Werkstudent, keine Festanstellung")
    if req.permanent is False:
        passed = False
        reasons.append("befristet")
    if req.seniority not in hard.get("seniority_ok", ["junior", "mid", "unclear"]):
        passed = False
        reasons.append(f"Level {req.seniority}")
    max_years = hard.get("max_years_experience")
    if max_years is not None and req.min_years_experience is not None and req.min_years_experience > max_years:
        passed = False
        reasons.append(f"verlangt {req.min_years_experience}+ Jahre")
    if hard.get("llm_experience_required") is False and req.llm_experience_required:
        passed = False
        reasons.append("LLM-Praxis ist Pflicht")
    employer_hit = _contains_any(f"{posting.company} {posting.description_text[:600]}", hard.get("exclude_employer_types", []))
    if employer_hit:
        passed = False
        reasons.append(f"Arbeitgebertyp: {employer_hit}")
    loc = location_status(posting, req, profile)
    if loc == "bad":
        passed = False
        reasons.append(f"Ort: {posting.location}")

    # --- weicher Score ------------------------------------------------------
    score = 0.5
    haystack = " ".join([posting.title, req.role_family, " ".join(req.must_haves)])
    domain_hit = _contains_any(haystack, soft.get("prefer_domains", []))
    if domain_hit:
        score += 0.15
        reasons.append(f"Fachrichtung passt ({domain_hit})")
    avoid_hit = _contains_any(haystack, soft.get("avoid", []))
    if avoid_hit:
        score -= 0.2
        reasons.append(f"eher nicht ({avoid_hit})")
    if soft.get("prefer_phd_welcome") and req.phd_mentioned:
        score += 0.1
        reasons.append("Promotion erwünscht")
    if loc == "ok":
        score += 0.1
        reasons.append("Ort passt")
    elif loc == "remote":
        score += 0.05
        reasons.append("remote möglich")
    elif loc == "unclear":
        reasons.append("Ort unklar")
    if req.seniority == "junior":
        score += 0.1
    elif req.seniority == "mid":
        score += 0.05
    if not passed:
        score = min(score, 0.2)
    score = max(0.0, min(1.0, round(score, 2)))
    return Match(posting_key=posting.key, hard_filter_passed=passed, score=score, reasons=reasons)


def evaluate_all(postings: list[Posting], reqs: dict[str, Requirements], profile: dict) -> list[Match]:
    matches = []
    for p in postings:
        req = reqs.get(p.key)
        if req is None:
            continue
        matches.append(evaluate(p, req, profile))
    return sorted(matches, key=lambda m: (m.hard_filter_passed, m.score), reverse=True)
