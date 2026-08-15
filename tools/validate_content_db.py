#!/usr/bin/env python3
"""Reject content that would teach a learner something wrong.

Every check below exists because the deterministic source validator in
``generate_source_cloze.py`` cannot see it: that one asks "is this attested?",
this one asks "is this true of *this* sense, short enough to show, and explained
without pointing at a sentence the player may never see?" (``action_plan.txt`` 7).

    python tools/validate_content_db.py
    python tools/validate_content_db.py --db data/content_v2.db --limit 40
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DB = ROOT / "data" / "content_v2.db"
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"

# One Flashcard line holds roughly this much Thai before it wraps past the card.
MEANING_MAX_CHARS = 42
EXPLANATION_MIN_CHARS = 12
# An explanation that points at another sentence is unusable: a player may see
# this sentence alone, in Cloze or on the card back.
CROSS_REFERENCE = re.compile(
    r"ประโยค(ที่|แรก|ที่สอง|ก่อนหน้า|ถัดไป|ด้านบน|ด้านล่าง)|ข้างต้น|ดังกล่าวข้างบน|ตัวอย่างที่ \d"
)
THAI = re.compile(r"[ก-๙]")


class Report:
    def __init__(self) -> None:
        self.failures: list[tuple[str, str]] = []

    def fail(self, check: str, detail: str) -> None:
        self.failures.append((check, detail))

    def check(self, name: str, rows: list[sqlite3.Row], detail) -> None:
        for row in rows:
            self.fail(name, detail(row))


def validate(db: sqlite3.Connection, source: sqlite3.Connection) -> Report:
    report = Report()
    db.row_factory = sqlite3.Row
    source.row_factory = sqlite3.Row

    # --- Thai learner text -------------------------------------------------
    report.check(
        "meaning-too-long",
        db.execute(
            "SELECT w.headword, s.pos, s.meaning_th FROM senses s JOIN words w ON w.id=s.word_id"
            " WHERE length(s.meaning_th) > ?", (MEANING_MAX_CHARS,)
        ).fetchall(),
        lambda row: f"{row['headword']} ({row['pos']}): {len(row['meaning_th'])} chars > {MEANING_MAX_CHARS}",
    )
    report.check(
        "meaning-not-thai",
        [row for row in db.execute(
            "SELECT w.headword, s.meaning_th FROM senses s JOIN words w ON w.id=s.word_id"
        ) if not THAI.search(row["meaning_th"])],
        lambda row: f"{row['headword']}: {row['meaning_th']!r}",
    )
    report.check(
        "duplicate-meaning",
        db.execute(
            "SELECT w.headword, s.pos, s.meaning_th, count(*) AS n FROM senses s JOIN words w ON w.id=s.word_id"
            " GROUP BY s.word_id, s.pos, s.meaning_th HAVING n > 1"
        ).fetchall(),
        lambda row: f"{row['headword']} ({row['pos']}): {row['meaning_th']} appears {row['n']} times",
    )
    report.check(
        "meaning-without-provenance",
        db.execute("SELECT w.headword FROM senses s JOIN words w ON w.id=s.word_id"
                   " WHERE trim(s.meaning_source) = ''").fetchall(),
        lambda row: f"{row['headword']}: meaning_source is empty",
    )

    # --- Examples ----------------------------------------------------------
    report.check(
        "explanation-cross-reference",
        [row for row in db.execute(
            "SELECT w.headword, e.rank, e.explanation_th FROM example_sentences e JOIN words w ON w.id=e.word_id"
        ) if CROSS_REFERENCE.search(row["explanation_th"])],
        lambda row: f"{row['headword']} rank {row['rank']}: refers to another sentence",
    )
    report.check(
        "explanation-too-thin",
        db.execute(
            "SELECT w.headword, e.rank FROM example_sentences e JOIN words w ON w.id=e.word_id"
            " WHERE length(e.explanation_th) < ? OR trim(e.explanation_source) = ''",
            (EXPLANATION_MIN_CHARS,)
        ).fetchall(),
        lambda row: f"{row['headword']} rank {row['rank']}: explanation missing, too short, or unsourced",
    )
    report.check(
        "cloze-span-wrong",
        [row for row in db.execute(
            "SELECT w.headword, e.rank, e.en_text, e.cloze_target, e.cloze_start, e.cloze_end"
            " FROM example_sentences e JOIN words w ON w.id=e.word_id"
        ) if row["en_text"][row["cloze_start"]:row["cloze_end"]].casefold() != row["cloze_target"].casefold()],
        lambda row: f"{row['headword']} rank {row['rank']}: cloze span does not cover the target",
    )
    # The example must teach the sense it is filed under: a noun example cannot
    # sit under a verb sense, and its form has to be a form of that POS.
    forms_by_word: dict[int, set[tuple[str, str]]] = {}
    for row in db.execute("SELECT word_id, lower(form_text) AS form, pos FROM word_forms WHERE form_type='inflection'"):
        forms_by_word.setdefault(row["word_id"], set()).add((row["form"], row["pos"]))
    for row in db.execute(
        "SELECT w.id AS word_id, w.headword, e.rank, e.form_used, s.pos FROM example_sentences e"
        " JOIN words w ON w.id=e.word_id JOIN senses s ON s.id=e.sense_id"
    ):
        form = row["form_used"].casefold()
        if form == row["headword"].casefold():
            continue
        if (form, row["pos"]) not in forms_by_word.get(row["word_id"], set()):
            report.fail(
                "example-form-not-of-sense",
                f"{row['headword']} rank {row['rank']}: '{row['form_used']}' is not a {row['pos']} form",
            )

    # --- Forms -------------------------------------------------------------
    source_forms: dict[str, set[str]] = {}
    for row in source.execute(
        "SELECT lower(w.headword) AS headword, lower(f.form_text) AS form FROM source_forms f"
        " JOIN words w ON w.id=f.word_id"
    ):
        source_forms.setdefault(row["headword"], set()).add(row["form"])
    source_derived: dict[str, set[str]] = {}
    for row in source.execute(
        "SELECT lower(w.headword) AS headword, lower(c.candidate) AS candidate FROM source_related_candidates c"
        " JOIN words w ON w.id=c.word_id WHERE c.candidate_type='derived'"
    ):
        source_derived.setdefault(row["headword"], set()).add(row["candidate"])
    for row in db.execute(
        "SELECT w.headword, f.form_text, f.form_type FROM word_forms f JOIN words w ON w.id=f.word_id"
    ):
        headword, form = row["headword"].casefold(), row["form_text"].casefold()
        attested = source_forms if row["form_type"] == "inflection" else source_derived
        if form not in attested.get(headword, set()):
            report.fail(
                f"{row['form_type']}-not-in-source",
                f"{row['headword']}: '{row['form_text']}' is not attested in the source",
            )
        # A derived family member has to look like family, not an etymological
        # cousin -- "capricious"/"capriole" share four letters and nothing useful.
        if row["form_type"] == "derived" and not (
            form.startswith(headword[:4]) or headword.startswith(form[:4])
        ):
            report.fail("derived-not-family", f"{row['headword']}: '{row['form_text']}' does not share the stem")

    report.check(
        "derived-without-thai",
        db.execute(
            "SELECT w.headword, f.form_text FROM word_forms f JOIN words w ON w.id=f.word_id"
            " WHERE f.form_type='derived' AND (f.meaning_th IS NULL OR trim(f.meaning_th)='')"
        ).fetchall(),
        lambda row: f"{row['headword']}: '{row['form_text']}' has no Thai meaning",
    )
    report.check(
        "form-pos-unknown",
        db.execute("SELECT w.headword, f.form_text FROM word_forms f JOIN words w ON w.id=f.word_id"
                   " WHERE f.pos IN ('', 'unknown')").fetchall(),
        lambda row: f"{row['headword']}: '{row['form_text']}' has no resolved POS",
    )

    # --- Relations ---------------------------------------------------------
    report.check(
        "relation-without-sense",
        db.execute("SELECT w.headword, r.related_headword FROM related_words r JOIN words w ON w.id=r.word_id"
                   " WHERE r.sense_id IS NULL").fetchall(),
        lambda row: f"{row['headword']} -> {row['related_headword']}: not tied to a sense",
    )
    report.check(
        "relation-without-explanation",
        db.execute(
            "SELECT w.headword, r.related_headword FROM related_words r JOIN words w ON w.id=r.word_id"
            " WHERE r.explanation_th IS NULL OR length(r.explanation_th) < ?", (EXPLANATION_MIN_CHARS,)
        ).fetchall(),
        lambda row: f"{row['headword']} -> {row['related_headword']}: no usable explanation",
    )
    # The explanation has to be about this pair, or the game shows a reason that
    # does not match the words on screen.
    for row in db.execute(
        "SELECT w.headword, r.related_headword, r.explanation_th FROM related_words r JOIN words w ON w.id=r.word_id"
    ):
        text = (row["explanation_th"] or "").casefold()
        if row["headword"].casefold() not in text or row["related_headword"].casefold() not in text:
            report.fail(
                "relation-explanation-mismatch",
                f"{row['headword']} -> {row['related_headword']}: explanation does not name both words",
            )
    report.check(
        "group-too-small",
        db.execute(
            "SELECT w.headword, count(m.word_id) AS n FROM relation_groups g JOIN words w ON w.id=g.hub_word_id"
            " LEFT JOIN relation_group_members m ON m.group_id=g.id GROUP BY g.id HAVING n < 3"
        ).fetchall(),
        lambda row: f"{row['headword']}: group has only {row['n']} members",
    )
    report.check(
        "group-without-explanation",
        db.execute(
            "SELECT w.headword FROM relation_groups g JOIN words w ON w.id=g.hub_word_id"
            " WHERE trim(g.category) = '' OR length(g.explanation_th) < ?", (EXPLANATION_MIN_CHARS,)
        ).fetchall(),
        lambda row: f"{row['headword']}: group has no category or explanation",
    )

    # --- Shape -------------------------------------------------------------
    report.check(
        "word-without-core-sense",
        db.execute(
            "SELECT headword FROM words WHERE id NOT IN (SELECT word_id FROM senses WHERE is_core=1)"
        ).fetchall(),
        lambda row: f"{row['headword']}: no core sense",
    )
    report.check(
        "word-without-examples",
        db.execute(
            "SELECT w.headword, count(e.id) AS n FROM words w LEFT JOIN example_sentences e ON e.word_id=w.id"
            " GROUP BY w.id HAVING n < 5"
        ).fetchall(),
        lambda row: f"{row['headword']}: {row['n']} examples, expected 5",
    )
    report.check(
        "word-without-reading",
        db.execute("SELECT headword FROM words WHERE thai_reading IS NULL OR trim(thai_reading) = ''").fetchall(),
        lambda row: f"{row['headword']}: no Thai reading",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=CONTENT_DB)
    parser.add_argument("--source-db", type=Path, default=SOURCE_DB)
    parser.add_argument("--limit", type=int, default=25, help="failures printed per check")
    args = parser.parse_args()

    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    source = sqlite3.connect(f"file:{args.source_db}?mode=ro", uri=True)
    try:
        report = validate(db, source)
    finally:
        db.close()
        source.close()

    grouped: dict[str, list[str]] = {}
    for check, detail in report.failures:
        grouped.setdefault(check, []).append(detail)
    for check in sorted(grouped, key=lambda name: -len(grouped[name])):
        details = grouped[check]
        print(f"FAIL {check} ({len(details)})", file=sys.stderr)
        for detail in details[:args.limit]:
            print(f"  {detail}", file=sys.stderr)
        if len(details) > args.limit:
            print(f"  ... and {len(details) - args.limit} more", file=sys.stderr)
    print(f"checks failed: {len(grouped)}  problems: {len(report.failures)}")
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
