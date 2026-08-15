#!/usr/bin/env python3
"""Validate one Terra batch against its immutable manifest assignment."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import translate_vocab_content as drafts


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"
MANIFEST = ROOT / "data" / "terra_missing_manifest.txt"
CANONICAL = ROOT / "data" / "terra_english_drafts"


def assigned_words(start: int, end: int) -> set[str]:
    assigned: set[str] = set()
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        sequence = int(fields[0])
        if start <= sequence <= end:
            assigned.add(fields[3].casefold())
    return assigned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--seq-start", type=int, required=True)
    parser.add_argument("--seq-end", type=int, required=True)
    args = parser.parse_args()
    expected = assigned_words(args.seq_start, args.seq_end)
    entries, errors = drafts.parse_draft(args.path)
    actual = set(entries)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            errors.append(f"missing assigned headwords: {', '.join(missing)}")
        if extra:
            errors.append(f"unassigned headwords: {', '.join(extra)}")

    for other in CANONICAL.glob("*.txt"):
        if other.resolve() == args.path.resolve():
            continue
        other_entries, other_errors = drafts.parse_draft(other)
        errors.extend(f"{other.name}: {error}" for error in other_errors)
        overlap = actual & set(other_entries)
        if overlap:
            errors.append(f"duplicates existing TXT: {', '.join(sorted(overlap))}")

    db = sqlite3.connect(SOURCE_DB)
    db.row_factory = sqlite3.Row
    for headword, rows in entries.items():
        validation, _ = drafts.validate_entry(db, headword, rows)
        errors.extend(f"{headword}: {error}" for error in validation)
    db.close()

    for error in errors:
        print(error, file=sys.stderr)
    print(
        f"file={args.path} assigned={len(expected)} words={len(entries)} "
        f"sentences={sum(map(len, entries.values()))} errors={len(errors)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
