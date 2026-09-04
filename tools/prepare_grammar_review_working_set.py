#!/usr/bin/env python3
"""Materialize an immutable grammar-review source and an editable final TSV."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_text(value: str) -> str:
    return digest_bytes(value.encode("utf-8"))


def load_accepted(path: Path) -> dict[tuple[str, int], str]:
    result: dict[tuple[str, int], str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            if len(row) != 3:
                raise ValueError(f"invalid accepted row: {row!r}")
            key = (row[0].casefold(), int(row[1]))
            if key in result:
                raise ValueError(f"duplicate accepted key: {key}")
            result[key] = row[2]
    return result


def load_quarantine(path: Path) -> dict[str, dict]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        key = item["headword"].casefold()
        if key in result:
            raise ValueError(f"duplicate quarantine headword: {key}")
        explanations = {}
        if item.get("raw"):
            try:
                raw = json.loads(item["raw"])
            except json.JSONDecodeError:
                raw = {"explanations": []}
            explanations = {
                int(row["rank"]): row.get("explanation_th", "")
                for row in raw.get("explanations", [])
            }
        result[key] = {**item, "explanations": explanations}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()
    if args.batch_size < 1:
        raise SystemExit("batch size must be positive")
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite: {args.output_dir}")

    input_path = args.run_dir / "input.jsonl"
    accepted_path = args.run_dir / "output" / "accepted.tsv"
    quarantine_path = args.run_dir / "output" / "quarantine.jsonl"
    items = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines()]
    accepted = load_accepted(accepted_path)
    quarantine = load_quarantine(quarantine_path)

    rows = []
    batches = []
    for offset in range(0, len(items), args.batch_size):
        batch = items[offset : offset + args.batch_size]
        batches.append({
            "index": len(batches) + 1,
            "first_seq": batch[0]["seq"],
            "last_seq": batch[-1]["seq"],
            "words": len(batch),
            "rows": len(batch) * 5,
        })
        for item in batch:
            headword = item["headword"]
            qitem = quarantine.get(headword.casefold())
            state = qitem["status"] if qitem else "accepted"
            for source in sorted(item["sentences"], key=lambda value: value["rank"]):
                key = (headword.casefold(), int(source["rank"]))
                candidate = accepted.get(key)
                if candidate is None and qitem:
                    candidate = qitem["explanations"].get(source["rank"], "")
                if candidate is None:
                    raise ValueError(f"missing candidate: {headword} rank {source['rank']}")
                source_json = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                rows.append({
                    "seq": item["seq"],
                    "headword": headword,
                    "rank": source["rank"],
                    "candidate_state": state,
                    "source": source,
                    "source_sha256": digest_text(source_json),
                    "candidate": candidate,
                    "candidate_sha256": digest_text(candidate),
                })

    expected = len(items) * 5
    if len(rows) != expected or len({(row["headword"].casefold(), row["rank"]) for row in rows}) != expected:
        raise ValueError("review rows are not a one-to-one mapping of run input")

    args.output_dir.mkdir(parents=True)
    candidates_path = args.output_dir / "candidates.jsonl"
    candidates_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    final_path = args.output_dir / "final.tsv"
    with final_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        for row in rows:
            writer.writerow((row["seq"], row["headword"], row["rank"], row["candidate"]))
    (args.output_dir / "reviewed_batches.txt").write_text("", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "run_id": args.run_dir.name,
        "input_sha256": digest_bytes(input_path.read_bytes()),
        "accepted_sha256": digest_bytes(accepted_path.read_bytes()),
        "quarantine_sha256": digest_bytes(quarantine_path.read_bytes()),
        "words": len(items),
        "rows": len(rows),
        "batch_size": args.batch_size,
        "batches": batches,
        "candidates_sha256": digest_bytes(candidates_path.read_bytes()),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output_dir), "words": len(items), "rows": len(rows),
                      "batches": len(batches)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
