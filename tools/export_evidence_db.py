#!/usr/bin/env python3
"""Export a portable evidence-only slice of ``data/vocabulary_source.db``.

The full source DB is 377 MB, but 232 MB of that is raw harvest payload
(``source_documents``), Thai translation candidates and association candidates
that the English generation and review passes never read.  Sol only needs the
exact senses, forms and examples (see ``sol_subagent.md``), and
``translate_vocab_content.validate_entry`` only reads ``words``,
``source_senses`` and ``source_forms``.

This tool copies that slice into ``data/vocabulary_evidence.db`` so a machine
without the local data lake -- a cloud session, a phone-driven session, or a CI
runner -- can generate, validate and review drafts.  It never writes to the
source DB.

Usage:
  python tools/export_evidence_db.py
  python tools/export_evidence_db.py --with-translations   # adds the Thai step
  python tools/export_evidence_db.py --check               # verify an export
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SOURCE_DB = DATA_DIR / "vocabulary_source.db"
EVIDENCE_DB = DATA_DIR / "vocabulary_evidence.db"

# Everything the English generate/validate/review passes read, and nothing else.
REVIEW_TABLES = (
    "library_meta",
    "words",
    "word_cefr_bands",
    "source_senses",
    "source_forms",
    "source_pronunciations",
    "source_examples",
)
# Only the translation pass needs this one; it costs ~48 MB.
TRANSLATION_TABLES = ("source_translations",)


def table_names(db: sqlite3.Connection, with_translations: bool) -> tuple[str, ...]:
    tables = REVIEW_TABLES + (TRANSLATION_TABLES if with_translations else ())
    present = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing = [name for name in tables if name not in present]
    if missing:
        raise SystemExit(f"source DB is missing tables: {', '.join(missing)}")
    return tables


def export(with_translations: bool) -> int:
    if not SOURCE_DB.exists():
        raise SystemExit(f"source DB not found: {SOURCE_DB}")
    if EVIDENCE_DB.exists():
        EVIDENCE_DB.unlink()

    source = sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True)
    tables = table_names(source, with_translations)
    source.execute("ATTACH DATABASE ? AS out", (str(EVIDENCE_DB),))

    # Recreate each table and its indexes verbatim so the copied slice keeps the
    # same constraints the validators rely on.
    for name in tables:
        for (sql,) in source.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name=? AND sql IS NOT NULL"
            " ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END",
            (name,),
        ):
            source.execute(sql.replace("CREATE TABLE ", "CREATE TABLE out.", 1)
                           .replace("CREATE INDEX ", "CREATE INDEX out.", 1)
                           .replace("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX out.", 1))

    counts: dict[str, int] = {}
    for name in tables:
        source.execute(f'INSERT INTO out."{name}" SELECT * FROM main."{name}"')
        counts[name] = source.execute(f'SELECT count(*) FROM out."{name}"').fetchone()[0]
    source.commit()

    provenance = source.execute(
        "SELECT DISTINCT source_name FROM main.source_senses ORDER BY source_name"
    ).fetchall()
    source.execute(
        "INSERT OR REPLACE INTO out.library_meta(key,value) VALUES('evidence_export_profile',?)",
        ("review+translations" if with_translations else "review",),
    )
    source.commit()
    source.execute("DETACH DATABASE out")
    source.close()

    # VACUUM cannot run inside the attached connection's transaction scope.
    out = sqlite3.connect(EVIDENCE_DB)
    out.execute("VACUUM")
    out.close()

    size = EVIDENCE_DB.stat().st_size
    original = SOURCE_DB.stat().st_size
    for name, count in counts.items():
        print(f"{name:28s} rows={count}")
    print(
        f"wrote {EVIDENCE_DB.relative_to(ROOT)} "
        f"{size / 1048576:.1f} MB (from {original / 1048576:.0f} MB, "
        f"{100 * size / original:.1f}%)"
    )
    print(f"lexical source_name values: {', '.join(row[0] for row in provenance)}")
    return 0


def check() -> int:
    if not EVIDENCE_DB.exists():
        raise SystemExit(f"evidence DB not found: {EVIDENCE_DB}")
    db = sqlite3.connect(f"file:{EVIDENCE_DB}?mode=ro", uri=True)
    errors: list[str] = []
    for name in REVIEW_TABLES:
        try:
            count = db.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
        except sqlite3.Error as exc:
            errors.append(f"{name}: {exc}")
            continue
        if count == 0:
            errors.append(f"{name}: empty")
        print(f"{name:28s} rows={count}")
    words = db.execute("SELECT count(*) FROM words").fetchone()[0]
    orphans = db.execute(
        "SELECT count(*) FROM source_senses WHERE word_id NOT IN (SELECT id FROM words)"
    ).fetchone()[0]
    if orphans:
        errors.append(f"source_senses has {orphans} rows with no word")
    profile = db.execute(
        "SELECT value FROM library_meta WHERE key='evidence_export_profile'"
    ).fetchone()
    db.close()
    print(f"words={words} profile={profile[0] if profile else 'unknown'} errors={len(errors)}")
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-translations",
        action="store_true",
        help="include source_translations for the Thai translation pass (~48 MB)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate an existing export instead of rebuilding it",
    )
    args = parser.parse_args()
    return check() if args.check else export(args.with_translations)


if __name__ == "__main__":
    raise SystemExit(main())
