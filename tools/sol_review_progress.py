#!/usr/bin/env python3
"""Validate Sol review reports/overlays and print immutable-manifest progress."""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import translate_vocab_content as drafts


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "sol_review_manifest.txt"
REPORT_DIR = ROOT / "data" / "sol_review_reports"
OVERLAY_DIR = ROOT / "data" / "sol_review_drafts"
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"
NAME = re.compile(r"sol_review_(\d{4})_(\d{4})\.tsv$")


def main() -> int:
    manifest = [
        line.split("\t")
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assigned = {int(row[0]): row[3].casefold() for row in manifest}
    reviewed: dict[int, str] = {}
    repaired_words: set[str] = set()
    errors: list[str] = []

    for path in sorted(REPORT_DIR.glob("*.tsv")) if REPORT_DIR.exists() else []:
        match = NAME.fullmatch(path.name)
        if not match:
            errors.append(f"unexpected report name: {path.name}")
            continue
        start, end = map(int, match.groups())
        rows = [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines() if line]
        expected = [assigned[seq] for seq in range(start, end + 1)]
        actual = [row[0].casefold() for row in rows if len(row) == 3]
        if len(rows) != len(actual) or actual != expected:
            errors.append(f"{path.name}: report rows do not match manifest {start}..{end}")
            continue
        for seq, row in zip(range(start, end + 1), rows, strict=True):
            if seq in reviewed:
                errors.append(f"duplicate reviewed seq: {seq}")
            if row[1] not in {"pass", "repaired"}:
                errors.append(f"{path.name}: invalid status for {row[0]}")
            reviewed[seq] = row[1]

    db = sqlite3.connect(SOURCE_DB)
    db.row_factory = sqlite3.Row
    for path in sorted(OVERLAY_DIR.glob("*.txt")) if OVERLAY_DIR.exists() else []:
        entries, parse_errors = drafts.parse_draft(path)
        errors.extend(f"{path.name}: {error}" for error in parse_errors)
        for headword, rows in entries.items():
            if headword in repaired_words:
                errors.append(f"duplicate repair overlay: {headword}")
            repaired_words.add(headword)
            validation, _ = drafts.validate_entry(db, headword, rows)
            errors.extend(f"{path.name}:{headword}: {error}" for error in validation)
    db.close()

    reported_repaired = {
        assigned[seq] for seq, status in reviewed.items() if status == "repaired"
    }
    if repaired_words != reported_repaired:
        missing = reported_repaired - repaired_words
        extra = repaired_words - reported_repaired
        if missing:
            errors.append(f"reported repair missing overlay: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"overlay not reported repaired: {', '.join(sorted(extra))}")

    failed_total = sum(1 for row in manifest if row[1] == "failed")
    print(
        f"reviewed={len(reviewed)}/{len(manifest)} repaired={len(reported_repaired)} "
        f"failed_priority_reviewed={sum(1 for seq in reviewed if seq <= failed_total)}/{failed_total} "
        f"errors={len(errors)}"
    )
    for error in errors[:100]:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
