#!/usr/bin/env python3
"""Advisory coverage validator for Terra English cloze drafts.

This is deliberately a *separate* script from ``validate_entry`` in
``translate_vocab_content.py``.  ``validate_entry`` is a blocking gate for
three callers (``validate_english_draft_batch.py``, ``sol_review_progress.py``,
``build_missing_draft_manifest.py``) and for CI; adding these coverage rules
there would retroactively fail all 565 already-reviewed words and block every
future commit until the whole backlog is repaired.  This script always exits
0 -- it produces a work order, not a gate.

Checks (see ``~/.claude/plans/claude-recursive-newt.md`` Part A for the design):

  pos-coverage     high    block does not cover every POS the source supplies
  form-variety     high    verbs only: fewer than 3 distinct target forms used
  rare-sense       high    row's sense carries a REJECT_TAGS rarity tag
  late-sense       medium  row's sense is ordinal >=9 within the word
  no-usage-example low     sense has no editor 'example' (only quotations)
  thin-rank1       medium  rank 1 sentence is under 6 words
  ambiguous-cloze  medium  target occurs more than once in the sentence
  hard-vocabulary  low     sentence contains a B2 corpus word for an A1/A2 headword
  template-sentence high   sentence is a generator template, not real content
  identical-block  high    all 5 sentences are the same sentence with the target swapped

    python tools/check_cloze_coverage.py --priority audit
    python tools/check_cloze_coverage.py --seq-start 566 --seq-end 570
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

import translate_vocab_content as drafts
from build_content_db import REJECT_TAGS

ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "data" / "terra_english_drafts"
MANIFEST = ROOT / "data" / "sol_review_manifest.txt"
OUTPUT = ROOT / "data" / "coverage_defects.tsv"
SOURCE_DB = drafts.SOURCE_DB

# Wiktionary's stock phrasing for a word whose true POS is an interjection but
# whose interjection sense was dropped at harvest (ALLOWED_POS lists "interj",
# kaikki emits "intj" -- every interjection/particle/postp sense is missing
# from this DB, see build_vocab_library.py:46,270).  When kaikki folds such a
# word's interjection use into a noun sense it almost always glosses it this
# way ("An utterance of wow", "An utterance of oh", "An utterance of goodbye").
# This is a signal already inside the evidence DB -- no external wordlist
# needed -- so a word carrying it is exempted from pos-coverage entirely: the
# "missing" POS is the dropped class, not a real gap a reviewer can fill.
DROPPED_CLASS_GLOSS = re.compile(r"^an? utterance of\b", re.I)

MIN_WORD_COUNT_RANK1 = 6
MIN_VERB_FORMS_FOR_VARIETY = 3
LATE_SENSE_ORDINAL = 9


def load_manifest() -> list[tuple[int, str, str]]:
    """Return (seq, priority, headword_casefold) rows in file order."""
    rows: list[tuple[int, str, str]] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        rows.append((int(fields[0]), fields[1].casefold(), fields[3].casefold()))
    return rows


def load_drafts() -> dict[str, list[drafts.DraftSentence]]:
    entries: dict[str, list[drafts.DraftSentence]] = {}
    for path in sorted(DRAFT_DIR.glob("*.txt")):
        file_entries, _errors = drafts.parse_draft(path)
        entries.update(file_entries)
    return entries


def word_count(text: str) -> int:
    return len(text.split())


def target_occurrence_count(target: str, sentence: str) -> int:
    pattern = rf"(?<![A-Za-z]){re.escape(target)}(?![A-Za-z])"
    return len(re.findall(pattern, sentence, re.I))


# The legacy generator that produced most of the corpus fell back to a
# handful of fixed frames whenever it had nothing to say: a copula clause
# ("It is basic.", "They were aware."), a habitual clause ("We bake every
# day."), or some other short subject+verb frame built entirely from
# pronouns, articles and other function words plus the target itself.  None
# of these state a situation, so instead of hardcoding the frames we strip
# stopwords and ask what is left: if the target is the *only* content word,
# the sentence is a template no matter which pronoun/tense/frame produced it.
STOPWORDS = frozenset(
    """
    a an the this that these those it its he she they we you i him her them us
    is are was were be been being am
    to of in on at for with and but or so as if then than
    very really just not no
    every day days today tonight now here there again also too always often sometimes never
    """.split()
)


def content_words(text: str, target: str) -> list[str]:
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z']+", text)]
    target_cf = target.casefold()
    return [token for token in tokens if token not in STOPWORDS and token != target_cf]


def is_template_sentence(text: str, target: str) -> bool:
    tokens = [token.casefold() for token in re.findall(r"[A-Za-z']+", text)]
    if not tokens:
        return True
    target_cf = target.casefold()
    non_stopword = [token for token in tokens if token not in STOPWORDS]
    # The target is present and it is the only content word in the sentence
    # ("It is basic.", "We bake every day.") -- no situation is described.
    if non_stopword and all(token == target_cf for token in non_stopword):
        return True
    # Nothing but stopwords at all, or a very short sentence with zero
    # non-target content words -- still no situation stated.
    if not non_stopword or (word_count(text) < MIN_WORD_COUNT_RANK1 and not content_words(text, target)):
        return True
    return False


def normalize_template_shape(text: str, target: str) -> str:
    """Text with the target span masked out, for near-copy comparison."""
    pattern = rf"(?<![A-Za-z]){re.escape(target)}(?![A-Za-z])"
    masked = re.sub(pattern, "\x00", text, flags=re.I)
    return re.sub(r"\s+", " ", masked).strip().casefold()


class Evidence:
    """Pre-loaded evidence DB slices, keyed by word_id."""

    def __init__(self, db: sqlite3.Connection) -> None:
        self.words: dict[str, sqlite3.Row] = {
            row["headword"].casefold(): row
            for row in db.execute("SELECT id, headword, cefr_first FROM words")
        }
        self.senses_by_word: dict[int, list[sqlite3.Row]] = {}
        for row in db.execute(
            "SELECT id, word_id, pos, gloss, tags_json FROM source_senses ORDER BY word_id, id"
        ):
            self.senses_by_word.setdefault(row["word_id"], []).append(row)
        self.forms_by_word: dict[int, list[sqlite3.Row]] = {}
        for row in db.execute("SELECT word_id, form_text, pos, tags_json FROM source_forms"):
            self.forms_by_word.setdefault(row["word_id"], []).append(row)
        self.examples_by_word: dict[int, list[sqlite3.Row]] = {}
        for row in db.execute(
            "SELECT word_id, pos, sense_gloss, example_type FROM source_examples"
        ):
            self.examples_by_word.setdefault(row["word_id"], []).append(row)


def check_word(
    headword: str, seq: int, rows: list[drafts.DraftSentence], evidence: Evidence
) -> list[dict]:
    findings: list[dict] = []
    word = evidence.words.get(headword)
    if word is None:
        return findings
    word_id = word["id"]
    senses = evidence.senses_by_word.get(word_id, [])
    forms = evidence.forms_by_word.get(word_id, [])
    examples = evidence.examples_by_word.get(word_id, [])
    sense_by_id = {sense["id"]: sense for sense in senses}
    ordinal_by_sense_id = {sense["id"]: i + 1 for i, sense in enumerate(senses)}

    def add(check_id: str, severity: str, rank: int | str, detail: str, action: str) -> None:
        findings.append(
            {
                "seq": seq,
                "headword": word["headword"],
                "check_id": check_id,
                "severity": severity,
                "rank": rank,
                "detail": detail,
                "suggested_action": action,
            }
        )

    # -- pos-coverage (high, word-level) ------------------------------------
    source_pos = {sense["pos"] for sense in senses}
    dropped_class_word = any(
        DROPPED_CLASS_GLOSS.match(sense["gloss"] or "") for sense in senses
    )
    if not dropped_class_word and len(source_pos) > 1:
        block_pos = {row.pos for row in rows}
        missing_pos = source_pos - block_pos
        if missing_pos and block_pos < source_pos:
            add(
                "pos-coverage",
                "high",
                "-",
                f"source supplies POS {sorted(source_pos)}; block covers only {sorted(block_pos)}",
                f"add a sentence for POS: {', '.join(sorted(missing_pos))}",
            )

    # -- form-variety (high, word-level, verbs only) ------------------------
    verb_rows = [row for row in rows if row.pos == "verb"]
    if verb_rows:
        available = {word["headword"].casefold()}
        for form in forms:
            if form["pos"] != "verb":
                continue
            try:
                form_tags = set(json.loads(form["tags_json"] or "[]"))
            except (json.JSONDecodeError, TypeError):
                form_tags = set()
            if form_tags & REJECT_TAGS:
                continue
            available.add(form["form_text"].strip().casefold())
        if len(available) >= MIN_VERB_FORMS_FOR_VARIETY:
            used = {row.target.casefold() for row in verb_rows}
            if len(used) < MIN_VERB_FORMS_FOR_VARIETY:
                add(
                    "form-variety",
                    "high",
                    "-",
                    f"block uses only {sorted(used)} ({len(used)} distinct form(s))",
                    f"use at least 3 distinct verb forms; available: {sorted(available)}",
                )

    # -- identical-block (high, word-level) ----------------------------
    if len(rows) >= 2:
        normalized = {normalize_template_shape(row.en_text, row.target) for row in rows}
        raw_texts = {row.en_text.casefold() for row in rows}
        if len(normalized) == 1:
            if len(raw_texts) == 1:
                detail = "all 5 sentences are byte-identical"
            else:
                detail = "all 5 sentences are the same frame with only the target's form swapped"
            add(
                "identical-block",
                "high",
                "-",
                detail,
                "rewrite the 5 sentences as 5 distinct situations, not one template repeated",
            )

    # -- per-row checks -------------------------------------------------
    for row in rows:
        sense = sense_by_id.get(row.sense_id)

        # rare-sense (high)
        if sense is not None:
            try:
                tags = set(json.loads(sense["tags_json"] or "[]"))
            except (json.JSONDecodeError, TypeError):
                tags = set()
            hit = tags & REJECT_TAGS
            if hit:
                add(
                    "rare-sense",
                    "high",
                    row.rank,
                    f"sense {row.sense_id} tagged {sorted(hit)}",
                    f"pick a common-sense alternative for POS {row.pos} if the source offers one",
                )

        # late-sense (medium)
        ordinal = ordinal_by_sense_id.get(row.sense_id)
        if ordinal is not None and ordinal >= LATE_SENSE_ORDINAL:
            add(
                "late-sense",
                "medium",
                row.rank,
                f"sense {row.sense_id} is ordinal {ordinal} of {len(senses)} for this word",
                "prefer an earlier-listed (more common) sense if one fits",
            )

        # no-usage-example (low)
        if sense is not None:
            matching = [
                example
                for example in examples
                if example["pos"] == sense["pos"] and example["sense_gloss"] == sense["gloss"]
            ]
            if not any(example["example_type"] == "example" for example in matching):
                add(
                    "no-usage-example",
                    "low",
                    row.rank,
                    f"sense (pos={sense['pos']}, gloss={sense['gloss'][:60]!r}) has no editor example",
                    "double-check this sense's usage against the gloss/quotations only",
                )

        # thin-rank1 (medium)
        if row.rank == 1:
            n = word_count(row.en_text)
            if n < MIN_WORD_COUNT_RANK1:
                add(
                    "thin-rank1",
                    "medium",
                    row.rank,
                    f"rank 1 sentence has {n} words (< {MIN_WORD_COUNT_RANK1})",
                    "lengthen rank 1 to carry an emotionally memorable situation",
                )

        # ambiguous-cloze (medium)
        occurrences = target_occurrence_count(row.target, row.en_text)
        if occurrences > 1:
            add(
                "ambiguous-cloze",
                "medium",
                row.rank,
                f"target '{row.target}' occurs {occurrences} times in the sentence",
                "rewrite so the target appears exactly once",
            )

        # template-sentence (high)
        if is_template_sentence(row.en_text, row.target):
            add(
                "template-sentence",
                "high",
                row.rank,
                f"'{row.en_text}' states no situation beyond the target itself",
                "rewrite as a concrete situation; do not reuse a copula/habitual filler frame",
            )

        # hard-vocabulary (low, advisory)
        if word["cefr_first"] in ("A1", "A2"):
            hard_words = []
            for token in re.findall(r"[A-Za-z']+", row.en_text):
                other = evidence.words.get(token.casefold())
                if other is not None and other["cefr_first"] == "B2":
                    hard_words.append(token)
            if hard_words:
                add(
                    "hard-vocabulary",
                    "low",
                    row.rank,
                    f"sentence contains B2-level word(s): {', '.join(hard_words)}",
                    "consider swapping for an A2/B1 or below alternative",
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq-start", type=int, default=None)
    parser.add_argument("--seq-end", type=int, default=None)
    parser.add_argument("--priority", choices=("failed", "audit"), default=None)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    manifest = load_manifest()
    selected = [
        (seq, headword)
        for seq, priority, headword in manifest
        if (args.seq_start is None or seq >= args.seq_start)
        and (args.seq_end is None or seq <= args.seq_end)
        and (args.priority is None or priority == args.priority)
    ]

    all_drafts = load_drafts()
    db = sqlite3.connect(f"file:{SOURCE_DB.as_posix()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    evidence = Evidence(db)
    db.close()

    findings: list[dict] = []
    missing_draft = 0
    for seq, headword in selected:
        rows = all_drafts.get(headword)
        if not rows:
            missing_draft += 1
            continue
        findings.extend(check_word(headword, seq, rows, evidence))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "seq\theadword\tcheck_id\tseverity\trank\tdetail\tsuggested_action\n"
        )
        for finding in findings:
            handle.write(
                "\t".join(
                    str(finding[key])
                    for key in (
                        "seq",
                        "headword",
                        "check_id",
                        "severity",
                        "rank",
                        "detail",
                        "suggested_action",
                    )
                )
                + "\n"
            )

    per_check: dict[str, int] = {}
    per_severity: dict[str, int] = {}
    words_with_high: set[str] = set()
    for finding in findings:
        per_check[finding["check_id"]] = per_check.get(finding["check_id"], 0) + 1
        per_severity[finding["severity"]] = per_severity.get(finding["severity"], 0) + 1
        if finding["severity"] == "high":
            words_with_high.add(finding["headword"])

    print(f"words_checked={len(selected) - missing_draft} missing_draft={missing_draft}")
    print("per_check=" + ", ".join(f"{k}={per_check[k]}" for k in sorted(per_check)))
    print("per_severity=" + ", ".join(f"{k}={per_severity[k]}" for k in sorted(per_severity)))
    print(f"words_with_high_severity_finding={len(words_with_high)}")
    print(f"output={args.output} rows={len(findings)}")

    # template-sentence, whole corpus, split by manifest priority: this is the
    # number that sizes how much of the audit bucket is full-rewrite work
    # rather than a coverage touch-up, independent of any --seq/--priority
    # slice used for the report above.
    template_words: dict[str, set[str]] = {"failed": set(), "audit": set()}
    for seq, priority, headword in manifest:
        rows = all_drafts.get(headword)
        if not rows:
            continue
        if any(is_template_sentence(row.en_text, row.target) for row in rows):
            template_words.setdefault(priority, set()).add(headword)
    print(
        "template_sentence_words (whole corpus): "
        f"failed={len(template_words.get('failed', set()))}/{sum(1 for _, p, _ in manifest if p == 'failed')} "
        f"audit={len(template_words.get('audit', set()))}/{sum(1 for _, p, _ in manifest if p == 'audit')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
