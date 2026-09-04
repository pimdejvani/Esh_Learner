#!/usr/bin/env python3
"""Re-review canonical/existing-overlay rows and materialize one production batch."""
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
CANONICAL = ROOT / "data" / "terra_english_drafts"
OVERLAY_DIR = ROOT / "data" / "sol_review_drafts"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    args = parser.parse_args()
    decisions = json.loads(args.decisions.read_text(encoding="utf-8")).get("words", {})

    manifest = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            fields = line.split("\t")
            manifest[int(fields[0])] = (fields[3].casefold(), fields[4])
    overlays = {}
    for path in sorted(OVERLAY_DIR.glob("*.txt")):
        entries, errors = drafts.parse_draft(path)
        if errors:
            raise SystemExit(f"{path.name}: {errors[0]}")
        overlays.update(entries)
    canonical_cache = {}
    report_lines = []
    overlay_lines = []
    final_entries = {}

    for seq in range(args.start, args.end + 1):
        headword, filename = manifest[seq]
        from_overlay = headword in overlays
        if from_overlay:
            source_rows = overlays[headword]
        else:
            if filename not in canonical_cache:
                entries, errors = drafts.parse_draft(CANONICAL / filename)
                if errors:
                    raise SystemExit(f"{filename}: {errors[0]}")
                canonical_cache[filename] = entries
            source_rows = canonical_cache[filename][headword]
        decision = decisions.get(headword, {})
        overrides = decision.get("rows", {})
        status = decision.get("status") or ("repaired" if from_overlay or overrides else "pass")
        if status == "pass" and overrides:
            raise SystemExit(f"{headword}: pass cannot contain row overrides")
        rows = []
        for source in sorted(source_rows, key=lambda item: item.rank):
            values = {
                "sense_id": source.sense_id,
                "pos": source.pos,
                "target": source.target,
                "sentence": source.en_text,
            }
            values.update(overrides.get(str(source.rank), {}))
            rows.append(
                drafts.DraftSentence(
                    rank=source.rank,
                    sense_id=int(values["sense_id"]),
                    pos=str(values["pos"]),
                    target=str(values["target"]),
                    memorable=source.rank == 1,
                    en_text=str(values["sentence"]),
                )
            )
        final_entries[headword] = rows
        reason = decision.get("reason") or (
            "Existing complete overlay passed ChatGPT semantic, grammar, and naturalness re-review"
            if status == "repaired"
            else "Canonical five-row block passed ChatGPT semantic, grammar, and naturalness review"
        )
        report_lines.append(f"{headword}\t{status}\t{reason}")
        if status == "repaired":
            overlay_lines.append(f"@ {headword}")
            for row in rows:
                overlay_lines.append(
                    f"{row.rank}\t{row.sense_id}\t{row.pos}\t{row.target}\t"
                    f"{int(row.memorable)}\t{row.en_text}"
                )

    db = sqlite3.connect(drafts.SOURCE_DB)
    db.row_factory = sqlite3.Row
    errors = []
    try:
        for headword, rows in final_entries.items():
            validation, _ = drafts.validate_entry(db, headword, rows)
            errors.extend(f"{headword}: {error}" for error in validation)
    finally:
        db.close()
    if errors:
        raise SystemExit("review batch failed validation:\n" + "\n".join(errors))
    atomic_write(args.report, "\n".join(report_lines) + "\n")
    atomic_write(args.overlay, "\n".join(overlay_lines) + ("\n" if overlay_lines else ""))
    print(f"wrote {args.report} ({len(report_lines)} reviewed words)")
    print(f"wrote {args.overlay} ({sum(line.startswith('@ ') for line in overlay_lines)} overlays)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
