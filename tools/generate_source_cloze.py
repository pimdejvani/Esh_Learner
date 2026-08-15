#!/usr/bin/env python3
"""Define the resumable, source-grounded EN/TH cloze data contract.

This deliberately writes generated content beside the harvested lexical data,
not into the app's production tables.  It only sends harvested senses and
forms to the model; a generated target is rejected unless it is one of those
forms.  A run can be resumed safely after interruption:

    python tools/generate_source_cloze.py --dry-run --limit 3

Generation is deliberately disabled in this script. The current project uses
Codex Terra agents and canonical English-only TXT instead of Gemini or any
external generation API. The source payload and deterministic validator remain
here so both paths use the same contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "vocabulary_source.db"
PROMPT_VERSION = "re-vocab-source-cloze-v1"
DEFAULT_MODEL = "gpt-5.6-terra"
STATUS_VALUES = ("pending", "generating", "passed", "failed", "needs_source")
FORM_RE = re.compile(r"^[A-Za-z]+(?:['-][A-Za-z]+)*$")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 5000")
    return db


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS generation_runs (
          id TEXT PRIMARY KEY,
          prompt_version TEXT NOT NULL,
          generator_model TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          settings_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS generation_word_status (
          run_id TEXT NOT NULL REFERENCES generation_runs(id) ON DELETE CASCADE,
          word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
          status TEXT NOT NULL CHECK(status IN ('pending','generating','passed','failed','needs_source')),
          attempts INTEGER NOT NULL DEFAULT 0,
          source_fingerprint TEXT NOT NULL,
          validation_errors_json TEXT NOT NULL DEFAULT '[]',
          last_error TEXT,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(run_id, word_id)
        );
        CREATE INDEX IF NOT EXISTS idx_generation_status_pending
          ON generation_word_status(run_id, status, word_id);

        CREATE TABLE IF NOT EXISTS generated_cloze_sentences (
          run_id TEXT NOT NULL REFERENCES generation_runs(id) ON DELETE CASCADE,
          word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
          rank INTEGER NOT NULL CHECK(rank BETWEEN 1 AND 5),
          pos TEXT NOT NULL,
          sense_gloss TEXT NOT NULL,
          en_text TEXT NOT NULL,
          th_text TEXT NOT NULL,
          cloze_target TEXT NOT NULL,
          is_emotional INTEGER NOT NULL CHECK(is_emotional IN (0,1)),
          explanation_th TEXT NOT NULL,
          source_fingerprint TEXT NOT NULL,
          generated_at TEXT NOT NULL,
          PRIMARY KEY(run_id, word_id, rank)
        );

        CREATE TABLE IF NOT EXISTS generation_cost_metadata (
          id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL REFERENCES generation_runs(id) ON DELETE CASCADE,
          word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
          request_id TEXT NOT NULL,
          generator_model TEXT NOT NULL,
          prompt_version TEXT NOT NULL,
          input_tokens INTEGER,
          candidate_tokens INTEGER,
          thinking_tokens INTEGER,
          billable_output_tokens INTEGER,
          generator_cost_usd REAL,
          repair_cost_usd REAL NOT NULL DEFAULT 0,
          total_cost_thb REAL,
          usd_thb REAL,
          pricing_as_of TEXT,
          validation_attempts INTEGER NOT NULL,
          repair_attempts INTEGER NOT NULL DEFAULT 0,
          final_status TEXT NOT NULL,
          validation_errors_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_generation_cost_word
          ON generation_cost_metadata(run_id, word_id, created_at);
        """
    )
    db.commit()


def get_or_create_run(db: sqlite3.Connection, run_key: str, model: str, args: argparse.Namespace) -> None:
    row = db.execute("SELECT id FROM generation_runs WHERE id = ?", (run_key,)).fetchone()
    if row:
        db.execute("UPDATE generation_runs SET updated_at = ?, generator_model = ? WHERE id = ?", (now(), model, run_key))
    else:
        settings = {"batch_size": args.batch_size, "max_forms_per_pos": args.max_forms_per_pos}
        db.execute(
            "INSERT INTO generation_runs VALUES (?, ?, ?, ?, ?, ?)",
            (run_key, PROMPT_VERSION, model, now(), now(), json.dumps(settings, sort_keys=True)),
        )
    db.commit()


def source_entry(db: sqlite3.Connection, word: sqlite3.Row, max_forms_per_pos: int) -> dict[str, Any] | None:
    senses = [dict(r) for r in db.execute(
        "SELECT pos, gloss, tags_json, source_name FROM source_senses WHERE word_id = ? ORDER BY id", (word["id"],)
    )]
    if not senses:
        return None
    positions = {row["pos"] for row in senses}
    forms: dict[str, list[str]] = {pos: [word["headword"]] for pos in positions}
    for row in db.execute(
        "SELECT form_text, pos, tags_json FROM source_forms WHERE word_id = ? ORDER BY id", (word["id"],)
    ):
        form, pos = row["form_text"].strip(), row["pos"]
        # Generated clozes must be simple visible English word forms.  This
        # excludes multi-word/annotation forms without inventing replacements.
        if pos in forms and FORM_RE.fullmatch(form) and form.lower() not in {x.lower() for x in forms[pos]}:
            forms[pos].append(form)
    forms = {pos: values[:max_forms_per_pos] for pos, values in forms.items()}
    # The translations are optional source evidence to help natural Thai; no
    # translation is fabricated into the source payload if harvesting lacks it.
    translations = [dict(r) for r in db.execute(
        """SELECT pos, sense_gloss, translation, source_name FROM source_translations
           WHERE word_id = ? AND language_code = 'th' ORDER BY id LIMIT 40""", (word["id"],)
    )]
    payload = {
        "headword": word["headword"],
        "parts_of_speech": sorted(positions),
        "senses": senses,
        "allowed_forms_by_pos": forms,
        "thai_translation_candidates": translations,
    }
    payload["source_fingerprint"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload


def seed_statuses(db: sqlite3.Connection, run_key: str, max_forms_per_pos: int, refresh_stale: bool) -> int:
    count = 0
    for word in db.execute("SELECT * FROM words WHERE source_status = 'harvested' ORDER BY source_rank"):
        entry = source_entry(db, word, max_forms_per_pos)
        if entry is None:
            continue
        old = db.execute("SELECT source_fingerprint FROM generation_word_status WHERE run_id=? AND word_id=?", (run_key, word["id"])).fetchone()
        if old is None:
            db.execute("INSERT INTO generation_word_status VALUES (?, ?, 'pending', 0, ?, '[]', NULL, ?)",
                       (run_key, word["id"], entry["source_fingerprint"], now()))
            count += 1
        elif refresh_stale and old["source_fingerprint"] != entry["source_fingerprint"]:
            db.execute("DELETE FROM generated_cloze_sentences WHERE run_id=? AND word_id=?", (run_key, word["id"]))
            db.execute("""UPDATE generation_word_status SET status='pending', attempts=0,
                       source_fingerprint=?, validation_errors_json='[]', last_error=NULL, updated_at=?
                       WHERE run_id=? AND word_id=?""", (entry["source_fingerprint"], now(), run_key, word["id"]))
            count += 1
    db.commit()
    return count


def prompt(entries: list[dict[str, Any]]) -> str:
    schema = {
        "headword": "exact source headword",
        "sentences": [{"rank": 1, "pos": "source POS", "sense_gloss": "exact source gloss", "en_text": "...", "th_text": "...", "cloze_target": "allowed source form", "is_emotional": True, "explanation_th": "..."}],
    }
    return f"""You generate source-grounded cloze content for a Thai English-learning app.
Return JSON only: an array containing exactly one object per SOURCE entry.

For each entry, return exactly 5 sentences in the supplied schema.
NON-NEGOTIABLE:
- Use only its supplied POS, exact sense_gloss values, and allowed_forms_by_pos. Do not add senses, POS, forms, or lexical facts.
- Every cloze_target must exactly occur in en_text and be one of the allowed forms for that sentence's POS (case-insensitive).
- Each sentence must name an exact supplied sense_gloss. Cover supplied POS when possible. Reuse a supplied form if fewer than five forms exist.
- rank 1 must be emotionally engaging; ranks are exactly 1 to 5.
- th_text naturally translates en_text. explanation_th stands alone: describe the context and why this word/form fits; include grammar only when useful. Do not reference another sentence.
- Keep English at A2/B1 level and concise. Thai fields must be Thai.
- Do not cite sources or output markdown.

OUTPUT SHAPE EXAMPLE (types only): {json.dumps(schema, ensure_ascii=False)}
SOURCE_ENTRIES: {json.dumps(entries, ensure_ascii=False, separators=(',', ':'))}"""


def parse_response(text: str) -> list[dict[str, Any]]:
    text = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("response root is not a JSON array")
    return data


def validate(item: dict[str, Any], source: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if item.get("headword", "").casefold() != source["headword"].casefold(): errors.append("headword mismatch")
    sentences = item.get("sentences")
    if not isinstance(sentences, list) or len(sentences) != 5: return errors + ["must contain exactly 5 sentences"]
    ranks = sorted(s.get("rank") for s in sentences if isinstance(s, dict))
    if ranks != [1, 2, 3, 4, 5]: errors.append("ranks must be exactly 1..5")
    source_glosses = {s["gloss"] for s in source["senses"]}
    for sentence in sentences:
        if not isinstance(sentence, dict): errors.append("sentence is not an object"); continue
        pos, gloss = sentence.get("pos"), sentence.get("sense_gloss")
        target, english = str(sentence.get("cloze_target", "")), str(sentence.get("en_text", ""))
        if pos not in source["allowed_forms_by_pos"]: errors.append(f"rank {sentence.get('rank')}: unsupported POS")
        elif target.casefold() not in {x.casefold() for x in source["allowed_forms_by_pos"][pos]}: errors.append(f"rank {sentence.get('rank')}: unsupported target")
        if gloss not in source_glosses: errors.append(f"rank {sentence.get('rank')}: non-source gloss")
        if not target or not re.search(re.escape(target), english, re.I): errors.append(f"rank {sentence.get('rank')}: target absent")
        if not re.search(r"[ก-๙]", str(sentence.get("th_text", ""))): errors.append(f"rank {sentence.get('rank')}: Thai translation missing")
        if not re.search(r"[ก-๙]", str(sentence.get("explanation_th", ""))): errors.append(f"rank {sentence.get('rank')}: Thai explanation missing")
    rank_one = next((s for s in sentences if s.get("rank") == 1), {})
    if rank_one.get("is_emotional") is not True: errors.append("rank 1 must be emotional")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-key", default="source-cloze-v1")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0, help="max pending words; 0 means all")
    parser.add_argument("--max-forms-per-pos", type=int, default=12)
    parser.add_argument("--refresh-stale", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="initialise/preview only; never call the API")
    args = parser.parse_args()
    if args.batch_size < 1 or args.max_forms_per_pos < 1: parser.error("batch sizes must be positive")
    db = connect(); ensure_schema(db); get_or_create_run(db, args.run_key, args.model, args)
    seeded = seed_statuses(db, args.run_key, args.max_forms_per_pos, args.refresh_stale)
    rows = list(db.execute("""SELECT w.* FROM generation_word_status g JOIN words w ON w.id=g.word_id
                            WHERE g.run_id=? AND g.status IN ('pending','failed') ORDER BY w.source_rank""", (args.run_key,)))
    if args.limit: rows = rows[:args.limit]
    print(f"run={args.run_key} seeded_or_refreshed={seeded} pending={len(rows)} batch_size={args.batch_size}")
    if args.dry_run:
        for word in rows[:3]:
            entry = source_entry(db, word, args.max_forms_per_pos)
            print(f"  {word['headword']}: {len(entry['senses'])} senses, forms={entry['allowed_forms_by_pos']}")
        return 0
    parser.error("External generation is disabled. Use Terra English TXT and translate_vocab_content.py.")


if __name__ == "__main__":
    raise SystemExit(main())
