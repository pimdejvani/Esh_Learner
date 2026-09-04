#!/usr/bin/env python3
"""Fetch the proper-noun entries the harvest never asked for.

``harvest_one`` (``build_vocab_library.py:227``) tries the lowercase spelling,
then Title case, then UPPER -- but it ``break``s on the first page that exists.
For a word like ``june`` the lowercase page exists and holds only the dated
Southern-US slang verb "to rush", so the month entry under ``June`` was never
fetched.  Eleven date words lost their month/weekday sense this way.

Append-only, like ``backfill_dropped_pos.py``: nothing is deleted, so existing
``source_senses.id`` values keep meaning what the drafts think they mean.  New
rows go to the source DB first and are mirrored into the evidence slice with
explicit ids so the two stay in agreement.

    python tools/backfill_titlecase_names.py --dry-run
    python tools/backfill_titlecase_names.py --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"
EVIDENCE_DB = ROOT / "data" / "vocabulary_evidence.db"
KAIKKI_BASE = "https://kaikki.org/dictionary/English/meaning"
USER_AGENT = "Esh-Learner-vocabulary-library/1.0"

DATE_WORDS = (
    "january february march april may june july august september october "
    "november december monday tuesday wednesday thursday friday saturday sunday"
).split()


def kaikki_url(word: str) -> str:
    first, first_two = word[:1], word[:2]
    return "/".join((KAIKKI_BASE, urllib.parse.quote(first),
                     urllib.parse.quote(first_two),
                     urllib.parse.quote(word))) + ".jsonl"


def fetch(word: str) -> list[dict]:
    request = urllib.request.Request(kaikki_url(word),
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
    out = []
    for line in body.splitlines():
        if line.strip():
            raw = json.loads(line)
            if raw.get("lang_code") == "en" and raw.get("pos") == "name":
                out.append(raw)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    src = sqlite3.connect(SOURCE_DB)
    src.row_factory = sqlite3.Row
    todo = []
    for word in DATE_WORDS:
        row = src.execute("SELECT id FROM words WHERE headword = ?", (word,)).fetchone()
        if row is None:
            continue
        stored = {r[0] for r in src.execute(
            "SELECT DISTINCT pos FROM source_senses WHERE word_id = ?", (row["id"],))}
        if "name" not in stored:
            todo.append((row["id"], word))
    print(f"words missing the proper-noun sense: {len(todo)} "
          f"({', '.join(w for _i, w in todo)})")
    if not args.apply:
        print("dry run -- pass --apply to fetch and write")
        return 0

    evi = sqlite3.connect(EVIDENCE_DB)
    inserted = 0
    for word_id, word in todo:
        records = fetch(word.title())
        if not records:
            print(f"  {word}: no 'name' entry found under {word.title()}")
            continue
        for rec in records:
            for sense in rec.get("senses") or []:
                for gloss in sense.get("glosses") or []:
                    tags = json.dumps(sense.get("tags") or [], ensure_ascii=False)
                    cur = src.execute(
                        "INSERT OR IGNORE INTO source_senses"
                        "(word_id,pos,gloss,tags_json,source_name) "
                        "VALUES (?,'name',?,?,'kaikki')", (word_id, gloss, tags))
                    if not cur.rowcount:
                        continue
                    inserted += 1
                    evi.execute(
                        "INSERT OR IGNORE INTO source_senses"
                        "(id,word_id,pos,gloss,tags_json,source_name) "
                        "VALUES (?,?,'name',?,?,'kaikki')",
                        (cur.lastrowid, word_id, gloss, tags))
                    for example in sense.get("examples") or []:
                        if isinstance(example, dict) and example.get("text"):
                            for db in (src, evi):
                                db.execute(
                                    "INSERT OR IGNORE INTO source_examples"
                                    "(word_id,pos,sense_gloss,example_text,"
                                    "example_type,reference_text,source_name) "
                                    "VALUES (?,'name',?,?,?,?,'kaikki')",
                                    (word_id, gloss, example["text"],
                                     example.get("type"), example.get("ref")))
        print(f"  {word}: ok")
    src.commit(); evi.commit()
    src.close(); evi.close()
    print(f"senses inserted: {inserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
