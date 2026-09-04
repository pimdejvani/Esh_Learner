#!/usr/bin/env python3
"""Pre-render everything a review agent needs for one batch into a single file.

Every review agent used to write its own sqlite queries against
``data/vocabulary_evidence.db``, rediscover the same joins, and hit the same
cp1252 crash on ``cap``'s emoji form.  That is ~20-30k tokens of fixed cost per
agent before it authors a single sentence, repeated once per batch.

This script does that work deterministically -- no model involved -- so the
agent opens one prepared file instead.  Senses that carry a rarity tag are
marked ``[RARE]`` and POS whose senses are *all* rare are called out, because
that is the judgement the agents were getting wrong (chasing POS coverage into
archaic senses and inventing "He attituded proudly").

    python tools/build_evidence_pack.py --seq-start 726 --seq-end 750
    python tools/build_evidence_pack.py --priority audit --batch-size 25
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import translate_vocab_content as drafts
from build_content_db import REJECT_TAGS

ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "data" / "terra_english_drafts"
MANIFEST = ROOT / "data" / "sol_review_manifest.txt"
DEFECTS = ROOT / "data" / "coverage_defects.tsv"
OUTPUT_DIR = ROOT / "data" / "evidence_packs"
SOURCE_DB = drafts.SOURCE_DB

# Keep a pack readable: a word like `cap` has 40+ senses, most of them junk.
MAX_SENSES_PER_POS = 12
MAX_EXAMPLES_PER_SENSE = 2


def rarity(tags_json: str | None) -> list[str]:
    """Rarity tags on a sense, in the project's existing vocabulary."""
    if not tags_json:
        return []
    try:
        tags = json.loads(tags_json)
    except (ValueError, TypeError):
        return []
    if isinstance(tags, dict):
        tags = tags.get("tags") or []
    return sorted({str(t) for t in tags if str(t) in REJECT_TAGS})


def manifest_rows(start: int, end: int) -> list[dict]:
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        seq = int(f[0])
        if start <= seq <= end:
            rows.append({
                "seq": seq, "priority": f[1], "source_rank": f[2],
                "headword": f[3], "source_file": f[4],
                "errors": f[5] if len(f) > 5 else "",
            })
    return rows


def canonical_blocks() -> dict[str, list[list[str]]]:
    """Every canonical draft block, keyed by casefolded headword."""
    blocks: dict[str, list[list[str]]] = {}
    for path in sorted(DRAFT_DIR.glob("*.txt")):
        current = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("@ "):
                current = line[2:].strip().casefold()
                blocks[current] = []
            elif line.strip() and current:
                fields = line.split("\t")
                if len(fields) >= 6:
                    blocks[current].append(fields)
    return blocks


def defect_rows() -> dict[str, list[list[str]]]:
    if not DEFECTS.exists():
        return {}
    out: dict[str, list[list[str]]] = defaultdict(list)
    lines = DEFECTS.read_text(encoding="utf-8").splitlines()
    for line in lines[1:]:
        f = line.split("\t")
        if len(f) >= 7:
            out[f[1].casefold()].append(f)
    return out


def render_word(db: sqlite3.Connection, row: dict, block: list[list[str]],
                defects: list[list[str]]) -> str:
    hw = row["headword"]
    word = db.execute(
        "SELECT id, cefr_first FROM words WHERE headword = ?", (hw,)
    ).fetchone()
    if word is None:
        return f"\n## {row['seq']} {hw}\n\nNOT IN EVIDENCE DB -- skip and report.\n"

    out = [f"\n## {row['seq']}  {hw}   (CEFR {word['cefr_first']}, "
           f"priority {row['priority']})"]

    senses = db.execute(
        "SELECT id, pos, gloss, tags_json FROM source_senses "
        "WHERE word_id = ? ORDER BY id", (word["id"],)
    ).fetchall()
    examples: dict[tuple, list[str]] = defaultdict(list)
    for ex in db.execute(
        "SELECT pos, sense_gloss, example_text, example_type FROM source_examples "
        "WHERE word_id = ?", (word["id"],)
    ):
        if ex["example_type"] == "example":
            examples[(ex["pos"], ex["sense_gloss"])].append(ex["example_text"])

    by_pos: dict[str, list] = defaultdict(list)
    for sense in senses:
        by_pos[sense["pos"]].append(sense)

    forms_by_pos: dict[str, set] = defaultdict(set)
    for form in db.execute(
        "SELECT DISTINCT form_text, pos, tags_json FROM source_forms WHERE word_id = ?",
        (word["id"],)
    ):
        text = form["form_text"]
        # Kaikki lists every attested spelling.  Drop the artefacts (emoji, IPA,
        # foreign script), the abbreviations and dialect spellings REJECT_TAGS
        # already exists to catch, and anything that is not a single word --
        # otherwise `about` offers "a., ab., aboot, abowt, abt." as its forms.
        if not text.isascii() or " " in text.strip() or "." in text:
            continue
        if rarity(form["tags_json"]):
            continue
        forms_by_pos[form["pos"]].add(text)
    # The headword itself is always a usable target for every POS it has.
    for pos in by_pos:
        forms_by_pos[pos].add(hw)

    out.append("\n### canonical block (READ-ONLY, discard the sentences)")
    if block:
        for f in block:
            out.append(f"  r{f[0]} sense={f[1]} {f[2]} [{f[3]}] {f[5]}")
    else:
        out.append("  (no canonical block found)")
    if row["errors"]:
        out.append(f"  manifest errors: {row['errors']}")

    out.append("\n### senses")
    for pos in sorted(by_pos):
        pos_senses = by_pos[pos]
        usable = [s for s in pos_senses if not rarity(s["tags_json"])]
        flag = "  <-- EVERY SENSE IS RARE/TAGGED: strong candidate to SKIP this POS" \
            if not usable else ""
        out.append(f"\n  [{pos}] {len(pos_senses)} senses, {len(usable)} untagged{flag}")
        forms = sorted(forms_by_pos.get(pos, set()))
        if forms:
            out.append(f"  forms available: {', '.join(forms)}")
        for sense in pos_senses[:MAX_SENSES_PER_POS]:
            tags = rarity(sense["tags_json"])
            mark = f" [RARE: {','.join(tags)}]" if tags else ""
            out.append(f"    {sense['id']}{mark}  {sense['gloss']}")
            for ex in examples.get((pos, sense["gloss"]), [])[:MAX_EXAMPLES_PER_SENSE]:
                out.append(f"        e.g. {ex}")
        if len(pos_senses) > MAX_SENSES_PER_POS:
            out.append(f"    ... {len(pos_senses) - MAX_SENSES_PER_POS} more senses "
                       f"omitted (query the DB if you need them)")

    if defects:
        out.append("\n### coverage findings (ADVISORY -- suggested_action is a "
                   "candidate, not an order)")
        for d in defects:
            rank = f" r{d[4]}" if d[4] not in ("-", "") else ""
            out.append(f"  {d[3]:6} {d[2]}{rank}: {d[5]}")
    return "\n".join(out) + "\n"


def build(start: int, end: int, blocks, defects, db) -> Path:
    rows = manifest_rows(start, end)
    if not rows:
        raise SystemExit(f"no manifest rows in seq {start}..{end}")
    header = [
        f"# Evidence pack: seq {start}-{end}  ({len(rows)} headwords)",
        "",
        "Generated by tools/build_evidence_pack.py -- deterministic, no model involved.",
        "Everything you need is here; you should not need to query the database.",
        "",
        "Senses tagged [RARE] carry one of the project's rarity tags "
        "(obsolete/archaic/dialectal/nonstandard/rare/dated/slang/...).",
        "A POS marked 'EVERY SENSE IS RARE' is one you should almost always SKIP -- "
        "chasing POS coverage into those senses is what produced "
        '"He attituded proudly on stage".',
        "Absence of a tag does NOT prove a sense is common: subject-field labels "
        "(nautical, law, ballet, chemistry) were dropped during import, so jargon "
        "senses often carry no tag at all. Judge them yourself.",
        "",
        "Words in this batch: " + ", ".join(r["headword"] for r in rows),
    ]
    body = [render_word(db, r, blocks.get(r["headword"].casefold(), []),
                        defects.get(r["headword"].casefold(), []))
            for r in rows]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"pack_{start:04d}_{end:04d}.md"
    path.write_text("\n".join(header) + "\n" + "".join(body), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq-start", type=int)
    parser.add_argument("--seq-end", type=int)
    parser.add_argument("--priority", choices=("failed", "audit"))
    parser.add_argument("--batch-size", type=int, default=25,
                        help="with --priority, split the range into packs this big")
    args = parser.parse_args()

    db = sqlite3.connect(SOURCE_DB)
    db.row_factory = sqlite3.Row
    blocks = canonical_blocks()
    defects = defect_rows()

    if args.priority:
        seqs = [r["seq"] for r in manifest_rows(1, 10**9)
                if r["priority"] == args.priority]
        lo, hi = min(seqs), max(seqs)
    else:
        if args.seq_start is None or args.seq_end is None:
            parser.error("give --seq-start/--seq-end or --priority")
        lo, hi = args.seq_start, args.seq_end

    if args.priority:
        start = lo
        while start <= hi:
            end = min(start + args.batch_size - 1, hi)
            path = build(start, end, blocks, defects, db)
            print(f"{path.name}\t{path.stat().st_size:,} bytes")
            start = end + 1
    else:
        path = build(lo, hi, blocks, defects, db)
        print(f"{path.name}\t{path.stat().st_size:,} bytes")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
