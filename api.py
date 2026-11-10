"""Schritt 6: kleiner Lesedienst über die gespeicherten Ergebnisse.

    python -m jobradar serve            # http://127.0.0.1:8000/docs zeigt die Endpunkte
    GET /postings                       # letzter Lauf
    GET /matches?passed_only=true       # Regelbewertung
    GET /assessments                    # Einschätzungen des Modells

Der Dienst ruft kein Modell auf, er liest nur `data/`. Rechnen tut der Cronjob (`python -m jobradar run`).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

from jobradar.assess import VERDICT_ORDER, load_assessments
from jobradar.extract import load_requirements
from jobradar.match import evaluate_all, load_profile
from jobradar.store import load_previous

DATA_DIR = Path(os.environ.get("JOBRADAR_DATA_DIR", "data"))
PROFILE = os.environ.get("JOBRADAR_PROFILE", "profile.yaml")

app = FastAPI(title="jobradar", version="0.1", description="Stellen, extrahierte Anforderungen, Bewertungen.")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "runs": len(list(DATA_DIR.glob("postings_*.json")))}


@app.get("/postings")
def postings() -> list[dict]:
    return [p.model_dump(mode="json", exclude={"description_text"}) for p in load_previous(DATA_DIR)]


@app.get("/postings/{key:path}")
def posting(key: str) -> dict:
    for p in load_previous(DATA_DIR):
        if p.key == key:
            data = p.model_dump(mode="json")
            rec = load_requirements(DATA_DIR / "requirements.json").get(key)
            data["requirements"] = rec.model_dump(mode="json") if rec else None
            return data
    raise HTTPException(status_code=404, detail="unknown posting key")


@app.get("/matches")
def matches(passed_only: bool = True) -> list[dict]:
    posts = load_previous(DATA_DIR)
    reqs = {k: v.requirements for k, v in load_requirements(DATA_DIR / "requirements.json").items()}
    by_key = {p.key: p for p in posts}
    out = []
    for m in evaluate_all(posts, reqs, load_profile(PROFILE)):
        if passed_only and not m.hard_filter_passed:
            continue
        p = by_key[m.posting_key]
        out.append({**m.model_dump(mode="json"), "company": p.company, "title": p.title, "url": p.url})
    return out


@app.get("/assessments")
def assessments() -> list[dict]:
    posts = {p.key: p for p in load_previous(DATA_DIR)}
    out = []
    for key, rec in load_assessments(DATA_DIR / "assessments.json").items():
        p = posts.get(key)
        out.append({"posting_key": key, "company": p.company if p else None, "title": p.title if p else None,
                    "url": p.url if p else None, **rec.model_dump(mode="json")})
    return sorted(out, key=lambda r: (VERDICT_ORDER[r["assessment"]["verdict"]], -r["assessment"]["fit_score"]))
