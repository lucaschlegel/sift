"""Kommandozeile: python -m jobradar fetch [--sources sources.yaml] [--all]

Schritt 1: Stellen von allen konfigurierten Quellen holen, als JSON speichern,
Tabelle der neuen Stellen (oder aller mit --all) ausgeben.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from jobradar.sources import build_sources
from jobradar.store import diff_new, load_previous, save_run


def print_table(postings, title: str) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:  # rich ist optional
        print(f"\n{title} ({len(postings)})")
        for p in postings:
            print(f"- {p.company:12} | {p.title:60.60} | {p.location:30.30} | {p.posted_at or ''} | {p.url}")
        return
    table = Table(title=f"{title} ({len(postings)})")
    for col in ("Firma", "Titel", "Ort", "Datum", "Art", "URL"):
        table.add_column(col, overflow="fold")
    for p in sorted(postings, key=lambda x: (x.company, x.title)):
        table.add_row(p.company, p.title, p.location, str(p.posted_at or ""), p.employment_type, p.url)
    Console().print(table)


def cmd_fetch(args: argparse.Namespace) -> int:
    config = yaml.safe_load(Path(args.sources).read_text(encoding="utf-8"))
    sources = build_sources(config.get("sources", {}))
    postings = []
    for source in sources:
        try:
            got = source.fetch()
        except Exception as exc:  # eine kaputte Quelle soll den Lauf nicht stoppen
            print(f"[warn] {source.name}: {exc}", file=sys.stderr)
            continue
        print(f"[ok] {source.name}: {len(got)} Stellen", file=sys.stderr)
        postings.extend(got)

    data_dir = Path(args.data_dir)
    previous = load_previous(data_dir)
    path = save_run(postings, data_dir)
    new = diff_new(postings, previous)
    print(f"[ok] gespeichert: {path}", file=sys.stderr)

    if args.all or not previous:
        print_table(postings, "Alle Stellen")
    else:
        print_table(new, "Neu seit letztem Lauf")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobradar")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="Stellen holen und neue anzeigen")
    fetch.add_argument("--sources", default="sources.yaml")
    fetch.add_argument("--data-dir", default="data")
    fetch.add_argument("--all", action="store_true", help="alle Stellen zeigen, nicht nur neue")
    fetch.set_defaults(func=cmd_fetch)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
