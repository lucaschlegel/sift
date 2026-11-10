# sift

A small end-to-end LLM application in Python: pull texts from public APIs, extract structured data from them with a language model into a fixed schema, filter the results with configurable rules, let the model verify its own judgement through tool calls, and measure extraction accuracy against a hand-labelled set. Read-only FastAPI on top.

The example data are job postings from public career-page feeds (Lever, Personio); the pipeline itself does not care what the texts are about.

*Deutsche Kurzfassung unten.*

## Pipeline

1. **Fetch** texts from public feeds and store each run as JSON; new items since the last run are listed.
2. **Extract** structured fields per text with Claude (`claude-haiku-5-5` by default): the model is forced to call a tool whose input schema is the JSON schema of a Pydantic model, so the output is always valid structured data (schema-constrained tool use). Results are cached together with prompt version and model.
3. **Match** the extracted fields against `profile.yaml`: hard filters and a simple score.
4. **Evaluate** the extraction against `data/labels.csv`, a hand-labelled set, field by field.
5. **Assess** the items that pass the filter: the model gets the text, the extracted fields and the rule result, may call tools (`check_posting_live`, `lookup_watchlist` over notes in `watchlist.yaml`) in a plain tool-use loop, and must finish with a structured verdict (apply / maybe / skip / applied, fit score, rationale, main gap).
6. **Serve** everything read-only with FastAPI (`/postings`, `/matches`, `/assessments`); `run` chains fetch, extract and assess for a cron job; Dockerfile included.

## Results (15 labelled texts, `claude-haiku-5-5`)

| Field | prompt v2 | prompt v3 |
| --- | --- | --- |
| minimum years of experience | 100 % (14/14) | 100 % (14/14) |
| LLM experience required | 100 % (10/10) | 100 % (10/10) |
| PhD mentioned | 100 % (10/10) | 100 % (10/10) |
| seniority | 69 % (9/13) | 85 % (11/13) |

Prompt v1 misread "(Senior)" in a title as senior, took "founded by four PhDs" for a PhD requirement and missed LLM requirements phrased as "frontier lab APIs". v2 fixed all three but lost two seniority calls. v3 orders the seniority rules explicitly (title word first, then text, else unclear) and gets both back.
The two remaining v3 "errors" turned out to be label errors: on re-reading, "first experience, e.g. internships" is junior and "degree or PhD" with no level statement is unclear. With the corrected labels v3 is 13/13 on seniority and v2 11/13. Lesson: check the labels before the prompt.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp profile.example.yaml profile.yaml       # your criteria; git-ignored
cp watchlist.example.yaml watchlist.yaml   # your notes; git-ignored
pytest                                     # fixtures only, no network, no API key
python -m sift fetch --all                 # first run: all items from sources.yaml
export ANTHROPIC_API_KEY=sk-ant-...
python -m sift extract                     # a few cents for ~40 texts
python -m sift match
python -m sift evaluate
python -m sift assess --top 5              # tool-use loop, a few cents
python -m sift serve                       # http://127.0.0.1:8000/docs
python -m sift run                         # fetch + extract + assess, for cron
```

Roadmap: more sources (SuccessFactors, Workday, Greenhouse), more labels (target 30), a second model in the results table, cron on a small VM.

---

## Kurzfassung

Eine kleine LLM-Anwendung von Anfang bis Ende: Texte aus öffentlichen APIs holen, mit einem Sprachmodell in ein festes Schema ziehen (erzwungener Werkzeugaufruf, Schema aus Pydantic), regelbasiert filtern, das Modell seine Einschätzung mit eigenen Werkzeugaufrufen prüfen lassen und die Extraktion gegen von Hand gesetzte Labels messen. Beispieldaten sind Stellenanzeigen aus öffentlichen Karriere-Feeds.

Befehle: `fetch`, `extract`, `match`, `evaluate`, `assess`, `serve`, `run`. Stand Prompt v3: Jahre, LLM-Pflicht und Promotion je 100 Prozent, Level 85 Prozent auf 15 Labels (100 Prozent nach Korrektur zweier falscher Labels).
