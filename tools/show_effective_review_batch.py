#!/usr/bin/env python3
"""Print canonical plus existing overlays with source glosses for re-review."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import translate_vocab_content as drafts


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "sol_review_manifest.txt"
CANONICAL = ROOT / "data" / "terra_english_drafts"
OVERLAYS = ROOT / "data" / "sol_review_drafts"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    range_group = parser.add_argument_group("selection")
    range_group.add_argument("--start", type=int)
    range_group.add_argument("--end", type=int)
    range_group.add_argument(
        "--seqs",
        help="Comma-separated sequence numbers; overrides the contiguous range",
    )
    args = parser.parse_args()
    if args.seqs:
        selected = [int(value) for value in args.seqs.split(",") if value.strip()]
    elif args.start is not None and args.end is not None:
        selected = list(range(args.start, args.end + 1))
    else:
        parser.error("provide --seqs or both --start and --end")
    manifest = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            fields = line.split("\t")
            manifest[int(fields[0])] = (fields[3].casefold(), fields[4])

    overlay_entries = {}
    for path in sorted(OVERLAYS.glob("*.txt")):
        entries, errors = drafts.parse_draft(path)
        if errors:
            raise SystemExit(f"{path.name}: {errors[0]}")
        overlay_entries.update(entries)
    canonical_cache = {}
    db = sqlite3.connect(drafts.SOURCE_DB)
    db.row_factory = sqlite3.Row
    try:
        for seq in selected:
            headword, filename = manifest[seq]
            if headword in overlay_entries:
                rows = overlay_entries[headword]
                origin = "overlay"
            else:
                if filename not in canonical_cache:
                    entries, errors = drafts.parse_draft(CANONICAL / filename)
                    if errors:
                        raise SystemExit(f"{filename}: {errors[0]}")
                    canonical_cache[filename] = entries
                rows = canonical_cache[filename][headword]
                origin = "canonical"
            print(f"\n### {seq} {headword} | {origin}")
            for row in sorted(rows, key=lambda item: item.rank):
                sense = db.execute(
                    "SELECT gloss FROM source_senses WHERE id=?", (row.sense_id,)
                ).fetchone()
                gloss = sense["gloss"] if sense else "MISSING SENSE"
                print(
                    f"{row.rank}|{row.sense_id}|{row.pos}|{row.target}|{row.en_text}|{gloss}"
                )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
