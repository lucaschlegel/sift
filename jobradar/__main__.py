"""Kommandozeile.

  python -m jobradar fetch [--all]          Schritt 1: Stellen holen, speichern, neue zeigen
  python -m jobradar extract [--limit N]    Schritt 2: Anforderungen per Modell extrahieren
  python -m jobradar match [--all]          Schritt 3: gegen profile.yaml bewerten
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from jobradar.extract import AnthropicExtractor, extract_missing, load_requirements, save_requirements
from jobradar.match import evaluate_all, load_profile
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


def print_requirements(postings, reqs) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        for p in postings:
            rec = reqs.get(p.key)
            if rec:
                r = rec.requirements
                print(f"- {p.company} | {p.title} | {r.seniority} | years>={r.min_years_experience} | LLM={r.llm_experience_required} | {r.remote_policy}")
        return
    table = Table(title=f"Extrahierte Anforderungen ({sum(1 for p in postings if p.key in reqs)})")
    for col in ("Firma", "Titel", "Rolle", "Level", "Jahre", "LLM", "PhD", "Remote", "Sprachen"):
        table.add_column(col, overflow="fold")
    for p in sorted(postings, key=lambda x: (x.company, x.title)):
        rec = reqs.get(p.key)
        if not rec:
            continue
        r = rec.requirements
        table.add_row(
            p.company, p.title, r.role_family, r.seniority,
            "" if r.min_years_experience is None else str(r.min_years_experience),
            "ja" if r.llm_experience_required else "nein",
            "ja" if r.phd_mentioned else "nein",
            r.remote_policy, ", ".join(r.languages),
        )
    Console().print(table)


def cmd_extract(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    postings = load_previous(data_dir)
    if not postings:
        print("[warn] keine gespeicherten Stellen, erst `python -m jobradar fetch` laufen lassen", file=sys.stderr)
        return 1
    if args.company:
        postings = [p for p in postings if args.company.lower() in p.company.lower()]
    cache = load_requirements(data_dir / "requirements.json")
    extractor = AnthropicExtractor(model=args.model)
    cache = extract_missing(
        postings, extractor, cache, limit=args.limit, force=args.force,
        log=lambda m: print(m, file=sys.stderr),
    )
    save_requirements(cache, data_dir / "requirements.json")
    print_requirements(postings, cache)
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    postings = load_previous(data_dir)
    records = load_requirements(data_dir / "requirements.json")
    reqs = {k: v.requirements for k, v in records.items()}
    profile = load_profile(args.profile)
    matches = evaluate_all(postings, reqs, profile)
    by_key = {p.key: p for p in postings}
    rows = [m for m in matches if args.all or m.hard_filter_passed]
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        for m in rows:
            p = by_key[m.posting_key]
            print(f"{m.score:.2f} {'ok ' if m.hard_filter_passed else 'raus'} {p.company} | {p.title} | {'; '.join(m.reasons)}")
        return 0
    table = Table(title=f"Bewertung ({len(rows)} von {len(matches)})")
    for col in ("Score", "Filter", "Firma", "Titel", "Gründe", "URL"):
        table.add_column(col, overflow="fold")
    for m in rows:
        p = by_key[m.posting_key]
        table.add_row(f"{m.score:.2f}", "ok" if m.hard_filter_passed else "raus", p.company, p.title, "; ".join(m.reasons), p.url)
    Console().print(table)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobradar")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch", help="Stellen holen und neue anzeigen")
    fetch.add_argument("--sources", default="sources.yaml")
    fetch.add_argument("--data-dir", default="data")
    fetch.add_argument("--all", action="store_true", help="alle Stellen zeigen, nicht nur neue")
    fetch.set_defaults(func=cmd_fetch)
    extract = sub.add_parser("extract", help="Anforderungen per Modell extrahieren (braucht ANTHROPIC_API_KEY)")
    extract.add_argument("--data-dir", default="data")
    extract.add_argument("--limit", type=int, default=None, help="höchstens N neue Anzeigen verarbeiten")
    extract.add_argument("--company", default=None, help="nur Anzeigen dieser Firma")
    extract.add_argument("--force", action="store_true", help="auch schon extrahierte Anzeigen neu verarbeiten")
    extract.add_argument("--model", default=None, help="Modellname, Standard aus JOBRADAR_MODEL oder claude-haiku-5-5")
    extract.set_defaults(func=cmd_extract)
    match = sub.add_parser("match", help="Stellen gegen profile.yaml bewerten")
    match.add_argument("--data-dir", default="data")
    match.add_argument("--profile", default="profile.yaml")
    match.add_argument("--all", action="store_true", help="auch Stellen zeigen, die am harten Filter scheitern")
    match.set_defaults(func=cmd_match)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
