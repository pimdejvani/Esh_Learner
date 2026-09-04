#!/usr/bin/env python3
"""Fail-closed structural checks and review routing for source sentences."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from grammar_explanation_pipeline import validate_input_items


WORD_EDGE = r"(?<!\w){target}(?!\w|'(?:s|re|ve|ll|d|m)\b)"


def contains_target(sentence: str, target: str) -> bool:
    return re.search(WORD_EDGE.format(target=re.escape(target)), sentence, re.IGNORECASE) is not None


def review_codes(sentence: str, target: str) -> list[str]:
    codes = []
    escaped = re.escape(target)
    if re.fullmatch(rf"We\s+{escaped}\s+every day\.", sentence, re.IGNORECASE):
        codes.append("generic-habitual")
    if re.fullmatch(rf"We walk\s+{escaped}\s+home\.", sentence, re.IGNORECASE):
        codes.append("generic-walk-home")
    if re.fullmatch(rf"It is\s+{escaped}\.", sentence, re.IGNORECASE):
        codes.append("thin-copular")
    if re.fullmatch(r"There (?:is|are) (?:one|two|three|a|an)\s+\w+\.", sentence, re.IGNORECASE):
        codes.append("thin-existential")
    if len(re.findall(r"[A-Za-z0-9']+", sentence)) < 4:
        codes.append("very-short")
    return codes


def inspect(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validated = validate_input_items(items)
    findings = []
    normalized_sentences: dict[str, list[tuple[int, str, int]]] = collections.defaultdict(list)
    for item in validated:
        for row in item["sentences"]:
            sentence = row["sentence"].strip()
            base = {
                "seq": item["seq"], "headword": item["headword"], "rank": row["rank"],
                "sense_id": row["sense_id"], "pos": row["pos"], "target": row["target"],
                "sentence": sentence, "gloss": row["gloss"],
            }
            if not contains_target(sentence, row["target"]):
                findings.append({**base, "severity": "error", "code": "target-absent"})
            if sentence[0].isascii() and sentence[0].isalpha() and sentence[0].islower():
                findings.append({**base, "severity": "error", "code": "lowercase-initial"})
            for code in review_codes(sentence, row["target"]):
                findings.append({**base, "severity": "review", "code": code})
            normalized = re.sub(r"\s+", " ", sentence.casefold())
            normalized_sentences[normalized].append((item["seq"], item["headword"], row["rank"]))

    for occurrences in normalized_sentences.values():
        if len(occurrences) < 2:
            continue
        for seq, headword, rank in occurrences:
            findings.append({
                "seq": seq, "headword": headword, "rank": rank,
                "severity": "review", "code": "duplicate-sentence",
                "occurrences": [
                    {"seq": other_seq, "headword": other_headword, "rank": other_rank}
                    for other_seq, other_headword, other_rank in occurrences
                ],
            })

    findings.sort(key=lambda row: (row["seq"], row["rank"], row["severity"], row["code"]))
    counts = collections.Counter((row["severity"], row["code"]) for row in findings)
    summary = {
        "words": len(validated),
        "sentences": len(validated) * 5,
        "errors": sum(1 for row in findings if row["severity"] == "error"),
        "review_findings": sum(1 for row in findings if row["severity"] == "review"),
        "deterministic_ready": not any(row["severity"] == "error" for row in findings),
        "counts": {f"{severity}:{code}": count for (severity, code), count in sorted(counts.items())},
    }
    return findings, summary


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], bytes]:
    raw = path.read_bytes()
    rows = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"input line {number}: invalid JSON: {exc}") from exc
    return rows, raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    items, raw = load_jsonl(args.input)
    findings, summary = inspect(items)
    summary["input_sha256"] = hashlib.sha256(raw).hexdigest()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in findings),
        encoding="utf-8", newline="\n",
    )
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["deterministic_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
