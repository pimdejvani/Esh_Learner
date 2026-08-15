#!/usr/bin/env python3
"""Shared, cached access to the SWOW-EN18 association data.

Both the word selector and the content builder need the same two things from
SWOW: how often a word is produced as a response, and how strongly two words are
associated. Reading the 53 MB strength file each time cost ~40 s per run and the
parsing was duplicated in two scripts.

The cache is derived once over the whole source headword list — which changes
only when the source library is re-harvested — and then filtered in memory for
whatever subset a caller wants.

    python tools/swow_cache.py --refresh
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"
CACHE_PATH = ROOT / "data" / "swow_cache.json"
SWOW_DIR = Path.home() / "Downloads" / "SWOW-EN18"
STRENGTH_CSV = SWOW_DIR / "strength.SWOW-EN.R123.20180827.csv"
RESPONSE_CSV = SWOW_DIR / "responseStats.SWOW-EN.20180827.csv"

# Below this, SWOW respondents linked the pair too rarely for it to read as
# "these belong together" (SPEC.md 6, the Odd One Out bar).
CLOSENESS_MIN = 0.036


def source_headwords() -> set[str]:
    db = sqlite3.connect(f"file:{SOURCE_DB}?mode=ro", uri=True)
    try:
        return {row[0].casefold() for row in db.execute("SELECT headword FROM words")}
    finally:
        db.close()


def build_cache(path: Path = CACHE_PATH) -> dict:
    if not STRENGTH_CSV.exists():
        raise SystemExit(f"{STRENGTH_CSV} not found -- SWOW-EN18 must be downloaded first")
    words = source_headwords()

    # Every response, not just the source headwords: the content builder scores
    # derived family members like "workplace" or "watermelon", which are real
    # words people produce but are not on the Oxford list.
    frequency: dict[str, int] = {}
    with RESPONSE_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            word = row["response"].casefold()
            # A response can appear under more than one row; the highest count
            # is the one the selector has always ordered by.
            frequency[word] = max(frequency.get(word, 0), int(row["Freq.R123"]))

    # Stored as "a\tb\tstrength" lines: a dict of 300k tuples costs far more to
    # load as JSON than a flat list of strings does.
    edges: dict[tuple[str, str], float] = {}
    with STRENGTH_CSV.open(encoding="utf-8", newline="") as handle:
        next(handle, None)
        for line in handle:
            row = line.rstrip("\n").split("\t")
            if len(row) < 5:
                continue
            cue, response = row[0].casefold(), row[1].casefold()
            if cue == response or cue not in words or response not in words:
                continue
            try:
                strength = float(row[4])
            except ValueError:
                continue
            if strength < CLOSENESS_MIN:
                continue
            key = (cue, response) if cue < response else (response, cue)
            if strength > edges.get(key, 0.0):
                edges[key] = strength

    payload = {
        "closeness_min": CLOSENESS_MIN,
        "source_words": len(words),
        "response_frequency": frequency,
        "edges": [f"{a}\t{b}\t{strength:.6f}" for (a, b), strength in sorted(edges.items())],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def load(refresh: bool = False) -> dict:
    if refresh or not CACHE_PATH.exists():
        return build_cache()
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def response_frequency(cache: dict | None = None) -> dict[str, int]:
    return (cache or load())["response_frequency"]


def edges_for(headwords: set[str], cache: dict | None = None) -> dict[tuple[str, str], float]:
    """Symmetric closeness between the given words, above [CLOSENESS_MIN]."""
    result: dict[tuple[str, str], float] = {}
    for line in (cache or load())["edges"]:
        left, right, strength = line.split("\t")
        if left in headwords and right in headwords:
            result[(left, right)] = float(strength)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="rebuild even if the cache exists")
    args = parser.parse_args()
    payload = load(refresh=args.refresh)
    print(
        f"cache={CACHE_PATH.name} source_words={payload['source_words']} "
        f"edges={len(payload['edges'])} frequencies={len(payload['response_frequency'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
