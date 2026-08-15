#!/usr/bin/env python3
"""Assemble compact Terra drafts into one JSON file; never writes SQLite.

Use only after the full first pass and second Terra retry are complete.
The output retains ``sense_id`` so the final DB build can re-resolve the
source gloss rather than trusting a copied field.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from import_terra_compact import DRAFT_DIR, parse_file


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "terra_compact_corpus.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-dir", type=Path, default=DRAFT_DIR)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    entries: dict[str, list[dict]] = {}
    errors: list[str] = []
    for path in sorted(args.draft_dir.glob("*.txt")):
        parsed, parse_errors = parse_file(path)
        # Later retry files intentionally replace the earlier word block.
        entries.update(parsed)
        errors.extend(parse_errors)
    corpus = {
        "format": "terra-compact-v2",
        "entry_count": len(entries),
        "parse_errors": errors,
        "entries": [{"headword": headword, "sentences": sentences}
                    for headword, sentences in sorted(entries.items())],
    }
    args.output.parent.mkdir(exist_ok=True)
    args.output.write_text(json.dumps(corpus, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"output={args.output} entries={len(entries)} parse_errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
