#!/usr/bin/env python3
"""Export the validated content DB as the app's bundled seed.

The app copies this file into its writable directory on first launch and then
layers the user's own tables on top, so the seed must contain content only --
never srs_state, reviews_log, daily_stats or settings.  ``content_meta`` carries
the version the app compares against to decide whether to reseed
(``lib/data/content_reseed.dart``).

    python tools/export_app_seed.py
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DB = ROOT / "data" / "content_v2.db"
SEED_DB = ROOT / "vocab_app" / "assets" / "seed" / "vocab.db"
USER_TABLES = ("srs_state", "reviews_log", "daily_stats", "settings", "schema_migrations")


def export(content: Path, seed: Path, include_test_words: bool) -> int:
    if not content.exists():
        raise SystemExit(f"{content} does not exist -- run tools/build_content_db.py first")
    seed.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(content, seed)

    db = sqlite3.connect(seed)
    db.execute("PRAGMA foreign_keys = ON")
    try:
        present = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        leaked = present & set(USER_TABLES)
        if leaked:
            raise SystemExit(f"content DB contains user tables: {', '.join(sorted(leaked))}")

        if not include_test_words:
            # The hard multi-POS set is scaffolding; a shipped seed must not carry it.
            db.execute("DELETE FROM words WHERE is_test_only=1")
            # Removing fixture words can leave an Odd One Out group too small to
            # play.  Drop only those now-invalid groups from the production copy.
            db.execute(
                "DELETE FROM relation_groups WHERE "
                "(SELECT count(*) FROM relation_group_members "
                " WHERE group_id=relation_groups.id) < 3"
            )

        # The store reads these for the focus-topic feature; they stay empty until
        # topics are modelled, but the queries must not fail.
        db.executescript(
            "CREATE TABLE IF NOT EXISTS topics (id INTEGER PRIMARY KEY, name TEXT, cefr TEXT);"
            "CREATE TABLE IF NOT EXISTS word_topics ("
            "  word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,"
            "  topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,"
            "  PRIMARY KEY(word_id, topic_id));"
        )
        db.execute(
            "INSERT OR REPLACE INTO content_meta VALUES ('includes_test_words', ?)",
            ("1" if include_test_words else "0",),
        )
        db.commit()
        counts = {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("words", "senses", "word_forms", "example_sentences", "related_words")
        }
        version = db.execute("SELECT value FROM content_meta WHERE key='content_version'").fetchone()[0]
    finally:
        db.close()

    # VACUUM after the deletes so the bundled asset stays small.
    db = sqlite3.connect(seed)
    db.execute("VACUUM")
    db.close()

    print(f"wrote {seed} ({seed.stat().st_size // 1024} KB) content_version={version}")
    print("  " + "  ".join(f"{name}={value}" for name, value in counts.items()))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-db", type=Path, default=CONTENT_DB)
    parser.add_argument("--out", type=Path, default=SEED_DB)
    parser.add_argument(
        "--include-test-words", action="store_true",
        help="keep the 30-word hard test set (development builds only)",
    )
    args = parser.parse_args()
    return export(args.content_db, args.out, args.include_test_words)


if __name__ == "__main__":
    raise SystemExit(main())
