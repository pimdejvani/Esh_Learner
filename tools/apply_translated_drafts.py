#!/usr/bin/env python3
"""Apply validated translated drafts to an existing content database.

This intentionally updates only ``example_sentences``.  It is used to prove
translation quality in a disposable test DB before exporting a production DB.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import build_content_db
import import_terra_compact as compact


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "content_test_v2.db"
DEFAULT_DRAFT_DIR = ROOT / "data" / "terra_test_translated_deepl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--draft-dir", type=Path, default=DEFAULT_DRAFT_DIR)
    parser.add_argument("--headwords", default="")
    parser.add_argument("--source-label", default="translated-test")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    selected = {value.strip().casefold() for value in args.headwords.split(",") if value.strip()}
    entries: dict[str, list[dict]] = {}
    errors: list[str] = []
    for path in sorted(args.draft_dir.glob("*.txt")):
        parsed, parse_errors = compact.parse_file(path)
        errors.extend(parse_errors)
        for headword, sentences in parsed.items():
            if not selected or headword in selected:
                entries[headword] = sentences

    if selected:
        missing = selected - set(entries)
        errors.extend(f"missing translated draft: {headword}" for headword in sorted(missing))
    if not entries:
        errors.append("no translated drafts selected")
    if not args.db.exists():
        errors.append(f"database does not exist: {args.db}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    applied = skipped = 0
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("BEGIN")
        for headword, sentences in entries.items():
            word = db.execute(
                "SELECT id FROM words WHERE lower(headword)=?", (headword,)
            ).fetchone()
            if word is None:
                skipped += 1
                continue
            if len(sentences) != 5 or sorted(row["rank"] for row in sentences) != [1, 2, 3, 4, 5]:
                errors.append(f"{headword}: expected ranks 1..5")
                continue

            prepared: list[tuple] = []
            for sentence in sentences:
                sense = db.execute(
                    "SELECT id FROM senses WHERE word_id=? AND source_sense_id=?",
                    (word["id"], sentence["sense_id"]),
                ).fetchone()
                if sense is None:
                    errors.append(
                        f"{headword} rank {sentence['rank']}: source sense is not in content DB"
                    )
                    continue
                start, end = build_content_db.cloze_span(
                    sentence["en_text"], sentence["cloze_target"]
                )
                if start < 0:
                    errors.append(f"{headword} rank {sentence['rank']}: cloze target not found")
                    continue
                prepared.append(
                    (
                        word["id"], sense["id"], sentence["rank"], sentence["en_text"],
                        sentence["th_text"], sentence["cloze_target"], start, end,
                        sentence["cloze_target"], int(sentence["is_emotional"]),
                        sentence["explanation_th"], args.source_label,
                    )
                )
            if len(prepared) != 5:
                continue
            db.execute("DELETE FROM example_sentences WHERE word_id=?", (word["id"],))
            db.executemany(
                """INSERT INTO example_sentences
                (word_id,sense_id,rank,en_text,th_text,cloze_target,cloze_start,cloze_end,
                 form_used,is_emotional,explanation_th,explanation_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                prepared,
            )
            applied += 1

        if errors or args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    for error in errors:
        print(error, file=sys.stderr)
    print(f"db={args.db} applied={applied} skipped={skipped} errors={len(errors)} dry_run={args.dry_run}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
