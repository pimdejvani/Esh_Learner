#!/usr/bin/env python3
"""Apply reviewed sentence repairs to a new, byte-preserving snapshot overlay."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REQUIRED_COLUMNS = (
    "seq", "headword", "rank", "sense_id", "pos", "target", "original",
    "decision", "corrected_sentence",
)
ROW_RE = re.compile(r"^(\d+)\t(\d+)\t([^\t]+)\t([^\t]+)\t([01])\t([^\t]*)$")


@dataclass(frozen=True)
class Repair:
    seq: int
    headword: str
    rank: int
    sense_id: int
    pos: str
    target: str
    original: str
    corrected_sentence: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def tree_sha256(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        encoded_name = name.encode("utf-8")
        content = files[name]
        digest.update(len(encoded_name).to_bytes(8, "big"))
        digest.update(encoded_name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def parse_positive_integer(value: str, label: str, row_number: int) -> int:
    if not re.fullmatch(r"[1-9]\d*", value):
        raise ValueError(f"repair row {row_number}: invalid {label}")
    return int(value)


def contains_exact_target(sentence: str, target: str) -> bool:
    pattern = rf"(?<![\w]){re.escape(target)}(?![\w])"
    return re.search(pattern, sentence, flags=re.UNICODE) is not None


def load_repairs(path: Path) -> list[Repair]:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"repair TSV is not a regular file: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t", strict=True)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError("repair TSV is empty") from exc
        if len(header) != len(set(header)):
            raise ValueError("repair TSV has duplicate column names")
        missing = [name for name in REQUIRED_COLUMNS if name not in header]
        if missing:
            raise ValueError(f"repair TSV missing columns: {', '.join(missing)}")
        indexes = {name: header.index(name) for name in REQUIRED_COLUMNS}
        repairs = []
        seen_coordinates: set[tuple[int, str, int]] = set()
        seen_full: set[tuple[object, ...]] = set()
        seen_originals: set[str] = set()
        seen_corrections: set[str] = set()
        for row_number, fields in enumerate(reader, 2):
            if len(fields) != len(header):
                raise ValueError(f"repair row {row_number}: expected {len(header)} fields")
            if any(any(character in value for character in "\t\r\n") for value in fields):
                raise ValueError(f"repair row {row_number}: embedded tab or newline")
            values = {name: fields[indexes[name]] for name in REQUIRED_COLUMNS}
            seq = parse_positive_integer(values["seq"], "seq", row_number)
            rank = parse_positive_integer(values["rank"], "rank", row_number)
            sense_id = parse_positive_integer(values["sense_id"], "sense_id", row_number)
            if rank not in range(1, 6):
                raise ValueError(f"repair row {row_number}: rank must be 1-5")
            for name in ("headword", "pos", "target", "original", "corrected_sentence"):
                if not values[name] or values[name] != values[name].strip():
                    raise ValueError(f"repair row {row_number}: invalid {name}")
            if values["decision"] != "invalid":
                raise ValueError(f"repair row {row_number}: decision must be invalid")
            if values["corrected_sentence"] == values["original"]:
                raise ValueError(f"repair row {row_number}: correction is unchanged")
            if not contains_exact_target(values["corrected_sentence"], values["target"]):
                raise ValueError(f"repair row {row_number}: corrected sentence lacks exact target")
            coordinate = (seq, values["headword"], rank)
            full = (
                seq, values["headword"], rank, sense_id, values["pos"],
                values["target"], values["original"],
            )
            if coordinate in seen_coordinates or full in seen_full:
                raise ValueError(f"repair row {row_number}: duplicate repair mapping")
            if values["original"] in seen_originals:
                raise ValueError(f"repair row {row_number}: duplicate original sentence")
            if values["corrected_sentence"] in seen_corrections:
                raise ValueError(f"repair row {row_number}: duplicate corrected sentence")
            seen_coordinates.add(coordinate)
            seen_full.add(full)
            seen_originals.add(values["original"])
            seen_corrections.add(values["corrected_sentence"])
            repairs.append(Repair(
                seq=seq, headword=values["headword"], rank=rank,
                sense_id=sense_id, pos=values["pos"], target=values["target"],
                original=values["original"],
                corrected_sentence=values["corrected_sentence"],
            ))
    if not repairs:
        raise ValueError("repair TSV contains no repairs")
    return repairs


def load_manifest(path: Path) -> dict[str, tuple[int, str]]:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"manifest is not a regular file: {path}")
    result: dict[str, tuple[int, str]] = {}
    seen_seq: set[int] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 5:
            raise ValueError(f"manifest line {number}: expected at least five fields")
        try:
            seq = int(fields[0])
        except ValueError as exc:
            raise ValueError(f"manifest line {number}: invalid seq") from exc
        headword, source_file = fields[3], fields[4]
        if seq < 1 or not headword or not source_file:
            raise ValueError(f"manifest line {number}: invalid mapping")
        if headword in result or seq in seen_seq:
            raise ValueError(f"manifest line {number}: duplicate seq or headword")
        result[headword] = (seq, source_file)
        seen_seq.add(seq)
    if not result:
        raise ValueError("manifest contains no mappings")
    return result


def snapshot_files(directory: Path) -> dict[str, bytes]:
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError(f"snapshot is not a regular directory: {directory}")
    result = {}
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"snapshot contains a non-regular entry: {path.name}")
        result[path.name] = path.read_bytes()
    if not result or not any(name.endswith(".txt") for name in result):
        raise ValueError("snapshot contains no text files")
    return result


def line_body_and_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""


def build_overlay(
    source_files: dict[str, bytes], repairs: list[Repair], manifest: dict[str, tuple[int, str]],
) -> tuple[dict[str, bytes], int]:
    by_coordinate = {(repair.seq, repair.headword, repair.rank): repair for repair in repairs}
    matched: set[tuple[int, str, int]] = set()
    output_files = dict(source_files)
    snapshot_headwords: set[str] = set()
    for file_name, content in source_files.items():
        if not file_name.endswith(".txt"):
            continue
        try:
            lines = content.decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError as exc:
            raise ValueError(f"snapshot file is not UTF-8: {file_name}") from exc
        headword = None
        changed = False
        for index, line in enumerate(lines):
            body, ending = line_body_and_ending(line)
            if not body or body.startswith("#"):
                continue
            if body.startswith("@ "):
                headword = body[2:].strip()
                if not headword or body != f"@ {headword}":
                    raise ValueError(f"{file_name}:{index + 1}: invalid headword line")
                if headword in snapshot_headwords:
                    raise ValueError(f"{file_name}:{index + 1}: duplicate headword: {headword}")
                snapshot_headwords.add(headword)
                continue
            if headword is None:
                raise ValueError(f"{file_name}:{index + 1}: row before headword")
            match = ROW_RE.fullmatch(body)
            if match is None:
                raise ValueError(f"{file_name}:{index + 1}: expected exactly six tab-separated fields")
            rank, sense_id = int(match.group(1)), int(match.group(2))
            pos, target, original = match.group(3), match.group(4), match.group(6)
            manifest_row = manifest.get(headword)
            if manifest_row is None:
                raise ValueError(f"{file_name}:{index + 1}: headword absent from manifest: {headword}")
            seq, expected_file = manifest_row
            if expected_file != file_name:
                raise ValueError(
                    f"{file_name}:{index + 1}: manifest expects {headword} in {expected_file}"
                )
            coordinate = (seq, headword, rank)
            repair = by_coordinate.get(coordinate)
            if repair is None:
                continue
            if coordinate in matched:
                raise ValueError(f"{file_name}:{index + 1}: repair matched more than once")
            actual = (seq, headword, rank, sense_id, pos, target, original)
            expected = (
                repair.seq, repair.headword, repair.rank, repair.sense_id,
                repair.pos, repair.target, repair.original,
            )
            if actual != expected:
                raise ValueError(f"{file_name}:{index + 1}: repair metadata or original mismatch")
            prefix = "\t".join(match.groups()[:5]) + "\t"
            lines[index] = prefix + repair.corrected_sentence + ending
            matched.add(coordinate)
            changed = True
        if changed:
            output_files[file_name] = "".join(lines).encode("utf-8")
    missing = set(by_coordinate) - matched
    if missing:
        seq, headword, rank = sorted(missing)[0]
        raise ValueError(f"repair did not match snapshot: seq={seq} headword={headword} rank={rank}")
    return output_files, len(matched)


def publish(output_dir: Path, files: dict[str, bytes]) -> None:
    if output_dir.exists():
        raise ValueError(f"output directory already exists: {output_dir}")
    if not output_dir.parent.is_dir():
        raise ValueError(f"output parent does not exist: {output_dir.parent}")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        for name, content in files.items():
            (temporary / name).write_bytes(content)
        os.rename(temporary, output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def run(snapshot: Path, repairs_path: Path, manifest_path: Path, output_dir: Path) -> dict[str, object]:
    source_resolved = snapshot.resolve()
    output_resolved = output_dir.resolve()
    if source_resolved == output_resolved or source_resolved in output_resolved.parents:
        raise ValueError("output directory must not be the snapshot or be inside it")
    if output_dir.exists():
        raise ValueError(f"output directory already exists: {output_dir}")
    repairs_bytes = repairs_path.read_bytes()
    repairs = load_repairs(repairs_path)
    manifest = load_manifest(manifest_path)
    source_files = snapshot_files(snapshot)
    output_files, repaired_count = build_overlay(source_files, repairs, manifest)
    changed_files = sum(source_files[name] != output_files[name] for name in source_files)
    publish(output_dir, output_files)
    return {
        "source_files": len(source_files),
        "changed_files": changed_files,
        "repaired_sentences": repaired_count,
        "repair_tsv_sha256": sha256_bytes(repairs_bytes),
        "source_tree_sha256": tree_sha256(source_files),
        "output_tree_sha256": tree_sha256(output_files),
        "output": str(output_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--repairs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/sol_review_manifest.txt")
    args = parser.parse_args()
    result = run(args.snapshot, args.repairs, args.manifest, args.output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
