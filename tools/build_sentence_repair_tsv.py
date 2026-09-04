#!/usr/bin/env python3
"""Expand reviewed sentence-repair decisions into the strict overlay TSV."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from apply_sentence_repairs import contains_exact_target
from grammar_explanation_pipeline import validate_input_items


OUTPUT_COLUMNS = (
    "seq", "headword", "rank", "sense_id", "pos", "target", "gloss", "original",
    "decision", "corrected_sentence", "reason",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")
    items = validate_input_items([
        json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line
    ])
    index = {
        (item["seq"], row["rank"]): (item["headword"], row)
        for item in items for row in item["sentences"]
    }
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("decisions must be a non-empty JSON array")
    seen = set()
    output_rows = []
    for number, decision in enumerate(decisions, 1):
        if set(decision) != {"seq", "rank", "headword", "corrected_sentence", "reason"}:
            raise ValueError(f"decision {number}: invalid schema")
        key = (decision["seq"], decision["rank"])
        if key in seen or key not in index:
            raise ValueError(f"decision {number}: duplicate or unknown key {key}")
        seen.add(key)
        headword, source = index[key]
        if decision["headword"] != headword:
            raise ValueError(f"decision {number}: headword mismatch")
        corrected = decision["corrected_sentence"]
        if any(character in corrected for character in "\t\r\n"):
            raise ValueError(f"decision {number}: unsafe corrected sentence")
        if not contains_exact_target(corrected, source["target"]):
            raise ValueError(f"decision {number}: corrected sentence lacks exact target")
        output_rows.append({
            "seq": decision["seq"], "headword": headword, "rank": source["rank"],
            "sense_id": source["sense_id"], "pos": source["pos"], "target": source["target"],
            "gloss": source["gloss"], "original": source["sentence"], "decision": "invalid",
            "corrected_sentence": corrected, "reason": decision["reason"],
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(json.dumps({"repairs": len(output_rows), "sha256": digest, "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
