"""Build and execute immutable, resumable vocabulary generation run packages.

This module deliberately has no third-party dependencies.  Build reads lexical
SQLite evidence in read-only mode; run consumes the copied JSONL evidence and
can therefore operate on a VM without access to the canonical corpus.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from collections import Counter, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


SCHEMA_VERSION = 1
THAI_RE = re.compile(r"[\u0e00-\u0e7f]")
PLACEHOLDER_RE = re.compile(r"\b(?:is|are|was|were) important\b|\bthis (?:word|sentence)\b", re.I)
MARKUP_RE = re.compile(r"```|^\s*#+\s|\*\*", re.M)
FIELD_LABEL_RE = re.compile(r"\b(?:sense_id|memorable|cloze_target|en_text)\s*[:=]", re.I)
SERIALIZATION_ARTIFACT_RE = re.compile(r"[{}]|\},\{")
GRAMMAR_RED_FLAG_RE = re.compile(
    r"\b(?:several|many|two|three)\s+(?:someone|somebody|something)\b|"
    r"\bsoon\s+than\b|\bthe\s+soon\s+[A-Za-z]+\b",
    re.I,
)
DETERMINER_VERB_FOLLOW_RE = re.compile(
    r"\b(?:is|are|was|were|has|have|had|happened|happens|do|does|did|can|could|will|would|should|must)\b",
    re.I,
)
# Explicit Wiktextract labels only. UK/US and ordinary grammatical labels are
# intentionally not restricted because they are commonly useful to learners.
RESTRICTED_USAGE_TAGS = {
    "archaic", "obsolete", "rare", "uncommon", "dated", "historical",
    "dialectal", "regional", "slang", "euphemistic", "vulgar",
    "derogatory", "offensive", "slur", "nonstandard", "proscribed",
    "misspelling", "poetic",
}
CORE_FUNCTION_POS = ("article", "num")
SAFE_SENSE_OVERRIDES = {"thanks": 67932, "thing": 41267}
EXACT_HEADWORD_OVERRIDES = {"thing"}
UNSAFE_TRIVIA_RE = re.compile(r"\b(?:letters?\s+in\s+the\s+word|stars?\s+on\s+the\s+flag|flag\s+of\s+the\s+united\s+states)\b", re.I)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def jsonl_append(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_manifest(directory: Path, destination: Path) -> None:
    rows = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file() and p != destination):
        rows.append(f"{sha256_file(path)}  {path.relative_to(directory).as_posix()}")
    atomic_text(destination, "\n".join(rows) + "\n")


def verify_manifest(directory: Path, manifest: Path) -> list[str]:
    errors: list[str] = []
    if not manifest.exists():
        return [f"missing manifest: {manifest}"]
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            errors.append(f"manifest line {number}: malformed")
            continue
        path = directory / Path(relative)
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            errors.append(f"missing input: {relative}")
            continue
        if directory.resolve() not in resolved.parents:
            errors.append(f"unsafe input path: {relative}")
        elif not path.is_file() or path.is_symlink():
            errors.append(f"input is not a regular file: {relative}")
        elif sha256_file(path) != expected:
            errors.append(f"checksum mismatch: {relative}")
    return errors


@dataclass(frozen=True)
class DraftRow:
    rank: int
    sense_id: int
    pos: str
    target: str
    memorable: int
    sentence: str


def parse_drafts(path: Path) -> dict[str, list[DraftRow]]:
    entries: dict[str, list[DraftRow]] = {}
    headword: str | None = None
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("@ "):
            headword = raw[2:].strip().casefold()
            entries.setdefault(headword, [])
            continue
        if headword is None:
            raise ValueError(f"{path}:{number}: row before headword")
        fields = raw.split("\t")
        if len(fields) not in (6, 8):
            raise ValueError(f"{path}:{number}: expected 6 or 8 fields")
        try:
            entries[headword].append(DraftRow(int(fields[0]), int(fields[1]), fields[2], fields[3], int(fields[4]), fields[5]))
        except (ValueError, IndexError) as error:
            raise ValueError(f"{path}:{number}: invalid draft row") from error
    return entries


def ro_connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def evidence_for(con: sqlite3.Connection, headword: str) -> dict[str, Any]:
    word = con.execute("SELECT id,headword,cefr_first,source_rank FROM words WHERE lower(headword)=?", (headword.casefold(),)).fetchone()
    if word is None:
        raise ValueError(f"unknown headword: {headword}")
    senses = [dict(row) for row in con.execute("SELECT id,pos,gloss,tags_json,source_name FROM source_senses WHERE word_id=? ORDER BY id", (word["id"],))]
    forms = [dict(row) for row in con.execute("SELECT form_text,pos,tags_json,source_name FROM source_forms WHERE word_id=? ORDER BY id", (word["id"],))]
    examples = [dict(row) for row in con.execute("SELECT pos,sense_gloss,example_text,example_type,source_name FROM source_examples WHERE word_id=? ORDER BY id", (word["id"],))]
    return {"word_id": word["id"], "headword": word["headword"], "cefr": word["cefr_first"], "source_rank": word["source_rank"], "senses": senses, "forms": forms, "examples": examples}


def usage_tags(row: dict[str, Any]) -> set[str]:
    """Return normalized explicit tags, tolerating damaged upstream metadata."""
    try:
        value = json.loads(row.get("tags_json") or "[]")
    except (TypeError, json.JSONDecodeError):
        return set()
    if not isinstance(value, list):
        return set()
    return {str(tag).strip().casefold() for tag in value if str(tag).strip()}


def restriction_tags(row: dict[str, Any]) -> list[str]:
    return sorted(usage_tags(row) & RESTRICTED_USAGE_TAGS)


def tag_suitability(row: dict[str, Any]) -> dict[str, Any]:
    restrictions = restriction_tags(row)
    return {**row, "learner_suitability": "restricted" if restrictions else "preferred", "restriction_tags": restrictions}


def compact_evidence(evidence: dict[str, Any], canonical: list[dict[str, Any]], primary_sense_id: int | None) -> dict[str, Any]:
    """Keep canonical audit evidence plus one conservative generation profile."""
    full_senses = [tag_suitability(row) for row in evidence["senses"]]
    full_forms = [tag_suitability(row) for row in evidence["forms"]]
    preferred = [row for row in full_senses if row["learner_suitability"] == "preferred"]
    lexical = [row for row in preferred if not (usage_tags(row) & {"form-of", "gerund", "participle"})]
    generation_candidates = lexical or preferred
    example_counts = Counter(
        (row.get("pos"), (row.get("sense_gloss") or "").casefold())
        for row in evidence["examples"]
        if row.get("sense_gloss") and row.get("example_type") == "example"
    )
    override_id = SAFE_SENSE_OVERRIDES.get(evidence["headword"].casefold())
    override = next((row for row in preferred if int(row["id"]) == override_id), None)
    primary = next((row for row in preferred if int(row["id"]) == primary_sense_id), None)
    core = next((row for pos in CORE_FUNCTION_POS for row in preferred if row["pos"] == pos), None)
    popular = max(
        generation_candidates,
        key=lambda row: (example_counts[(row["pos"], row["gloss"].casefold())], -int(row["id"])),
        default=None,
    )
    rank_one_id = next((int(row["sense_id"]) for row in canonical if int(row["rank"]) == 1), None)
    rank_one = next((row for row in generation_candidates if int(row["id"]) == rank_one_id), None)
    rank_one_evidence = next((row for row in preferred if int(row["id"]) == rank_one_id), None)
    popular_count = 0 if popular is None else example_counts[(popular["pos"], popular["gloss"].casefold())]
    rank_one_count = 0 if rank_one_evidence is None else example_counts[(rank_one_evidence["pos"], rank_one_evidence["gloss"].casefold())]
    if popular_count < 5 or rank_one_count != 0:
        popular = None
    safe_sense = override or core or primary or popular or rank_one or (generation_candidates[0] if generation_candidates else None)
    wanted_ids = {int(row["sense_id"]) for row in canonical}
    if safe_sense is not None:
        wanted_ids.add(int(safe_sense["id"]))
    senses = [row for row in full_senses if int(row["id"]) in wanted_ids]
    selected_pos = {row["pos"] for row in senses}
    canonical_forms = {(row["pos"], row["target"].casefold()) for row in canonical}
    forms = [row for row in full_forms if (row["pos"], row["form_text"].casefold()) in canonical_forms]
    seen_forms = {(row["pos"], row["form_text"].casefold()) for row in forms}
    for row in full_forms:
        key = (row["pos"], row["form_text"].casefold())
        if row["pos"] in selected_pos and row["learner_suitability"] == "preferred" and key not in seen_forms and len(forms) < 20:
            forms.append(row); seen_forms.add(key)
    glosses = {(row["pos"], row["gloss"].casefold()) for row in senses}
    ranked_examples = sorted(
        (row for row in evidence["examples"] if row["pos"] in selected_pos),
        key=lambda row: ((row["pos"], (row.get("sense_gloss") or "").casefold()) not in glosses),
    )
    examples = []
    seen_examples: set[str] = set()
    for row in ranked_examples:
        key = row["example_text"].casefold()
        if key not in seen_examples:
            examples.append(row); seen_examples.add(key)
        if len(examples) >= 20:
            break
    safe_profile = None if safe_sense is None else {
        "sense_id": int(safe_sense["id"]), "pos": safe_sense["pos"], "target": evidence["headword"],
        "gloss": safe_sense["gloss"],
        "exact_target": evidence["headword"].casefold() in EXACT_HEADWORD_OVERRIDES,
    }
    return {**evidence, "senses": senses, "forms": forms, "examples": examples, "safe_profile": safe_profile,
            "compaction": {"full_senses": len(evidence["senses"]), "full_forms": len(evidence["forms"]), "full_examples": len(evidence["examples"])}}


OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headword", "decision", "reason", "rows"],
    "properties": {
        "headword": {"type": "string"},
        "decision": {"type": "string", "enum": ["pass", "repair", "generate"]},
        "reason": {"type": "string"},
        "rows": {
            "type": "array", "minItems": 5, "maxItems": 5,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["rank", "sense_id", "pos", "target", "memorable", "sentence"],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 5},
                    "sense_id": {"type": "integer"}, "pos": {"type": "string"},
                    "target": {"type": "string"}, "memorable": {"type": "integer", "enum": [0, 1]},
                    "sentence": {"type": "string"},
                },
            },
        },
    },
}


PROMPT = """You generate source-grounded English learner sentences. Return only JSON matching the supplied schema. Produce exactly five distinct rows. Never invent sense IDs, POS values, or target forms. For every editable rank, use exactly the supplied safe_profile sense_id, POS, and gloss; a supplied learner-suitable inflected target with the same POS is allowed unless safe_profile.exact_target is true. Every sentence must use the exact meaning stated in safe_profile.gloss, never an idiom, related meaning, or another common sense of the word. Vary only the everyday sentence context. EVERY sentence, including rank 2, must contain its exact declared target string as a complete word with the same capitalization; never write blanks, underscores, or remove the target because the downstream app creates the cloze later. Only rank 1 is memorable=1. Rank 2 must become unambiguous after the downstream app hides the target. Write short, concrete, idiomatic learner sentences, usually 6–16 words and one simple clause. Do not write dictionary definitions, metalinguistic examples, tautologies, unverifiable trivia, or claims about spelling, flags, clocks, schedules, or exact quantities unless the evidence explicitly supports the fact. Do not put contradictory facts in two clauses. Give every pronoun a clear antecedent; possessive determiners such as their must name the plural owner earlier in the same sentence. A determiner must directly modify a noun, an article must precede a noun phrase, and a pronoun must stand in for a noun phrase. Reliability is more important than sense coverage. Sentence/context diversity is required, but sense diversity is not a goal. Senses and forms marked learner_suitability=restricted are forbidden. In audit_repair mode with rank-specific deterministic_errors, change only the named ranks and preserve every other canonical row byte-for-byte. When deterministic_errors is empty, generate all editable rows from the safe profile; a later human review owns optional coverage improvements. Before returning JSON, silently verify each sentence against the exact gloss for its sense_id. Do not include Thai, Markdown, serialization fragments, or field labels in sentences."""

CRITIC_PROMPT = """You are the final quality gate for English learner sentences. Return only a complete JSON candidate matching the supplied schema. Inspect every row and silently correct the candidate before returning it. Every editable rank must use exactly the supplied safe_profile POS; prefer its sense_id and headword target, while another supplied learner-suitable sense or inflected target with the same POS is allowed. Grammar and naturalness are mandatory, not stylistic preferences. Check subject-verb agreement, articles, countability, plural forms, comparative forms, preposition choice, word order, and complete idiomatic clauses. The exact declared target must appear and function as the declared POS. The sentence context must unambiguously match the exact supplied sense gloss. Reject sense drift, awkward nounification, unusual conversion to another POS, invalid comparative use, invented collocations, dictionary-style or metalinguistic examples, tautologies, vague contexts, unsupported factual or normative claims, and rare or archaic usages unsuitable for ordinary learners. Rank 1 need not be especially memorable; weak memorability alone is not a reason to rewrite it, but its semantics, grammar, and naturalness remain mandatory. Preserve canonical ranks that the assignment does not allow changing. If a row is uncertain, replace it with a short ordinary sentence using the safe profile. Never invent a sense ID, POS, or form."""


def init_state(path: Path, assignments: list[dict[str, Any]], config_sha256: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS run_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS words (
          seq INTEGER PRIMARY KEY, headword TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, first_pass INTEGER, errors_json TEXT NOT NULL DEFAULT '[]',
          started_at TEXT, updated_at TEXT, elapsed_seconds REAL NOT NULL DEFAULT 0
        );
        """)
        con.execute("INSERT OR REPLACE INTO run_meta VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
        con.execute("INSERT OR REPLACE INTO run_meta VALUES('config_sha256',?)", (config_sha256,))
        for row in assignments:
            con.execute("INSERT OR IGNORE INTO words(seq,headword,status,updated_at) VALUES(?,?,'pending',?)", (row["seq"], row["headword"], utc_now()))
        con.commit()
    finally:
        con.close()


def build_run(run_dir: Path, evidence_db: Path, manifest: Path, draft_dir: Path, seq_start: int, seq_end: int, *, mode: str = "audit_repair", review_report_dir: Path | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"run directory is not empty: {run_dir}")
    if mode not in {"audit_repair", "generate"}:
        raise ValueError("mode must be audit_repair or generate")
    rows = []
    reviewed_headwords: set[str] = set()
    review_reports_sha256 = None
    if review_report_dir is not None:
        digest = hashlib.sha256()
        for path in sorted(review_report_dir.glob("sol_review_*.tsv")):
            digest.update(path.name.encode("utf-8") + b"\0" + bytes.fromhex(sha256_file(path)))
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                fields = line.split("\t")
                if len(fields) != 3 or fields[1] not in {"pass", "repaired"}:
                    raise ValueError(f"malformed review report row: {path.name}:{number}")
                folded = fields[0].casefold()
                if folded in reviewed_headwords:
                    raise ValueError(f"duplicate reviewed headword: {fields[0]}")
                reviewed_headwords.add(folded)
        review_reports_sha256 = digest.hexdigest()
    lines = manifest.read_text(encoding="utf-8").splitlines()
    header = next((line.removeprefix("# ").split("\t") for line in lines if line.startswith("# ")), [])
    sol_schema = header[:5] == ["seq", "priority", "source_rank", "headword", "source_file"]
    missing_schema = header[:4] == ["seq", "source_rank", "word_id", "headword"]
    if mode == "audit_repair" and not sol_schema:
        raise ValueError("audit_repair requires the Sol review manifest schema")
    if not (sol_schema or missing_schema):
        raise ValueError("unsupported manifest schema")
    for raw in lines:
        if not raw or raw.startswith("#"):
            continue
        fields = raw.split("\t")
        seq = int(fields[0])
        if seq_start <= seq <= seq_end:
            if sol_schema:
                if len(fields) < 5:
                    raise ValueError("malformed Sol manifest row")
                row = {"seq": seq, "priority": fields[1], "source_rank": int(fields[2]), "headword": fields[3], "source_file": fields[4], "deterministic_errors": fields[5] if len(fields) > 5 else "", "primary_sense_id": None, "primary_pos": None}
            else:
                if len(fields) < 7:
                    raise ValueError("malformed generate manifest row")
                row = {"seq": seq, "priority": "generate", "source_rank": int(fields[1]), "headword": fields[3], "source_file": "", "deterministic_errors": "", "primary_sense_id": int(fields[5]), "primary_pos": fields[6]}
            if row["headword"].casefold() not in reviewed_headwords:
                rows.append(row)
    if not rows:
        raise ValueError("assignment range contains no unreviewed words")
    if review_report_dir is None and (rows[0]["seq"] != seq_start or rows[-1]["seq"] != seq_end or len(rows) != seq_end - seq_start + 1):
        raise ValueError("assignment range is missing or non-contiguous")
    drafts_by_file: dict[str, dict[str, list[DraftRow]]] = {}
    con = ro_connect(evidence_db)
    evidence_rows = []
    try:
        for item in rows:
            evidence = evidence_for(con, item["headword"])
            canonical: list[dict[str, Any]] = []
            if mode == "audit_repair":
                source_file = item["source_file"]
                if source_file not in drafts_by_file:
                    source_path = draft_dir / source_file
                    resolved = source_path.resolve(strict=True)
                    if draft_dir.resolve() not in resolved.parents or source_path.is_symlink() or not source_path.is_file():
                        raise ValueError(f"unsafe canonical source path: {source_file}")
                    drafts_by_file[source_file] = parse_drafts(source_path)
                canonical = [asdict(row) for row in drafts_by_file[source_file].get(item["headword"].casefold(), [])]
                if len(canonical) != 5:
                    raise ValueError(f"{item['headword']}: canonical block does not contain five rows")
            prompt_canonical = locked_canonical_for_prompt({**item, "canonical": canonical})
            evidence = compact_evidence(evidence, prompt_canonical, item.get("primary_sense_id"))
            evidence_rows.append({**item, "evidence": evidence, "canonical": canonical})
    finally:
        con.close()
    input_dir = run_dir / "input"
    for directory in (input_dir, run_dir / "output" / "accepted", run_dir / "output" / "quarantine", run_dir / "state", run_dir / "logs"):
        directory.mkdir(parents=True, exist_ok=True)
    atomic_text(input_dir / "assignment.tsv", "seq\tpriority\tsource_rank\theadword\tsource_file\tdeterministic_errors\n" + "\n".join("\t".join(str(row[k]) for k in ("seq", "priority", "source_rank", "headword", "source_file", "deterministic_errors")) for row in rows) + "\n")
    atomic_text(input_dir / "evidence.jsonl", "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in evidence_rows))
    atomic_text(input_dir / "canonical_blocks.txt", "\n".join(render_block(row["headword"], row["canonical"]) for row in evidence_rows if row["canonical"]))
    atomic_text(input_dir / "prompt.txt", PROMPT + "\n")
    atomic_json(input_dir / "output.schema.json", OUTPUT_SCHEMA)
    write_manifest(input_dir, input_dir / "manifest.sha256")
    effective = {"schema_version": SCHEMA_VERSION, "mode": mode, "api_url": "http://127.0.0.1:8082/v1/chat/completions", "model": "Qwen3-30B-A3B-Instruct-2507-Q4_K_M", "temperature": 0.2, "max_tokens": 600, "timeout": 120, "max_model_retries": 2, "http_retries": 1, "critic_pass": True, "evidence_db_sha256": sha256_file(evidence_db), "worker_sha256": sha256_file(Path(__file__)), "review_reports_sha256": review_reports_sha256, "excluded_reviewed": len(reviewed_headwords), **(config or {})}
    atomic_json(run_dir / "config.json", effective)
    init_state(run_dir / "state" / "run.sqlite", rows, sha256_file(run_dir / "config.json"))
    make_summary(run_dir)
    return {"run_dir": str(run_dir), "assigned": len(rows), "excluded_reviewed": len(reviewed_headwords), "input_manifest_sha256": sha256_file(input_dir / "manifest.sha256")}


def target_occurs(target: str, sentence: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z]){re.escape(target)}(?![A-Za-z])", sentence, re.I))


def normalize_candidate_targets(candidate: Any, record: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(candidate, dict) or not isinstance(candidate.get("rows"), list):
        return []
    allowed: dict[str, dict[str, str]] = {}
    for sense in record["evidence"]["senses"]:
        allowed.setdefault(sense["pos"], {})[record["headword"].casefold()] = record["headword"]
    for form in record["evidence"]["forms"]:
        allowed.setdefault(form["pos"], {})[form["form_text"].casefold()] = form["form_text"]
    changes = []
    for row in candidate["rows"]:
        if not isinstance(row, dict) or not all(isinstance(row.get(key), str) for key in ("pos", "target", "sentence")):
            continue
        if target_occurs(row["target"], row["sentence"]):
            continue
        matches = [source for source in allowed.get(row["pos"], {}).values() if target_occurs(source, row["sentence"])]
        if len(matches) == 1:
            previous = row["target"]
            row["target"] = matches[0]
            changes.append({"rank": row.get("rank"), "from": previous, "to": matches[0]})
    return changes


def editable_ranks_for(record: dict[str, Any]) -> set[int]:
    if not record.get("canonical"):
        return {1, 2, 3, 4, 5}
    deterministic_errors = record.get("deterministic_errors", "")
    error_ranks = {int(x) for x in re.findall(r"rank\s+(\d+)", deterministic_errors, re.I)}
    if any(part.strip() and not re.match(r"rank\s+\d+", part.strip(), re.I) for part in deterministic_errors.split(" | ")):
        return {1, 2, 3, 4, 5}
    return error_ranks or {1, 2, 3, 4, 5}


def locked_canonical_for_prompt(record: dict[str, Any]) -> list[dict[str, Any]]:
    editable = editable_ranks_for(record)
    return [row for row in record.get("canonical", []) if row.get("rank") not in editable]


def validate_candidate(candidate: Any, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(candidate, dict):
        return ["schema: candidate must be an object"]
    if candidate.get("headword") != record["headword"]:
        errors.append("schema: headword must match exactly")
    if candidate.get("decision") not in {"pass", "repair", "generate"} or not isinstance(candidate.get("reason"), str):
        errors.append("schema: invalid decision/reason")
    rows = candidate.get("rows")
    if not isinstance(rows, list) or len(rows) != 5:
        return errors + ["schema: rows must contain exactly five objects"]
    expected_keys = {"rank", "sense_id", "pos", "target", "memorable", "sentence"}
    structural = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != expected_keys:
            structural.append(f"schema: row {index + 1} has invalid fields")
        elif type(row["rank"]) is not int:
            structural.append(f"schema: row {index + 1} rank must be an integer")
    if structural:
        return errors + structural
    ranks = [row["rank"] for row in rows]
    if sorted(ranks) != [1, 2, 3, 4, 5]:
        errors.append("schema: ranks must be exactly 1..5")
    sense_records = {int(s["id"]): s for s in record["evidence"]["senses"]}
    senses = {sense_id: sense["pos"] for sense_id, sense in sense_records.items()}
    allowed: dict[str, set[str]] = {}
    for pos in set(senses.values()):
        allowed.setdefault(pos, set()).add(record["headword"].casefold())
    for form in record["evidence"]["forms"]:
        allowed.setdefault(form["pos"], set()).add(form["form_text"].casefold())
    form_records: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for form in record["evidence"]["forms"]:
        form_records.setdefault((form["pos"], form["form_text"].casefold()), []).append(form)
    seen_sentences: set[str] = set()
    canonical = {row["rank"]: row for row in record.get("canonical", [])}
    editable_ranks = editable_ranks_for(record)
    safe_profile = record["evidence"].get("safe_profile")
    for index, row in enumerate(rows):
        rank, sense_id, pos, target, memorable, sentence = (row[k] for k in ("rank", "sense_id", "pos", "target", "memorable", "sentence"))
        if type(rank) is not int or type(sense_id) is not int or type(memorable) is not int or memorable not in (0, 1) or not all(isinstance(x, str) and x.strip() for x in (pos, target, sentence)):
            errors.append(f"schema: row {index + 1} has invalid types")
            continue
        if sense_id not in senses:
            errors.append(f"rank {rank}: unsupported sense_id")
        elif senses[sense_id] != pos:
            errors.append(f"rank {rank}: POS does not match sense_id")
        elif sense_records[sense_id].get("learner_suitability") == "restricted" or restriction_tags(sense_records[sense_id]):
            labels = ", ".join(sense_records[sense_id].get("restriction_tags") or restriction_tags(sense_records[sense_id])) or "restricted usage"
            errors.append(f"rank {rank}: learner-unsuitable sense ({labels})")
        if rank in editable_ranks and safe_profile is not None:
            if pos != safe_profile["pos"]:
                errors.append(f"rank {rank}: must use the safe generation profile")
            if safe_profile.get("exact_target") and target.casefold() != safe_profile["target"].casefold():
                errors.append(f"rank {rank}: safe profile requires the exact headword target")
        if target.casefold() not in allowed.get(pos, set()):
            errors.append(f"rank {rank}: unsupported target form")
        elif target.casefold() != record["headword"].casefold():
            matching_forms = form_records.get((pos, target.casefold()), [])
            if matching_forms and all(form.get("learner_suitability") == "restricted" or restriction_tags(form) for form in matching_forms):
                labels = sorted({label for form in matching_forms for label in (form.get("restriction_tags") or restriction_tags(form))})
                errors.append(f"rank {rank}: learner-unsuitable target form ({', '.join(labels) or 'restricted usage'})")
        if not target_occurs(target, sentence):
            errors.append(f"rank {rank}: target is absent as a complete word")
        if memorable != (1 if rank == 1 else 0):
            errors.append(f"rank {rank}: memorable must be 1 only for rank 1")
        folded = sentence.casefold()
        if folded in seen_sentences:
            errors.append(f"rank {rank}: duplicate sentence")
        seen_sentences.add(folded)
        if THAI_RE.search(sentence) or MARKUP_RE.search(sentence) or FIELD_LABEL_RE.search(sentence) or SERIALIZATION_ARTIFACT_RE.search(sentence):
            errors.append(f"rank {rank}: Thai, Markdown, or field label in sentence")
        if PLACEHOLDER_RE.search(sentence):
            errors.append(f"rank {rank}: placeholder sentence")
        if safe_profile is not None:
            gloss_phrase = re.sub(r"[^a-z0-9]+", " ", str(safe_profile.get("gloss", "")).casefold()).strip()
            sentence_phrase = re.sub(r"[^a-z0-9]+", " ", sentence.casefold()).strip()
            if len(gloss_phrase.split()) >= 2 and re.search(rf"(?:^|\s){re.escape(gloss_phrase)}(?:$|\s)", sentence_phrase):
                errors.append(f"rank {rank}: sentence echoes the safe gloss verbatim instead of demonstrating it")
        if GRAMMAR_RED_FLAG_RE.search(sentence):
            errors.append(f"rank {rank}: known grammar/naturalness red flag")
        if UNSAFE_TRIVIA_RE.search(sentence):
            errors.append(f"rank {rank}: unsupported factual trivia")
        if pos == "det":
            following = re.search(rf"(?<![A-Za-z]){re.escape(target)}\s+([A-Za-z]+)", sentence, re.I)
            if following is None or DETERMINER_VERB_FOLLOW_RE.fullmatch(following.group(1)):
                errors.append(f"rank {rank}: determiner target does not directly modify a noun phrase")
            if target.casefold() == "their":
                prefix = sentence[:sentence.casefold().find(target.casefold())]
                if not re.search(r"\b(?:they|them|people|children|students|team|[A-Za-z]+s)\b", prefix, re.I):
                    errors.append(f"rank {rank}: their has no explicit plural owner antecedent")
        # A deterministic-error assignment identifies the exact ranks that may
        # change.  A semantic-audit assignment has no machine-known good ranks,
        # so the model may repair any rank and the human review remains final.
        if record.get("canonical") and rank not in editable_ranks and canonical.get(rank) != row:
            errors.append(f"rank {rank}: valid canonical rank changed")
    return errors


def render_block(headword: str, rows: Iterable[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: row["rank"])
    body = "\n".join(f"{row['rank']}\t{row['sense_id']}\t{row['pos']}\t{row['target']}\t{row['memorable']}\t{row['sentence']}" for row in ordered)
    return f"@ {headword}\n{body}\n"


class OpenAIClient:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def __call__(self, messages: list[dict[str, str]], schema: dict[str, Any]) -> str:
        payload = {"model": self.config["model"], "messages": messages, "temperature": self.config["temperature"], "max_tokens": self.config["max_tokens"], "response_format": {"type": "json_schema", "json_schema": {"name": "vocab_candidate", "strict": True, "schema": schema}}}
        data = json.dumps(payload).encode("utf-8")
        last: Exception | None = None
        for attempt in range(int(self.config.get("http_retries", 3))):
            try:
                request = urllib.request.Request(self.config["api_url"], data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=float(self.config.get("timeout", 180))) as response:
                    decoded = json.load(response)
                return decoded["choices"][0]["message"]["content"]
            except (OSError, KeyError, ValueError, urllib.error.URLError) as error:
                last = error
                if attempt + 1 < int(self.config.get("http_retries", 3)):
                    time.sleep(min(2 ** attempt, 4))
        raise RuntimeError(f"local model API failed: {last}")


def load_records(run_dir: Path) -> dict[int, dict[str, Any]]:
    result = {}
    for line in (run_dir / "input" / "evidence.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        result[int(row["seq"])] = row
    return result


def word_prompt(record: dict[str, Any], mode: str, errors: list[str], previous: Any) -> str:
    payload = {"mode": mode, "assignment": {k: record.get(k) for k in ("seq", "headword", "deterministic_errors", "primary_sense_id", "primary_pos")}, "editable_ranks": sorted(editable_ranks_for(record)), "safe_profile": record["evidence"].get("safe_profile"), "evidence": record["evidence"], "locked_canonical": locked_canonical_for_prompt(record), "validation_errors": errors, "previous_candidate": previous}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def critic_prompt(record: dict[str, Any], mode: str, candidate: dict[str, Any]) -> str:
    payload = {
        "mode": mode,
        "assignment": {k: record.get(k) for k in ("seq", "headword", "deterministic_errors", "primary_sense_id", "primary_pos")},
        "editable_ranks": sorted(editable_ranks_for(record)),
        "safe_profile": record["evidence"].get("safe_profile"),
        "evidence": record["evidence"],
        "locked_canonical": locked_canonical_for_prompt(record),
        "candidate_to_audit_and_correct": candidate,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def reconcile(run_dir: Path, con: sqlite3.Connection) -> None:
    for folder, state in (("accepted", "accepted"), ("quarantine", "quarantine")):
        for path in (run_dir / "output" / folder).glob("*.json"):
            try:
                seq = int(path.stem.split("_", 1)[0])
                json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, json.JSONDecodeError):
                continue
            con.execute("UPDATE words SET status=?,updated_at=? WHERE seq=? AND status NOT IN ('accepted','quarantine')", (state, utc_now(), seq))
    con.execute("UPDATE words SET status='pending',updated_at=? WHERE status IN ('generating','retry_pending')", (utc_now(),))
    con.commit()


def resource_error(run_dir: Path) -> str | None:
    if shutil.disk_usage(run_dir).free < 15 * 1024**3:
        return "disk free below 15 GiB"
    if Path("/proc/meminfo").exists():
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0]) * 1024
        if values.get("MemAvailable", 1 << 60) < 8 * 1024**3:
            return "available RAM below 8 GiB"
        swap_used = values.get("SwapTotal", 0) - values.get("SwapFree", 0)
        if swap_used > 1024**3:
            return "swap usage above 1 GiB"
    return None


def update_combined(run_dir: Path) -> None:
    blocks = []
    report = ["seq\theadword\tstatus\tattempts\terrors"]
    con = sqlite3.connect(run_dir / "state" / "run.sqlite")
    try:
        for seq, headword, status, attempts, errors in con.execute("SELECT seq,headword,status,attempts,errors_json FROM words ORDER BY seq"):
            report.append(f"{seq}\t{headword}\t{status}\t{attempts}\t{errors}")
            if status == "accepted":
                path = run_dir / "output" / "accepted" / f"{seq:04d}_{safe_name(headword)}.json"
                candidate = json.loads(path.read_text(encoding="utf-8"))
                blocks.append(render_block(headword, candidate["rows"]))
    finally:
        con.close()
    atomic_text(run_dir / "output" / "accepted_six_field.txt", "\n".join(blocks))
    atomic_text(run_dir / "output" / "review_report.tsv", "\n".join(report) + "\n")


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "word"


def breaker_reason(outcomes: deque[tuple[bool, bool, list[str]]], consecutive_schema: int, consecutive_timeout: int, sentence_counts: Counter[str]) -> str | None:
    if consecutive_schema >= 5:
        return "five consecutive schema failures"
    if consecutive_timeout >= 3:
        return "three consecutive API timeouts/failures"
    if any(count >= 10 for count in sentence_counts.values()):
        return "sentence duplicated across ten words"
    if len(outcomes) >= 50:
        quarantine = sum(1 for accepted, _, _ in outcomes if not accepted) / len(outcomes)
        first_pass = sum(1 for _, first, _ in outcomes if first) / len(outcomes)
        if quarantine > 0.05:
            return "rolling quarantine rate above 5%"
        if first_pass < 0.85:
            return "rolling first-pass rate below 85%"
    return None


def run_worker(run_dir: Path, client: Callable[[list[dict[str, str]], dict[str, Any]], str] | None = None, *, ignore_resources: bool = False) -> dict[str, Any]:
    input_errors = verify_manifest(run_dir / "input", run_dir / "input" / "manifest.sha256")
    if input_errors:
        raise ValueError("; ".join(input_errors))
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    client = client or OpenAIClient(config)
    records = load_records(run_dir)
    state_path = run_dir / "state" / "run.sqlite"
    con = sqlite3.connect(state_path)
    con.row_factory = sqlite3.Row
    stored_config_sha = con.execute("SELECT value FROM run_meta WHERE key='config_sha256'").fetchone()
    if stored_config_sha is None or stored_config_sha[0] != sha256_file(run_dir / "config.json"):
        con.close()
        raise ValueError("config checksum mismatch")
    reconcile(run_dir, con)
    outcomes: deque[tuple[bool, bool, list[str]]] = deque(maxlen=50)
    sentence_counts: Counter[str] = Counter()
    sentence_window: deque[set[str]] = deque()
    consecutive_schema = consecutive_timeout = 0
    breaker: str | None = None
    try:
        pending = list(con.execute("SELECT seq,headword FROM words WHERE status='pending' ORDER BY seq"))
        for state in pending:
            if verify_manifest(run_dir / "input", run_dir / "input" / "manifest.sha256"):
                breaker = "input checksum changed during run"
                break
            if not ignore_resources and (problem := resource_error(run_dir)):
                breaker = problem
                break
            seq, headword = state["seq"], state["headword"]
            record = records[seq]
            con.execute("UPDATE words SET status='generating',started_at=?,updated_at=? WHERE seq=?", (utc_now(), utc_now(), seq)); con.commit()
            started = time.monotonic(); previous: Any = None; errors: list[str] = []
            accepted: dict[str, Any] | None = None; first_pass = False; api_failed = False
            max_attempts = 1 + int(config.get("max_model_retries", 2))
            for attempt in range(1, max_attempts + 1):
                con.execute("UPDATE words SET attempts=?,updated_at=? WHERE seq=?", (attempt, utc_now(), seq)); con.commit()
                messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": word_prompt(record, config["mode"], errors, previous)}]
                try:
                    raw = client(messages, OUTPUT_SCHEMA)
                    candidate = json.loads(raw)
                    normalizations = normalize_candidate_targets(candidate, record)
                    errors = validate_candidate(candidate, record)
                    previous = candidate
                    api_failed = False
                    if not errors and config.get("critic_pass", True):
                        critic_messages = [
                            {"role": "system", "content": CRITIC_PROMPT},
                            {"role": "user", "content": critic_prompt(record, config["mode"], candidate)},
                        ]
                        critic_raw = client(critic_messages, OUTPUT_SCHEMA)
                        critic_candidate = json.loads(critic_raw)
                        critic_normalizations = normalize_candidate_targets(critic_candidate, record)
                        critic_errors = validate_candidate(critic_candidate, record)
                        jsonl_append(run_dir / "logs" / "events.jsonl", {
                            "at": utc_now(), "event": "critic", "seq": seq,
                            "headword": headword, "attempt": attempt,
                            "normalizations": critic_normalizations, "errors": critic_errors,
                        })
                        candidate = critic_candidate
                        previous = critic_candidate
                        normalizations.extend(critic_normalizations)
                        errors = critic_errors
                except (json.JSONDecodeError, TypeError) as error:
                    detail = error.msg if isinstance(error, json.JSONDecodeError) else str(error)
                    errors = [f"schema: malformed JSON: {detail}"]; previous = raw; api_failed = False; normalizations = []
                except Exception as error:  # the API boundary must quarantine and preserve state
                    errors = [f"api: {error}"]; previous = None; api_failed = True; normalizations = []
                jsonl_append(run_dir / "logs" / "events.jsonl", {"at": utc_now(), "event": "attempt", "seq": seq, "headword": headword, "attempt": attempt, "normalizations": normalizations, "errors": errors})
                if not errors:
                    accepted = candidate
                    first_pass = attempt == 1
                    break
                if api_failed:
                    break
                if attempt < max_attempts:
                    con.execute("UPDATE words SET status='retry_pending',errors_json=?,updated_at=? WHERE seq=?", (json.dumps(errors, ensure_ascii=False), utc_now(), seq)); con.commit()
            elapsed = time.monotonic() - started
            folder = "accepted" if accepted is not None else "quarantine"
            payload = accepted if accepted is not None else {"headword": headword, "errors": errors, "last_candidate": previous}
            destination = run_dir / "output" / folder / f"{seq:04d}_{safe_name(headword)}.json"
            atomic_json(destination, payload)
            status = "accepted" if accepted is not None else "quarantine"
            con.execute("UPDATE words SET status=?,first_pass=?,errors_json=?,elapsed_seconds=?,updated_at=? WHERE seq=?", (status, int(first_pass), json.dumps(errors, ensure_ascii=False), elapsed, utc_now(), seq)); con.commit()
            outcomes.append((accepted is not None, first_pass, errors))
            if len(sentence_window) == 50:
                for sentence in sentence_window.popleft():
                    sentence_counts[sentence] -= 1
                    if sentence_counts[sentence] <= 0:
                        del sentence_counts[sentence]
            current_sentences: set[str] = set()
            if accepted:
                for row in accepted["rows"]:
                    current_sentences.add(row["sentence"].casefold())
                sentence_counts.update(current_sentences)
            sentence_window.append(current_sentences)
            schema_failed = accepted is None and any(error.startswith("schema:") for error in errors)
            consecutive_schema = consecutive_schema + 1 if schema_failed else 0
            consecutive_timeout = consecutive_timeout + 1 if api_failed else 0
            breaker = breaker_reason(outcomes, consecutive_schema, consecutive_timeout, sentence_counts)
            if breaker:
                break
        final_state = "needs_attention" if breaker else "completed"
        con.execute("INSERT OR REPLACE INTO run_meta VALUES('status',?)", (final_state,))
        con.execute("INSERT OR REPLACE INTO run_meta VALUES('breaker_reason',?)", (breaker or "",))
        con.commit()
    finally:
        con.close()
    update_combined(run_dir)
    write_manifest(run_dir / "output", run_dir / "output" / "manifest.sha256")
    result = make_summary(run_dir)
    jsonl_append(run_dir / "logs" / "events.jsonl", {"at": utc_now(), "event": result["status"], "breaker_reason": result.get("breaker_reason")})
    return result


def status_report(run_dir: Path) -> dict[str, Any]:
    con = sqlite3.connect(run_dir / "state" / "run.sqlite")
    try:
        counts = dict(con.execute("SELECT status,count(*) FROM words GROUP BY status"))
        meta = dict(con.execute("SELECT key,value FROM run_meta"))
        total = con.execute("SELECT count(*) FROM words").fetchone()[0]
    finally:
        con.close()
    return {"status": meta.get("status", "built"), "total": total, "counts": counts, "breaker_reason": meta.get("breaker_reason") or None}


def make_summary(run_dir: Path) -> dict[str, Any]:
    report = status_report(run_dir)
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    con = sqlite3.connect(run_dir / "state" / "run.sqlite")
    try:
        attempts = Counter(str(row[0]) for row in con.execute("SELECT attempts FROM words"))
        elapsed = con.execute("SELECT coalesce(sum(elapsed_seconds),0) FROM words").fetchone()[0]
        errors = Counter()
        for (raw,) in con.execute("SELECT errors_json FROM words"):
            for error in json.loads(raw):
                errors[error.split(":", 1)[0]] += 1
    finally:
        con.close()
    model_provenance_path = Path("/opt/models/Qwen_Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf.provenance.json")
    try:
        model_provenance = json.loads(model_provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        model_provenance = None
    try:
        llama_commit = Path("/etc/vocab-pipeline/llama.commit").read_text(encoding="utf-8").strip()
    except OSError:
        llama_commit = None
    runtime = {"model_provenance": model_provenance, "llama_commit": llama_commit,
               "qwen": {key: os.environ.get(key) for key in ("QWEN_CONTEXT", "QWEN_THREADS", "QWEN_GPU_LAYERS", "QWEN_CPU_MOE", "QWEN_KV_K", "QWEN_KV_V")}}
    summary = {**report, "updated_at": utc_now(), "input_manifest_sha256": sha256_file(run_dir / "input" / "manifest.sha256"), "evidence_db_sha256": config.get("evidence_db_sha256"), "worker_sha256": config.get("worker_sha256"), "model": config.get("model"), "runtime": runtime, "sampling": {k: config.get(k) for k in ("temperature", "max_tokens", "timeout")}, "attempt_histogram": dict(attempts), "error_histogram": dict(errors), "elapsed_seconds": elapsed, "accepted_words_per_minute": (report["counts"].get("accepted", 0) * 60 / elapsed if elapsed else 0)}
    atomic_json(run_dir / "summary.json", summary)
    return summary


def summary_report(run_dir: Path) -> dict[str, Any]:
    return make_summary(run_dir)


def verify_result(run_dir: Path) -> dict[str, Any]:
    errors = verify_manifest(run_dir / "input", run_dir / "input" / "manifest.sha256")
    output_manifest = run_dir / "output" / "manifest.sha256"
    errors.extend(verify_manifest(run_dir / "output", output_manifest))
    records = load_records(run_dir)
    state = status_report(run_dir)
    con = sqlite3.connect(run_dir / "state" / "run.sqlite")
    try:
        meta = dict(con.execute("SELECT key,value FROM run_meta"))
        accepted = list(con.execute("SELECT seq,headword FROM words WHERE status='accepted' ORDER BY seq"))
        quarantine_count = con.execute("SELECT count(*) FROM words WHERE status='quarantine'").fetchone()[0]
    finally:
        con.close()
    if meta.get("config_sha256") != sha256_file(run_dir / "config.json"):
        errors.append("config checksum mismatch")
    for seq, headword in accepted:
        path = run_dir / "output" / "accepted" / f"{seq:04d}_{safe_name(headword)}.json"
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as error:
            errors.append(f"accepted seq {seq}: unreadable candidate: {error}")
            continue
        errors.extend(f"accepted seq {seq}: {error}" for error in validate_candidate(candidate, records[seq]))
    accepted_files = len(list((run_dir / "output" / "accepted").glob("*.json")))
    quarantine_files = len(list((run_dir / "output" / "quarantine").glob("*.json")))
    if accepted_files != len(accepted):
        errors.append("accepted file count differs from state database")
    if quarantine_files != quarantine_count:
        errors.append("quarantine file count differs from state database")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    if summary.get("counts") != state.get("counts") or summary.get("status") != state.get("status"):
        errors.append("summary differs from state database")
    return {"ok": not errors, "status": state["status"], "counts": state["counts"], "errors": errors}


def doctor(api_url: str | None = None) -> dict[str, Any]:
    checks: dict[str, Any] = {"python": True, "sqlite": sqlite3.sqlite_version, "atomic_replace": True}
    if Path("/proc/meminfo").exists():
        problem = resource_error(Path.cwd())
        checks["resource_gate"] = problem or "ok"
        if problem:
            checks["resource_ok"] = False
    if api_url:
        health = api_url.split("/v1/", 1)[0] + "/health"
        try:
            with urllib.request.urlopen(health, timeout=5) as response:
                checks["api"] = response.status == 200
        except OSError as error:
            checks["api"] = False
            checks["api_error"] = str(error)
    checks["ok"] = all(value is not False for value in checks.values())
    return checks
