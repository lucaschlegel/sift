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
pytest                                # Tests mit Fixtures, ohne Netz
```

Jeder Lauf speichert die Stellen unter `data/postings_<datum>.json`. Neue Firmen kommen in
`sources.yaml`, das eigene Profil steht in `profile.yaml`.

## Stand

- [x] Schritt 1: Quellen Lever und Personio, Speichern, Abgleich neu/alt, Tabelle
- [ ] Schritt 1b: SuccessFactors, Workday, Avature, Jobbörse
- [ ] Schritt 2: Extraktion mit LLM (schema-constrained)
- [ ] Schritt 3: Bewertung gegen `profile.yaml`
- [ ] Schritt 4: Evaluation gegen `data/labels.csv`
- [ ] Schritt 5: Werkzeugaufrufe (Live-Check, Watchlist)
- [ ] Schritt 6: FastAPI, Docker
