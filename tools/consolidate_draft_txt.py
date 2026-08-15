#!/usr/bin/env python3
"""Consolidate legacy draft formats into one English-only TXT corpus.

Existing files in ``data/terra_english_drafts`` always win.  Compact TXT is
then used only for headwords not already present, followed by JSON and retired
TXT.  This prevents a legacy version from overwriting newer authored work.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import import_terra_compact as compact
import translate_vocab_content as english


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CANONICAL = DATA / "terra_english_drafts"
ACTIVE_COMPACT = DATA / "terra_compact_drafts"
LEGACY_JSON = DATA / "terra_drafts"
RETIRED = DATA / "retired_legacy_drafts"
OUTPUT = CANONICAL / "terra_en_000_consolidated_legacy.txt"
REPORT = DATA / "draft_consolidation_report.txt"
SOURCE_DB = DATA / "vocabulary_source.db"


def render(headword: str, rows: list[dict]) -> str:
    lines = [f"@ {headword}"]
    for row in sorted(rows, key=lambda value: int(value["rank"])):
        fields = (
            row["rank"], row["sense_id"], row["pos"], row["cloze_target"],
            1 if row["is_emotional"] else 0, row["en_text"],
        )
        lines.append("\t".join(str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ") for value in fields))
    return "\n".join(lines)


def json_entries(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and "headword" in value:
        return [value]
    if isinstance(value, dict):
        for key in ("entries", "items", "drafts"):
            if isinstance(value.get(key), list):
                return value[key]
    raise ValueError(f"unsupported JSON shape: {path}")


def convert_json(db: sqlite3.Connection, draft: dict) -> tuple[str, list[dict]]:
    headword = str(draft["headword"]).casefold()
    word = db.execute(
        "SELECT id,headword FROM words WHERE headword=? COLLATE NOCASE", (headword,)
    ).fetchone()
    if word is None:
        raise ValueError(f"unknown JSON headword: {headword}")
    rows: list[dict] = []
    for sentence in draft.get("sentences") or draft.get("cloze_examples") or []:
        gloss = sentence.get("sense_gloss") or sentence.get("source_gloss")
        sense = db.execute(
            "SELECT id FROM source_senses WHERE word_id=? AND pos=? AND gloss=? ORDER BY id LIMIT 1",
            (word["id"], sentence.get("pos"), gloss),
        ).fetchone()
        if sense is None:
            raise ValueError(f"{headword} rank {sentence.get('rank')}: source sense not found")
        rows.append(
            {
                "rank": int(sentence["rank"]),
                "sense_id": int(sense["id"]),
                "pos": str(sentence["pos"]),
                "cloze_target": str(sentence["cloze_target"]),
                "is_emotional": bool(sentence.get("is_emotional")),
                "en_text": str(sentence["en_text"]),
            }
        )
    return str(word["headword"]), rows


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite existing output: {OUTPUT}")

    db = sqlite3.connect(SOURCE_DB)
    db.row_factory = sqlite3.Row
    source_rank = {
        row["headword"].casefold(): int(row["source_rank"])
        for row in db.execute("SELECT headword,source_rank FROM words")
    }

    canonical: set[str] = set()
    parse_errors: list[str] = []
    for path in sorted(CANONICAL.glob("*.txt")):
        entries, errors = english.parse_draft(path)
        canonical.update(entries)
        parse_errors.extend(f"{path.name}: {error}" for error in errors)

    additions: dict[str, tuple[str, list[dict], str]] = {}
    counts = {"existing": len(canonical), "compact_seen": 0, "json_seen": 0, "retired_seen": 0}

    def add_compact_directory(directory: Path, label: str) -> None:
        seen: set[str] = set()
        for path in sorted(directory.glob("*.txt")):
            entries, errors = compact.parse_file(path)
            parse_errors.extend(f"{path.name}: {error}" for error in errors)
            for headword, rows in entries.items():
                seen.add(headword)
                if headword not in canonical and headword not in additions:
                    additions[headword] = (headword, rows, label)
        counts[f"{label}_seen"] = len(seen)

    add_compact_directory(ACTIVE_COMPACT, "compact")

    json_seen: set[str] = set()
    for path in sorted(LEGACY_JSON.glob("*.json")):
        for draft in json_entries(path):
            headword = str(draft["headword"]).casefold()
            json_seen.add(headword)
            if headword in canonical or headword in additions:
                continue
            display, rows = convert_json(db, draft)
            additions[headword] = (display, rows, "json")
    counts["json_seen"] = len(json_seen)

    add_compact_directory(RETIRED, "retired")

    blocks = [
        render(display, rows)
        for key, (display, rows, _) in sorted(
            additions.items(), key=lambda item: source_rank.get(item[0], 10**9)
        )
    ]
    OUTPUT.write_text("\n".join(blocks) + "\n", encoding="utf-8")

    parsed_output, output_errors = english.parse_draft(OUTPUT)
    parse_errors.extend(f"{OUTPUT.name}: {error}" for error in output_errors)
    source_errors: list[str] = []
    for headword, rows in parsed_output.items():
        errors, _ = english.validate_entry(db, headword, rows)
        source_errors.extend(f"{headword}: {error}" for error in errors)

    by_source: dict[str, int] = {}
    for _, _, source in additions.values():
        by_source[source] = by_source.get(source, 0) + 1
    source_total = db.execute(
        "SELECT count(*) FROM words w WHERE EXISTS(SELECT 1 FROM source_senses s WHERE s.word_id=w.id)"
    ).fetchone()[0]
    db.close()

    canonical_total = len(canonical | set(parsed_output))
    report_lines = [
        "Draft consolidation report",
        f"existing_english_headwords={len(canonical)}",
        f"compact_headwords_seen={counts['compact_seen']}",
        f"json_headwords_seen={counts['json_seen']}",
        f"retired_headwords_seen={counts['retired_seen']}",
        f"added_from_compact={by_source.get('compact', 0)}",
        f"added_from_json={by_source.get('json', 0)}",
        f"added_from_retired={by_source.get('retired', 0)}",
        f"canonical_headwords={canonical_total}",
        f"source_headwords={source_total}",
        f"missing_headwords={source_total - canonical_total}",
        f"parse_errors={len(parse_errors)}",
        f"source_validation_errors={len(source_errors)}",
        "",
        "JSON headwords already represented by newer/compact TXT were skipped to avoid overwriting.",
    ]
    if parse_errors:
        report_lines += ["", "Parse errors:", *parse_errors[:100]]
    if source_errors:
        report_lines += ["", "Source validation errors (review after corpus completion):", *source_errors[:200]]
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print("\n".join(report_lines[:14]))
    print(f"output={OUTPUT}")
    print(f"report={REPORT}")
    return 1 if parse_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
