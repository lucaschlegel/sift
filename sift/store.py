"""Speichern der Läufe als JSON und Abgleich 'neu seit letztem Lauf'."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jobradar.models import Posting

DATA_DIR = Path("data")


def save_run(postings: list[Posting], data_dir: Path = DATA_DIR) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = data_dir / f"postings_{stamp}.json"
    path.write_text(
        json.dumps([p.model_dump(mode="json") for p in postings], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_previous(data_dir: Path = DATA_DIR, before: Path | None = None) -> list[Posting]:
    """Den jüngsten gespeicherten Lauf laden (optional: den jüngsten vor `before`)."""
    files = sorted(data_dir.glob("postings_*.json"))
    if before is not None:
        files = [f for f in files if f != before]
    if not files:
        return []
    raw = json.loads(files[-1].read_text(encoding="utf-8"))
    return [Posting.model_validate(item) for item in raw]


def diff_new(current: list[Posting], previous: list[Posting]) -> list[Posting]:
    seen = {p.key for p in previous}
    return [p for p in current if p.key not in seen]
