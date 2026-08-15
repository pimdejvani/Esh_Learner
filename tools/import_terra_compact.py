#!/usr/bin/env python3
"""Import compact, tab-separated Terra cloze drafts without an API call.

Format v2 is documented in ``terra_compact_format.md``. A word header is
``@ headword``.  Each following sentence has eight tab-separated fields:
rank, source_senses.id, POS, target, emotional 0|1, English, Thai, explanation.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import generate_source_cloze as generator


ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "data" / "terra_translated_drafts"
RUN_KEY = "terra-source-cloze-v1"
MODEL = "gpt-5.6-terra"


def parse_file(path: Path) -> tuple[dict[str, list[dict]], list[str]]:
    entries: dict[str, list[dict]] = {}
    errors: list[str] = []
    headword: str | None = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("@ "):
            headword = line[2:].strip()
            if not headword:
                errors.append(f"{path.name}:{number}: empty headword header")
            continue
        if headword is None:
            errors.append(f"{path.name}:{number}: sentence appears before @ headword header")
            continue
        fields = line.split("\t")
        if len(fields) != 8:
            errors.append(f"{path.name}:{number}: expected 8 tab-separated fields")
            continue
        rank, sense_id, pos, target, emotional, en, th, explanation = fields
        try:
            rank_int = int(rank)
            sense_id_int = int(sense_id)
            emotional_bool = {"0": False, "1": True}[emotional]
        except (ValueError, KeyError):
            errors.append(f"{path.name}:{number}: rank/sense_id must be integers and emotional must be 0 or 1")
            continue
        entries.setdefault(headword.strip().casefold(), []).append(
            {"rank": rank_int, "sense_id": sense_id_int, "pos": pos,
             "cloze_target": target, "is_emotional": emotional_bool,
             "en_text": en, "th_text": th, "explanation_th": explanation}
        )
    return entries, errors


def ensure_run(db: sqlite3.Connection) -> None:
    if db.execute("SELECT 1 FROM generation_runs WHERE id=?", (RUN_KEY,)).fetchone() is None:
        db.execute(
            "INSERT INTO generation_runs VALUES (?, ?, ?, ?, ?, ?)",
            (RUN_KEY, "terra-source-cloze-compact-v1", MODEL, generator.now(), generator.now(),
             json.dumps({"draft_format": "tab-separated-v1"}, sort_keys=True)),
        )


def save(db: sqlite3.Connection, word_id: int, source: dict, item: dict, errors: list[str]) -> None:
    status = "passed" if not errors else "failed"
    db.execute(
        """INSERT INTO generation_word_status
        (run_id,word_id,status,attempts,source_fingerprint,validation_errors_json,last_error,updated_at)
        VALUES (?,?,?,1,?,?,?,?)
        ON CONFLICT(run_id,word_id) DO UPDATE SET
          status=excluded.status, attempts=generation_word_status.attempts+1,
          source_fingerprint=excluded.source_fingerprint,
          validation_errors_json=excluded.validation_errors_json,
          last_error=excluded.last_error, updated_at=excluded.updated_at""",
        (RUN_KEY, word_id, status, source["source_fingerprint"], json.dumps(errors, ensure_ascii=False),
         "; ".join(errors)[:2000] or None, generator.now()),
    )
    db.execute("DELETE FROM generated_cloze_sentences WHERE run_id=? AND word_id=?", (RUN_KEY, word_id))
    if status == "passed":
        db.executemany(
            """INSERT INTO generated_cloze_sentences VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            [(RUN_KEY, word_id, sentence["rank"], sentence["pos"], sentence["sense_gloss"],
              sentence["en_text"], sentence["th_text"], sentence["cloze_target"],
              int(sentence["is_emotional"]), sentence["explanation_th"],
              source["source_fingerprint"], generator.now()) for sentence in item["sentences"]],
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    files = sorted(args.draft_dir.glob("*.txt")) if args.draft_dir.exists() else []
    all_entries: dict[str, list[dict]] = {}
    parse_errors: list[str] = []
    for path in files:
        entries, errors = parse_file(path)
        all_entries.update(entries)
        parse_errors.extend(errors)
    print(f"draft_dir={args.draft_dir} files={len(files)} headwords={len(all_entries)} parse_errors={len(parse_errors)}")
    for error in parse_errors:
        print(error, file=sys.stderr)
    if args.dry_run:
        return 1 if parse_errors else 0
    db = generator.connect()
    try:
        generator.ensure_schema(db)
        ensure_run(db)
        passed = failed = skipped = 0
        for normalized_headword, sentences in all_entries.items():
            word = db.execute("SELECT * FROM words WHERE lower(headword)=?", (normalized_headword,)).fetchone()
            if word is None:
                print(f"unknown headword: {normalized_headword}", file=sys.stderr); skipped += 1; continue
            source = generator.source_entry(db, word, 12)
            if source is None:
                print(f"no source senses: {word['headword']}", file=sys.stderr); skipped += 1; continue
            errors: list[str] = []
            for sentence in sentences:
                sense = db.execute("SELECT word_id,pos,gloss FROM source_senses WHERE id=?", (sentence.pop("sense_id"),)).fetchone()
                if sense is None or sense["word_id"] != word["id"]:
                    errors.append(f"rank {sentence.get('rank')}: sense_id is not for this headword")
                elif sense["pos"] != sentence["pos"]:
                    errors.append(f"rank {sentence.get('rank')}: POS does not match sense_id")
                else:
                    sentence["sense_gloss"] = sense["gloss"]
            item = {"headword": word["headword"], "sentences": sentences}
            errors.extend(generator.validate(item, source))
            save(db, word["id"], source, item, errors)
            passed += not bool(errors); failed += bool(errors)
        db.commit()
    finally:
        db.close()
    print(f"run={RUN_KEY} passed={passed} failed={failed} skipped={skipped}")
    return 1 if parse_errors or failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
