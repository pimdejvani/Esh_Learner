#!/usr/bin/env python3
"""Materialize a human-reviewed Qwen batch as a complete production overlay.

The reviewer records only the rows that need changes in a small JSON decision
file.  Every other row is copied verbatim from the Qwen candidate.  The command
validates the resulting five-row entries before atomically replacing the report
and overlay, so a partial candidate can never be promoted by accident.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import translate_vocab_content as drafts


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "sol_review_manifest.txt"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def manifest_slice(start: int, end: int) -> list[tuple[int, str]]:
    rows = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            fields = line.split("\t")
            rows[int(fields[0])] = fields[3].casefold()
    return [(seq, rows[seq]) for seq in range(start, end + 1)]


def load_candidate(run_dir: Path, seq: int, headword: str) -> dict:
    matches = []
    for disposition in ("accepted", "quarantine"):
        matches.extend((run_dir / "output" / disposition).glob(f"{seq}_{headword}.json"))
    if len(matches) != 1:
        raise SystemExit(f"expected one Qwen candidate for {seq} {headword}; found {len(matches)}")
    candidate = json.loads(matches[0].read_text(encoding="utf-8"))
    if candidate.get("headword", "").casefold() != headword:
        raise SystemExit(f"candidate headword mismatch: {matches[0]}")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    args = parser.parse_args()

    decisions = json.loads(args.decisions.read_text(encoding="utf-8")).get("words", {})
    entries: dict[str, list[drafts.DraftSentence]] = {}
    report_lines: list[str] = []
    overlay_lines: list[str] = []

    for seq, headword in manifest_slice(args.start, args.end):
        candidate = load_candidate(args.run_dir, seq, headword)
        decision = decisions.get(headword, {})
        overrides = decision.get("rows", {})
        source_rows = {int(row["rank"]): row for row in candidate.get("rows", [])}
        if source_rows and sorted(source_rows) != [1, 2, 3, 4, 5]:
            raise SystemExit(f"candidate ranks are not 1..5: {seq} {headword}")

        built: list[drafts.DraftSentence] = []
        overlay_lines.append(f"@ {headword}")
        for rank in range(1, 6):
            row = dict(source_rows.get(rank, {}))
            row.update(overrides.get(str(rank), {}))
            missing = {"sense_id", "pos", "target", "sentence"} - set(row)
            if missing:
                raise SystemExit(
                    f"incomplete row {rank} for {seq} {headword}; missing {', '.join(sorted(missing))}"
                )
            item = drafts.DraftSentence(
                rank=rank,
                sense_id=int(row["sense_id"]),
                pos=str(row["pos"]),
                target=str(row["target"]),
                memorable=rank == 1,
                en_text=str(row["sentence"]),
            )
            built.append(item)
            overlay_lines.append(
                f"{item.rank}\t{item.sense_id}\t{item.pos}\t{item.target}\t"
                f"{int(item.memorable)}\t{item.en_text}"
            )
        entries[headword] = built
        reason = decision.get(
            "reason",
            "Qwen candidate passed human semantic, grammar, and naturalness review; approved as complete overlay",
        )
        report_lines.append(f"{headword}\trepaired\t{reason}")

    db = sqlite3.connect(drafts.SOURCE_DB)
    db.row_factory = sqlite3.Row
    errors = []
    try:
        for headword, rows in entries.items():
            validation, _ = drafts.validate_entry(db, headword, rows)
            errors.extend(f"{headword}: {error}" for error in validation)
    finally:
        db.close()
    if errors:
        raise SystemExit("reviewed overlay failed validation:\n" + "\n".join(errors))

    atomic_write(args.report, "\n".join(report_lines) + "\n")
    atomic_write(args.overlay, "\n".join(overlay_lines) + "\n")
    print(f"wrote {args.report} ({len(report_lines)} reviewed words)")
    print(f"wrote {args.overlay} ({len(overlay_lines) - len(entries)} sentence rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
