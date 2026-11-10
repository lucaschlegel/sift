# Job-Radar – Projektplan

Ein kleines Werkzeug, das Karriereseiten beobachtet, neue Stellen erkennt, ihre Anforderungen mit einem Sprachmodell in ein festes Schema zieht und gegen mein Profil bewertet. Nebenbei das Portfolio-Projekt, mit dem ich belegen kann, dass ich Anwendungen auf LLMs bauen kann (API-Aufrufe, strukturierte Ausgaben, Werkzeugaufrufe, systematische Bewertung, kleiner Service).

## Ziel in einem Satz

Alle paar Tage eine Tabelle: welche Stellen sind neu, wie gut passen sie, warum, und für die guten ein Entwurf des Anschreibens in meinem Stil.

## Bausteine (jeder Schritt läuft für sich und ist auf GitHub nachvollziehbar)

1. **Quellen (ohne LLM, ohne API-Schlüssel).** Stellen von Karriereseiten einsammeln. Zuerst die Portale mit sauberen Feeds, weil sie stabil sind und niemanden stören:
   - Lever (QuantCo): `https://api.lever.co/v0/postings/<firma>?mode=json`
   - Personio (Staburo, Coriolis, TNG, appliedAI): `https://<firma>.jobs.personio.com/xml` oder `.../search.json`
   - Greenhouse (Celonis, Scopely): `https://boards-api.greenhouse.io/v1/boards/<firma>/jobs?content=true`
   - SmartRecruiters (Bosch, Eurofins): `https://api.smartrecruiters.com/v1/companies/<firma>/postings`
   - SuccessFactors (SAP, Munich Re, TÜV SÜD, BestSecret, Campari), Workday (LEGO, AstraZeneca), Avature (Siemens), Jobbörse der Arbeitsagentur: später, brauchen HTML-Parsing oder einen Browser.
   Ergebnis: eine Liste von `Posting`-Objekten (Firma, Titel, Ort, URL, Datum, Volltext), gespeichert als JSON. Neue Stellen erkennt man am Abgleich mit dem letzten Lauf.

2. **Extraktion mit dem Modell.** Jeder Volltext geht mit einem Prompt und einem Pydantic-Schema an die API (Anthropic oder OpenAI, alternativ ein lokales Modell über Ollama). Zurück kommt JSON mit festen Feldern: Rolle, Seniorität, Jahre Erfahrung min, Promotion erwünscht ja/nein, LLM-Praxis Pflicht ja/nein, Sprachen, Remote-Regel, Befristung, Gehaltsangabe, Kernanforderungen als Liste. Hier lernt man „structured outputs" und wie man Prompts systematisch verbessert.

3. **Bewertung gegen das Profil.** `profile.yaml` enthält meine harten Kriterien (unbefristet, Vollzeit, München hybrid oder remote Deutschland, kein Forschungsinstitut, keine LLM-Pflicht, Seniorität Junior bis Mid) und weichen Vorlieben (Bio/Pharma, Statistik, Beratung, Trainee mit Festvertrag). Regeln filtern, das Modell begründet in zwei Sätzen. Ausgabe: Tabelle mit Score und Begründung.

4. **Messen.** Die 13 bisherigen Bewerbungen plus die Stellen, die wir bewusst verworfen haben, sind der Testdatensatz mit bekanntem Ausgang. Ein Skript lässt alle durch Schritt 2 und 3 laufen und misst: Wie oft trifft die Extraktion die von Hand gesetzten Felder (Jahre, LLM-Pflicht, Seniorität)? Rangiert die Bewertung die passenden Stellen oben? Zwei Prompt-Varianten vergleichen. Das ist der Teil, der im Lebenslauf zählt („systematic evaluation").

5. **Werkzeugaufruf.** Das Modell darf selbst Werkzeuge nutzen: Posting live nachladen (ist die Stelle noch online?), Firma im Watchlist-Notizbuch nachschlagen, Excel-Zeile vorbereiten. Damit ist „tool use / agentic" abgedeckt, ohne dass es ein Agentenframework braucht.

6. **Service.** Ein `run`-Befehl für den Cronjob, eine kleine FastAPI mit zwei Endpunkten (`/postings`, `/matches`), ein Dockerfile, pytest mit Fixtures, README mit den Messergebnissen als Tabelle.

## Reihenfolge und Aufwand

| Schritt | Ergebnis | Aufwand |
| --- | --- | --- |
| 1 | `python -m jobradar fetch` liefert Tabelle aller Stellen von Lever- und Personio-Quellen | 1 Abend (Gerüst liegt vor) |
| 2 | `python -m jobradar extract` füllt das Schema per LLM | 1 Wochenende |
| 3 | `python -m jobradar match` bewertet gegen `profile.yaml` | 1 Tag |
| 4 | `python -m jobradar evaluate` misst gegen `data/labels.csv` | 1 Wochenende |
| 5 | Werkzeuge (Live-Check, Watchlist) | 1 Tag |
| 6 | FastAPI, Docker, Tests, README | 1 Wochenende |

## Technik

- Python 3.11+, `requests`, `pydantic`, `pyyaml`, `rich` (Tabellen im Terminal), später `anthropic` oder `openai`, `fastapi`, `uvicorn`, `pytest`.
- Kein Scraping hinter Logins, keine Umgehung von Schutzmechanismen, nur öffentliche Feeds und Seiten, mit höflichem Abstand zwischen Anfragen und einem ehrlichen User-Agent.
- API-Schlüssel nur über Umgebungsvariable (`ANTHROPIC_API_KEY`), nie im Repo. Kosten für das ganze Projekt im einstelligen Euro-Bereich.
- Daten liegen unter `data/` als JSON, versioniert mit Datum, damit „neu seit letztem Lauf" funktioniert.

## Lebenslauf-Zeile, auf die wir hinarbeiten

„Built a job-market radar that collects postings from company career APIs, extracts structured requirements with an LLM (schema-constrained outputs, tool calls), scores them against a profile and is evaluated against a labelled set of real applications (Python, Pydantic, Anthropic API, FastAPI, Docker)."
