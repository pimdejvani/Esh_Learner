#!/usr/bin/env python3
"""Merge exact-match grammar notes and generate only stale/missing notes.

All output is confined to a caller-selected directory below ``staging/``.
The translated input and the old candidate are read-only.  SQLite checkpoints
make repeated invocations resume-safe; production promotion is deliberately
outside this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from grammar_explanation_pipeline import (
    DEFAULT_POLICY_FILE,
    load_generation_policy,
    validate_explanations,
    validate_text,
)


ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "staging"
DEFAULT_OLD = STAGING / (
    "grammar_production_candidate_20260831-071557-grammar-26-2967-bd9cfe09ead9/merged"
)
DEFAULT_MODEL = "gemini-2.5-flash-lite"


class MergeError(ValueError):
    pass


@dataclass(frozen=True)
class DraftRow:
    headword: str
    rank: int
    fields: tuple[str, ...]
    file_name: str
    ordinal: int

    @property
    def source_fields(self) -> tuple[str, ...]:
        """Fields whose exact equality authorizes reuse (rank through en_text)."""
        return self.fields[:6]

    @property
    def explanation(self) -> str:
        return self.fields[7].strip()

    def prompt_row(self) -> dict:
        return {
            "headword": self.headword,
            "rank": self.rank,
            "sense_id": int(self.fields[1]),
            "pos": self.fields[2],
            "target": self.fields[3],
            "is_emotional": self.fields[4] == "1",
            "en_text": self.fields[5],
            "th_text": self.fields[6],
        }


def _files_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(directory.glob("*.txt"))
    if not paths:
        raise MergeError(f"no .txt files in {directory}")
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def parse_drafts(directory: Path) -> list[DraftRow]:
    rows: list[DraftRow] = []
    seen: set[tuple[str, int]] = set()
    ordinal = 0
    for path in sorted(directory.glob("*.txt")):
        headword: str | None = None
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw or raw.startswith("#"):
                continue
            if raw.startswith("@ "):
                headword = raw[2:].strip().casefold()
                if not headword:
                    raise MergeError(f"{path.name}:{number}: empty headword")
                continue
            if headword is None:
                raise MergeError(f"{path.name}:{number}: row before headword")
            fields = tuple(raw.split("\t"))
            if len(fields) != 8:
                raise MergeError(f"{path.name}:{number}: expected 8 fields, got {len(fields)}")
            try:
                rank = int(fields[0])
                int(fields[1])
            except ValueError as exc:
                raise MergeError(f"{path.name}:{number}: invalid rank or sense_id") from exc
            if rank not in range(1, 6) or fields[4] not in {"0", "1"}:
                raise MergeError(f"{path.name}:{number}: invalid rank or is_emotional")
            key = (headword, rank)
            if key in seen:
                raise MergeError(f"duplicate row {key}")
            seen.add(key)
            rows.append(DraftRow(headword, rank, fields, path.name, ordinal))
            ordinal += 1
    by_word: dict[str, set[int]] = {}
    for row in rows:
        by_word.setdefault(row.headword, set()).add(row.rank)
    bad = {word: sorted(ranks) for word, ranks in by_word.items() if ranks != set(range(1, 6))}
    if bad:
        word, ranks = next(iter(bad.items()))
        raise MergeError(f"{word}: ranks {ranks} != [1, 2, 3, 4, 5]")
    return rows


def reusable_explanations(
    current: list[DraftRow], old: list[DraftRow], validator_rules: dict
) -> dict[tuple[str, int], str]:
    old_by_key = {(row.headword, row.rank): row for row in old}
    result: dict[tuple[str, int], str] = {}
    for row in current:
        prior = old_by_key.get((row.headword, row.rank))
        if (
            prior is not None
            and prior.source_fields == row.source_fields
            and prior.explanation
            and not validate_text(prior.explanation, validator_rules)
        ):
            result[(row.headword, row.rank)] = prior.explanation
    return result


def _input_item(rows: list[DraftRow]) -> dict:
    return {
        "seq": min(row.ordinal for row in rows) + 1,
        "headword": rows[0].headword,
        "forms": [],
        "sentences": [
            {
                "rank": row.rank,
                "sense_id": int(row.fields[1]),
                "pos": row.fields[2],
                "target": row.fields[3],
                "sentence": row.fields[5],
                "gloss": row.fields[6] or "คำแปลภาษาไทย",
            }
            for row in sorted(rows, key=lambda item: item.rank)
        ],
    }


def validate_word(rows: list[DraftRow], explanations: dict[int, str], validator_rules: dict) -> list[str]:
    raw = {
        "explanations": [
            {"rank": rank, "input_ok": True, "input_error": "", "explanation_th": explanations.get(rank, "")}
            for rank in range(1, 6)
        ]
    }
    _, errors = validate_explanations(raw, validator_rules, _input_item(rows))
    # The production requirement is stricter than the legacy validator: no two
    # explanations within a word may be exactly equal, even if only 2-4 match.
    normalized = ["".join(explanations.get(rank, "").casefold().split()) for rank in range(1, 6)]
    if len(set(normalized)) != 5:
        errors.append("duplicate-within-word")
    return errors


def _rank_errors(errors: list[str]) -> set[int]:
    result: set[int] = set()
    for error in errors:
        if error.startswith("rank-"):
            try:
                result.add(int(error.split(":", 1)[0][5:]))
            except ValueError:
                pass
    return result


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_prompt(rows: list[DraftRow], previous_errors: dict[tuple[str, int], list[str]]) -> str:
    payload = []
    for row in rows:
        item = row.prompt_row()
        errors = previous_errors.get((row.headword, row.rank), [])
        if errors:
            item["previous_validation_errors"] = errors
        payload.append(item)
    return """You write production-ready Thai grammar explanations for an English-learning app.
Return one JSON object only: {"explanations":[{"headword":"...","rank":1,"explanation_th":"..."}]}.
Return exactly one row for every input row, with headword and rank copied exactly.

For each explanation: use 30-240 characters of natural Thai; make it fully standalone; explain the
target's meaning in this exact sentence, its part of speech and grammatical role, and why this exact
form fits. Use only facts visible in that row. Never mention another sentence, an example/rank number,
or text above/below. Do not copy one template across rows. Explanations for the same headword must be
meaningfully distinct. Do not emit tabs or newlines inside explanation_th.

Validation details: when the target is an adjective immediately after am/is/are/was/were, explicitly
say in Thai that it is "ส่วนเติมเต็ม" of that linking verb; do not call it a noun modifier. Keep every
answer at most 220 characters. If previous_validation_errors are supplied, correct each named error.

INPUT JSON:
""" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def call_gemini(api_key: str, model: str, rows: list[DraftRow], errors: dict) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=build_prompt(rows, errors),
        config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"),
    )
    return json.loads(response.text)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def open_state(
    output_dir: Path,
    rows: list[DraftRow],
    reused: dict[tuple[str, int], str],
    binding: dict,
) -> sqlite3.Connection:
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output_dir / "state.sqlite3")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rows(
            headword TEXT NOT NULL, rank INTEGER NOT NULL, file_name TEXT NOT NULL,
            ordinal INTEGER NOT NULL, fields_json TEXT NOT NULL, status TEXT NOT NULL,
            explanation TEXT, provenance TEXT, attempts INTEGER NOT NULL DEFAULT 0,
            errors_json TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY(headword, rank)
        );
    """)
    encoded = json.dumps(binding, sort_keys=True, separators=(",", ":"))
    stored = connection.execute("SELECT value FROM meta WHERE key='binding'").fetchone()
    if stored and stored[0] != encoded:
        connection.close()
        raise MergeError("checkpoint binding does not match current inputs/options")
    with connection:
        if not stored:
            connection.execute("INSERT INTO meta VALUES('binding',?)", (encoded,))
        for row in rows:
            explanation = reused.get((row.headword, row.rank))
            connection.execute(
                "INSERT OR IGNORE INTO rows VALUES(?,?,?,?,?,?,?,?,0,'[]')",
                (row.headword, row.rank, row.file_name, row.ordinal,
                 json.dumps(row.fields, ensure_ascii=False),
                 "reused" if explanation else "pending", explanation,
                 "exact-old-match" if explanation else None),
            )
    if connection.execute("SELECT count(*) FROM rows").fetchone()[0] != len(rows):
        connection.close()
        raise MergeError("checkpoint row set does not match input")
    return connection


def _parse_response(raw: object, expected: set[tuple[str, int]], validator_rules: dict) -> dict[tuple[str, int], str]:
    if not isinstance(raw, dict) or set(raw) != {"explanations"} or not isinstance(raw["explanations"], list):
        raise MergeError("Gemini response schema")
    result: dict[tuple[str, int], str] = {}
    for item in raw["explanations"]:
        if not isinstance(item, dict) or set(item) != {"headword", "rank", "explanation_th"}:
            raise MergeError("Gemini response row schema")
        if not isinstance(item["headword"], str) or not isinstance(item["rank"], int) or not isinstance(item["explanation_th"], str):
            raise MergeError("Gemini response row types")
        key = (item["headword"].casefold(), item["rank"])
        if key in result:
            raise MergeError(f"duplicate generated key {key}")
        errors = validate_text(item["explanation_th"].strip(), validator_rules)
        if errors:
            raise MergeError(f"{key}: {','.join(errors)}")
        result[key] = item["explanation_th"].strip()
    if set(result) != expected:
        raise MergeError("Gemini response keys do not exactly match request")
    return result


def materialize(connection: sqlite3.Connection, source_dir: Path, output_dir: Path, binding: dict) -> dict:
    explanations = {
        (word, rank): explanation
        for word, rank, explanation in connection.execute(
            "SELECT headword,rank,explanation FROM rows WHERE status IN ('reused','generated')"
        )
    }
    merged_dir = output_dir / "merged"
    merged_dir.mkdir(exist_ok=True)
    hashes: dict[str, str] = {}
    for source in sorted(source_dir.glob("*.txt")):
        headword: str | None = None
        lines = []
        for raw in source.read_text(encoding="utf-8").splitlines():
            if raw.startswith("@ "):
                headword = raw[2:].strip().casefold()
                lines.append(raw)
            elif not raw or raw.startswith("#"):
                lines.append(raw)
            else:
                fields = raw.split("\t")
                key = (headword or "", int(fields[0]))
                lines.append("\t".join(fields[:7] + [explanations.get(key, "")]))
        value = "\n".join(lines) + "\n"
        _atomic_text(merged_dir / source.name, value)
        hashes[source.name] = hashlib.sha256(value.encode("utf-8")).hexdigest()
    counts = dict(connection.execute("SELECT status,count(*) FROM rows GROUP BY status"))
    for status in ("reused", "generated", "pending", "quarantine"):
        counts.setdefault(status, 0)
    quarantine = [
        {"headword": word, "rank": rank, "attempts": attempts, "errors": json.loads(errors)}
        for word, rank, attempts, errors in connection.execute(
            "SELECT headword,rank,attempts,errors_json FROM rows WHERE status='quarantine' ORDER BY ordinal"
        )
    ]
    manifest = {**binding, "counts": counts, "complete": counts["pending"] == 0 and counts["quarantine"] == 0,
                "quarantine": quarantine, "output_files": hashes}
    _atomic_text(output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def _chunks(words: list[str], rows_by_word: dict[str, list[DraftRow]], maximum_rows: int) -> list[list[str]]:
    result: list[list[str]] = []
    current: list[str] = []
    size = 0
    for word in words:
        pending_size = len(rows_by_word[word])
        if current and size + pending_size > maximum_rows:
            result.append(current)
            current, size = [], 0
        current.append(word)
        size += pending_size
    if current:
        result.append(current)
    return result


def run_merge(args: argparse.Namespace, generator: Callable | None = None) -> dict:
    output_dir = args.output_dir.resolve()
    if output_dir == STAGING.resolve() or STAGING.resolve() not in output_dir.parents:
        raise MergeError("output-dir must be a child of the repository staging directory")
    current = parse_drafts(args.translated_dir)
    old = parse_drafts(args.old_candidate_dir)
    policy, policy_bytes = load_generation_policy(args.policy_file)
    rules = policy["validator_rules"]
    reused = reusable_explanations(current, old, rules)
    binding = {
        "translated_dir": str(args.translated_dir.resolve()),
        "translated_sha256": _files_digest(args.translated_dir),
        "old_candidate_dir": str(args.old_candidate_dir.resolve()),
        "old_candidate_sha256": _files_digest(args.old_candidate_dir),
        "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "model": args.model,
        "batch_rows": args.batch_rows,
    }
    connection = open_state(output_dir, current, reused, binding)
    if getattr(args, "retry_quarantine", False):
        with connection:
            connection.execute(
                "UPDATE rows SET status='pending',attempts=0 WHERE status='quarantine'"
            )
    all_by_word: dict[str, list[DraftRow]] = {}
    for row in current:
        all_by_word.setdefault(row.headword, []).append(row)

    # Reused content must pass the same applicable checks. Rank-specific errors
    # invalidate that reused row. Exact duplicates cannot coexist within a word.
    # If a complete reused word fails a holistic check, regenerate the word.
    with connection:
        for word, rows in all_by_word.items():
            values = dict(connection.execute(
                "SELECT rank,explanation FROM rows WHERE headword=? AND explanation IS NOT NULL", (word,)
            ))
            errors = validate_word(rows, values, rules)
            invalidate = _rank_errors(errors) & set(values)
            normalized: dict[str, list[int]] = {}
            for rank, value in values.items():
                normalized.setdefault("".join(value.casefold().split()), []).append(rank)
            for duplicate_ranks in normalized.values():
                invalidate.update(duplicate_ranks[1:])
            if len(values) == 5 and errors:
                invalidate = set(range(1, 6))
            for rank in invalidate:
                connection.execute(
                    "UPDATE rows SET status='pending',explanation=NULL,provenance=NULL WHERE headword=? AND rank=?",
                    (word, rank),
                )

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY")
    if generator is None:
        if not api_key:
            api_key = _load_env(ROOT / ".env").get("GEMINI_API_KEY") or _load_env(ROOT / ".env").get("API_KEY")
        if not api_key:
            connection.close()
            raise MergeError("GEMINI_API_KEY or API_KEY is required")
        generator = lambda rows, errors: call_gemini(api_key, args.model, rows, errors)

    while True:
        pending_records = connection.execute(
            "SELECT headword,rank,attempts,errors_json FROM rows WHERE status='pending' AND attempts < ? ORDER BY ordinal",
            (args.max_attempts,),
        ).fetchall()
        if not pending_records:
            break
        pending_keys = {(word, rank) for word, rank, _, _ in pending_records}
        pending_by_word = {
            word: [row for row in rows if (word, row.rank) in pending_keys]
            for word, rows in all_by_word.items()
            if any((word, row.rank) in pending_keys for row in rows)
        }
        batches = _chunks(list(pending_by_word), pending_by_word, args.batch_rows)

        def invoke(words: list[str]):
            batch_rows = [row for word in words for row in pending_by_word[word]]
            prior = {
                (word, rank): json.loads(errors_json)
                for word, rank, _, errors_json in pending_records
                if word in words
            }
            return words, batch_rows, generator(batch_rows, prior)

        futures = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(invoke, batch): batch for batch in batches}
            for future in as_completed(futures):
                requested_words = futures[future]
                batch_rows = [row for word in requested_words for row in pending_by_word[word]]
                try:
                    words, batch_rows, raw = future.result()
                    expected = {(row.headword, row.rank) for row in batch_rows}
                    generated = _parse_response(raw, expected, rules)
                    batch_error = None
                except Exception as exc:
                    generated = {}
                    batch_error = f"{type(exc).__name__}:{exc}"
                    words = requested_words
                with connection:
                    for word in words:
                        word_generated = {rank: text for (headword, rank), text in generated.items() if headword == word}
                        existing = dict(connection.execute(
                            "SELECT rank,explanation FROM rows WHERE headword=? AND explanation IS NOT NULL", (word,)
                        ))
                        combined = {**existing, **word_generated}
                        errors = [batch_error] if batch_error else (
                            validate_word(all_by_word[word], combined, rules) if len(combined) == 5 else []
                        )
                        requested_ranks = [row.rank for row in pending_by_word[word]]
                        if not errors and len(combined) == 5:
                            for rank in requested_ranks:
                                connection.execute(
                                    "UPDATE rows SET status='generated',explanation=?,provenance=?,attempts=attempts+1,errors_json='[]' "
                                    "WHERE headword=? AND rank=?",
                                    (word_generated[rank], args.model, word, rank),
                                )
                        else:
                            encoded_errors = json.dumps(errors or ["incomplete-word"], ensure_ascii=False)
                            for rank in requested_ranks:
                                connection.execute(
                                    "UPDATE rows SET attempts=attempts+1,errors_json=? WHERE headword=? AND rank=?",
                                    (encoded_errors, word, rank),
                                )
                            if not batch_error:
                                reused_ranks = set(existing) - set(requested_ranks)
                                implicated = _rank_errors(errors) & reused_ranks
                                holistic = any(not error.startswith("rank-") for error in errors)
                                if holistic:
                                    implicated = reused_ranks
                                for rank in implicated:
                                    connection.execute(
                                        "UPDATE rows SET status='pending',explanation=NULL,provenance=NULL,errors_json=? "
                                        "WHERE headword=? AND rank=?",
                                        (encoded_errors, word, rank),
                                    )
                materialize(connection, args.translated_dir, output_dir, binding)

    with connection:
        connection.execute(
            "UPDATE rows SET status='quarantine' WHERE status='pending' AND attempts >= ?", (args.max_attempts,)
        )
    manifest = materialize(connection, args.translated_dir, output_dir, binding)
    connection.close()
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translated-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--old-candidate-dir", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--policy-file", type=Path, default=DEFAULT_POLICY_FILE)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-rows", type=int, default=50)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--retry-quarantine", action="store_true",
        help="reset quarantined rows to pending after improving prompts or models",
    )
    parser.add_argument("--api-key", help=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.batch_rows < 5 or args.workers < 1 or args.max_attempts < 1:
        raise MergeError("batch-rows >= 5, workers >= 1, and max-attempts >= 1 are required")
    manifest = run_merge(args)
    print(json.dumps(manifest, ensure_ascii=False))
    return 0 if manifest["complete"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
