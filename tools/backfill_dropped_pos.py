#!/usr/bin/env python3
"""Re-insert senses that the original harvest dropped on the floor.

``insert_records`` filters kaikki records by ``ALLOWED_POS``
(``build_vocab_library.py:46``).  That set was tightened after the harvest ran
and it never contained kaikki's actual interjection tag (``intj``, not
``interj``), so 188 words lost a whole part of speech and 35 more lost a POS
that the set does allow today -- ``fifteen`` kept only "an Irish traybake" and
lost the cardinal number.

The raw kaikki payload is still in ``source_documents.raw_json``, so this is an
offline repair.  It is strictly APPEND-ONLY: re-running the harvest would
delete and re-insert senses (``build_vocab_library.py:257``) and silently
re-point every draft's ``sense_id``.  Nothing here deletes, so existing ids
keep meaning what the drafts think they mean.  New rows are written to the
source DB first and then copied into the evidence slice *with their explicit
ids*, so the two stay in agreement.

    python tools/backfill_dropped_pos.py --dry-run
    python tools/backfill_dropped_pos.py --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"
EVIDENCE_DB = ROOT / "data" / "vocabulary_evidence.db"

# The POS kaikki actually emits that a learner corpus wants.  `intj` is the
# name it uses; `interj` in ALLOWED_POS never matched anything.
WANTED = {"noun", "verb", "adj", "adv", "prep", "pron", "det", "conj", "name",
          "num", "intj", "particle", "contraction", "article", "postp"}


def missing_records(db: sqlite3.Connection) -> list[tuple[int, str, dict]]:
    """(word_id, headword, kaikki record) for every POS with no senses stored."""
    out = []
    for row in db.execute(
        "SELECT w.id wid, w.headword hw, d.raw_json rj FROM source_documents d "
        "JOIN words w ON w.id = d.word_id WHERE d.source_name = 'kaikki'"
    ).fetchall():
        have = {r[0] for r in db.execute(
            "SELECT DISTINCT pos FROM source_senses WHERE word_id = ?", (row["wid"],))}
        for rec in json.loads(row["rj"]):
            pos = rec.get("pos")
            if pos in WANTED and pos not in have and (rec.get("senses") or []):
                out.append((row["wid"], row["hw"], rec))
    return out


def apply_to_source(db: sqlite3.Connection, records) -> list[int]:
    """Insert senses/examples/forms; return the new source_senses ids."""
    new_ids = []
    for word_id, _hw, rec in records:
        pos = rec["pos"]
        for sense in rec.get("senses") or []:
            for gloss in sense.get("glosses") or []:
                cur = db.execute(
                    "INSERT OR IGNORE INTO source_senses"
                    "(word_id,pos,gloss,tags_json,source_name) VALUES (?,?,?,?,'kaikki')",
                    (word_id, pos, gloss,
                     json.dumps(sense.get("tags") or [], ensure_ascii=False)))
                if cur.rowcount:
                    new_ids.append(cur.lastrowid)
                for example in sense.get("examples") or []:
                    if isinstance(example, dict) and example.get("text"):
                        db.execute(
                            "INSERT OR IGNORE INTO source_examples"
                            "(word_id,pos,sense_gloss,example_text,example_type,"
                            "reference_text,source_name) VALUES (?,?,?,?,?,?,'kaikki')",
                            (word_id, pos, gloss, example["text"],
                             example.get("type"), example.get("ref")))
        for form in rec.get("forms") or []:
            if isinstance(form, dict) and form.get("form"):
                db.execute(
                    "INSERT OR IGNORE INTO source_forms"
                    "(word_id,form_text,pos,tags_json,source_name) VALUES (?,?,?,?,'kaikki')",
                    (word_id, form["form"], pos,
                     json.dumps(form.get("tags") or [], ensure_ascii=False)))
    return new_ids


def copy_to_evidence(src: sqlite3.Connection, evi: sqlite3.Connection,
                     new_ids: list[int], records) -> int:
    """Mirror the new rows into the evidence slice, ids preserved."""
    copied = 0
    for sense_id in new_ids:
        row = src.execute(
            "SELECT id,word_id,pos,gloss,tags_json,source_name FROM source_senses "
            "WHERE id = ?", (sense_id,)).fetchone()
        cur = evi.execute(
            "INSERT OR IGNORE INTO source_senses"
            "(id,word_id,pos,gloss,tags_json,source_name) VALUES (?,?,?,?,?,?)",
            tuple(row))
        copied += cur.rowcount
    touched = {(wid, rec["pos"]) for wid, _hw, rec in records}
    for word_id, pos in touched:
        for table, cols in (
            ("source_examples",
             "word_id,pos,sense_gloss,example_text,example_type,reference_text,source_name"),
            ("source_forms", "word_id,form_text,pos,tags_json,source_name"),
        ):
            for row in src.execute(
                f"SELECT {cols} FROM {table} WHERE word_id = ? AND pos = ?",
                (word_id, pos)):
                evi.execute(
                    f"INSERT OR IGNORE INTO {table}({cols}) VALUES "
                    f"({','.join('?' * len(row))})", tuple(row))
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    src = sqlite3.connect(SOURCE_DB)
    src.row_factory = sqlite3.Row
    records = missing_records(src)
    by_pos = Counter(rec["pos"] for _w, _h, rec in records)
    words = {hw for _w, hw, _r in records}
    print(f"words affected: {len(words)}")
    print(f"records to restore: {len(records)}  {by_pos.most_common()}")
    if not args.apply:
        print("dry run -- pass --apply to write")
        return 0

    new_ids = apply_to_source(src, records)
    evi = sqlite3.connect(EVIDENCE_DB)
    copied = copy_to_evidence(src, evi, new_ids, records)
    src.commit(); evi.commit()
    src.close(); evi.close()
    print(f"senses inserted: {len(new_ids)}  mirrored to evidence: {copied}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
