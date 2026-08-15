#!/usr/bin/env python3
"""Build the v2 content database for the RE Vocab rebuild.

Schema v2 exists because the old seed could not express what the final Flashcard,
the full Dictionary and the group games need (see ``action_plan.txt`` steps 2-5):

* a word has several POS, each POS several senses, each sense a source and a rank
* forms are split into *inflection* (drive -> drove) and *derived family*
  (decide -> decision), each with its own POS and provenance
* every example sentence carries its own standalone Thai explanation, the form it
  uses, and the grammar reason -- a player may see one sentence and nothing else
* related words hang off a **sense**, not off the headword, and carry the relation
  type, an explanation, a source and a confidence; groups additionally carry the
  hub/category that Odd One Out explains itself with

Lexical facts come only from ``data/vocabulary_source.db`` (kaikki/Wiktextract) and
SWOW-EN18.  Thai learner text comes from the authored files in ``data/content_th/``
so it is reviewable and reproducible; nothing Thai is invented at build time.

    python tools/build_content_db.py
    python tools/build_content_db.py --out data/content_v2.db
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import generate_source_cloze as generator
import import_terra_compact as compact
import swow_cache

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DB = ROOT / "data" / "vocabulary_source.db"
DRAFT_DIR = ROOT / "data" / "terra_translated_drafts"
PILOT_JSON = ROOT / "data" / "pilot_100.json"
# Test scaffolding: 30 harder multi-POS words used to exercise the Flashcard back
# and the Dictionary while content is being built.  Rows land in the content DB
# with is_test_only=1 and must be dropped from the pipeline before the app ships
# (after_revocab.md item 7).
HARD_TEST_JSON = ROOT / "data" / "hard_test_30.json"
THAI_DIR = ROOT / "data" / "content_th"
OUT_DB = ROOT / "data" / "content_v2.db"

CONTENT_VERSION = 2
SOURCE_LICENSE = "CC BY-SA 4.0 (Wiktionary via kaikki.org)"
SWOW_LICENSE = "CC BY-NC 4.0 (SWOW-EN18)"

# Inflection tags worth teaching, and the tags that mark a form as not current
# English.  Kaikki lists every attested spelling, including "drinked" and "dhrink".
INFLECTION_TAGS = ("plural", "past", "participle", "third-person", "comparative", "superlative", "present")
REJECT_TAGS = frozenset({
    "alternative", "obsolete", "archaic", "dialectal", "nonstandard", "misspelling",
    "pronunciation-spelling", "rare", "dated", "poetic", "abbreviation", "slang", "childish",
})
# A derived family member has to be a word learners plausibly meet: either it is on
# the Oxford source list, or SWOW respondents produced it this often.
DERIVED_MIN_FREQ = 20
DERIVED_PER_WORD = 8

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE content_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE words (
  id INTEGER PRIMARY KEY,
  headword TEXT NOT NULL UNIQUE,
  cefr TEXT NOT NULL,
  freq_rank INTEGER NOT NULL,
  ipa TEXT,
  thai_reading TEXT,
  stress_index INTEGER,
  is_test_only INTEGER NOT NULL DEFAULT 0 CHECK(is_test_only IN (0,1)),
  source_word_id INTEGER NOT NULL
);

CREATE TABLE senses (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  pos TEXT NOT NULL,
  sense_rank INTEGER NOT NULL,
  is_core INTEGER NOT NULL CHECK(is_core IN (0,1)),
  gloss_en TEXT NOT NULL,
  meaning_th TEXT NOT NULL,
  meaning_source TEXT NOT NULL,
  source_sense_id INTEGER NOT NULL UNIQUE,
  source_name TEXT NOT NULL,
  UNIQUE(word_id, pos, sense_rank)
);
CREATE INDEX idx_senses_word_pos ON senses(word_id, pos, sense_rank);

-- Inflections and derived family members are different things to a learner, so
-- they are one table with an explicit form_type rather than two lookalike tables.
CREATE TABLE word_forms (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  sense_id INTEGER REFERENCES senses(id) ON DELETE SET NULL,
  form_text TEXT NOT NULL,
  form_type TEXT NOT NULL CHECK(form_type IN ('inflection','derived')),
  pos TEXT NOT NULL,
  relation TEXT NOT NULL,
  meaning_th TEXT,
  is_irregular INTEGER NOT NULL DEFAULT 0 CHECK(is_irregular IN (0,1)),
  source_name TEXT NOT NULL,
  source_license TEXT NOT NULL,
  UNIQUE(word_id, form_text, form_type, pos)
);
CREATE INDEX idx_forms_word ON word_forms(word_id, form_type);

CREATE TABLE example_sentences (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  sense_id INTEGER NOT NULL REFERENCES senses(id) ON DELETE CASCADE,
  rank INTEGER NOT NULL CHECK(rank BETWEEN 1 AND 5),
  en_text TEXT NOT NULL,
  th_text TEXT NOT NULL,
  cloze_target TEXT NOT NULL,
  cloze_start INTEGER NOT NULL,
  cloze_end INTEGER NOT NULL,
  form_used TEXT NOT NULL,
  is_emotional INTEGER NOT NULL CHECK(is_emotional IN (0,1)),
  explanation_th TEXT NOT NULL,
  explanation_source TEXT NOT NULL,
  UNIQUE(word_id, rank)
);
CREATE INDEX idx_examples_sense ON example_sentences(sense_id, rank);

CREATE TABLE related_words (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  sense_id INTEGER REFERENCES senses(id) ON DELETE CASCADE,
  related_word_id INTEGER REFERENCES words(id) ON DELETE CASCADE,
  related_headword TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  closeness REAL,
  confidence REAL NOT NULL,
  explanation_th TEXT,
  is_giveaway INTEGER NOT NULL DEFAULT 0 CHECK(is_giveaway IN (0,1)),
  source_name TEXT NOT NULL,
  source_license TEXT NOT NULL,
  UNIQUE(word_id, related_headword, relation_type)
);
CREATE INDEX idx_related_word ON related_words(word_id, relation_type);

-- Odd One Out must explain the round from the data that built it, so the hub and
-- the reason live here instead of being reconstructed after the answer.
CREATE TABLE relation_groups (
  id INTEGER PRIMARY KEY,
  hub_word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  explanation_th TEXT NOT NULL,
  source_name TEXT NOT NULL
);

CREATE TABLE relation_group_members (
  group_id INTEGER NOT NULL REFERENCES relation_groups(id) ON DELETE CASCADE,
  word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
  closeness REAL,
  PRIMARY KEY(group_id, word_id)
);
"""


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_authored(name: str) -> list[dict[str, str]]:
    """Read an authored content file.

    The separator is ``|`` rather than a tab: these files are hand-edited and a
    tab that turns into spaces silently corrupts a column, while ``|`` never
    appears inside Thai or English learner text.
    """
    path = THAI_DIR / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader((line for line in handle if not line.startswith("#")), delimiter="|")
        return [{key: (value or "").strip() for key, value in row.items() if key} for row in rows]


def content_words() -> list[dict]:
    """The pilot subset, plus the hard test set flagged as test-only."""
    words = [dict(word, is_test_only=0) for word in json.loads(PILOT_JSON.read_text(encoding="utf-8"))["words"]]
    if HARD_TEST_JSON.exists():
        words += [dict(word, is_test_only=1)
                  for word in json.loads(HARD_TEST_JSON.read_text(encoding="utf-8"))["words"]]
    return words


def load_drafts(headwords: set[str]) -> dict[str, list[dict]]:
    entries: dict[str, list[dict]] = {}
    for path in sorted(DRAFT_DIR.glob("*.txt")):
        parsed, errors = compact.parse_file(path)
        if errors:
            raise SystemExit(f"{path.name}: {errors[0]}")
        for headword, sentences in parsed.items():
            if headword in headwords:
                entries[headword] = sentences
    return entries


def cloze_span(en_text: str, target: str) -> tuple[int, int]:
    lowered, needle = en_text.casefold(), target.casefold()
    start = lowered.find(needle)
    return (start, start + len(target)) if start >= 0 else (-1, -1)


def build(out_path: Path) -> int:
    words = content_words()
    headwords = {word["headword"].casefold() for word in words}
    drafts = load_drafts(headwords)
    missing_drafts = sorted(headwords - set(drafts))
    if missing_drafts:
        raise SystemExit(f"no draft for: {', '.join(missing_drafts)}")

    thai_words = {row["headword"].casefold(): row for row in read_authored("words_th.txt")}
    thai_senses = {int(row["source_sense_id"]): row for row in read_authored("senses_th.txt")}
    thai_relations = {
        (row["headword"].casefold(), row["related"].casefold()): row for row in read_authored("relations_th.txt")
    }
    thai_groups = {row["hub"].casefold(): row for row in read_authored("groups_th.txt")}
    # Whitelist: a derived family member ships only when it has been curated with
    # a Thai meaning and a real POS. Kaikki's derived lists include words that
    # merely look like family ("aft" under afternoon, "window" under wind).
    thai_forms = {
        (row["headword"].casefold(), row["form"].casefold()): row
        for row in read_authored("forms_th.txt")
    }

    source = generator.connect()
    if out_path.exists():
        out_path.unlink()
    db = sqlite3.connect(out_path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)

    gaps: list[str] = []
    word_ids: dict[str, int] = {}
    sense_ids: dict[int, int] = {}

    for rank, word in enumerate(words, 1):
        headword = word["headword"]
        key = headword.casefold()
        row = source.execute("SELECT * FROM words WHERE id=?", (word["word_id"],)).fetchone()
        ipa = source.execute(
            "SELECT ipa FROM source_pronunciations WHERE word_id=? ORDER BY id LIMIT 1", (row["id"],)
        ).fetchone()
        thai = thai_words.get(key, {})
        if not thai.get("thai_reading"):
            gaps.append(f"words_th.txt missing thai_reading for {headword}")
        db.execute(
            "INSERT INTO words (headword,cefr,freq_rank,ipa,thai_reading,stress_index,is_test_only,"
            "source_word_id) VALUES (?,?,?,?,?,?,?,?)",
            (headword, row["cefr_first"], rank, ipa["ipa"] if ipa else None,
             thai.get("thai_reading") or None,
             int(thai["stress_index"]) if thai.get("stress_index") else None,
             word["is_test_only"], row["id"]),
        )
        word_ids[key] = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Senses: exactly those the curated drafts use, so every displayed sense is one
    # a learner actually meets in an example.
    for headword_key, sentences in drafts.items():
        word_id = word_ids[headword_key]
        seen: dict[str, int] = defaultdict(int)
        for sentence in sorted(sentences, key=lambda item: item["rank"]):
            source_sense_id = sentence["sense_id"]
            if source_sense_id in sense_ids:
                continue
            sense = source.execute(
                "SELECT id,word_id,pos,gloss,source_name FROM source_senses WHERE id=?", (source_sense_id,)
            ).fetchone()
            thai = thai_senses.get(source_sense_id)
            if thai is None:
                gaps.append(f"senses_th.txt missing meaning_th for {headword_key} sense {source_sense_id}")
                continue
            seen[sense["pos"]] += 1
            db.execute(
                "INSERT INTO senses (word_id,pos,sense_rank,is_core,gloss_en,meaning_th,meaning_source,"
                "source_sense_id,source_name) VALUES (?,?,?,?,?,?,?,?,?)",
                (word_id, sense["pos"], seen[sense["pos"]], int(seen[sense["pos"]] == 1),
                 sense["gloss"], thai["meaning_th"], thai.get("meaning_source") or "authored",
                 source_sense_id, sense["source_name"]),
            )
            sense_ids[source_sense_id] = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Examples: one row per draft sentence, each with its own standalone explanation.
    for headword_key, sentences in drafts.items():
        word_id = word_ids[headword_key]
        for sentence in sorted(sentences, key=lambda item: item["rank"]):
            sense_id = sense_ids.get(sentence["sense_id"])
            if sense_id is None:
                continue
            start, end = cloze_span(sentence["en_text"], sentence["cloze_target"])
            if start < 0:
                gaps.append(f"{headword_key} rank {sentence['rank']}: cloze target not found in sentence")
                continue
            db.execute(
                "INSERT INTO example_sentences (word_id,sense_id,rank,en_text,th_text,cloze_target,"
                "cloze_start,cloze_end,form_used,is_emotional,explanation_th,explanation_source)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (word_id, sense_id, sentence["rank"], sentence["en_text"], sentence["th_text"],
                 sentence["cloze_target"], start, end, sentence["cloze_target"],
                 int(sentence["is_emotional"]), sentence["explanation_th"], "terra-source-cloze-v1"),
            )

    # Forms: inflections from source_forms, derived family from source derived
    # candidates restricted to single words that are not just the inflections again.
    known_words = {row[0].casefold() for row in source.execute("SELECT headword FROM words")}
    swow = swow_cache.load()
    response_frequency = swow_cache.response_frequency(swow)
    used_targets: dict[str, set[str]] = {
        headword: {sentence["cloze_target"].casefold() for sentence in sentences}
        for headword, sentences in drafts.items()
    }
    for headword_key, word_id in word_ids.items():
        source_word_id = db.execute("SELECT source_word_id FROM words WHERE id=?", (word_id,)).fetchone()[0]
        # Kaikki lists every attested spelling of an inflection, so several rows can
        # claim the same slot ("drank", "dranken", "drinken" are all tagged past).
        # Keep the one people actually produce, by SWOW response frequency.
        by_slot: dict[tuple[str, str], tuple[str, int]] = {}
        for form in source.execute(
            "SELECT form_text,pos,tags_json FROM source_forms WHERE word_id=? ORDER BY id", (source_word_id,)
        ):
            text = form["form_text"].strip()
            if not generator.FORM_RE.fullmatch(text) or text.casefold() == headword_key:
                continue
            tags = set(json.loads(form["tags_json"] or "[]"))
            if tags & REJECT_TAGS:
                continue
            relation = " ".join(tag for tag in INFLECTION_TAGS if tag in tags)
            if not relation:
                continue
            frequency = response_frequency.get(text.casefold(), 0)
            if text.casefold() in used_targets[headword_key]:
                # A form the curated examples teach keeps its own slot rather than
                # competing -- "sprang" and "sprung" are both tagged past, and the
                # examples teach both.
                slot = (form["pos"], relation, text.casefold())
            else:
                slot = (form["pos"], relation)
            if slot not in by_slot or frequency > by_slot[slot][1]:
                by_slot[slot] = (text, frequency)
        inflections = {(text.casefold(), slot[0]) for slot, (text, _) in by_slot.items()}
        for slot, (text, _) in by_slot.items():
            pos, relation = slot[0], slot[1]
            db.execute(
                "INSERT OR IGNORE INTO word_forms (word_id,form_text,form_type,pos,relation,is_irregular,"
                "source_name,source_license) VALUES (?,?,'inflection',?,?,?,?,?)",
                (word_id, text, pos, relation,
                 int(not text.casefold().startswith(headword_key)), "kaikki", SOURCE_LICENSE),
            )
        family: dict[str, tuple[str, int]] = {}
        for candidate in source.execute(
            "SELECT candidate,pos FROM source_related_candidates WHERE word_id=? AND candidate_type='derived'"
            " ORDER BY id", (source_word_id,)
        ):
            text = candidate["candidate"].strip()
            key = text.casefold()
            if not text.isalpha() or key == headword_key or (key, candidate["pos"]) in inflections:
                continue
            # A derived family member must visibly share the headword's stem, or it
            # is an etymological cousin that does not help a learner.
            if not (key.startswith(headword_key[:4]) or headword_key.startswith(key[:4])):
                continue
            frequency = response_frequency.get(key, 0)
            if key not in known_words and frequency < DERIVED_MIN_FREQ:
                continue
            if key not in family or frequency > family[key][1]:
                # The candidate's POS is the POS of the *section* it was listed
                # under, not of the derived word, so resolve it from the source
                # entry for that word when we have one.
                resolved = source.execute(
                    "SELECT s.pos FROM source_senses s JOIN words w ON w.id=s.word_id"
                    " WHERE lower(w.headword)=? ORDER BY s.id LIMIT 1", (key,)
                ).fetchone()
                family[key] = (resolved["pos"] if resolved else "unknown", frequency)
        for key, (pos, frequency) in sorted(family.items(), key=lambda item: -item[1][1])[:DERIVED_PER_WORD]:
            authored = thai_forms.get((headword_key, key))
            if authored is None:
                continue
            db.execute(
                "INSERT OR IGNORE INTO word_forms (word_id,form_text,form_type,pos,relation,meaning_th,"
                "is_irregular,source_name,source_license) VALUES (?,?,'derived',?,'derived',?,0,?,?)",
                (word_id, key, authored.get("pos") or pos, authored["meaning_th"],
                 "kaikki", SOURCE_LICENSE),
            )

    # Related words and Odd One Out groups from SWOW association strength.
    edges = swow_cache.edges_for(headwords, swow)
    neighbours: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (left, right), strength in edges.items():
        neighbours[left].append((right, strength))
        neighbours[right].append((left, strength))
    for headword_key, word_id in word_ids.items():
        core = db.execute(
            "SELECT id FROM senses WHERE word_id=? AND is_core=1 ORDER BY id LIMIT 1", (word_id,)
        ).fetchone()
        for related, strength in sorted(neighbours.get(headword_key, ()), key=lambda item: -item[1]):
            # An authored relation describes the pair, so it applies in both
            # directions; only the closeness is directional in SWOW.
            thai = thai_relations.get((headword_key, related)) or thai_relations.get((related, headword_key), {})
            # Word Association explains itself from this row, so every pair gets an
            # explanation now.  An authored one wins; otherwise the shared category
            # of the group the pair sits in is stated -- still built from real data,
            # never written at play time.
            explanation = thai.get("explanation_th")
            if not explanation:
                category = (thai_groups.get(headword_key) or thai_groups.get(related) or {}).get("category")
                explanation = (
                    f"{headword_key} กับ {related} เป็นคำที่คนมักนึกถึงคู่กันในเรื่อง{category}"
                    if category else f"{headword_key} กับ {related} เป็นคำที่คนมักนึกถึงคู่กัน"
                )
            db.execute(
                "INSERT OR IGNORE INTO related_words (word_id,sense_id,related_word_id,related_headword,"
                "relation_type,closeness,confidence,explanation_th,is_giveaway,source_name,source_license)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (word_id, core["id"] if core else None, word_ids[related], related,
                 thai.get("relation_type") or "association", strength, round(min(strength / 0.2, 1.0), 3),
                 explanation, int(thai.get("is_giveaway") == "1"), "SWOW-EN18", SWOW_LICENSE),
            )
    for headword_key, word_id in word_ids.items():
        members = sorted(neighbours.get(headword_key, ()), key=lambda item: -item[1])
        if len(members) < 3:
            continue
        thai = thai_groups.get(headword_key)
        if thai is None:
            gaps.append(f"groups_th.txt missing category/explanation for hub {headword_key}")
            continue
        db.execute(
            "INSERT INTO relation_groups (hub_word_id,category,explanation_th,source_name) VALUES (?,?,?,?)",
            (word_id, thai["category"], thai["explanation_th"], "SWOW-EN18"),
        )
        group_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for related, strength in members:
            db.execute(
                "INSERT OR IGNORE INTO relation_group_members (group_id,word_id,closeness) VALUES (?,?,?)",
                (group_id, word_ids[related], strength),
            )

    for key, value in {
        "content_version": str(CONTENT_VERSION),
        "built_at": now(),
        "word_count": str(len(word_ids)),
        "test_only_words": str(sum(1 for word in words if word["is_test_only"])),
        "source_db": SOURCE_DB.name,
        "generation_run": compact.RUN_KEY,
        "licenses": f"{SOURCE_LICENSE}; {SWOW_LICENSE}",
    }.items():
        db.execute("INSERT INTO content_meta VALUES (?,?)", (key, value))

    db.commit()
    counts = {
        table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("words", "senses", "word_forms", "example_sentences", "related_words", "relation_groups")
    }
    db.close()
    source.close()

    print(f"built {out_path}")
    print("  " + "  ".join(f"{name}={value}" for name, value in counts.items()))
    if gaps:
        print(f"  content gaps: {len(gaps)}")
        for gap in gaps[:15]:
            print(f"    {gap}")
        if len(gaps) > 15:
            print(f"    ... and {len(gaps) - 15} more")
    return 1 if gaps else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DB)
    return build(parser.parse_args().out)


if __name__ == "__main__":
    raise SystemExit(main())
