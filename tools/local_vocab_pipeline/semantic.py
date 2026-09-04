from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any, Callable

from .pipeline import OpenAIClient, atomic_json, load_records, sha256_file, validate_candidate


SEMANTIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headword", "decision", "severity", "reason", "checks", "issues", "rows"],
    "properties": {
        "headword": {"type": "string"},
        "decision": {"type": "string", "enum": ["pass", "repair", "quarantine"]},
        "severity": {"type": "string", "enum": ["pass", "soft", "hard", "severe"]},
        "reason": {"type": "string"},
        "checks": {
            "type": "array", "minItems": 5, "maxItems": 5,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["rank", "gloss_match", "grammar_natural", "target_pos_match", "learner_safe", "reason"],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 5},
                    "gloss_match": {"type": "boolean"},
                    "grammar_natural": {"type": "boolean"},
                    "target_pos_match": {"type": "boolean"},
                    "learner_safe": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            },
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["rank", "severity", "code", "reason"],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 5},
                    "severity": {"type": "string", "enum": ["soft", "hard", "severe"]},
                    "code": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
        "rows": {
            "type": "array", "minItems": 5, "maxItems": 5,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["rank", "sense_id", "pos", "target", "memorable", "sentence"],
                "properties": {
                    "rank": {"type": "integer", "minimum": 1, "maximum": 5},
                    "sense_id": {"type": "integer"},
                    "pos": {"type": "string"},
                    "target": {"type": "string"},
                    "memorable": {"type": "integer", "enum": [0, 1]},
                    "sentence": {"type": "string"},
                },
            },
        },
    },
}


SEMANTIC_PROMPT = """You are an independent final semantic validator for English learner sentences. Return only JSON matching the schema. First return exactly five checks, one per rank in order. For each input row, independently decide whether it matches the exact supplied gloss, is grammatical and idiomatic including agreement and countability, uses its target as the declared POS, and is safe for an ordinary learner. A pass requires every check boolean to be true. Grammar, countability, articles, word order, idiomatic collocation, target function, and natural modern usage are blocking. Reject sense drift, dictionary-style or metalinguistic examples, tautologies, vague contexts, invented collocations, unsupported factual or normative claims, and rare, archaic, restricted, or technical usages unsuitable for ordinary learners. Test the exact sense by mentally substituting a short paraphrase of the supplied gloss for the target; if the sentence changes meaning, becomes false, or only works under a more common sense, gloss_match is false. A related sense, metaphor, emotional state, personal quality, output, or associated object is not interchangeable with a gloss that names a literal entity unless the gloss explicitly allows it. Preserve the semantic roles in the gloss: the subject, direct object, target, instrument, and affected or launched item in a sentence must fill the roles stated by the gloss. Do not demonstrate a gloss by merely echoing its wording next to the target or by disguising it in a target-to-act, target-to-start, or similar circular phrase; use a concrete event that entails the meaning, or quarantine the sense if no idiomatic learner context exists. Check particles and prepositions as part of the lexical sense: a bare verb followed by a fixed particle or preposition may become a different phrasal or prepositional verb, so reject it unless the supplied evidence authorizes that construction for the exact gloss. When the gloss specifies a manner adverb, the target must describe how an explicit action is performed, not act as a focus particle, sentence-level emphasis, or a synonym of merely or just. A comparison adverb requires an explicit comparison standard or two clearly parallel actors or actions. For factual or technical senses, prefer neutral identification, classification, or recording contexts grounded in the gloss instead of inventing causal mechanisms. For a relational adjective, prefer an attributive noun phrase that makes the supplied relation concrete; do not turn it into a gradable personality judgment unless the gloss supports that use. Every form listed in allowed_targets is authorized, including grammatical inflections that differ from the headword; never demand the base form merely because it is the headword. Rank 2 must remain unambiguous when the target is hidden. Rank 1 need not be especially memorable: weak memorability alone is only soft and must never cause repair, but semantic, grammar, and naturalness defects in rank 1 remain blocking.

When human_findings are supplied, repair exactly those ranks first and preserve every other row byte-for-byte unless another hard or severe defect is certain. When findings identify the same systemic semantic failure across all five ranks after repeated repairs, quarantine the safe sense if five concrete idiomatic contexts are not genuinely possible; never keep disguising the gloss as circular example sentences. On a clean validation pass, do not rewrite merely for style. Use decision=pass when the input needs no changes. Use decision=repair when the input has defects, and return a complete corrected five-row candidate; the returned rows must already be clean. Use decision=quarantine when the supplied safe sense cannot support five natural modern learner sentences without changing the source authority. For each row, choose a target only from allowed_targets and declare the exact chosen form in the target field; its sentence must contain that chosen target as a complete word functioning as required_pos. Realize POS conventionally: an adjective modifies a noun or follows a linking verb, an adverb modifies a verb or modifier, a noun fills a noun-phrase role, and a finite verb agrees with its subject. Do not expose chain-of-thought; checks and issue reasons must be short."""


CONSTRAINT_REPAIR_PROMPT = """You repair machine-reported constraints in English learner sentences. Return only JSON matching the schema. Change only ranks named in human_findings and copy every other row exactly. For each named rank, discard its previous sentence and create a genuinely new short sentence from scratch; do not make a minimal suffix or word-form substitution. Choose one form from allowed_targets, declare it in the target field, and include that exact chosen form as a complete word functioning as required_pos. An adjective must modify a noun or follow a linking verb; an adverb modifies a verb or modifier; a noun fills a noun-phrase role; a finite verb agrees with its subject. Return decision=repair with the complete five rows and five short checks. The returned rows must already satisfy all reported constraints."""


DEFAULT_CONFIG = {
    "api_url": "http://127.0.0.1:8082/v1/chat/completions",
    "model": "Qwen3-30B-A3B-Instruct-2507-Q4_K_M",
    "temperature": 0.1,
    "max_tokens": 1400,
    "timeout": 180,
    "http_retries": 2,
    "max_semantic_attempts": 6,
    "batch_size": 25,
    "minimum_gate_words": 25,
    "max_quarantine_rate": 0.05,
}


def _candidate_path(run_dir: Path, seq: int) -> Path:
    matches = list((run_dir / "output" / "accepted").glob(f"{seq:04d}_*.json"))
    if not matches:
        matches = list((run_dir / "output" / "quarantine").glob(f"{seq:04d}_*.json"))
    if len(matches) != 1:
        raise ValueError(f"seq {seq}: expected exactly one accepted or quarantine candidate")
    return matches[0]


def _load_candidate(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidate = payload.get("last_candidate", payload.get("candidate", payload))
    if not isinstance(candidate, dict) or not isinstance(candidate.get("rows"), list):
        raise ValueError(f"candidate has no complete rows: {path}")
    return candidate


def _audit_payload(record: dict[str, Any], candidate: dict[str, Any], findings: list[dict[str, Any]]) -> str:
    evidence = record["evidence"]
    forms_by_pos: dict[str, set[str]] = {}
    for form in evidence.get("forms", []):
        form_text = str(form.get("form_text", "")).strip()
        if form_text and not any(character.isspace() for character in form_text):
            forms_by_pos.setdefault(str(form.get("pos")), set()).add(form_text)
    forms_by_pos.setdefault(str(evidence.get("safe_profile", {}).get("pos")), set()).add(str(evidence["headword"]))
    return json.dumps({
        "assignment": {"seq": record["seq"], "headword": record["headword"]},
        "safe_profile": record["evidence"].get("safe_profile"),
        "evidence": record["evidence"],
        "human_findings": findings,
        "required_row_constraints": [
            {"rank": row["rank"], "current_target": row["target"], "allowed_targets": sorted(forms_by_pos.get(str(row["pos"]), {row["target"]})), "required_pos": row["pos"]}
            for row in candidate["rows"]
        ],
        "candidate_to_validate": candidate,
    }, ensure_ascii=False, sort_keys=True)


def _as_candidate(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "headword": audit["headword"],
        "decision": "repair" if audit["decision"] == "repair" else "pass",
        "reason": audit["reason"],
        "rows": audit["rows"],
    }


def _lock_unflagged_rows(previous: dict[str, Any], repaired: dict[str, Any], flagged_ranks: set[int]) -> None:
    """Prevent the reviewer from turning a targeted repair into stylistic churn."""
    previous_by_rank = {int(row["rank"]): row for row in previous["rows"]}
    repaired["rows"] = [
        row if int(row["rank"]) in flagged_ranks else dict(previous_by_rank[int(row["rank"])])
        for row in repaired["rows"]
    ]


def _deterministic_findings(errors: list[str]) -> list[dict[str, Any]]:
    findings = []
    for error in errors:
        prefix, separator, detail = error.partition(":")
        if not separator or not prefix.startswith("rank "):
            continue
        try:
            rank = int(prefix.removeprefix("rank "))
        except ValueError:
            continue
        findings.append({
            "rank": rank,
            "severity": "hard",
            "codes": ["DETERMINISTIC_VALIDATION"],
            "reason": detail.strip(),
        })
    return findings


def _feedback_constraint_errors(candidate: dict[str, Any], findings: list[dict[str, Any]]) -> list[str]:
    """Keep a repaired row from repeating a lexical construction the human rejected."""
    rows = {int(row["rank"]): row for row in candidate.get("rows", [])}
    errors = []
    particles = r"(?:to|for|with|at|on|off|up|down|out|over|through|after|into|from|by)"
    for finding in findings:
        if "SYSTEMIC_PHRASAL_SENSE_DRIFT" not in finding.get("codes", []):
            continue
        rank = int(finding["rank"])
        row = rows.get(rank)
        if row is None:
            continue
        target = re.escape(str(row["target"]))
        if re.search(rf"(?<![A-Za-z]){target}\s+{particles}(?![A-Za-z])", str(row["sentence"]), re.I):
            errors.append(f"rank {rank}: human-rejected target-plus-particle lexical construction is still present")
    return errors


def _failed_check_findings(audit: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    labels = {
        "gloss_match": "SENSE_DRIFT",
        "grammar_natural": "GRAMMAR_OR_NATURALNESS",
        "target_pos_match": "TARGET_POS_MISMATCH",
        "learner_safe": "LEARNER_SAFETY",
    }
    for check in audit.get("checks", []):
        failed = [code for field, code in labels.items() if check.get(field) is False]
        if failed:
            findings.append({
                "rank": int(check["rank"]),
                "severity": "hard",
                "codes": failed,
                "reason": str(check.get("reason", "failed semantic checklist")),
            })
    return findings


def validate_calibration(calibration: dict[str, Any]) -> None:
    words = calibration.get("words")
    if not isinstance(words, list) or not words:
        raise ValueError("calibration must contain at least one word")
    seqs = [word.get("seq") for word in words]
    if seqs != sorted(set(seqs)):
        raise ValueError("calibration words must be unique and ordered")
    if seqs[0] != calibration["seq_start"] or seqs[-1] != calibration["seq_end"]:
        raise ValueError("calibration range must match its first and last word")
    if calibration.get("mode") != "blind_audit" and seqs != list(range(seqs[0], seqs[-1] + 1)):
        raise ValueError("review calibration words must be consecutive")
    for word in words:
        ranks = [issue.get("rank") for issue in word.get("issues", [])]
        if len(ranks) != len(set(ranks)) or any(rank not in range(1, 6) for rank in ranks):
            raise ValueError(f"seq {word.get('seq')}: invalid or duplicate issue rank")


def build_blind_calibration(run_dir: Path, exclusion_paths: list[Path], output_path: Path, count: int) -> dict[str, Any]:
    if count < 1:
        raise ValueError("blind count must be positive")
    excluded: set[int] = set()
    exclusion_hashes = []
    for path in exclusion_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        excluded.update(int(word["seq"]) for word in payload.get("words", []))
        exclusion_hashes.append({"path": path.name, "sha256": sha256_file(path)})
    records = load_records(run_dir)
    eligible = [
        record for seq, record in sorted(records.items())
        if seq not in excluded and (
            list((run_dir / "output" / "accepted").glob(f"{seq:04d}_*.json"))
            or list((run_dir / "output" / "quarantine").glob(f"{seq:04d}_*.json"))
        )
    ]
    if excluded:
        after = [record for record in eligible if int(record["seq"]) > max(excluded)]
        eligible = after + [record for record in eligible if int(record["seq"]) <= max(excluded)]
    selected = eligible[:count]
    if len(selected) != count:
        raise ValueError(f"requested {count} blind words but only {len(selected)} untouched candidates remain")
    calibration = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "mode": "blind_audit",
        "seq_start": int(selected[0]["seq"]),
        "seq_end": int(selected[-1]["seq"]),
        "selection": {"kind": "untouched", "count": count, "exclusions": exclusion_hashes},
        "words": [{"seq": int(record["seq"]), "headword": record["headword"], "issues": []} for record in selected],
    }
    atomic_json(output_path, calibration)
    return calibration


def semantic_revalidate(
    run_dir: Path,
    calibration_path: Path,
    output_dir: Path,
    *,
    source_candidate_dir: Path | None = None,
    client: Callable[[list[dict[str, str]], dict[str, Any]], str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    effective = {**DEFAULT_CONFIG, **(config or {})}
    validate_calibration(calibration)
    records = load_records(run_dir)
    client = client or OpenAIClient(effective)
    output_dir.mkdir(parents=True, exist_ok=True)
    accepted_dir = output_dir / "accepted"
    quarantine_dir = output_dir / "quarantine"
    accepted_dir.mkdir(exist_ok=True)
    quarantine_dir.mkdir(exist_ok=True)
    atomic_json(output_dir / "config.json", {
        **effective,
        "prompt_sha256": __import__("hashlib").sha256((SEMANTIC_PROMPT + CONSTRAINT_REPAIR_PROMPT + json.dumps(SEMANTIC_SCHEMA, sort_keys=True)).encode()).hexdigest(),
        "source_run_id": calibration["run_id"],
        "source_calibration_sha256": sha256_file(calibration_path),
    })

    audit_all = calibration.get("mode") == "blind_audit"
    repair_words = list(calibration["words"]) if audit_all else [word for word in calibration["words"] if word["issues"]]
    if not repair_words:
        raise ValueError("calibration selects no words to validate")
    recent: deque[bool] = deque(maxlen=50)
    counts = {"total": len(repair_words), "accepted": 0, "quarantine": 0, "pending": 0}
    breaker_reason: str | None = None
    report: list[dict[str, Any]] = []
    for index, word in enumerate(repair_words):
        seq = int(word["seq"])
        record = records.get(seq)
        if record is None or record["headword"] != word["headword"]:
            raise ValueError(f"seq {seq}: calibration does not match source run")
        destination_name = f"{seq:04d}_{word['headword']}.json"
        existing = list(accepted_dir.glob(f"{seq:04d}_*.json")) + list(quarantine_dir.glob(f"{seq:04d}_*.json"))
        if existing:
            payload = json.loads(existing[0].read_text(encoding="utf-8"))
            state = "accepted" if existing[0].parent == accepted_dir else "quarantine"
            counts[state] += 1
            recent.append(state == "accepted")
            report.append(payload["report"])
            continue

        if source_candidate_dir is None:
            candidate = _load_candidate(_candidate_path(run_dir, seq))
        else:
            source_matches = list(source_candidate_dir.glob(f"{seq:04d}_*.json"))
            if len(source_matches) != 1:
                raise ValueError(f"seq {seq}: expected exactly one source candidate")
            candidate = _load_candidate(source_matches[0])
        attempts: list[dict[str, Any]] = []
        final_state = "quarantine"
        prompt_findings = word["issues"]
        for attempt in range(1, int(effective["max_semantic_attempts"]) + 1):
            clean_context_audit = not prompt_findings
            constraint_repair = bool(prompt_findings) and all(
                finding.get("codes") == ["DETERMINISTIC_VALIDATION"] for finding in prompt_findings
            )
            messages = [
                {"role": "system", "content": CONSTRAINT_REPAIR_PROMPT if constraint_repair else SEMANTIC_PROMPT},
                {"role": "user", "content": _audit_payload(record, candidate, prompt_findings)},
            ]
            try:
                audit = json.loads(client(messages, SEMANTIC_SCHEMA))
                repaired = _as_candidate(audit)
                flagged_ranks = {
                    int(issue["rank"]) for issue in (prompt_findings or audit.get("issues", []))
                }
                _lock_unflagged_rows(candidate, repaired, flagged_ranks)
                deterministic_errors = validate_candidate(repaired, record)
                deterministic_errors.extend(_feedback_constraint_errors(repaired, word["issues"]))
                prompt_findings = _deterministic_findings(deterministic_errors)
                if not prompt_findings and audit.get("decision") == "pass":
                    prompt_findings = _failed_check_findings(audit)
                attempts.append({
                    "attempt": attempt,
                    "decision": audit.get("decision"),
                    "severity": audit.get("severity"),
                    "issues": audit.get("issues", []),
                    "deterministic_errors": deterministic_errors,
                })
                candidate = repaired
                if audit.get("decision") == "quarantine":
                    break
                if clean_context_audit and audit.get("decision") in {"pass", "repair"} and not deterministic_errors and not prompt_findings:
                    final_state = "accepted"
                    break
            except (KeyError, TypeError, json.JSONDecodeError) as error:
                attempts.append({"attempt": attempt, "schema_error": str(error)})

        if final_state == "quarantine" and attempts and attempts[-1].get("severity") == "severe":
            breaker_reason = f"severe semantic failure after repair at seq {seq}"
        result_report = {
            "seq": seq,
            "headword": word["headword"],
            "state": final_state,
            "attempts": attempts,
        }
        payload = {"candidate": candidate, "report": result_report}
        atomic_json((accepted_dir if final_state == "accepted" else quarantine_dir) / destination_name, payload)
        counts[final_state] += 1
        recent.append(final_state == "accepted")
        report.append(result_report)

        if breaker_reason:
            counts["pending"] = len(repair_words) - index - 1
            break
        if len(recent) >= int(effective["minimum_gate_words"]) and sum(not passed for passed in recent) / len(recent) > float(effective["max_quarantine_rate"]):
            breaker_reason = f"rolling semantic quarantine rate above {float(effective['max_quarantine_rate']):.1%}"
            counts["pending"] = len(repair_words) - index - 1
            break

    summary = {
        "ok": breaker_reason is None and counts["accepted"] == counts["total"],
        "status": "completed" if breaker_reason is None and counts["pending"] == 0 else "stopped",
        "counts": counts,
        "breaker_reason": breaker_reason,
        "ready_for_blind_gate": breaker_reason is None and counts["accepted"] == counts["total"] and counts["quarantine"] == 0,
        "report": report,
    }
    atomic_json(output_dir / "summary.json", summary)
    return summary
