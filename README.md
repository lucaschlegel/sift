# jobradar

A small tool that watches company career pages, extracts the requirements of each posting with an LLM into a fixed schema, and scores postings against a personal profile. Built as a portfolio project to practise LLM application work: API calls, schema-constrained outputs, caching, rule-based matching and a labelled evaluation set.

*Deutsche Kurzfassung unten.*

## What it does

1. **Fetch** postings from public career feeds (Lever, Personio) and store each run as JSON. New postings since the last run are listed.
2. **Extract** structured requirements per posting with Claude (`claude-haiku-5-5`): role, seniority, minimum years, PhD mentioned, LLM experience required, languages, remote policy, contract type. The model is forced to call a tool whose input schema is the JSON schema of a Pydantic model, so the output is always valid structured data. Results are cached with prompt version and model.
3. **Match** postings against `profile.yaml`: hard filters (internship, fixed-term, seniority, years, LLM requirement, location) and a simple score.
4. **Evaluate** extraction and matching against `data/labels.csv`, a hand-labelled set of postings.

## Results (prompt v2, 15 labelled postings)

| Field | Accuracy |
| --- | --- |
| minimum years of experience | 100 % (14/14) |
| LLM experience required | 100 % (10/10) |
| PhD mentioned | 100 % (10/10) |
| seniority | 69 % (9/13) |

Postings I judged as a fit pass the hard filter 2/2; postings I judged as no fit fail it 10/13.
Prompt v1 misread "(Senior)" in a title as senior, took "founded by four PhDs" for a PhD requirement and missed LLM requirements phrased as "frontier lab APIs"; v2 fixes all three.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                  # fixtures only, no network, no API key
python -m jobradar fetch --all          # first run: all postings from sources.yaml
export ANTHROPIC_API_KEY=sk-ant-...
python -m jobradar extract              # a few cents for ~40 postings
python -m jobradar match
python -m jobradar evaluate
```

Roadmap: more sources (SuccessFactors, Workday, Greenhouse, Arbeitsagentur), tool calls (live check whether a posting is still open), a short LLM-written rationale per match, FastAPI endpoint and Dockerfile.

---

## Kurzfassung

Ein kleines Werkzeug, das Karriereseiten beobachtet, die Anforderungen jeder Stelle mit einem Sprachmodell in ein festes Schema zieht und gegen ein eigenes Profil bewertet. Entstanden als Portfolio-Projekt, um Anwendungsentwicklung mit LLMs zu üben: API-Aufrufe, strukturierte Ausgaben über erzwungene Werkzeugaufrufe, Caching, regelbasierte Bewertung und eine Messung gegen von Hand gesetzte Labels.

Befehle: `fetch` (Stellen holen, neue anzeigen), `extract` (Anforderungen per Claude extrahieren, Schema aus Pydantic), `match` (harte Filter und Score aus `profile.yaml`), `evaluate` (Trefferquote pro Feld gegen `data/labels.csv`). Stand Prompt v2: Jahre, LLM-Pflicht und Promotion je 100 Prozent, Level 69 Prozent auf 15 Labels. Plan für die nächsten Schritte in `PLAN.md`.
