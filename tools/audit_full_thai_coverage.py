#!/usr/bin/env python3
"""Read-only Thai-content coverage audit for the reviewed vocabulary corpus."""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import import_terra_compact as compact  # noqa: E402
import swow_cache  # noqa: E402
import translate_vocab_content as drafts  # noqa: E402


def pipe_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {key: (value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(
                (line for line in handle if not line.startswith("#")), delimiter="|"
            )
        ]


def load_english(directory: Path) -> dict[str, list[drafts.DraftSentence]]:
    output: dict[str, list[drafts.DraftSentence]] = {}
    for path in sorted(directory.glob("*.txt")):
        entries, errors = drafts.parse_draft(path)
        if errors:
            raise SystemExit(f"{path}: {errors[0]}")
        for headword, rows in entries.items():
            if headword in output:
                raise SystemExit(f"duplicate English headword: {headword}")
            output[headword] = rows
    return output


def load_compact(directory: Path) -> dict[str, list[dict]]:
    output: dict[str, list[dict]] = {}
    for path in sorted(directory.glob("*.txt")):
        entries, errors = compact.parse_file(path)
        if errors:
            raise SystemExit(f"{path}: {errors[0]}")
        for headword, rows in entries.items():
            if headword in output:
                raise SystemExit(f"duplicate compact headword: {headword}")
            output[headword] = rows
    return output


def english_key(row) -> tuple:
    if isinstance(row, drafts.DraftSentence):
        return (row.rank, row.sense_id, row.pos, row.target, int(row.memorable), row.en_text)
    return (
        int(row["rank"]), int(row["sense_id"]), row["pos"], row["cloze_target"],
        int(row["is_emotional"]), row["en_text"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--english-dir", type=Path, required=True)
    parser.add_argument("--translated-dir", type=Path)
    parser.add_argument("--explanation-dir", type=Path)
    parser.add_argument("--source-db", type=Path, default=ROOT / "data/vocabulary_source.db")
    parser.add_argument("--thai-dir", type=Path, default=ROOT / "data/content_th")
    args = parser.parse_args()

    english = load_english(args.english_dir)
    translated = load_compact(args.translated_dir) if args.translated_dir else {}
    explained = load_compact(args.explanation_dir) if args.explanation_dir else {}
    headwords = set(english)
    sentence_count = sum(len(rows) for rows in english.values())
    used_senses = {row.sense_id for rows in english.values() for row in rows}

    word_rows = {row["headword"].casefold(): row for row in pipe_rows(args.thai_dir / "words_th.txt")}
    sense_rows = {int(row["source_sense_id"]): row for row in pipe_rows(args.thai_dir / "senses_th.txt")}
    form_rows = {
        (row["headword"].casefold(), row["form"].casefold()): row
        for row in pipe_rows(args.thai_dir / "forms_th.txt")
    }
    relation_rows = pipe_rows(args.thai_dir / "relations_th.txt")
    group_rows = {row["hub"].casefold(): row for row in pipe_rows(args.thai_dir / "groups_th.txt")}

    translated_rows = {
        (headword, int(row["rank"])): row
        for headword, rows in translated.items() for row in rows
    }
    thai_sentences_present = 0
    explanation_present = 0
    explanation_exact_binding = 0
    explanation_stale_binding = 0
    words_needing_explanations: set[str] = set()
    explained_rows = {
        (headword, int(row["rank"])): row
        for headword, rows in explained.items() for row in rows
    }
    for headword, rows in english.items():
        for row in rows:
            translated_row = translated_rows.get((headword, row.rank))
            if translated_row and translated_row["th_text"].strip():
                thai_sentences_present += 1
            old = explained_rows.get((headword, row.rank))
            if old and old["explanation_th"].strip():
                explanation_present += 1
                if english_key(old) == english_key(row):
                    explanation_exact_binding += 1
                else:
                    explanation_stale_binding += 1
                    words_needing_explanations.add(headword)
            else:
                words_needing_explanations.add(headword)

    db = sqlite3.connect(f"file:{args.source_db}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    source_words = {
        row["headword"].casefold(): row
        for row in db.execute(
            "SELECT id,headword FROM words WHERE lower(headword) IN (%s)" %
            ",".join("?" for _ in headwords), tuple(sorted(headwords))
        )
    }
    words_with_source_ipa = {
        row["headword"].casefold()
        for row in db.execute(
            "SELECT DISTINCT w.headword FROM words w JOIN source_pronunciations p ON p.word_id=w.id "
            "WHERE lower(w.headword) IN (%s) AND trim(p.ipa) != ''" %
            ",".join("?" for _ in headwords), tuple(sorted(headwords))
        )
    }

    # Mirror build_content_db's derived-form filtering. Missing authored rows are
    # optional coverage: the builder simply omits those candidates.
    known_words = {row[0].casefold() for row in db.execute("SELECT headword FROM words")}
    swow = swow_cache.load()
    response_frequency = swow_cache.response_frequency(swow)
    derived_selected: set[tuple[str, str]] = set()
    for headword in headwords:
        source_word = source_words.get(headword)
        if not source_word:
            continue
        family: dict[str, tuple[str, int]] = {}
        for candidate in db.execute(
            "SELECT candidate,pos FROM source_related_candidates WHERE word_id=? "
            "AND candidate_type='derived' ORDER BY id", (source_word["id"],)
        ):
            text = candidate["candidate"].strip()
            key = text.casefold()
            if not text.isalpha() or key == headword:
                continue
            if not (key.startswith(headword[:4]) or headword.startswith(key[:4])):
                continue
            frequency = response_frequency.get(key, 0)
            if key not in known_words and frequency < 20:
                continue
            if key not in family or frequency > family[key][1]:
                family[key] = (candidate["pos"], frequency)
        for key, _ in sorted(family.items(), key=lambda item: -item[1][1])[:8]:
            derived_selected.add((headword, key))

    edges = swow_cache.edges_for(headwords, swow)
    neighbours: dict[str, set[str]] = {word: set() for word in headwords}
    for left, right in edges:
        neighbours[left].add(right)
        neighbours[right].add(left)
    required_group_hubs = {word for word, values in neighbours.items() if len(values) >= 3}
    db.close()

    report = {
        "corpus": {"words": len(headwords), "sentences": sentence_count, "used_senses": len(used_senses)},
        "word_readings": {
            "present": len(headwords & set(word_rows)),
            "missing": len(headwords - set(word_rows)),
            "source_ipa_available": len(words_with_source_ipa),
            "source_ipa_missing": len(headwords - words_with_source_ipa),
        },
        "sense_meanings": {
            "present": len(used_senses & set(sense_rows)),
            "missing": len(used_senses - set(sense_rows)),
        },
        "sentence_translations": {
            "present": thai_sentences_present,
            "missing": sentence_count - thai_sentences_present,
        },
        "sentence_explanations": {
            "present_at_same_headword_rank": explanation_present,
            "exactly_bound_to_current_english": explanation_exact_binding,
            "stale_english_binding": explanation_stale_binding,
            "missing_or_unusable": sentence_count - explanation_exact_binding,
            "words_needing_one_or_more_rows": len(words_needing_explanations),
        },
        "derived_forms_optional": {
            "eligible_selected_by_builder": len(derived_selected),
            "authored_whitelist_matches": len(derived_selected & set(form_rows)),
            "not_authored_and_therefore_omitted": len(derived_selected - set(form_rows)),
        },
        "relations": {
            "swow_edges": len(edges),
            "authored_pair_overrides_total_file": len(relation_rows),
            "note": "pair overrides are optional; builder deterministically emits a generic Thai explanation",
        },
        "groups": {
            "required_hubs_with_at_least_3_neighbours": len(required_group_hubs),
            "authored_required_hubs": len(required_group_hubs & set(group_rows)),
            "missing_required_hubs": len(required_group_hubs - set(group_rows)),
        },
        "missing_samples": {
            "word_readings": sorted(headwords - set(word_rows))[:20],
            "sense_ids": sorted(used_senses - set(sense_rows))[:20],
            "group_hubs": sorted(required_group_hubs - set(group_rows))[:20],
            "words_needing_explanations": sorted(words_needing_explanations)[:20],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
