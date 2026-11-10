"""Schritt 4: Messen, wie gut Extraktion und Bewertung treffen.

Grundlage ist data/labels.csv, von Hand gesetzte Wahrheiten für einzelne Anzeigen:
    posting_key, seniority, min_years, llm_required, phd_mentioned, fit, note
Leere Zellen heißen "nicht gelabelt", sie werden für dieses Feld nicht gewertet.
`fit` ist das eigene Urteil (yes/no), ob die Stelle für mich in Frage kommt.

Gemessen wird pro Feld die Trefferquote der Extraktion gegen die Labels und für die
Bewertung, ob Stellen mit fit=yes den harten Filter bestehen und ob fit=no durchfällt.
Mit --requirements lassen sich verschiedene Extraktionsläufe (Prompt-Versionen) vergleichen.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from sift.extract import ExtractionRecord
from sift.match import evaluate
from sift.models import Posting

LABELS_FILE = Path("data") / "labels.csv"
FIELDS = ("seniority", "min_years", "llm_required", "phd_mentioned")


@dataclass
class Label:
    posting_key: str
    seniority: str | None
    min_years: int | None
    llm_required: bool | None
    phd_mentioned: bool | None
    fit: bool | None
    note: str = ""


def _parse_bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v in ("", "?"):
        return None
    return v in ("1", "true", "yes", "ja", "y")


def _parse_int(value: str) -> int | None:
    v = value.strip()
    if v in ("", "?"):
        return None
    if v.lower() in ("none", "null", "-"):
        return 0  # "keine Jahresangabe" wird als 0 gelabelt, siehe compare()
    return int(v)


def load_labels(path: Path = LABELS_FILE) -> list[Label]:
    if not path.exists():
        return []
    labels = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("posting_key"):
                continue
            labels.append(
                Label(
                    posting_key=row["posting_key"].strip(),
                    seniority=(row.get("seniority") or "").strip() or None,
                    min_years=_parse_int(row.get("min_years") or ""),
                    llm_required=_parse_bool(row.get("llm_required") or ""),
                    phd_mentioned=_parse_bool(row.get("phd_mentioned") or ""),
                    fit=_parse_bool(row.get("fit") or ""),
                    note=(row.get("note") or "").strip(),
                )
            )
    return labels


@dataclass
class FieldScore:
    correct: int = 0
    total: int = 0
    misses: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float | None:
        return None if self.total == 0 else self.correct / self.total


@dataclass
class Report:
    fields: dict[str, FieldScore]
    fit_yes_passed: int = 0
    fit_yes_total: int = 0
    fit_no_failed: int = 0
    fit_no_total: int = 0
    unlabeled_missing: list[str] = field(default_factory=list)


def compare(label: Label, record: ExtractionRecord) -> dict[str, tuple[bool, str]]:
    """Pro gelabeltem Feld: (richtig?, Beschreibung des Fehlers)."""
    r = record.requirements
    out = {}
    if label.seniority is not None:
        out["seniority"] = (r.seniority == label.seniority, f"seniority {r.seniority} statt {label.seniority}")
    if label.min_years is not None:
        got = r.min_years_experience or 0
        out["min_years"] = (got == label.min_years, f"min_years {got} statt {label.min_years}")
    if label.llm_required is not None:
        out["llm_required"] = (r.llm_experience_required == label.llm_required, f"llm {r.llm_experience_required} statt {label.llm_required}")
    if label.phd_mentioned is not None:
        out["phd_mentioned"] = (r.phd_mentioned == label.phd_mentioned, f"phd {r.phd_mentioned} statt {label.phd_mentioned}")
    return out


def run(labels: list[Label], postings: list[Posting], records: dict[str, ExtractionRecord], profile: dict) -> Report:
    by_key = {p.key: p for p in postings}
    report = Report(fields={f: FieldScore() for f in FIELDS})
    for label in labels:
        record = records.get(label.posting_key)
        posting = by_key.get(label.posting_key)
        if record is None or posting is None:
            report.unlabeled_missing.append(label.posting_key)
            continue
        for name, (ok, msg) in compare(label, record).items():
            fs = report.fields[name]
            fs.total += 1
            if ok:
                fs.correct += 1
            else:
                fs.misses.append(f"{posting.company} / {posting.title}: {msg}")
        if label.fit is not None:
            m = evaluate(posting, record.requirements, profile)
            if label.fit:
                report.fit_yes_total += 1
                report.fit_yes_passed += int(m.hard_filter_passed)
            else:
                report.fit_no_total += 1
                report.fit_no_failed += int(not m.hard_filter_passed)
    return report


def format_report(report: Report, title: str = "Evaluation") -> str:
    lines = [title, "=" * len(title)]
    for name, fs in report.fields.items():
        acc = "n/a" if fs.accuracy is None else f"{fs.accuracy:.0%} ({fs.correct}/{fs.total})"
        lines.append(f"{name:14} {acc}")
        for miss in fs.misses:
            lines.append(f"    - {miss}")
    if report.fit_yes_total or report.fit_no_total:
        lines.append("")
        lines.append(f"fit=yes bestehen Filter: {report.fit_yes_passed}/{report.fit_yes_total}")
        lines.append(f"fit=no  fallen durch:     {report.fit_no_failed}/{report.fit_no_total}")
    if report.unlabeled_missing:
        lines.append("")
        lines.append(f"ohne Extraktion oder Posting: {len(report.unlabeled_missing)} Labels")
        for k in report.unlabeled_missing:
            lines.append(f"    - {k}")
    return "\n".join(lines)
