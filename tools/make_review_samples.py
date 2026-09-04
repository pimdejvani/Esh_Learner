#!/usr/bin/env python3
"""Create reproducible, group-stratified review samples from the vocabulary DB."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--group-size", type=int, default=100)
    parser.add_argument("--sample-size", type=int, default=15)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--order", choices=("ascending", "descending"), default="ascending")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def group_seed(seed: str, start: int, end: int) -> int:
    digest = hashlib.sha256(f"{seed}:{start}:{end}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def main() -> int:
    args = parse_args()
    if args.start < 1 or args.end < args.start:
        raise SystemExit("invalid start/end range")
    if args.group_size < 1 or args.sample_size < 1:
        raise SystemExit("group-size and sample-size must be positive")

    with sqlite3.connect(args.db) as connection:
        rows = connection.execute(
            "SELECT source_rank, headword FROM words "
            "WHERE source_rank BETWEEN ? AND ? ORDER BY source_rank",
            (args.start, args.end),
        ).fetchall()
    by_rank = dict(rows)

    groups = []
    for group_start in range(args.start, args.end + 1, args.group_size):
        group_end = min(group_start + args.group_size - 1, args.end)
        population = [(rank, by_rank[rank]) for rank in range(group_start, group_end + 1) if rank in by_rank]
        if not population:
            continue
        count = min(args.sample_size, len(population))
        rng = random.Random(group_seed(args.seed, group_start, group_end))
        sample = sorted(rng.sample(population, count))
        groups.append(
            {
                "start": group_start,
                "end": group_end,
                "population_size": len(population),
                "sample": [{"seq": rank, "word": word} for rank, word in sample],
            }
        )

    if args.order == "descending":
        groups.reverse()
    payload = {
        "db": str(args.db),
        "start": args.start,
        "end": args.end,
        "group_size": args.group_size,
        "sample_size": args.sample_size,
        "seed": args.seed,
        "order": args.order,
        "groups": groups,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({len(groups)} groups, {sum(len(g['sample']) for g in groups)} samples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
