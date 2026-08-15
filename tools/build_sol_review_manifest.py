#!/usr/bin/env python3
"""Build an immutable Sol review manifest, prioritizing deterministic failures."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import translate_vocab_content as drafts


ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "data" / "terra_english_drafts"
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"
OUTPUT = ROOT / "data" / "sol_review_manifest.txt"


def main() -> int:
    if OUTPUT.exists():
        print(f"manifest_preserved={OUTPUT}")
        return 0
    db = sqlite3.connect(SOURCE_DB)
    db.row_factory = sqlite3.Row
    rows: list[tuple[int, int, str, str, str]] = []
    seen: set[str] = set()
    for path in sorted(DRAFT_DIR.glob("*.txt")):
        entries, parse_errors = drafts.parse_draft(path)
        if parse_errors:
            raise SystemExit(f"{path.name}: {parse_errors[0]}")
        for headword, sentences in entries.items():
            if headword in seen:
                raise SystemExit(f"duplicate canonical headword: {headword}")
            seen.add(headword)
            errors, _ = drafts.validate_entry(db, headword, sentences)
            source_rank = db.execute(
                "SELECT source_rank FROM words WHERE lower(headword)=?", (headword,)
            ).fetchone()[0]
            rows.append((0 if errors else 1, source_rank, headword, path.name, " | ".join(errors)))
    db.close()
    rows.sort(key=lambda row: (row[0], row[1]))
    lines = ["# seq\tpriority\tsource_rank\theadword\tsource_file\tdeterministic_errors"]
    for sequence, (priority, rank, headword, source_file, errors) in enumerate(rows, 1):
        lines.append(
            "\t".join(
                (str(sequence), "failed" if priority == 0 else "audit", str(rank), headword, source_file, errors)
            )
        )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    failed = sum(1 for row in rows if row[0] == 0)
    print(f"review_words={len(rows)} failed_priority={failed} audit_priority={len(rows)-failed} output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
