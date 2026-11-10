# jobradar

Ein kleines Werkzeug, das Karriereseiten beobachtet, neue Stellen erkennt und sie
(ab Schritt 2) mit einem Sprachmodell in ein festes Schema zieht und gegen ein Profil bewertet.
Plan und Bausteine stehen in `PLAN.md`.

## Schnellstart

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m jobradar fetch --all        # erster Lauf: alle Stellen der Quellen in sources.yaml
python -m jobradar fetch              # spätere Läufe: nur neue Stellen seit dem letzten Lauf
pytest                                # Tests mit Fixtures, ohne Netz und ohne API-Schlüssel
```

## Schritt 2: Anforderungen extrahieren (LLM)

Braucht einen API-Schlüssel von Anthropic in der Umgebung, nie im Repo:

```bash
export ANTHROPIC_API_KEY=sk-ant-...      # oder in ~/.bashrc eintragen
python -m jobradar extract --limit 5     # erst mit wenigen Anzeigen testen
python -m jobradar extract               # alle noch nicht extrahierten Anzeigen
python -m jobradar extract --company staburo --force   # eine Firma neu verarbeiten
```

So funktioniert es: Der Stellentext geht zusammen mit einem Werkzeug `record_requirements`
an das Modell. Das Eingabeschema des Werkzeugs ist das JSON-Schema des Pydantic-Modells
`Requirements` (`jobradar/models.py`). Über `tool_choice` wird das Modell gezwungen, genau dieses
Werkzeug aufzurufen, die Antwort ist also immer ein JSON-Objekt im festen Format, das Pydantic
noch einmal prüft. Ergebnisse landen in `data/requirements.json`, schon extrahierte Anzeigen werden
nicht noch einmal bezahlt. Standardmodell ist `claude-haiku-5-5` (günstig, für Extraktion
ausreichend), änderbar über `JOBRADAR_MODEL` oder `--model`.

Jeder Lauf speichert die Stellen unter `data/postings_<datum>.json`. Neue Firmen kommen in
`sources.yaml`, das eigene Profil steht in `profile.yaml`.

## Schritt 3: Bewerten

```bash
python -m jobradar match          # Stellen, die die harten Filter bestehen, nach Score sortiert
python -m jobradar match --all    # alle, mit Grund für das Ausscheiden
```

Harte Filter kommen aus `profile.yaml` (Praktikum, befristet, Level, Mindestjahre, LLM-Pflicht,
Arbeitgebertyp, Ort). Der Score ist eine einfache Summe aus Fachrichtung, Promotion erwünscht,
Ort und Einstiegsniveau. Alles regelbasiert und in `tests/test_match.py` geprüft, damit man
später messen kann, ob ein Modell es besser macht.

Die Extraktion speichert jetzt auch Prompt-Version und Modell zu jedem Ergebnis
(`data/requirements.json`). Nach einer Prompt-Änderung `PROMPT_VERSION` in `jobradar/extract.py`
hochzählen und mit `extract --force` neu laufen lassen, dann lassen sich Varianten vergleichen.

## Stand

- [x] Schritt 1: Quellen Lever und Personio, Speichern, Abgleich neu/alt, Tabelle
- [ ] Schritt 1b: SuccessFactors, Workday, Avature, Jobbörse
- [x] Schritt 2: Extraktion mit LLM (schema-constrained über tool use)
- [x] Schritt 3: Bewertung gegen `profile.yaml` (harte Filter plus Score, ohne Modell)
- [ ] Schritt 4: Evaluation gegen `data/labels.csv`
- [ ] Schritt 5: Werkzeugaufrufe (Live-Check, Watchlist)
- [ ] Schritt 6: FastAPI, Docker
