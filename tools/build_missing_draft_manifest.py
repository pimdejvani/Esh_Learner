#!/usr/bin/env python3
"""Write the immutable list of source words missing from canonical TXT drafts."""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

import translate_vocab_content as drafts


ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "data" / "terra_english_drafts"
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"
OUTPUT = ROOT / "data" / "terra_missing_manifest.txt"


def main() -> int:
    occurrences: Counter[str] = Counter()
    structurally_complete: set[str] = set()
    parse_errors: list[str] = []
    for path in sorted(DRAFT_DIR.glob("*.txt")):
        entries, errors = drafts.parse_draft(path)
        occurrences.update(entries.keys())
        structurally_complete.update(
            headword
            for headword, rows in entries.items()
            if len(rows) == 5 and sorted(row.rank for row in rows) == [1, 2, 3, 4, 5]
        )
        parse_errors.extend(f"{path.name}: {error}" for error in errors)
    duplicates = sorted(word for word, count in occurrences.items() if count > 1)
    if parse_errors or duplicates:
        for error in parse_errors:
            print(error, file=sys.stderr)
        if duplicates:
            print(f"duplicate headwords: {', '.join(duplicates[:50])}", file=sys.stderr)
        return 1

    if OUTPUT.exists():
        assigned = []
        for line in OUTPUT.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                assigned.append(line.split("\t")[3].casefold())
        remaining = [headword for headword in assigned if headword not in structurally_complete]
        print(
            f"canonical={len(occurrences)} assigned_total={len(assigned)} "
            f"completed={len(assigned) - len(remaining)} remaining={len(remaining)} "
            f"duplicates=0 parse_errors=0 manifest_preserved={OUTPUT}"
        )
        return 0

    db = sqlite3.connect(SOURCE_DB)
    db.row_factory = sqlite3.Row
    missing = [
        row
        for row in db.execute(
            """SELECT w.id,w.source_rank,w.headword,w.cefr_first,
                      (SELECT s.id FROM source_senses s WHERE s.word_id=w.id ORDER BY s.id LIMIT 1) primary_sense_id,
                      (SELECT s.pos FROM source_senses s WHERE s.word_id=w.id ORDER BY s.id LIMIT 1) primary_pos
               FROM words w
               WHERE EXISTS(SELECT 1 FROM source_senses s WHERE s.word_id=w.id)
               ORDER BY w.source_rank"""
        )
        if row["headword"].casefold() not in occurrences
    ]
    db.close()

    lines = [
        "# seq\tsource_rank\tword_id\theadword\tcefr\tprimary_sense_id\tprimary_pos"
    ]
    lines.extend(
        "\t".join(
            map(
                str,
                (
                    sequence, row["source_rank"], row["id"], row["headword"],
                    row["cefr_first"], row["primary_sense_id"], row["primary_pos"],
                ),
            )
        )
        for sequence, row in enumerate(missing, 1)
    )
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"canonical={len(occurrences)} missing={len(missing)} "
        f"duplicates=0 parse_errors=0 output={OUTPUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
