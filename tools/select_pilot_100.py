#!/usr/bin/env python3
"""Select the 100-word pilot subset for the RE Vocab content rebuild.

Constraints (agreed 2026-08-13):

* band quota 40 A1 / 35 A2 / 15 B1 / 10 B2, taken from ``words.cefr_first``
* "most used first" -- ordered by SWOW-EN18 response frequency (Freq.R123)
* the subset must support the group games (Matching / Odd One Out / Word
  Association): it has to contain at least three semantic groups, where a group
  is a hub word plus >= 3 neighbours with SWOW closeness >= 0.036 (SPEC 6.
  Odd One Out threshold)
* at least 10 of the words must have two or more source POS

Output: ``data/pilot_100.json`` -- the word list plus the group structure and
the draft-coverage report used to decide what still needs generation.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import swow_cache

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "vocabulary_source.db"
DRAFT_DIR = ROOT / "data" / "terra_translated_drafts"
OUT_PATH = ROOT / "data" / "pilot_100.json"
CLOSENESS_MIN = swow_cache.CLOSENESS_MIN  # SPEC 6, Odd One Out similarity threshold
QUOTA = {"A1": 40, "A2": 35, "B1": 15, "B2": 10}
MIN_GROUPS = 3
MIN_GROUP_SIZE = 4  # hub + 3 neighbours
MIN_MULTI_POS = 10


def load_pool(db: sqlite3.Connection) -> dict[str, dict]:
    pool: dict[str, dict] = {}
    for row in db.execute(
        "SELECT id, headword, cefr_first FROM words "
        "WHERE source_status='harvested' AND cefr_first IN ('A1','A2','B1','B2')"
    ):
        pool[row[1].casefold()] = {"word_id": row[0], "headword": row[1], "band": row[2]}
    pos_by_word: dict[int, set[str]] = defaultdict(set)
    for word_id, pos in db.execute("SELECT word_id, pos FROM source_senses"):
        if pos:
            pos_by_word[word_id].add(pos)
    for entry in pool.values():
        entry["pos_list"] = sorted(pos_by_word.get(entry["word_id"], ()))
    return pool


def select(pool: dict[str, dict], freq: dict[str, int], edges: dict[str, dict[str, float]]) -> list[str]:
    """Frequency-seeded, connectivity-greedy fill inside the band quotas."""
    ordered = sorted(pool, key=lambda word: (-freq.get(word, 0), word))
    taken: list[str] = []
    per_band = dict.fromkeys(QUOTA, 0)

    def room(word: str) -> bool:
        return per_band[pool[word]["band"]] < QUOTA[pool[word]["band"]]

    def take(word: str) -> None:
        taken.append(word)
        per_band[pool[word]["band"]] += 1

    # Seeds: the most-used word of each band, then hubs with the most in-pool
    # neighbours, so the subset starts from real association clusters.
    hubs = sorted(
        (word for word in ordered if len(edges.get(word, ())) >= MIN_GROUP_SIZE - 1),
        key=lambda word: (-len(edges[word]), -freq.get(word, 0), word),
    )
    for word in hubs[: MIN_GROUPS * 2]:
        if room(word) and word not in taken:
            take(word)

    # Fill: prefer words that connect to what is already selected, breaking ties
    # by SWOW frequency, so groups densify instead of scattering.
    while len(taken) < sum(QUOTA.values()):
        selected = set(taken)
        best: tuple[int, int, str] | None = None
        for word in ordered:
            if word in selected or not room(word):
                continue
            links = sum(1 for other in edges.get(word, ()) if other in selected)
            key = (-links, -freq.get(word, 0), word)
            if best is None or key < best:
                best = key
        if best is None:
            break
        take(best[2])
    return taken


def groups(taken: list[str], edges: dict[str, dict[str, float]]) -> list[dict]:
    selected = set(taken)
    found: list[dict] = []
    for word in taken:
        members = sorted(other for other in edges.get(word, ()) if other in selected)
        if len(members) + 1 >= MIN_GROUP_SIZE:
            found.append({"hub": word, "members": members})
    return sorted(found, key=lambda group: -len(group["members"]))


def draft_coverage(taken: list[str]) -> dict[str, list[str]]:
    drafted: set[str] = set()
    for path in sorted(DRAFT_DIR.glob("*.txt")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("@ "):
                drafted.add(line[2:].strip().casefold())
    return {
        "drafted": [word for word in taken if word in drafted],
        "missing": [word for word in taken if word not in drafted],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)
    try:
        pool = load_pool(db)
    finally:
        db.close()
    keys = set(pool)
    cache = swow_cache.load()
    freq = swow_cache.response_frequency(cache)
    edges = defaultdict(dict)
    for (left, right), strength in swow_cache.edges_for(keys, cache).items():
        edges[left][right] = strength
        edges[right][left] = strength
    taken = select(pool, freq, edges)

    found = groups(taken, edges)
    multi_pos = [word for word in taken if len(pool[word]["pos_list"]) >= 2]
    coverage = draft_coverage(taken)
    payload = {
        "closeness_min": CLOSENESS_MIN,
        "quota": QUOTA,
        "words": [
            {**pool[word], "swow_freq": freq.get(word, 0),
             "neighbours": sorted(other for other in edges.get(word, ()) if other in set(taken))}
            for word in taken
        ],
        "groups": found,
        "multi_pos_words": multi_pos,
        "draft_coverage": coverage,
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    per_band: dict[str, int] = defaultdict(int)
    for word in taken:
        per_band[pool[word]["band"]] += 1
    print(f"selected={len(taken)} bands={dict(per_band)}")
    print(f"groups(>= {MIN_GROUP_SIZE} words)={len(found)} multi_pos={len(multi_pos)}")
    print(f"drafted={len(coverage['drafted'])} missing_drafts={len(coverage['missing'])}")
    print(f"wrote {args.out}")

    problems = []
    if len(taken) != sum(QUOTA.values()):
        problems.append("band quota not filled")
    if len(found) < MIN_GROUPS:
        problems.append(f"only {len(found)} semantic groups")
    if len(multi_pos) < MIN_MULTI_POS:
        problems.append(f"only {len(multi_pos)} multi-POS words")
    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
