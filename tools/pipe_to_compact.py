#!/usr/bin/env python3
"""Convert a pipe-separated draft into the tab-separated compact format v2.

Authoring drafts with ``|`` avoids tabs being mangled by editors and shells;
this converter is the only step that writes real tabs.  Sentence rows must have
the eight fields of ``terra_compact_format.md``; a trailing ``|`` is allowed.

    python tools/pipe_to_compact.py in.txt data/terra_translated_drafts/batch_x.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

FIELDS = 8


def convert(text: str) -> str:
    out: list[str] = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.startswith(("@", "#")):
            out.append(line)
            continue
        fields = [part.strip() for part in line.rstrip("|").split("|")]
        if len(fields) != FIELDS:
            raise SystemExit(f"line {number}: expected {FIELDS} fields, got {len(fields)}")
        if any("\t" in part for part in fields):
            raise SystemExit(f"line {number}: field contains a tab")
        out.append("\t".join(fields))
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit(__doc__)
    source, destination = Path(argv[0]), Path(argv[1])
    destination.write_text(convert(source.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
