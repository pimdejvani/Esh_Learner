#!/usr/bin/env python3
"""Mechanical staging builder for the grammar-explanation production candidate.

This tool performs ONLY deterministic assembly of 8-field compact drafts
(``docs/formats/terra_compact_format.md``).  It makes no linguistic keep/rewrite judgement,
invents no issue codes, rewrites no explanation text, and runs no network
calls.  All semantic review is done upstream by the main AI; the artefacts it
produced (``final.tsv`` for reviewed words, ``data/sol_review_explanations`` for
legacy words) are treated as immutable field-8 inputs here.

Subcommands
-----------
snapshot  Apply the ``source_repairs.tsv`` sentence overlay onto the reviewed
          candidates and assemble an immutable fields-1-6 snapshot for every
          word (reviewed + legacy).  Field 7 (Thai translation) is left empty:
          it is filled later by ``tools/translate_vocab_content.py``.  Writes a
          ``snapshot_index.json`` binding every (headword, rank) key to its
          origin and content/source hashes.

validate  Check a directory of compact draft files against the compact-format
          invariants (7 tabs / 8 fields, ranks 1..5 unique, emotional==1 iff
          rank==1, target verbatim in the sentence, no tab/newline in a field,
          field-7 / field-8 presence per stage) and, when a snapshot index is
          supplied, verify the fields-1-6 SHA binding.

merge     Fill ONLY field 8 onto the translated drafts (field 7 already filled)
          using the reviewed/legacy field-8 sources with reviewed precedence.
          Fields 1-7 of the output are byte-equivalent to the translated input.

pack      Write the staging manifest + checksums binding every input and output
          hash.  The translation provider provenance is left as an empty slot
          to be filled after the translation step actually runs.

Legacy fields-1-6 source (discovered from the real files):
  * ``data/sol_review_drafts/sol_repair_*.txt`` is the *repaired* legacy draft
    subset; where a legacy word has a full 5-rank block there, its field-8
    explanations bind to THOSE sentences (verified by content).
  * ``data/terra_english_drafts/*.txt`` is the canonical fallback for legacy
    words with no sol-repair block; their explanations bind to terra sentences.
  * Reviewed words never draw fields 1-6 from legacy: they come from
    ``candidates.jsonl`` + the ``source_repairs.tsv`` overlay.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# --------------------------------------------------------------------------- #
# hashing / serialization (identical to prepare_grammar_review_working_set.py) #
# --------------------------------------------------------------------------- #
def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_dict_sha256(source: dict) -> str:
    """Canonical source-object hash, matching the reviewed run's serialization."""
    blob = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_text(blob)


def target_occurs(target: str, sentence: str) -> bool:
    pattern = rf"(?<![A-Za-z]){re.escape(target)}(?![A-Za-z])"
    return bool(re.search(pattern, sentence, re.I))


# --------------------------------------------------------------------------- #
# data model                                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class Row:
    headword: str
    rank: int
    sense_id: int
    pos: str
    target: str
    emotional: int
    sentence: str  # effective English sentence (field 6)
    origin: str  # "reviewed" | "legacy-sol" | "legacy-terra"
    seq: int | None = None
    source_sha256_original: str | None = None
    effective_source_sha256: str | None = None
    repaired: bool = False

    def fields16(self) -> tuple[str, ...]:
        return (
            str(self.rank),
            str(self.sense_id),
            self.pos,
            self.target,
            str(self.emotional),
            self.sentence,
        )

    def fields16_line(self) -> str:
        return "\t".join(self.fields16())

    def fields16_sha256(self) -> str:
        return sha256_text(self.fields16_line())


class BuildError(Exception):
    pass


# --------------------------------------------------------------------------- #
# parsing helpers                                                             #
# --------------------------------------------------------------------------- #
def parse_compact_blocks(path: Path) -> dict[str, dict[int, tuple[str, ...]]]:
    """Parse an @-headword compact draft file into {headword: {rank: fields}}.

    Accepts 6- or 8-field rows; returns whatever fields are present.
    """
    out: dict[str, dict[int, tuple[str, ...]]] = {}
    headword: str | None = None
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("@ "):
            headword = raw[2:].strip().casefold()
            if not headword:
                raise BuildError(f"{path.name}:{number}: empty headword")
            out.setdefault(headword, {})
            continue
        if headword is None:
            raise BuildError(f"{path.name}:{number}: row before headword")
        fields = raw.split("\t")
        if len(fields) not in (6, 8):
            raise BuildError(f"{path.name}:{number}: expected 6 or 8 fields, got {len(fields)}")
        try:
            rank = int(fields[0])
        except ValueError:
            raise BuildError(f"{path.name}:{number}: bad rank {fields[0]!r}")
        out[headword][rank] = tuple(fields)
    return out


def parse_compact_dir(directory: Path) -> dict[str, dict[int, tuple[str, ...]]]:
    merged: dict[str, dict[int, tuple[str, ...]]] = {}
    for path in sorted(directory.glob("*.txt")):
        for headword, ranks in parse_compact_blocks(path).items():
            dest = merged.setdefault(headword, {})
            for rank, fields in ranks.items():
                if rank in dest:
                    raise BuildError(f"duplicate key ({headword}, rank {rank}) across {directory}")
                dest[rank] = fields
    return merged


def load_candidates(path: Path) -> dict[tuple[int, int], dict]:
    """{(seq, rank): candidate object} keyed for repair-overlay lookup."""
    rows: dict[tuple[int, int], dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            obj = json.loads(line)
            rows[(obj["seq"], obj["rank"])] = obj
    return rows


def load_repairs(path: Path) -> dict[tuple[int, int], tuple[str, str]]:
    """{(seq, rank): (headword, repaired_sentence)} from a quoting-aware TSV."""
    repairs: dict[tuple[int, int], tuple[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for lineno, row in enumerate(reader, 1):
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            if len(row) != 4:
                raise BuildError(f"{path.name}:{lineno}: expected 4 columns, got {len(row)}")
            seq, headword, rank, sentence = row
            key = (int(seq), int(rank))
            if key in repairs:
                raise BuildError(f"{path.name}:{lineno}: duplicate repair key {key}")
            repairs[key] = (headword.casefold(), sentence)
    return repairs


def load_final_tsv(path: Path) -> dict[tuple[str, int], str]:
    """{(headword, rank): explanation} from reviewed final.tsv (4 cols)."""
    out: dict[tuple[str, int], str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if len(parts) != 4:
            raise BuildError(f"{path.name}:{lineno}: expected 4 columns, got {len(parts)}")
        _seq, headword, rank, explanation = parts
        out[(headword.casefold(), int(rank))] = explanation
    return out


def load_explanations_dir(directory: Path) -> dict[str, dict[int, str]]:
    """{headword: {rank: explanation}} from legacy sol_review_explanations (3 cols)."""
    out: dict[str, dict[int, str]] = {}
    for path in sorted(directory.glob("*.tsv")):
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            parts = raw.split("\t")
            if len(parts) != 3:
                raise BuildError(f"{path.name}:{lineno}: expected 3 columns, got {len(parts)}")
            headword, rank, explanation = parts
            out.setdefault(headword.casefold(), {})[int(rank)] = explanation
    return out


def full_rank_words(mapping: dict) -> set[str]:
    def ranks(value):
        return sorted(value.keys()) if isinstance(value, dict) else sorted(r for r in value)
    return {word for word, value in mapping.items() if ranks(value) == [1, 2, 3, 4, 5]}


# --------------------------------------------------------------------------- #
# snapshot assembly                                                           #
# --------------------------------------------------------------------------- #
@dataclass
class Assembly:
    rows: dict[str, dict[int, Row]] = field(default_factory=dict)
    blocked: list[dict] = field(default_factory=list)

    def add(self, row: Row) -> None:
        self.rows.setdefault(row.headword, {})[row.rank] = row


def assemble(
    candidates: dict[tuple[int, int], dict],
    repairs: dict[tuple[int, int], tuple[str, str]],
    legacy_sol: dict[str, dict[int, tuple[str, ...]]],
    legacy_terra: dict[str, dict[int, tuple[str, ...]]],
    legacy_expl: dict[str, dict[int, str]],
) -> Assembly:
    asm = Assembly()

    # -- reviewed words (precedence winner) --------------------------------- #
    reviewed_words: set[str] = set()
    seq_by_word: dict[str, int] = {}
    for (seq, rank), obj in candidates.items():
        headword = obj["headword"].casefold()
        reviewed_words.add(headword)
        seq_by_word[headword] = seq
        source = dict(obj["source"])  # rank, sense_id, pos, target, sentence, gloss
        original_source_sha = obj["source_sha256"]
        repaired = False
        if (seq, rank) in repairs:
            rep_word, rep_sentence = repairs[(seq, rank)]
            if rep_word != headword:
                raise BuildError(
                    f"repair seq {seq} rank {rank}: headword {rep_word!r} != candidate {headword!r}"
                )
            if not target_occurs(source["target"], rep_sentence):
                raise BuildError(
                    f"repair seq {seq} rank {rank}: target {source['target']!r} absent in repaired sentence"
                )
            source["sentence"] = rep_sentence
            repaired = True
        sentence = source["sentence"].strip()
        if not target_occurs(source["target"], sentence):
            raise BuildError(
                f"reviewed seq {seq} rank {rank}: target {source['target']!r} absent in sentence"
            )
        asm.add(
            Row(
                headword=headword,
                rank=rank,
                sense_id=int(source["sense_id"]),
                pos=source["pos"].strip(),
                target=source["target"].strip(),
                emotional=1 if rank == 1 else 0,
                sentence=sentence,
                origin="reviewed",
                seq=seq,
                source_sha256_original=original_source_sha,
                effective_source_sha256=source_dict_sha256(source),
                repaired=repaired,
            )
        )

    # -- legacy words (only where field 8 exists as a full 5-rank block) ----- #
    expl_full = full_rank_words(legacy_expl)
    sol_full = full_rank_words(legacy_sol)
    terra_full = full_rank_words(legacy_terra)

    for headword in sorted(expl_full):
        if headword in reviewed_words:
            # reviewed precedence: never let legacy overwrite a reviewed word.
            continue
        if headword in sol_full:
            source_block = legacy_sol[headword]
            origin = "legacy-sol"
        elif headword in terra_full:
            source_block = legacy_terra[headword]
            origin = "legacy-terra"
        else:
            asm.blocked.append(
                {"headword": headword, "reason": "legacy explanation present but no full 5-rank fields-1-6 draft in sol or terra"}
            )
            continue
        for rank in (1, 2, 3, 4, 5):
            fields = source_block[rank]
            rank_v, sense_id, pos, tgt, emo, sentence = fields[:6]
            sentence = sentence.strip()
            emotional = 1 if rank == 1 else 0
            if not target_occurs(tgt.strip(), sentence):
                raise BuildError(
                    f"legacy {headword} rank {rank}: target {tgt!r} absent in sentence"
                )
            row = Row(
                headword=headword,
                rank=rank,
                sense_id=int(sense_id),
                pos=pos.strip(),
                target=tgt.strip(),
                emotional=emotional,
                sentence=sentence,
                origin=origin,
            )
            row.effective_source_sha256 = None
            asm.add(row)

    # words with a legacy explanation that is NOT a clean 5-rank block:
    for headword, ranks in sorted(legacy_expl.items()):
        if headword in reviewed_words or headword in asm.rows:
            continue
        if sorted(ranks.keys()) != [1, 2, 3, 4, 5]:
            asm.blocked.append(
                {
                    "headword": headword,
                    "reason": f"legacy explanation ranks {sorted(ranks.keys())} != [1,2,3,4,5]",
                }
            )
    return asm


def render_block(headword: str, rows: dict[int, Row], fields: int = 6) -> str:
    lines = [f"@ {headword}"]
    for rank in (1, 2, 3, 4, 5):
        row = rows[rank]
        if fields == 6:
            lines.append(row.fields16_line())
        else:
            raise ValueError("render_block only emits 6-field snapshot rows")
    return "\n".join(lines)


def cmd_snapshot(args: argparse.Namespace) -> int:
    review_dir = args.review_dir
    out_dir = args.out_dir
    if out_dir.exists():
        raise BuildError(f"output directory already exists: {out_dir}")

    candidates = load_candidates(review_dir / "candidates.jsonl")
    repairs = load_repairs(review_dir / "source_repairs.tsv")
    legacy_sol = parse_compact_dir(args.legacy_draft_dir)
    legacy_terra = parse_compact_dir(args.legacy_fallback_draft_dir)
    legacy_expl = load_explanations_dir(args.legacy_expl_dir)

    # repair scope: every repair key must exist in candidates.
    for key in repairs:
        if key not in candidates:
            raise BuildError(f"repair key {key} is out of run scope (no matching candidate)")

    asm = assemble(candidates, repairs, legacy_sol, legacy_terra, legacy_expl)

    out_dir.mkdir(parents=True)
    snapshot_dir = out_dir / "snapshot"
    snapshot_dir.mkdir()

    # deterministic file split: one file per origin, words sorted.
    index: dict[str, dict] = {}
    origin_files: dict[str, list[str]] = {}
    origins = {}
    counts = {"reviewed": 0, "legacy-sol": 0, "legacy-terra": 0}
    for headword in sorted(asm.rows):
        rows = asm.rows[headword]
        if sorted(rows.keys()) != [1, 2, 3, 4, 5]:
            raise BuildError(f"{headword}: assembled ranks {sorted(rows.keys())} != [1,2,3,4,5]")
        origin = rows[1].origin
        origins[headword] = origin
        counts[origin] = counts.get(origin, 0) + 1
        origin_files.setdefault(origin, []).append(render_block(headword, rows))
        for rank in (1, 2, 3, 4, 5):
            row = rows[rank]
            index[f"{headword}\t{rank}"] = {
                "headword": headword,
                "rank": rank,
                "origin": row.origin,
                "seq": row.seq,
                "fields16_sha256": row.fields16_sha256(),
                "source_sha256_original": row.source_sha256_original,
                "effective_source_sha256": row.effective_source_sha256,
                "repaired": row.repaired,
            }

    file_hashes: dict[str, str] = {}
    for origin, blocks in sorted(origin_files.items()):
        name = f"snapshot_{origin.replace('-', '_')}.txt"
        content = "\n".join(blocks) + "\n"
        (snapshot_dir / name).write_text(content, encoding="utf-8")
        file_hashes[name] = sha256_text(content)

    index_blob = json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    (out_dir / "snapshot_index.json").write_text(index_blob, encoding="utf-8")

    manifest = {
        "stage": "snapshot",
        "review_dir": str(review_dir),
        "candidates_sha256": sha256_bytes((review_dir / "candidates.jsonl").read_bytes()),
        "source_repairs_sha256": sha256_bytes((review_dir / "source_repairs.tsv").read_bytes()),
        "legacy_draft_dir": str(args.legacy_draft_dir),
        "legacy_fallback_draft_dir": str(args.legacy_fallback_draft_dir),
        "legacy_expl_dir": str(args.legacy_expl_dir),
        "snapshot_index_sha256": sha256_text(index_blob),
        "snapshot_files": file_hashes,
        "repairs_applied": sum(1 for v in index.values() if v["repaired"]),
        "counts": {
            "reviewed_words": counts.get("reviewed", 0),
            "legacy_sol_words": counts.get("legacy-sol", 0),
            "legacy_terra_words": counts.get("legacy-terra", 0),
            "merged_words": len(asm.rows),
            "merged_rows": sum(len(r) for r in asm.rows.values()),
            "blocked_words": len(asm.blocked),
        },
        "blocked": asm.blocked,
    }
    manifest_blob = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (out_dir / "snapshot_manifest.json").write_text(manifest_blob, encoding="utf-8")

    print(json.dumps({"stage": "snapshot", "out": str(out_dir), **manifest["counts"]}, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- #
# validate                                                                    #
# --------------------------------------------------------------------------- #
def load_policy_checkers(policy: dict) -> tuple[list[str], list[re.Pattern]]:
    rules = policy.get("validator_rules", {})
    literals = list(rules.get("banned_literals", []))
    regexes = [re.compile(pat) for pat in rules.get("banned_regexes", [])]
    return literals, regexes


def validate_dir(
    directory: Path,
    *,
    require_translation: bool,
    require_explanation: bool,
    snapshot_index: dict | None = None,
    policy: dict | None = None,
) -> list[str]:
    errors: list[str] = []
    banned_literals: list[str] = []
    banned_regexes: list[re.Pattern] = []
    if policy is not None:
        banned_literals, banned_regexes = load_policy_checkers(policy)
    seen: dict[str, set[int]] = {}
    for path in sorted(directory.glob("*.txt")):
        headword: str | None = None
        raw_text = path.read_text(encoding="utf-8")
        for number, raw in enumerate(raw_text.splitlines(), 1):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            if raw.startswith("@ "):
                headword = raw[2:].strip().casefold()
                seen.setdefault(headword, set())
                continue
            if headword is None:
                errors.append(f"{path.name}:{number}: row before headword")
                continue
            if raw.count("\t") != 7:
                errors.append(f"{path.name}:{number}: expected 7 tabs, got {raw.count('\t')}")
                continue
            fields = raw.split("\t")
            rank_s, sense_s, pos, target, emo, sentence, thai, expl = fields
            for name, value in zip(
                ("rank", "sense_id", "pos", "target", "emotional", "sentence", "thai", "explanation"),
                fields,
            ):
                if "\n" in value or "\r" in value:
                    errors.append(f"{path.name}:{number}: newline inside field {name}")
            try:
                rank = int(rank_s)
            except ValueError:
                errors.append(f"{path.name}:{number}: non-integer rank {rank_s!r}")
                continue
            if rank < 1 or rank > 5:
                errors.append(f"{path.name}:{number}: rank {rank} out of range 1..5")
            if rank in seen[headword]:
                errors.append(f"{path.name}:{number}: duplicate rank {rank} for {headword}")
            seen[headword].add(rank)
            try:
                int(sense_s)
            except ValueError:
                errors.append(f"{path.name}:{number}: non-integer sense_id {sense_s!r}")
            if emo not in ("0", "1"):
                errors.append(f"{path.name}:{number}: emotional must be 0/1, got {emo!r}")
            elif (emo == "1") != (rank == 1):
                errors.append(f"{path.name}:{number}: emotional==1 must hold iff rank==1")
            if not target_occurs(target, sentence):
                errors.append(f"{path.name}:{number}: target {target!r} absent as a whole word in sentence")
            if require_translation and not thai.strip():
                errors.append(f"{path.name}:{number}: field 7 (Thai translation) is empty")
            if require_explanation and not expl.strip():
                errors.append(f"{path.name}:{number}: field 8 (Thai explanation) is empty")
            if expl.strip():
                for literal in banned_literals:
                    if literal in expl:
                        errors.append(f"{path.name}:{number}: explanation contains banned literal {literal!r}")
                for pattern in banned_regexes:
                    if pattern.search(expl):
                        errors.append(f"{path.name}:{number}: explanation matches banned pattern {pattern.pattern!r}")
            if snapshot_index is not None:
                key = f"{headword}\t{rank}"
                record = snapshot_index.get(key)
                if record is None:
                    errors.append(f"{path.name}:{number}: key ({headword}, {rank}) not in snapshot index")
                else:
                    got = sha256_text("\t".join(fields[:6]))
                    if got != record["fields16_sha256"]:
                        errors.append(
                            f"{path.name}:{number}: fields-1-6 SHA mismatch for ({headword}, {rank})"
                        )
    # per-word rank coverage
    for headword, ranks in seen.items():
        if ranks and ranks != {1, 2, 3, 4, 5}:
            errors.append(f"{headword}: ranks {sorted(ranks)} != [1,2,3,4,5]")
    if snapshot_index is not None:
        expected = {tuple(k.split("\t")) for k in snapshot_index}
        got = {(w, str(r)) for w, ranks in seen.items() for r in ranks}
        for w, r in sorted(expected - got):
            errors.append(f"missing key from output: ({w}, {r})")
    return errors


def cmd_validate(args: argparse.Namespace) -> int:
    snapshot_index = None
    if args.snapshot_index:
        snapshot_index = json.loads(args.snapshot_index.read_text(encoding="utf-8"))
    policy = None
    if args.policy:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
    errors = validate_dir(
        args.draft_dir,
        require_translation=args.require_translation,
        require_explanation=args.require_explanation,
        snapshot_index=snapshot_index,
        policy=policy,
    )
    for error in errors[:100]:
        print(error, file=sys.stderr)
    if len(errors) > 100:
        print(f"... {len(errors) - 100} more errors", file=sys.stderr)
    print(json.dumps({"stage": "validate", "dir": str(args.draft_dir), "errors": len(errors)}, ensure_ascii=False))
    return 1 if errors else 0


# --------------------------------------------------------------------------- #
# merge                                                                        #
# --------------------------------------------------------------------------- #
def cmd_merge(args: argparse.Namespace) -> int:
    out_dir = args.out_dir
    if out_dir.exists():
        raise BuildError(f"output directory already exists: {out_dir}")
    snapshot_index = json.loads(args.snapshot_index.read_text(encoding="utf-8"))

    final = load_final_tsv(args.review_final)
    legacy_expl = load_explanations_dir(args.legacy_expl_dir)

    # field-8 map with reviewed precedence, scoped by the snapshot origin.
    def explanation_for(headword: str, rank: int, origin: str) -> str:
        if origin == "reviewed":
            value = final.get((headword, rank))
            if value is None:
                raise BuildError(f"reviewed ({headword}, {rank}) missing from final.tsv")
            return value
        value = legacy_expl.get(headword, {}).get(rank)
        if value is None:
            raise BuildError(f"legacy ({headword}, {rank}) missing from explanations")
        return value

    out_dir.mkdir(parents=True)
    file_hashes: dict[str, str] = {}
    filled = 0
    for path in sorted(args.translated_dir.glob("*.txt")):
        out_lines: list[str] = []
        headword: str | None = None
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                out_lines.append(raw)
                continue
            if raw.startswith("@ ") or raw.lstrip().startswith("#"):
                out_lines.append(raw)
                if raw.startswith("@ "):
                    headword = raw[2:].strip().casefold()
                continue
            fields = raw.split("\t")
            if len(fields) != 8:
                raise BuildError(f"{path.name}:{number}: translated row must have 8 fields, got {len(fields)}")
            rank = int(fields[0])
            key = f"{headword}\t{rank}"
            record = snapshot_index.get(key)
            if record is None:
                raise BuildError(f"{path.name}:{number}: ({headword}, {rank}) not in snapshot scope")
            if sha256_text("\t".join(fields[:6])) != record["fields16_sha256"]:
                raise BuildError(f"{path.name}:{number}: fields-1-6 diverge from snapshot for ({headword}, {rank})")
            if not fields[6].strip():
                raise BuildError(f"{path.name}:{number}: field 7 empty; translate before merge")
            explanation = explanation_for(headword, rank, record["origin"])
            if "\t" in explanation or "\n" in explanation or "\r" in explanation:
                raise BuildError(f"{path.name}:{number}: explanation contains a tab/newline")
            if not explanation.strip():
                raise BuildError(f"{path.name}:{number}: explanation is empty")
            merged = fields[:7] + [explanation]
            out_lines.append("\t".join(merged))
            filled += 1
        content = "\n".join(out_lines) + "\n"
        (out_dir / path.name).write_text(content, encoding="utf-8")
        file_hashes[path.name] = sha256_text(content)

    manifest = {
        "stage": "merge",
        "translated_dir": str(args.translated_dir),
        "review_final_sha256": sha256_bytes(args.review_final.read_bytes()),
        "snapshot_index_sha256": sha256_bytes(args.snapshot_index.read_bytes()),
        "rows_filled": filled,
        "output_files": file_hashes,
    }
    (out_dir / "merge_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"stage": "merge", "out": str(out_dir), "rows_filled": filled}, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- #
# pack                                                                         #
# --------------------------------------------------------------------------- #
def cmd_pack(args: argparse.Namespace) -> int:
    out_path = args.out_manifest
    if out_path.exists():
        raise BuildError(f"manifest already exists: {out_path}")
    review_dir = args.review_dir

    def hb(path: Path) -> str:
        return sha256_bytes(path.read_bytes())

    output_hashes: dict[str, str] = {}
    for path in sorted(args.merged_dir.glob("*.txt")):
        output_hashes[path.name] = hb(path)

    manifest = {
        "stage": "staging-candidate",
        "run_id": args.run_id,
        "policy_sha256": hb(args.policy),
        "candidates_sha256": hb(review_dir / "candidates.jsonl"),
        "final_tsv_sha256": hb(review_dir / "final.tsv"),
        "source_repairs_sha256": hb(review_dir / "source_repairs.tsv"),
        "manifest_source_sha256": hb(review_dir / "manifest.json"),
        "decision_ledger_sha256": hb(review_dir / "decision_ledger.jsonl"),
        "snapshot_manifest_sha256": hb(args.snapshot_manifest),
        "snapshot_index_sha256": hb(args.snapshot_index),
        "merge_manifest_sha256": hb(args.merged_dir / "merge_manifest.json"),
        "merged_output_sha256": output_hashes,
        "translation_provenance": {
            "status": "PENDING",
            "note": "Fill after tools/translate_vocab_content.py runs: providers, cache sha, usage.",
            "providers": [],
        },
    }
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": "pack", "manifest": str(out_path), "outputs": len(output_hashes)}, ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("snapshot", help="build the fields-1-6 repaired snapshot (translate input)")
    p.add_argument("--review-dir", type=Path, required=True)
    p.add_argument("--legacy-draft-dir", type=Path, required=True, help="sol_review_drafts (repaired legacy, precedence)")
    p.add_argument("--legacy-fallback-draft-dir", type=Path, required=True, help="terra_english_drafts (fallback)")
    p.add_argument("--legacy-expl-dir", type=Path, required=True, help="sol_review_explanations (legacy field 8)")
    p.add_argument("--out-dir", type=Path, required=True, help="NEW directory; must not exist")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("validate", help="validate a directory of compact drafts")
    p.add_argument("--draft-dir", type=Path, required=True)
    p.add_argument("--snapshot-index", type=Path, default=None)
    p.add_argument("--policy", type=Path, default=None, help="policy JSON; check field 8 against banned literals/regexes")
    p.add_argument("--require-translation", action="store_true", help="field 7 must be non-empty")
    p.add_argument("--require-explanation", action="store_true", help="field 8 must be non-empty")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("merge", help="fill field 8 onto translated drafts (fields 1-7 byte-preserved)")
    p.add_argument("--translated-dir", type=Path, required=True)
    p.add_argument("--snapshot-index", type=Path, required=True)
    p.add_argument("--review-final", type=Path, required=True, help="reviewed final.tsv")
    p.add_argument("--legacy-expl-dir", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True, help="NEW directory; must not exist")
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("pack", help="write staging manifest binding every input/output hash")
    p.add_argument("--run-id", required=True)
    p.add_argument("--review-dir", type=Path, required=True)
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--snapshot-manifest", type=Path, required=True)
    p.add_argument("--snapshot-index", type=Path, required=True)
    p.add_argument("--merged-dir", type=Path, required=True)
    p.add_argument("--out-manifest", type=Path, required=True, help="NEW file; must not exist")
    p.set_defaults(func=cmd_pack)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
