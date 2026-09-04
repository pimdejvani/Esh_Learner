#!/usr/bin/env python3
"""Prepare, generate, and validate Thai per-sentence grammar explanations.

The tool never edits canonical drafts or SQLite.  Inputs and results are JSONL/
TSV staging artifacts so a reviewer must explicitly promote accepted output.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import difflib
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
THAI_RE = re.compile(r"[\u0e01-\u0e5b]")
CROSS_REF_RE = re.compile(
    r"ประโยคก่อนหน้า|ประโยคถัดไป|ประโยค(?:แรก|ด้านบน|ด้านล่าง)|"
    r"ตัวอย่างที่\s*\d|ประโยคที่\s*\d|ข้อที่\s*\d|ข้างต้น|"
    r"\b(?:rank|example)\s*\d+\b|\b(?:previous|next|above|below)\s+(?:sentence|example)\b",
    re.IGNORECASE,
)
SPACE_RE = re.compile(r"\s+")
PIPELINE_STATE_VERSION = 2
VALIDATOR_VERSION = "2026-08-31-production-v15"
OUTPUT_SCHEMA_VERSION = 1
DEFAULT_PROMPT_FILE = ROOT / "config/grammar_explanation_prompt_production_v15.txt"
DEFAULT_POLICY_FILE = ROOT / "config/grammar_explanation_policy_v4.json"
INPUT_KEYS = {"seq", "headword", "forms", "sentences"}
SENTENCE_KEYS = {"rank", "sense_id", "pos", "target", "sentence", "gloss"}
OUTPUT_KEYS = {"explanations"}
OUTPUT_ROW_KEYS = {"rank", "input_ok", "input_error", "explanation_th"}
TERMINAL_STATUSES = {"accepted", "quarantine", "input-quarantine"}


def read_manifest(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        rows.append({"seq": int(fields[0]), "headword": fields[3].casefold(), "source_file": fields[4]})
    return rows


def parse_snapshot(directory: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(directory.glob("*.txt")):
        headword = None
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line or line.startswith("#"):
                continue
            if line.startswith("@ "):
                headword = line[2:].strip().casefold()
                if headword in result:
                    raise ValueError(f"duplicate headword in snapshot: {headword}")
                result[headword] = []
                continue
            if headword is None:
                raise ValueError(f"{path}:{number}: row before headword")
            fields = line.split("\t")
            if len(fields) < 6:
                raise ValueError(f"{path}:{number}: expected at least 6 fields")
            result[headword].append(
                {"rank": int(fields[0]), "sense_id": int(fields[1]), "pos": fields[2],
                 "target": fields[3], "sentence": fields[5]}
            )
    return result


def load_evidence(db_path: Path) -> tuple[dict[int, str], dict[str, list[str]]]:
    connection = sqlite3.connect(db_path)
    try:
        gloss = {int(row[0]): row[1] for row in connection.execute("SELECT id, gloss FROM source_senses")}
        forms: dict[str, list[str]] = defaultdict(list)
        for headword, form in connection.execute(
            "SELECT w.headword, f.form_text FROM source_forms f JOIN words w ON w.id=f.word_id"
        ):
            if form not in forms[headword.casefold()]:
                forms[headword.casefold()].append(form)
        return gloss, dict(forms)
    finally:
        connection.close()


def load_existing(directory: Path) -> tuple[dict[tuple[str, int], str], list[dict[str, Any]]]:
    candidates: dict[tuple[str, int], list[tuple[str, str, int]]] = defaultdict(list)
    anomalies = []
    validator_rules = load_generation_policy(DEFAULT_POLICY_FILE)[0]["validator_rules"]
    for path in sorted(directory.glob("*.tsv")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            fields = line.split("\t")
            if len(fields) != 3:
                anomalies.append({"file": path.name, "line": number, "code": "field-count"})
                continue
            headword, rank_text, explanation = fields
            try:
                rank = int(rank_text)
            except ValueError:
                rank = -1
            if rank not in range(1, 6):
                anomalies.append({"file": path.name, "line": number, "code": "rank", "value": rank_text})
                continue
            key = (headword.casefold(), rank)
            candidates[key].append((explanation.strip(), path.name, number))
    valid: dict[tuple[str, int], str] = {}
    for key, rows in candidates.items():
        if len(rows) != 1:
            for _, file_name, number in rows[1:]:
                anomalies.append({"file": file_name, "line": number, "code": "duplicate-key"})
            continue
        explanation, file_name, number = rows[0]
        text_errors = validate_text(explanation, validator_rules)
        for code in text_errors:
            anomalies.append({"file": file_name, "line": number, "code": code})
        if not text_errors:
            valid[key] = explanation
    return valid, anomalies


def normalize(value: str) -> str:
    return SPACE_RE.sub("", value.casefold())


def template_similarity(left: str, right: str) -> float:
    """Conservatively detect near-identical templates with only rank-like details changed."""
    left_normalized = re.sub(r"\d+", "#", normalize(left))
    right_normalized = re.sub(r"\d+", "#", normalize(right))
    if min(len(left_normalized), len(right_normalized)) < 30:
        return 0.0
    return difflib.SequenceMatcher(None, left_normalized, right_normalized, autojunk=False).ratio()


def validate_text(value: str, validator_rules: dict[str, Any] | None = None) -> list[str]:
    errors = []
    value = value.strip()
    if len(value) < 30:
        errors.append("too-short")
    if len(value) > 240:
        errors.append("too-long")
    if not THAI_RE.search(value):
        errors.append("no-thai")
    if CROSS_REF_RE.search(value):
        errors.append("cross-reference")
    if any(character in value for character in "\t\r\n"):
        errors.append("unsafe-tsv-character")
    if validator_rules is None:
        validator_rules = load_generation_policy(DEFAULT_POLICY_FILE)[0]["validator_rules"]
    if (any(literal in value for literal in validator_rules["banned_literals"])
            or any(re.search(pattern, value, re.I) for pattern in validator_rules["banned_regexes"])):
        errors.append("nonsense-grammar-term")
    return errors


def validate_explanations(raw: Any, validator_rules: dict[str, Any] | None = None,
                          input_item: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    if validator_rules is None:
        validator_rules = load_generation_policy(DEFAULT_POLICY_FILE)[0]["validator_rules"]
    if (not isinstance(raw, dict) or set(raw) != OUTPUT_KEYS
            or not isinstance(raw.get("explanations"), list)):
        return [], ["schema"]
    rows = raw["explanations"]
    errors = []
    by_rank: dict[int, dict[str, Any]] = {}
    for row in rows:
        if (not isinstance(row, dict) or set(row) != OUTPUT_ROW_KEYS
                or not isinstance(row.get("rank"), int) or isinstance(row.get("rank"), bool)
                or not isinstance(row.get("input_ok"), bool)
                or not isinstance(row.get("input_error"), str)
                or not isinstance(row.get("explanation_th"), str)):
            errors.append("schema-row")
            continue
        rank = row["rank"]
        if rank in by_rank:
            errors.append(f"duplicate-rank:{rank}")
        by_rank[rank] = {"rank": rank, "input_ok": row["input_ok"],
                         "input_error": row["input_error"].strip(),
                         "explanation_th": row["explanation_th"].strip()}
    if set(by_rank) != set(range(1, 6)):
        errors.append("ranks")
    for rank, row in by_rank.items():
        if not row["input_ok"]:
            reason = row["input_error"] or "unspecified"
            errors.append(f"rank-{rank}:input-error:{reason}")
        elif row["input_error"]:
            errors.append(f"rank-{rank}:unexpected-input-error")
        if row["input_ok"]:
            errors.extend(f"rank-{rank}:{code}" for code in validate_text(row["explanation_th"], validator_rules))
            if input_item is not None:
                source = next((item for item in input_item["sentences"] if item["rank"] == rank), None)
                if source is None:
                    errors.append(f"rank-{rank}:source-rank-missing")
                else:
                    text = row["explanation_th"]
                    sentence = source["sentence"]
                    checks = set(validator_rules["grounding_checks"])
                    if ("copula_is_must_be_present" in checks and "หลัง is" in text
                            and not re.search(r"\bis\b", sentence, re.I)):
                        errors.append(f"rank-{rank}:unsupported-copula-is")
                    if ("num_must_not_be_noun" in checks and source["pos"] == "num"
                            and "คำนาม" in text):
                        errors.append(f"rank-{rank}:pos-conflict-num-as-noun")
                    if ("mentioned_one_must_be_present" in checks
                            and re.search(r"ใช้(?:ร่วม)?กับ\s+one\b", text, re.I)
                            and not re.search(r"\bone\b", sentence, re.I)):
                        errors.append(f"rank-{rank}:unsupported-token-one")
                    target = re.escape(source["target"])
                    predicate_adjective = re.search(
                        rf"\b(?:am|is|are|was|were)\s+(?:(?:too|very|quite|rather|so)\s+)?{target}\b",
                        sentence,
                        re.I,
                    )
                    if ("adj_after_be_must_be_complement" in checks
                            and source["pos"] == "adj" and predicate_adjective
                            and "ส่วนเติมเต็ม" not in text):
                        errors.append(f"rank-{rank}:predicate-adjective-not-complement")
    accepted_rows = [row for row in by_rank.values() if row["input_ok"]]
    normalized = [normalize(row["explanation_th"]) for row in accepted_rows]
    if len(normalized) == 5 and len(set(normalized)) == 1:
        errors.append("duplicate-explanation")
    if len(accepted_rows) == 5 and len(set(normalized)) > 1:
        similarities = [
            template_similarity(left["explanation_th"], right["explanation_th"])
            for index, left in enumerate(accepted_rows)
            for right in accepted_rows[index + 1:]
        ]
        if similarities and min(similarities) >= 0.96:
            errors.append("template-copy:all")
        common_prefix = os.path.commonprefix(normalized)
        if len(common_prefix) >= validator_rules["max_common_prefix_chars"]:
            errors.append("template-copy-prefix:all")
    return ([by_rank[rank] for rank in sorted(by_rank)], errors)


def validate_input_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError("input must be a JSONL sequence")
    if not items:
        raise ValueError("input must contain at least one item")
    seen_seq: set[int] = set()
    seen_headword: set[str] = set()
    validated = []
    for index, item in enumerate(items, 1):
        label = f"input row {index}"
        if not isinstance(item, dict) or set(item) != INPUT_KEYS:
            raise ValueError(f"{label}: invalid object schema")
        seq = item["seq"]
        headword = item["headword"]
        forms = item["forms"]
        sentences = item["sentences"]
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
            raise ValueError(f"{label}: invalid seq")
        if (not isinstance(headword, str) or not headword.strip() or headword != headword.strip()
                or any(character in headword for character in "\t\r\n")):
            raise ValueError(f"{label}: invalid headword")
        if (not isinstance(forms, list)
                or any(not isinstance(form, str) or not form.strip() for form in forms)):
            raise ValueError(f"{label}: invalid forms")
        if not isinstance(sentences, list) or len(sentences) != 5:
            raise ValueError(f"{label}: expected exactly five sentences")
        ranks = []
        for sentence in sentences:
            if not isinstance(sentence, dict) or set(sentence) != SENTENCE_KEYS:
                raise ValueError(f"{label}: invalid sentence schema")
            rank = sentence["rank"]
            sense_id = sentence["sense_id"]
            if not isinstance(rank, int) or isinstance(rank, bool):
                raise ValueError(f"{label}: invalid sentence rank")
            if not isinstance(sense_id, int) or isinstance(sense_id, bool) or sense_id < 1:
                raise ValueError(f"{label}: invalid sense_id")
            for field in ("pos", "target", "sentence", "gloss"):
                if not isinstance(sentence[field], str) or not sentence[field].strip():
                    raise ValueError(f"{label}: invalid {field}")
            ranks.append(rank)
        if set(ranks) != set(range(1, 6)) or len(set(ranks)) != 5:
            raise ValueError(f"{label}: ranks must be exactly 1-5")
        folded = headword.casefold()
        if seq in seen_seq or folded in seen_headword:
            raise ValueError(f"{label}: duplicate seq or headword")
        seen_seq.add(seq); seen_headword.add(folded)
        validated.append(item)
    return validated


def ranges(value: str) -> set[int]:
    result = set()
    for part in value.split(","):
        bounds = part.strip().split("-", 1)
        start = int(bounds[0]); end = int(bounds[-1])
        if end < start:
            raise argparse.ArgumentTypeError(f"invalid range: {part}")
        result.update(range(start, end + 1))
    return result


def prepare(args: argparse.Namespace) -> None:
    manifest = read_manifest(args.manifest)
    snapshot = parse_snapshot(args.snapshot)
    glosses, forms = load_evidence(args.evidence_db)
    existing, _ = load_existing(args.existing_dir)
    wanted = ranges(args.ranges) if args.ranges else {row["seq"] for row in manifest}
    output = []
    for item in manifest:
        if item["seq"] not in wanted:
            continue
        headword = item["headword"]
        if args.only_missing and all((headword, rank) in existing for rank in range(1, 6)):
            continue
        sentences = snapshot.get(headword)
        if (not sentences or len(sentences) != 5
                or {row["rank"] for row in sentences} != set(range(1, 6))):
            raise ValueError(f"snapshot does not have five ranks: {headword}")
        if any(row["sense_id"] not in glosses or not glosses[row["sense_id"]].strip() for row in sentences):
            raise ValueError(f"missing source gloss: {headword}")
        output.append({
            "seq": item["seq"], "headword": headword,
            "forms": forms.get(headword, []),
            "sentences": [{**row, "gloss": glosses.get(row["sense_id"], "")} for row in sorted(sentences, key=lambda x: x["rank"])],
        })
        if args.limit and len(output) >= args.limit:
            break
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({"items": len(output), "explanations": len(output) * 5, "sha256": digest,
                      "output": str(args.output)}, ensure_ascii=False))


def extract_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def load_generation_policy(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    policy = json.loads(raw.decode("utf-8"))
    gate_keys = {
        "semantic_pass_rate_min", "severe_error_rate_max",
        "deterministic_acceptance_rate_min", "repeated_error_pattern_max_rows",
        "accepted_words_per_minute_min", "average_minutes_per_word_max",
        "post_review_sample_pass_rate_min",
    }
    time_keys = {"production_generation_and_critic_max", "publish_checksum_audit_reserved"}
    if (not isinstance(policy, dict)
            or set(policy) != {"schema_version", "policy_version", "validator_rules", "production_gates", "time_budget_hours"}
            or policy.get("schema_version") != 1
            or not isinstance(policy.get("policy_version"), str) or not policy["policy_version"]
            or not isinstance(policy.get("production_gates"), dict)
            or set(policy["production_gates"]) != gate_keys
            or not isinstance(policy.get("time_budget_hours"), dict)
            or set(policy["time_budget_hours"]) != time_keys):
        raise ValueError("invalid grammar generation policy schema")
    validator_rules = policy["validator_rules"]
    if (not isinstance(validator_rules, dict)
            or set(validator_rules) != {"banned_literals", "banned_regexes", "max_common_prefix_chars", "grounding_checks"}
            or not isinstance(validator_rules["banned_literals"], list)
            or not isinstance(validator_rules["banned_regexes"], list)
            or any(not isinstance(value, str) or not value for value in validator_rules["banned_literals"])
            or any(not isinstance(value, str) or not value for value in validator_rules["banned_regexes"])
            or not isinstance(validator_rules["max_common_prefix_chars"], int)
            or isinstance(validator_rules["max_common_prefix_chars"], bool)
            or validator_rules["max_common_prefix_chars"] < 30
            or not isinstance(validator_rules["grounding_checks"], list)
            or set(validator_rules["grounding_checks"]) != {
                "copula_is_must_be_present", "num_must_not_be_noun", "mentioned_one_must_be_present",
                "adj_after_be_must_be_complement",
            }):
        raise ValueError("invalid grammar validator policy")
    try:
        for pattern in validator_rules["banned_regexes"]:
            re.compile(pattern, re.I)
    except re.error as exc:
        raise ValueError(f"invalid grammar validator regex: {exc}") from exc
    gates = policy["production_gates"]
    numeric = [value for value in gates.values() if not isinstance(value, bool)]
    if (len(numeric) != len(gates)
            or any(not isinstance(value, (int, float)) or value < 0 for value in numeric)
            or not 0 <= gates["semantic_pass_rate_min"] <= 1
            or not 0 <= gates["severe_error_rate_max"] <= 1
            or not 0 <= gates["deterministic_acceptance_rate_min"] <= 1
            or not 0 <= gates["post_review_sample_pass_rate_min"] <= 1
            or not isinstance(gates["repeated_error_pattern_max_rows"], int)):
        raise ValueError("invalid grammar production gate values")
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0
           for value in policy["time_budget_hours"].values()):
        raise ValueError("invalid grammar time budget values")
    return policy, raw


def call_model(endpoint: str, model: str, item: dict[str, Any], max_tokens: int,
               reasoning_effort: str, system_prompt: str,
               repair_context: dict[str, Any] | None = None) -> tuple[str, dict[str, Any], float]:
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {"explanations": {
            "type": "array", "minItems": 5, "maxItems": 5,
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 5},
                    "input_ok": {"type": "boolean"},
                    "input_error": {"type": "string"},
                    "explanation_th": {"type": "string"},
                },
                "required": ["rank", "input_ok", "input_error", "explanation_th"],
            },
        }},
        "required": ["explanations"],
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(item, ensure_ascii=False, separators=(",", ":"))},
    ]
    if repair_context is not None:
        instruction = repair_context.get(
            "instruction",
            "Rewrite the complete JSON object after fixing every deterministic validator error. "
            "Do not repeat invalid wording. Errors: "
            + json.dumps(repair_context.get("errors", []), ensure_ascii=False, separators=(",", ":")),
        )
        messages.extend([
            {"role": "assistant", "content": repair_context["raw"]},
            {"role": "user", "content": instruction},
        ])
    payload = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "reasoning_effort": reasoning_effort,
        "messages": messages,
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "grammar_explanations", "strict": True, "schema": schema,
        }},
    }
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=300) as response:
        result = json.load(response)
    elapsed = time.monotonic() - started
    content = result["choices"][0]["message"]["content"]
    return content, result.get("usage", {}), elapsed


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def validate_loopback_endpoint(endpoint: str) -> str:
    parsed = urlsplit(endpoint)
    if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
            or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
        raise ValueError("endpoint must be an HTTP(S) loopback URL without credentials, query, or fragment")
    if parsed.port is None:
        raise ValueError("endpoint must include an explicit loopback port")
    return endpoint.rstrip("/")


def atomic_write_bytes(path: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def atomic_write_text(path: Path, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))


@contextlib.contextmanager
def single_writer_lock(output_dir: Path):
    """Hold a non-blocking, cross-platform advisory lock for one run directory."""
    lock_path = output_dir / ".run.lock"
    handle = lock_path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            raise RuntimeError(f"output directory is already in use: {output_dir}") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def open_state(output_dir: Path, items: list[dict[str, Any]], binding: dict[str, Any], input_bytes: bytes) -> sqlite3.Connection:
    state_path = output_dir / "state.sqlite3"
    legacy_paths = [output_dir / name for name in ("events.jsonl", "accepted.tsv", "summary.json")]
    if not state_path.exists() and any(path.exists() for path in legacy_paths):
        raise ValueError("output directory contains legacy uncheckpointed artifacts; use a new output directory")
    connection = sqlite3.connect(state_path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS words(
            seq INTEGER PRIMARY KEY,
            headword TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','accepted','quarantine','input-quarantine')),
            attempts INTEGER NOT NULL DEFAULT 0,
            accepted_json TEXT,
            last_errors_json TEXT,
            last_raw TEXT,
            elapsed_seconds REAL NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seq INTEGER NOT NULL,
            attempt INTEGER NOT NULL,
            event_json TEXT NOT NULL,
            UNIQUE(seq, attempt),
            FOREIGN KEY(seq) REFERENCES words(seq)
        );
    """)
    encoded_binding = json.dumps(binding, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    stored = connection.execute("SELECT value FROM meta WHERE key='binding'").fetchone()
    if stored is not None and stored[0] != encoded_binding:
        connection.close()
        raise ValueError("resume configuration does not match the existing checkpoint")
    with connection:
        if stored is None:
            connection.execute("INSERT INTO meta(key,value) VALUES('binding',?)", (encoded_binding,))
            connection.execute("INSERT INTO meta(key,value) VALUES('created_at',?)", (utc_now(),))
        for item in items:
            connection.execute(
                "INSERT OR IGNORE INTO words(seq,headword,status) VALUES(?,?,'pending')",
                (item["seq"], item["headword"]),
            )
    state_rows = connection.execute("SELECT seq,headword FROM words ORDER BY seq").fetchall()
    expected_rows = sorted((item["seq"], item["headword"]) for item in items)
    if state_rows != expected_rows:
        connection.close()
        raise ValueError("checkpoint word set does not match input")
    input_copy = output_dir / "input.jsonl"
    if input_copy.exists() and hashlib.sha256(input_copy.read_bytes()).hexdigest() != binding["input_sha256"]:
        connection.close()
        raise ValueError("staged input copy does not match checkpoint")
    if not input_copy.exists():
        atomic_write_bytes(input_copy, input_bytes)
    provenance = {
        **binding,
        "created_at": connection.execute("SELECT value FROM meta WHERE key='created_at'").fetchone()[0],
        "state": "state.sqlite3",
    }
    atomic_write_text(output_dir / "provenance.json", json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    return connection


def materialize_artifacts(connection: sqlite3.Connection, output_dir: Path) -> None:
    event_lines = [row[0] for row in connection.execute("SELECT event_json FROM attempts ORDER BY id")]
    atomic_write_text(output_dir / "events.jsonl", "".join(line + "\n" for line in event_lines))
    accepted_lines = []
    for headword, payload in connection.execute(
        "SELECT headword,accepted_json FROM words WHERE status='accepted' ORDER BY seq"
    ):
        for row in json.loads(payload):
            accepted_lines.append(f"{headword}\t{row['rank']}\t{row['explanation_th']}\n")
    atomic_write_text(output_dir / "accepted.tsv", "".join(accepted_lines))
    quarantine_lines = []
    for seq, headword, status, attempts, errors, raw in connection.execute(
        "SELECT seq,headword,status,attempts,last_errors_json,last_raw FROM words "
        "WHERE status IN ('quarantine','input-quarantine') ORDER BY seq"
    ):
        quarantine_lines.append(json.dumps({
            "seq": seq, "headword": headword, "status": status, "attempts": attempts,
            "errors": json.loads(errors or "[]"), "raw": raw or "",
        }, ensure_ascii=False) + "\n")
    atomic_write_text(output_dir / "quarantine.jsonl", "".join(quarantine_lines))


def _integer_usage(usage: Any, key: str) -> int:
    if not isinstance(usage, dict):
        return 0
    value = usage.get(key, 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def merge_usage(*values: dict[str, Any]) -> dict[str, int]:
    return {
        key: sum(_integer_usage(value, key) for value in values)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def _breaker_failure(errors: list[str]) -> bool:
    schema_codes = ("schema", "schema-row", "ranks", "duplicate-rank:")
    return any(error.startswith("request-or-parse:") or error.startswith(schema_codes) for error in errors)


def run(args: argparse.Namespace) -> int:
    if args.max_tokens < 1 or args.retries < 0 or args.breaker < 1:
        raise ValueError("max-tokens and breaker must be positive; retries must be non-negative")
    endpoint = validate_loopback_endpoint(args.endpoint)
    prompt_path = getattr(args, "prompt_file", DEFAULT_PROMPT_FILE)
    policy_path = getattr(args, "policy_file", DEFAULT_POLICY_FILE)
    prompt_bytes = prompt_path.read_bytes()
    system_prompt = prompt_bytes.decode("utf-8").strip()
    if not system_prompt:
        raise ValueError("grammar prompt file is empty")
    policy, policy_bytes = load_generation_policy(policy_path)
    input_bytes = args.input.read_bytes()
    parsed_items = []
    for number, line in enumerate(input_bytes.decode("utf-8").splitlines(), 1):
        if not line:
            continue
        try:
            parsed_items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"input line {number}: invalid JSON: {exc}") from exc
    items = validate_input_items(parsed_items)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_sha256 = hashlib.sha256(input_bytes).hexdigest()
    prompt_sha256 = hashlib.sha256(prompt_bytes).hexdigest()
    policy_sha256 = hashlib.sha256(policy_bytes).hexdigest()
    binding = {
        "input_sha256": input_sha256,
        "pipeline_state_version": PIPELINE_STATE_VERSION,
        "validator_version": VALIDATOR_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "model": args.model,
        "endpoint": endpoint,
        "prompt_version": prompt_path.name,
        "prompt_sha256": prompt_sha256,
        "policy_version": policy["policy_version"],
        "policy_sha256": policy_sha256,
        "production_gates": policy["production_gates"],
        "time_budget_hours": policy["time_budget_hours"],
        "temperature": 0.1,
        "reasoning_effort": args.reasoning_effort,
        "critic_mode": args.critic_mode,
        "max_tokens": args.max_tokens,
        "retries": args.retries,
        "breaker": args.breaker,
    }
    lock_context = single_writer_lock(args.output_dir)
    lock_context.__enter__()
    try:
        connection = open_state(args.output_dir, items, binding, input_bytes)
        materialize_artifacts(connection, args.output_dir)
    except BaseException:
        lock_context.__exit__(None, None, None)
        raise
    start = time.monotonic(); accepted = 0; quarantined = 0; input_quarantined = 0
    attempts_this_run = 0; prompt_tokens = 0; completion_tokens = 0; total_tokens = 0
    consecutive_failures = 0
    breaker_reason = None
    try:
        for item in items:
            state = connection.execute(
                "SELECT status,attempts FROM words WHERE seq=?", (item["seq"],)
            ).fetchone()
            if state[0] in TERMINAL_STATUSES:
                continue
            word_accepted = False
            final_errors: list[str] = []
            repair_context = None
            for attempt in range(state[1] + 1, args.retries + 2):
                content = ""
                request_started = time.monotonic()
                try:
                    if repair_context is None and args.critic_mode == "rewrite":
                        draft, draft_usage, draft_elapsed = call_model(
                            endpoint, args.model, item, args.max_tokens, args.reasoning_effort,
                            system_prompt, None
                        )
                        critic_context = {
                            "raw": draft,
                            "instruction": (
                                "Act as an adversarial grammar critic. Re-read the exact input, distrust the draft, "
                                "and return a fully rewritten JSON object. For every rank verify target meaning, POS, "
                                "the target's own subject/object/modifier/complement role, its actual governor, "
                                "countability or inflection trigger, and natural standard Thai. Remove invented facts, "
                                "copied dictionary glosses, Chinese/Japanese characters, mixed-language grammar labels, "
                                "and every claim not supported by the sentence. Return only the corrected full JSON."
                            ),
                        }
                        content, critic_usage, critic_elapsed = call_model(
                            endpoint, args.model, item, args.max_tokens, args.reasoning_effort,
                            system_prompt, critic_context
                        )
                        usage = merge_usage(draft_usage, critic_usage)
                        elapsed = draft_elapsed + critic_elapsed
                    else:
                        content, usage, elapsed = call_model(
                            endpoint, args.model, item, args.max_tokens, args.reasoning_effort,
                            system_prompt, repair_context
                        )
                    rows, errors = validate_explanations(
                        extract_json(content), policy["validator_rules"], item
                    )
                except Exception as exc:
                    usage, elapsed, rows, errors = {}, time.monotonic() - request_started, [], [f"request-or-parse:{type(exc).__name__}:{exc}"]
                attempts_this_run += 1
                attempt_prompt_tokens = _integer_usage(usage, "prompt_tokens")
                attempt_completion_tokens = _integer_usage(usage, "completion_tokens")
                attempt_total_tokens = _integer_usage(usage, "total_tokens")
                prompt_tokens += attempt_prompt_tokens
                completion_tokens += attempt_completion_tokens
                total_tokens += attempt_total_tokens
                event = {"seq": item["seq"], "headword": item["headword"], "attempt": attempt,
                         "timestamp": utc_now(), "elapsed_seconds": round(elapsed, 3),
                         "usage": usage, "errors": errors}
                if not errors:
                    event["status"] = "accepted"; accepted += 1; consecutive_failures = 0
                    word_accepted = True
                    status = "accepted"
                else:
                    final_errors = errors
                    repair_context = {"raw": content, "errors": errors}
                    input_quarantine = any(":input-error:" in error for error in errors)
                    status = "input-quarantine" if input_quarantine else ("retry" if attempt <= args.retries else "quarantine")
                    event["status"] = status
                    event["raw"] = content
                with connection:
                    connection.execute(
                        "INSERT INTO attempts(seq,attempt,event_json) VALUES(?,?,?)",
                        (item["seq"], attempt, json.dumps(event, ensure_ascii=False)),
                    )
                    connection.execute(
                        "UPDATE words SET status=?,attempts=?,accepted_json=?,last_errors_json=?,last_raw=?,"
                        "elapsed_seconds=elapsed_seconds+?,prompt_tokens=prompt_tokens+?,"
                        "completion_tokens=completion_tokens+?,total_tokens=total_tokens+? WHERE seq=?",
                        ("pending" if status == "retry" else status, attempt,
                         json.dumps(rows, ensure_ascii=False) if status == "accepted" else None,
                         json.dumps(errors, ensure_ascii=False), content if errors else None, elapsed,
                         attempt_prompt_tokens, attempt_completion_tokens, attempt_total_tokens, item["seq"]),
                    )
                materialize_artifacts(connection, args.output_dir)
                if status in TERMINAL_STATUSES:
                    break
            if not word_accepted:
                if any(":input-error:" in error for error in final_errors):
                    input_quarantined += 1
                else:
                    quarantined += 1
                consecutive_failures = consecutive_failures + 1 if _breaker_failure(final_errors) else 0
                if consecutive_failures >= args.breaker:
                    breaker_reason = f"{consecutive_failures} consecutive request/schema failures"
                    break
        elapsed_total = time.monotonic() - start
        counts = dict(connection.execute("SELECT status,count(*) FROM words GROUP BY status"))
        for status in ("pending", "accepted", "quarantine", "input-quarantine"):
            counts.setdefault(status, 0)
        pending = counts["pending"]
        complete = pending == 0
        attempts_cumulative = connection.execute("SELECT count(*) FROM attempts").fetchone()[0]
        cumulative = connection.execute(
            "SELECT coalesce(sum(prompt_tokens),0),coalesce(sum(completion_tokens),0),"
            "coalesce(sum(total_tokens),0),coalesce(sum(elapsed_seconds),0) FROM words"
        ).fetchone()
        attempted_terminal = counts["accepted"] + counts["quarantine"] + counts["input-quarantine"]
        error_histogram: Counter[str] = Counter()
        for event_json, in connection.execute("SELECT event_json FROM attempts"):
            for error in json.loads(event_json).get("errors", []):
                error_histogram[error] += 1
        attempt_histogram = Counter(
            str(attempt_count) for attempt_count, in connection.execute(
                "SELECT attempts FROM words WHERE attempts > 0"
            )
        )
        summary = {
            **binding,
            "complete": complete,
            "deterministic_ready": complete and counts["quarantine"] == 0 and counts["input-quarantine"] == 0,
            "breaker_reason": breaker_reason,
            "counts": {**counts, "total": len(items), "pending": pending},
            "accepted_words_this_run": accepted,
            "quarantine_words_this_run": quarantined,
            "input_quarantine_words_this_run": input_quarantined,
            "attempts_this_run": attempts_this_run,
            "attempts_cumulative": attempts_cumulative,
            "elapsed_seconds_this_run": round(elapsed_total, 3),
            "api_elapsed_seconds_cumulative": round(cumulative[3], 3),
            "accepted_words_per_minute": round(accepted / elapsed_total * 60, 3) if elapsed_total else 0,
            "deterministic_acceptance_rate": round(counts["accepted"] / attempted_terminal, 6) if attempted_terminal else None,
            "terminal_words_cumulative": attempted_terminal,
            "attempt_histogram": dict(attempt_histogram),
            "error_histogram": dict(error_histogram),
            "usage_this_run": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": total_tokens},
            "usage_cumulative": {"prompt_tokens": cumulative[0], "completion_tokens": cumulative[1], "total_tokens": cumulative[2]},
            "updated_at": utc_now(),
        }
        summary["artifact_sha256"] = {
            name: hashlib.sha256((args.output_dir / name).read_bytes()).hexdigest()
            for name in ("input.jsonl", "events.jsonl", "accepted.tsv", "quarantine.jsonl", "provenance.json")
        }
        atomic_write_text(args.output_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(summary, ensure_ascii=False))
        if not complete:
            return 2
        return 0 if summary["deterministic_ready"] else 3
    finally:
        try:
            connection.close()
        finally:
            lock_context.__exit__(None, None, None)


def audit(args: argparse.Namespace) -> None:
    existing, anomalies = load_existing(args.existing_dir)
    words = {headword for headword, _ in existing}
    complete_words = sum(all((headword, rank) in existing for rank in range(1, 6)) for headword in words)
    counts = Counter(item["code"] for item in anomalies)
    print(json.dumps({"valid_rows": len(existing), "covered_words": len(words), "complete_words": complete_words,
                      "complete_rows": complete_words * 5,
                      "anomalies": len(anomalies), "anomaly_codes": counts,
                      "details": anomalies}, ensure_ascii=False, indent=2, default=dict))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--snapshot", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    prepare_parser.add_argument("--ranges")
    prepare_parser.add_argument("--limit", type=int, default=0)
    prepare_parser.add_argument("--only-missing", action="store_true")
    prepare_parser.add_argument("--manifest", type=Path, default=ROOT / "data/sol_review_manifest.txt")
    prepare_parser.add_argument("--evidence-db", type=Path, default=ROOT / "data/vocabulary_source.db")
    prepare_parser.add_argument("--existing-dir", type=Path, default=ROOT / "data/sol_review_explanations")
    prepare_parser.set_defaults(func=prepare)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--input", type=Path, required=True)
    run_parser.add_argument("--output-dir", type=Path, required=True)
    run_parser.add_argument("--endpoint", required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--max-tokens", type=int, default=1000)
    run_parser.add_argument("--reasoning-effort", choices=("low", "medium"), default="low")
    run_parser.add_argument("--critic-mode", choices=("none", "rewrite"), default="none")
    run_parser.add_argument("--prompt-file", type=Path, default=DEFAULT_PROMPT_FILE)
    run_parser.add_argument("--policy-file", type=Path, default=DEFAULT_POLICY_FILE)
    run_parser.add_argument("--retries", type=int, default=1)
    run_parser.add_argument("--breaker", type=int, default=5)
    run_parser.set_defaults(func=run)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--existing-dir", type=Path, default=ROOT / "data/sol_review_explanations")
    audit_parser.set_defaults(func=audit)
    args = parser.parse_args()
    result = args.func(args)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
