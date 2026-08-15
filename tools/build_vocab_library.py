#!/usr/bin/env python3
"""Build a source-first vocabulary library, separate from the Flutter seed.

The existing ``build_dataset.py`` produces app-ready data for a small seed and
contains generated learner content.  This tool deliberately does not touch it.
It creates ``data/vocabulary_source.db`` as the durable lexical evidence store
for the whole Oxford-3000 source list.  Generated Thai copy, examples and app
tables can be added only after this source layer has passed validation.

Usage:
  python tools/build_vocab_library.py bootstrap
  python tools/build_vocab_library.py normalize
  python tools/build_vocab_library.py harvest --workers 12
  python tools/build_vocab_library.py validate

``harvest`` is resumable: a failed word remains in the queue for the next run.
No lexical value is inferred when a dictionary record is absent.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "vocabulary_source.db"
OXFORD_URL = (
    "https://raw.githubusercontent.com/Kolia951/The_Oxford_3000_CEFR/"
    "main/package.txt"
)
KAIKKI_BASE = "https://kaikki.org/dictionary/English/meaning"
USER_AGENT = "Esh-Learner-vocabulary-library/1.0"
LEVELS = ("A1", "A2", "B1", "B2")
ALLOWED_POS = {"noun", "verb", "adj", "adv", "prep", "pron", "det", "conj", "interj", "name", "num"}

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS library_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS words (
  id INTEGER PRIMARY KEY,
  headword TEXT NOT NULL UNIQUE COLLATE NOCASE,
  cefr_first TEXT NOT NULL,
  source_rank INTEGER NOT NULL UNIQUE,
  source_status TEXT NOT NULL DEFAULT 'queued'
    CHECK(source_status IN ('queued','harvested','not_found','failed')),
  source_error TEXT,
  harvested_at TEXT
);
CREATE TABLE IF NOT EXISTS word_cefr_bands (
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  cefr TEXT NOT NULL,
  PRIMARY KEY(word_id, cefr)
);
CREATE TABLE IF NOT EXISTS source_documents (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  license TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  UNIQUE(word_id, source_name)
);
CREATE TABLE IF NOT EXISTS source_senses (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  pos TEXT NOT NULL,
  gloss TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  source_name TEXT NOT NULL,
  UNIQUE(word_id, pos, gloss)
);
CREATE TABLE IF NOT EXISTS source_forms (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  form_text TEXT NOT NULL,
  pos TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  source_name TEXT NOT NULL,
  UNIQUE(word_id, form_text, pos, tags_json)
);
CREATE TABLE IF NOT EXISTS source_related_candidates (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  candidate TEXT NOT NULL,
  candidate_type TEXT NOT NULL CHECK(candidate_type IN ('derived','related')),
  pos TEXT NOT NULL,
  source_name TEXT NOT NULL,
  UNIQUE(word_id, candidate, candidate_type, pos)
);
CREATE TABLE IF NOT EXISTS source_pronunciations (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  pos TEXT NOT NULL,
  ipa TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  source_name TEXT NOT NULL,
  UNIQUE(word_id, pos, ipa, tags_json)
);
CREATE TABLE IF NOT EXISTS source_translations (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  pos TEXT NOT NULL,
  sense_gloss TEXT,
  language_code TEXT NOT NULL,
  translation TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  source_name TEXT NOT NULL,
  UNIQUE(word_id, pos, sense_gloss, language_code, translation, tags_json)
);
CREATE TABLE IF NOT EXISTS source_examples (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  pos TEXT NOT NULL,
  sense_gloss TEXT NOT NULL,
  example_text TEXT NOT NULL,
  example_type TEXT,
  reference_text TEXT,
  source_name TEXT NOT NULL,
  UNIQUE(word_id, pos, sense_gloss, example_text)
);
CREATE INDEX IF NOT EXISTS idx_words_status ON words(source_status, source_rank);
CREATE INDEX IF NOT EXISTS idx_senses_word ON source_senses(word_id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request_bytes(url: str, attempts: int = 3) -> bytes:
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=45) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
        time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("unreachable")


def fetch_oxford() -> dict[str, list[str]]:
    payload = json.loads(request_bytes(OXFORD_URL).decode("utf-8"))
    if not all(level in payload and isinstance(payload[level], list) for level in LEVELS):
        raise ValueError("Oxford source does not contain the expected A1–B2 arrays")
    return payload


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(SCHEMA)
    return con


def bootstrap() -> None:
    source = fetch_oxford()
    bands: dict[str, set[str]] = {}
    for level in LEVELS:
        bands[level] = {str(word).strip().lower() for word in source[level] if str(word).strip()}

    # The first level where a word appears is its introduction band.  The
    # ordered list is deterministic and does not claim to be a frequency rank.
    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for level in LEVELS:
        for word in source[level]:
            headword = str(word).strip().lower()
            if headword and headword not in seen:
                seen.add(headword)
                ordered.append((headword, level))

    with connect() as con:
        con.executescript(SCHEMA)
        con.execute("DELETE FROM word_cefr_bands")
        con.execute("DELETE FROM words")
        con.execute("DELETE FROM library_meta")
        con.executemany(
            "INSERT INTO words(headword, cefr_first, source_rank) VALUES (?, ?, ?)",
            ((word, level, rank) for rank, (word, level) in enumerate(ordered, 1)),
        )
        for level, words in bands.items():
            con.executemany(
                "INSERT INTO word_cefr_bands(word_id, cefr) "
                "SELECT id, ? FROM words WHERE headword = ?",
                ((level, word) for word in words),
            )
        con.executemany(
            "INSERT INTO library_meta(key, value) VALUES (?, ?)",
            [
                ("oxford_source_url", OXFORD_URL),
                ("oxford_source_retrieved_at", now()),
                ("source_word_count", str(len(ordered))),
                ("library_schema_version", "1"),
            ],
        )
    print(f"Bootstrapped {len(ordered)} unique source words into {DB_PATH}")


def kaikki_url(word: str) -> str:
    first, first_two = word[:1], word[:2]
    return "/".join((KAIKKI_BASE, urllib.parse.quote(first), urllib.parse.quote(first_two), urllib.parse.quote(word))) + ".jsonl"


def harvest_one(word_id: int, word: str) -> tuple[int, str, str | None, list[dict]]:
    spellings = dict.fromkeys((word, word.title(), word.upper()))
    lines = None
    for spelling in spellings:
        try:
            lines = request_bytes(kaikki_url(spelling)).decode("utf-8").splitlines()
            break
        except urllib.error.HTTPError as error:
            if error.code != 404:
                return word_id, "failed", f"HTTP {error.code}", []
        except Exception as error:  # kept as queue state, never silently dropped
            return word_id, "failed", str(error)[:500], []
    if lines is None:
        return word_id, "not_found", None, []
    records = []
    try:
        for line in lines:
            if not line.strip():
                continue
            raw = json.loads(line)
            raw_word = raw.get("word")
            if isinstance(raw_word, str) and raw_word.lower() == word.lower() and raw.get("lang_code") == "en":
                records.append(raw)
    except (json.JSONDecodeError, AttributeError, TypeError) as error:
        return word_id, "failed", f"parse error: {error}"[:500], []
    return word_id, ("harvested" if records else "not_found"), None, records


def insert_records(con: sqlite3.Connection, word_id: int, word: str, records: list[dict]) -> None:
    con.execute("DELETE FROM source_documents WHERE word_id = ? AND source_name = 'kaikki'", (word_id,))
    con.execute("DELETE FROM source_senses WHERE word_id = ? AND source_name = 'kaikki'", (word_id,))
    con.execute("DELETE FROM source_forms WHERE word_id = ? AND source_name = 'kaikki'", (word_id,))
    con.execute("DELETE FROM source_related_candidates WHERE word_id = ? AND source_name = 'kaikki'", (word_id,))
    con.execute("DELETE FROM source_pronunciations WHERE word_id = ? AND source_name = 'kaikki'", (word_id,))
    con.execute("DELETE FROM source_translations WHERE word_id = ? AND source_name = 'kaikki'", (word_id,))
    con.execute("DELETE FROM source_examples WHERE word_id = ? AND source_name = 'kaikki'", (word_id,))
    source_url = kaikki_url(records[0].get("word", word))
    con.execute(
        "INSERT INTO source_documents(word_id, source_name, source_url, license, retrieved_at, raw_json) VALUES (?, 'kaikki', ?, 'CC BY-SA and GFDL', ?, ?)",
        (word_id, source_url, now(), json.dumps(records, ensure_ascii=False, separators=(",", ":"))),
    )
    for raw in records:
        pos = raw.get("pos")
        if pos not in ALLOWED_POS:
            continue
        for sound in raw.get("sounds") or []:
            ipa = sound.get("ipa") if isinstance(sound, dict) else None
            if ipa:
                con.execute(
                    "INSERT OR IGNORE INTO source_pronunciations(word_id,pos,ipa,tags_json,source_name) VALUES (?,?,?,?, 'kaikki')",
                    (word_id, pos, ipa, json.dumps(sound.get("tags") or [], ensure_ascii=False)),
                )
        for translation in raw.get("translations") or []:
            if not isinstance(translation, dict) or not translation.get("word"):
                continue
            language_code = translation.get("lang_code") or translation.get("code")
            if language_code:
                con.execute(
                    "INSERT OR IGNORE INTO source_translations(word_id,pos,sense_gloss,language_code,translation,tags_json,source_name) VALUES (?,?,?,?,?,?, 'kaikki')",
                    (word_id, pos, translation.get("sense"), language_code, translation["word"], json.dumps(translation.get("tags") or [], ensure_ascii=False)),
                )
        for sense in raw.get("senses") or []:
            for gloss in sense.get("glosses") or []:
                con.execute(
                    "INSERT OR IGNORE INTO source_senses(word_id,pos,gloss,tags_json,source_name) VALUES (?,?,?,?, 'kaikki')",
                    (word_id, pos, gloss, json.dumps(sense.get("tags") or [], ensure_ascii=False)),
                )
                for example in sense.get("examples") or []:
                    if isinstance(example, dict) and example.get("text"):
                        con.execute(
                            "INSERT OR IGNORE INTO source_examples(word_id,pos,sense_gloss,example_text,example_type,reference_text,source_name) VALUES (?,?,?,?,?,?, 'kaikki')",
                            (word_id, pos, gloss, example["text"], example.get("type"), example.get("ref")),
                        )
        for form in raw.get("forms") or []:
            form_text = form.get("form")
            if form_text and "symbol" not in (form.get("tags") or []):
                con.execute(
                    "INSERT OR IGNORE INTO source_forms(word_id,form_text,pos,tags_json,source_name) VALUES (?,?,?,?, 'kaikki')",
                    (word_id, form_text, pos, json.dumps(form.get("tags") or [], ensure_ascii=False)),
                )
        for field, kind in (("derived", "derived"), ("related", "related")):
            for item in raw.get(field) or []:
                candidate = item.get("word") if isinstance(item, dict) else None
                if candidate:
                    con.execute(
                        "INSERT OR IGNORE INTO source_related_candidates(word_id,candidate,candidate_type,pos,source_name) VALUES (?,?,?,?, 'kaikki')",
                        (word_id, candidate, kind, pos),
                    )


def harvest(workers: int, limit: int | None, retry_not_found: bool) -> None:
    with connect() as con:
        statuses = "('queued','failed','not_found')" if retry_not_found else "('queued','failed')"
        rows = con.execute(
            f"SELECT id, headword FROM words WHERE source_status IN {statuses} ORDER BY source_rank" + (" LIMIT ?" if limit else ""),
            (() if not limit else (limit,)),
        ).fetchall()
    if not rows:
        print("Nothing queued for harvest.")
        return
    print(f"Harvesting {len(rows)} words with {workers} workers…")
    lock = threading.Lock()
    completed = 0
    words_by_id = dict(rows)
    with connect() as con, concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(harvest_one, row[0], row[1]) for row in rows]
        for future in concurrent.futures.as_completed(futures):
            word_id, status, error, records = future.result()
            word = words_by_id[word_id]
            with lock:
                if records:
                    insert_records(con, word_id, word, records)
                con.execute("UPDATE words SET source_status=?, source_error=?, harvested_at=? WHERE id=?", (status, error, now(), word_id))
                completed += 1
                if completed % 25 == 0:
                    con.commit()
                if completed % 50 == 0 or completed == len(rows):
                    print(f"  {completed}/{len(rows)} complete")
        con.commit()


def normalize(missing_senses_only: bool) -> None:
    """Rebuild normalized rows from cached raw documents; no network calls."""
    with connect() as con:
        where = " AND NOT EXISTS (SELECT 1 FROM source_senses s WHERE s.word_id=w.id)" if missing_senses_only else ""
        rows = con.execute(
            "SELECT w.id, w.headword, d.raw_json FROM source_documents d "
            "JOIN words w ON w.id=d.word_id WHERE d.source_name='kaikki' "
            + where + " ORDER BY w.source_rank"
        ).fetchall()
        for index, (word_id, word, raw_json) in enumerate(rows, 1):
            insert_records(con, word_id, word, json.loads(raw_json))
            if index % 25 == 0:
                con.commit()
            if index % 250 == 0 or index == len(rows):
                print(f"  normalized {index}/{len(rows)}")
        con.commit()


def validate() -> None:
    with connect() as con:
        counts = dict(con.execute("SELECT source_status, COUNT(*) FROM words GROUP BY source_status"))
        total = con.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        missing = con.execute("SELECT COUNT(*) FROM words w LEFT JOIN word_cefr_bands b ON b.word_id=w.id WHERE b.word_id IS NULL").fetchone()[0]
        raw = con.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
        senses = con.execute("SELECT COUNT(*) FROM source_senses").fetchone()[0]
        forms = con.execute("SELECT COUNT(*) FROM source_forms").fetchone()[0]
        pronunciations = con.execute("SELECT COUNT(*) FROM source_pronunciations").fetchone()[0]
        thai_translations = con.execute("SELECT COUNT(*) FROM source_translations WHERE language_code='th'").fetchone()[0]
        examples = con.execute("SELECT COUNT(*) FROM source_examples").fetchone()[0]
    print(json.dumps({"words": total, "statuses": counts, "words_without_cefr": missing, "raw_documents": raw, "source_senses": senses, "source_forms": forms, "source_pronunciations": pronunciations, "thai_translations": thai_translations, "source_examples": examples}, indent=2))
    if missing:
        raise SystemExit("Validation failed: a word lacks CEFR provenance")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bootstrap")
    normalize_parser = sub.add_parser("normalize")
    normalize_parser.add_argument("--missing-senses-only", action="store_true")
    harvest_parser = sub.add_parser("harvest")
    harvest_parser.add_argument("--workers", type=int, default=12)
    harvest_parser.add_argument("--limit", type=int)
    harvest_parser.add_argument("--retry-not-found", action="store_true")
    sub.add_parser("validate")
    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap()
    elif args.command == "normalize":
        normalize(args.missing_senses_only)
    elif args.command == "harvest":
        harvest(max(1, args.workers), args.limit, args.retry_not_found)
    else:
        validate()


if __name__ == "__main__":
    main()
