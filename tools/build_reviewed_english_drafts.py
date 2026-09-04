#!/usr/bin/env python3
"""Create an immutable English snapshot with Sol repair overlays applied.

Canonical drafts remain untouched.  Each overlay headword is replaced only in
the canonical source file named by ``sol_review_manifest.txt``.
"""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

import translate_vocab_content as drafts


ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DIR = ROOT / "data" / "terra_english_drafts"
OVERLAY_DIR = ROOT / "data" / "sol_review_drafts"
MANIFEST = ROOT / "data" / "sol_review_manifest.txt"


def render(headword: str, rows: list[drafts.DraftSentence]) -> list[str]:
    lines = [f"@ {headword}"]
    for row in sorted(rows, key=lambda item: item.rank):
        lines.append(
            f"{row.rank}\t{row.sense_id}\t{row.pos}\t{row.target}\t"
            f"{int(row.memorable)}\t{row.en_text}"
        )
    return lines


def replace_blocks(lines: list[str], replacements: dict[str, list[str]]) -> tuple[list[str], set[str]]:
    output: list[str] = []
    replaced: set[str] = set()
    index = 0
    while index < len(lines):
        if not lines[index].startswith("@ "):
            output.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and not lines[end].startswith("@ "):
            end += 1
        headword = lines[index][2:].strip().casefold()
        if headword in replacements:
            output.extend(replacements[headword])
            replaced.add(headword)
        else:
            output.extend(lines[index:end])
        index = end
    return output, replaced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--canonical-dir", type=Path, default=CANONICAL_DIR)
    parser.add_argument("--overlay-dir", type=Path, default=OVERLAY_DIR)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"refusing to overwrite existing snapshot: {args.output_dir}")

    source_file: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            fields = line.split("\t")
            source_file[fields[3].casefold()] = fields[4]

    by_file: dict[str, dict[str, list[str]]] = {}
    overlay_count = 0
    for path in sorted(args.overlay_dir.glob("*.txt")):
        entries, errors = drafts.parse_draft(path)
        if errors:
            raise SystemExit(f"{path.name}: {errors[0]}")
        for headword, rows in entries.items():
            if headword not in source_file:
                raise SystemExit(f"overlay headword is absent from manifest: {headword}")
            target = by_file.setdefault(source_file[headword], {})
            if headword in target:
                raise SystemExit(f"duplicate overlay headword: {headword}")
            target[headword] = render(headword, rows)
            overlay_count += 1

    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{args.output_dir.name}.", dir=args.output_dir.parent))
    try:
        seen: set[str] = set()
        for path in sorted(args.canonical_dir.glob("*.txt")):
            lines = path.read_text(encoding="utf-8").splitlines()
            updated, replaced = replace_blocks(lines, by_file.get(path.name, {}))
            seen.update(replaced)
            (temporary / path.name).write_text("\n".join(updated) + "\n", encoding="utf-8")
        expected = {headword for replacements in by_file.values() for headword in replacements}
        missing = expected - seen
        if missing:
            raise SystemExit(f"overlay blocks not found in canonical source: {', '.join(sorted(missing))}")
        os.replace(temporary, args.output_dir)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    print(f"snapshot={args.output_dir} overlays={overlay_count} canonical_unchanged=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
