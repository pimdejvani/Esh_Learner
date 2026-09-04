#!/usr/bin/env python3
"""Print a compact evidence/candidate packet for one Qwen review batch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    args = parser.parse_args()
    evidence = {
        row["seq"]: row
        for row in map(
            json.loads,
            (args.run_dir / "input" / "evidence.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    }
    for seq in range(args.start, args.end + 1):
        matches = []
        for disposition in ("accepted", "quarantine"):
            matches.extend((args.run_dir / "output" / disposition).glob(f"{seq}_*.json"))
        if len(matches) != 1:
            raise SystemExit(f"expected one candidate for seq {seq}; found {len(matches)}")
        candidate = json.loads(matches[0].read_text(encoding="utf-8"))
        profile = evidence[seq]["evidence"]["safe_profile"]
        print(
            f"\n### {seq} {candidate['headword']} | {profile['sense_id']} "
            f"{profile['pos']} | {profile['gloss']}"
        )
        if not candidate.get("rows"):
            print(f"NO ROWS | {candidate.get('reason', '')}")
        for row in candidate.get("rows", []):
            print(
                f"{row['rank']}|{row['sense_id']}|{row['pos']}|{row['target']}|"
                f"{row['sentence']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
