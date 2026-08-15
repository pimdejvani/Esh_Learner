#!/usr/bin/env python3
"""Deterministically validate source-grounded generated vocabulary entries.

The generator stores one JSON candidate per row in ``generated_entries``.
This tool never calls a model: it compares each candidate directly with the
lexical evidence already normalized in ``vocabulary_source.db``.

The current pipeline stores one sentence per row in ``generated_cloze_sentences``
and word state in ``generation_word_status``.  Legacy full-entry JSON rows are
also supported through ``--entry-table``.  The validator can update pending
word states without calling a model.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "vocabulary_source.db"
THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
OTHER_SENTENCE_RE = re.compile(
    r"(?:ประโยค(?:ที่)?\s*\d|ตัวอย่าง(?:ที่)?\s*\d|ประโยคก่อนหน้า|ตัวอย่างอื่น|คำอธิบายด้านบน|ดังกล่าวข้างต้น)"
)
VALID_COUNTABILITY = {"countable", "uncountable", None}
VALID_FORM_KINDS = {"inflection", "derived"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_list(value: Any) -> bool:
    return isinstance(value, list)


def is_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def add(errors: list[str], path: str, message: str) -> None:
    errors.append(f"{path}: {message}")


def load_source(con: sqlite3.Connection, word_id: int) -> dict[str, Any]:
    word = con.execute("SELECT headword FROM words WHERE id=?", (word_id,)).fetchone()
    if word is None:
        raise ValueError(f"word_id={word_id} does not exist")
    senses: dict[str, set[str]] = defaultdict(set)
    for pos, gloss in con.execute(
        "SELECT pos, gloss FROM source_senses WHERE word_id=?", (word_id,)
    ):
        senses[pos].add(gloss)
    forms: dict[str, set[str]] = defaultdict(set)
    form_sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    for text, pos, source in con.execute(
        "SELECT form_text, pos, source_name FROM source_forms WHERE word_id=?", (word_id,)
    ):
        forms[text.casefold()].add(pos)
        form_sources[(text.casefold(), pos)].add(source)
    # The headword is an allowed form for every sourced POS, even when the
    # dictionary's forms array does not repeat its lemma.
    for pos in senses:
        forms[word[0].casefold()].add(pos)
    related: dict[str, set[str]] = defaultdict(set)
    related_sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    for candidate, pos, source in con.execute(
        "SELECT candidate, pos, source_name FROM source_related_candidates WHERE word_id=?", (word_id,)
    ):
        related[candidate.casefold()].add(pos)
        related_sources[(candidate.casefold(), pos)].add(source)
    return {
        "headword": word[0], "senses": senses, "forms": forms,
        "form_sources": form_sources, "related": related,
        "related_sources": related_sources,
    }


def validate_entry(candidate: Any, source: dict[str, Any]) -> list[str]:
    """Return stable, human-readable errors for one decoded candidate JSON."""
    errors: list[str] = []
    if not isinstance(candidate, dict):
        return ["$: candidate must be a JSON object"]
    if candidate.get("headword") != source["headword"]:
        add(errors, "headword", "must match the source headword exactly")

    parts = candidate.get("parts_of_speech")
    if not is_list(parts):
        add(errors, "parts_of_speech", "must be an array")
        parts = []
    generated_senses: set[tuple[str, str]] = set()
    generated_pos: set[str] = set()
    for index, part in enumerate(parts):
        path = f"parts_of_speech[{index}]"
        if not isinstance(part, dict):
            add(errors, path, "must be an object")
            continue
        pos = part.get("pos")
        if not is_string(pos) or pos not in source["senses"]:
            add(errors, f"{path}.pos", "is not a source-supported POS")
            continue
        generated_pos.add(pos)
        if part.get("countability") not in VALID_COUNTABILITY:
            add(errors, f"{path}.countability", "must be countable, uncountable, or null")
        meanings = part.get("meanings")
        if not is_list(meanings) or not meanings:
            add(errors, f"{path}.meanings", "must be a non-empty array")
            meanings = []
        for meaning_index, meaning in enumerate(meanings):
            mpath = f"{path}.meanings[{meaning_index}]"
            if not isinstance(meaning, dict):
                add(errors, mpath, "must be an object")
                continue
            if not is_string(meaning.get("thai")) or not THAI_RE.search(meaning.get("thai", "")):
                add(errors, f"{mpath}.thai", "must contain Thai text")
            gloss = meaning.get("source_gloss")
            if not is_string(gloss) or gloss not in source["senses"][pos]:
                add(errors, f"{mpath}.source_gloss", "must be a verbatim source gloss for this POS")
            else:
                generated_senses.add((pos, gloss))
    required_senses = {(pos, gloss) for pos, glosses in source["senses"].items() for gloss in glosses}
    if generated_pos != set(source["senses"]):
        add(errors, "parts_of_speech", "must contain exactly the source-supported POS set")
    if generated_senses != required_senses:
        add(errors, "parts_of_speech.meanings", "must contain every source gloss exactly once with no invented gloss")

    forms = candidate.get("word_family_and_forms", [])
    if not is_list(forms):
        add(errors, "word_family_and_forms", "must be an array")
        forms = []
    seen_forms: set[str] = set()
    for index, form in enumerate(forms):
        path = f"word_family_and_forms[{index}]"
        if not isinstance(form, dict):
            add(errors, path, "must be an object")
            continue
        word = form.get("word")
        if not is_string(word):
            add(errors, f"{path}.word", "must be a non-empty string")
            continue
        key = word.casefold()
        if key in seen_forms:
            add(errors, f"{path}.word", "is duplicated; merge its POS values into one record")
        seen_forms.add(key)
        pos_values = form.get("pos")
        if not is_list(pos_values) or not all(is_string(pos) for pos in pos_values):
            add(errors, f"{path}.pos", "must be a non-empty array of POS strings")
            continue
        supported = source["forms"].get(key, set())
        if set(pos_values) != supported:
            add(errors, f"{path}.pos", "must exactly match the source-supported POS for this spelling")
        if form.get("kind") not in VALID_FORM_KINDS:
            add(errors, f"{path}.kind", "must be inflection or derived")
        if form.get("meaning_th") is not None and (not is_string(form["meaning_th"]) or not THAI_RE.search(form["meaning_th"])):
            add(errors, f"{path}.meaning_th", "must be Thai text or JSON null")
        if not is_string(form.get("source")):
            add(errors, f"{path}.source", "must name the supporting source")
        elif any(form["source"] not in source["form_sources"].get((key, pos), set()) for pos in set(pos_values) if key != source["headword"].casefold()):
            add(errors, f"{path}.source", "does not support this form/POS combination")

    related_words = candidate.get("related_words", [])
    if not is_list(related_words):
        add(errors, "related_words", "must be an array")
        related_words = []
    if len(related_words) > 3:
        add(errors, "related_words", "may contain at most 3 candidates")
    for index, related in enumerate(related_words):
        path = f"related_words[{index}]"
        if not isinstance(related, dict):
            add(errors, path, "must be an object")
            continue
        word = related.get("word")
        pos_values = related.get("pos")
        if not is_string(word) or not is_list(pos_values) or not all(is_string(pos) for pos in pos_values):
            add(errors, path, "word and pos array are required")
            continue
        key = word.casefold()
        if not set(pos_values).issubset(source["related"].get(key, set())):
            add(errors, f"{path}.pos", "contains an invented related word or POS")
        for field in ("meaning_th", "relation_keyword", "relationship_th"):
            value = related.get(field)
            if not is_string(value) or not THAI_RE.search(value):
                add(errors, f"{path}.{field}", "must contain Thai text")
        source_name = related.get("source")
        if not is_string(source_name) or any(source_name not in source["related_sources"].get((key, pos), set()) for pos in set(pos_values)):
            add(errors, f"{path}.source", "does not support this related word/POS combination")

    cloze = candidate.get("cloze_examples")
    if not is_list(cloze) or len(cloze) != 5:
        add(errors, "cloze_examples", "must contain exactly 5 objects")
        cloze = []
    ranks: list[int] = []
    cloze_pos: set[str] = set()
    for index, example in enumerate(cloze):
        path = f"cloze_examples[{index}]"
        if not isinstance(example, dict):
            add(errors, path, "must be an object")
            continue
        rank = example.get("rank")
        if type(rank) is not int:
            add(errors, f"{path}.rank", "must be an integer")
        else:
            ranks.append(rank)
        pos = example.get("pos")
        if not is_string(pos) or pos not in source["senses"]:
            add(errors, f"{path}.pos", "is not a source-supported POS")
        else:
            cloze_pos.add(pos)
        en_text, th_text, target = example.get("en_text"), example.get("th_text"), example.get("cloze_target")
        if not is_string(en_text):
            add(errors, f"{path}.en_text", "must be a non-empty string")
        if not is_string(th_text) or not THAI_RE.search(th_text):
            add(errors, f"{path}.th_text", "must contain Thai text")
        if not is_string(target) or not is_string(en_text) or target not in en_text:
            add(errors, f"{path}.cloze_target", "must appear verbatim in en_text")
        elif is_string(pos) and target.casefold() not in source["forms"]:
            add(errors, f"{path}.cloze_target", "is not a source-supported form")
        elif is_string(pos) and pos not in source["forms"].get(target.casefold(), set()):
            add(errors, f"{path}.cloze_target", "is not source-supported for the stated POS")
        if type(example.get("is_emotional")) is not bool:
            add(errors, f"{path}.is_emotional", "must be a JSON boolean")
        explanation = example.get("explanation_th")
        if not is_string(explanation) or not THAI_RE.search(explanation):
            add(errors, f"{path}.explanation_th", "must contain a standalone Thai explanation")
        elif OTHER_SENTENCE_RE.search(explanation):
            add(errors, f"{path}.explanation_th", "must not refer to another sentence or example")
    if sorted(ranks) != [1, 2, 3, 4, 5]:
        add(errors, "cloze_examples.rank", "must contain each rank 1 through 5 exactly once")
    rank_one = next((item for item in cloze if isinstance(item, dict) and item.get("rank") == 1), None)
    if rank_one is None or rank_one.get("is_emotional") is not True:
        add(errors, "cloze_examples.rank=1", "must have is_emotional: true")
    if cloze_pos != set(source["senses"]):
        add(errors, "cloze_examples", "must cover every source-supported POS")
    return errors


def assert_entry_table(con: sqlite3.Connection, table: str) -> set[str]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        raise ValueError("entry table must be a simple SQLite identifier")
    columns = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
    required = {"id", "word_id", "candidate_json", "status", "validation_errors"}
    if not required.issubset(columns):
        raise ValueError(f"{table} must include columns: {', '.join(sorted(required))}")
    return columns


def validate_sentence_payload(payload: Any, rank: int, source: dict[str, Any]) -> list[str]:
    """Validate one generated cloze sentence (dict or decoded JSON)."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["$: payload must be a JSON object"]
    if "rank" in payload and payload["rank"] != rank:
        add(errors, "rank", "must match the row rank")
    pos = payload.get("pos")
    if not is_string(pos) or pos not in source["senses"]:
        add(errors, "pos", "is not a source-supported POS")
    target, en_text = payload.get("cloze_target"), payload.get("en_text")
    if not is_string(en_text):
        add(errors, "en_text", "must be a non-empty string")
    if not is_string(target) or not is_string(en_text) or target not in en_text:
        add(errors, "cloze_target", "must appear verbatim in en_text")
    elif target.casefold() not in source["forms"]:
        add(errors, "cloze_target", "is not a source-supported form")
    elif is_string(pos) and pos not in source["forms"].get(target.casefold(), set()):
        add(errors, "cloze_target", "is not source-supported for the stated POS")
    for field in ("th_text", "explanation_th"):
        value = payload.get(field)
        if not is_string(value) or not THAI_RE.search(value):
            add(errors, field, "must contain Thai text")
    explanation = payload.get("explanation_th")
    if is_string(explanation) and OTHER_SENTENCE_RE.search(explanation):
        add(errors, "explanation_th", "must not refer to another sentence or example")
    if type(payload.get("is_emotional")) is not bool:
        add(errors, "is_emotional", "must be a JSON boolean")
    if rank == 1 and payload.get("is_emotional") is not True:
        add(errors, "is_emotional", "must be true for rank 1")
    # If a generator includes a source gloss in its sentence payload, it must
    # be verbatim.  This catches invented sense labels without requiring the
    # sentence-only table to duplicate all lexical fields.
    if "source_gloss" in payload and payload["source_gloss"] not in source["senses"].get(pos, set()):
        add(errors, "source_gloss", "must be a verbatim source gloss for this POS")
    return errors


def run_generation_tables(con: sqlite3.Connection, args: argparse.Namespace) -> int:
    """Validate pending ``generation_word_status`` rows and update them."""
    status_columns = {row[1] for row in con.execute("PRAGMA table_info(generation_word_status)")}
    sentence_columns = {row[1] for row in con.execute("PRAGMA table_info(generated_cloze_sentences)")}
    required_status = {"run_id", "word_id", "status", "validation_errors_json"}
    required_sentences = {
        "run_id", "word_id", "rank", "pos", "sense_gloss", "en_text",
        "th_text", "cloze_target", "is_emotional", "explanation_th",
    }
    if not required_status.issubset(status_columns) or not required_sentences.issubset(sentence_columns):
        raise ValueError("generation tables do not have the required pipeline columns")
    where, params = ["status=?"], [args.status]
    if args.run_id is not None:
        where.append("run_id=?")
        params.append(args.run_id)
    words = con.execute(
        "SELECT run_id, word_id FROM generation_word_status WHERE " + " AND ".join(where) + " ORDER BY run_id, word_id",
        params,
    ).fetchall()
    passed = failed = 0
    for run_id, word_id in words:
        errors: list[str] = []
        try:
            source = load_source(con, word_id)
            rows = con.execute(
                "SELECT rank, pos, sense_gloss, en_text, th_text, cloze_target, is_emotional, explanation_th "
                "FROM generated_cloze_sentences WHERE run_id=? AND word_id=? ORDER BY rank",
                (run_id, word_id),
            ).fetchall()
            ranks = [row[0] for row in rows]
            if ranks != [1, 2, 3, 4, 5]:
                errors.append("cloze_examples.rank: must contain exactly ranks 1 through 5")
            seen_pos: set[str] = set()
            for row in rows:
                rank, pos, sense_gloss, en_text, th_text, cloze_target, is_emotional, explanation_th = row
                try:
                    payload = {
                        "rank": rank, "pos": pos, "source_gloss": sense_gloss,
                        "en_text": en_text, "th_text": th_text,
                        "cloze_target": cloze_target, "is_emotional": bool(is_emotional)
                        if type(is_emotional) is int and is_emotional in (0, 1) else is_emotional,
                        "explanation_th": explanation_th,
                    }
                    if is_string(pos):
                        seen_pos.add(pos)
                    errors.extend(f"rank {rank}.{error}" for error in validate_sentence_payload(payload, rank, source))
                except TypeError as error:
                    errors.append(f"rank {rank}: invalid sentence data: {error}")
            if rows and seen_pos != set(source["senses"]):
                errors.append("cloze_examples: must cover every source-supported POS")
        except ValueError as error:
            errors.append(f"$: invalid source data: {error}")
        state = "passed" if not errors else "failed"
        passed += not bool(errors)
        failed += bool(errors)
        print(json.dumps({"run_id": run_id, "word_id": word_id, "status": state, "errors": errors}, ensure_ascii=False))
        if args.update_status:
            assignments = ["status=?", "validation_errors_json=?"]
            values: list[Any] = [state, json.dumps(errors, ensure_ascii=False)]
            if "updated_at" in status_columns:
                assignments.append("validated_at=?")
                values.append(utc_now())
            con.execute(
                "UPDATE generation_word_status SET " + ", ".join(assignments) + " WHERE run_id=? AND word_id=?",
                (*values, run_id, word_id),
            )
    if args.update_status:
        con.commit()
    print(json.dumps({"checked": len(words), "passed": passed, "failed": failed}, ensure_ascii=False))
    return 1 if failed else 0


def run(args: argparse.Namespace) -> int:
    con = sqlite3.connect(args.db)
    try:
        has_generation_tables = {
            row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if args.entry_table == "generation" or (args.entry_table == "auto" and {"generation_word_status", "generated_cloze_sentences"}.issubset(has_generation_tables)):
            return run_generation_tables(con, args)
        if args.entry_table == "auto":
            args.entry_table = "generated_entries"
        columns = assert_entry_table(con, args.entry_table)
        where, params = ["status=?"], [args.status]
        if args.batch_id is not None:
            if "batch_id" not in columns:
                raise ValueError(f"{args.entry_table} has no batch_id column")
            where.append("batch_id=?")
            params.append(args.batch_id)
        rows = con.execute(
            f"SELECT id, word_id, candidate_json FROM {args.entry_table} WHERE {' AND '.join(where)} ORDER BY id",
            params,
        ).fetchall()
        passed = failed = 0
        for entry_id, word_id, raw_json in rows:
            try:
                candidate = json.loads(raw_json)
                errors = validate_entry(candidate, load_source(con, word_id))
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                errors = [f"$: invalid candidate/source data: {error}"]
            state = "passed" if not errors else "human_review"
            passed += not bool(errors)
            failed += bool(errors)
            print(json.dumps({"id": entry_id, "status": state, "errors": errors}, ensure_ascii=False))
            if args.update_status:
                updates = {"status": state, "validation_errors": json.dumps(errors, ensure_ascii=False)}
                if "validated_at" in columns:
                    updates["validated_at"] = utc_now()
                con.execute(
                    f"UPDATE {args.entry_table} SET " + ", ".join(f"{key}=?" for key in updates) + " WHERE id=?",
                    (*updates.values(), entry_id),
                )
        if args.update_status:
            con.commit()
        print(json.dumps({"checked": len(rows), "passed": passed, "human_review": failed}, ensure_ascii=False))
        return 1 if failed else 0
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--entry-table", default="auto", help="auto (default), generation, or legacy candidate table name")
    parser.add_argument("--batch-id", type=int)
    parser.add_argument("--run-id", help="generation_runs id when using generation tables")
    parser.add_argument("--status", default="pending", help="candidate status to validate (default: pending)")
    parser.add_argument("--update-status", action="store_true")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
