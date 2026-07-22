# -*- coding: utf-8 -*-
"""One-off generator: reads the validated gemini-3.6-flash_round1.json content
(minus the 9 words that failed QC and had no clean regeneration available,
see NOTES.md) and writes tools/llm_sentences.py in the same
DATA-dict-keyed-by-headword shape as tools/thai_data.py.

Not part of the rerunnable pipeline itself -- run once to produce
llm_sentences.py, which IS part of the pipeline (consumed by build_dataset.py).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
IN_PATH = os.path.join(ROOT, "tools", "model_compare_results", "gemini-3.6-flash_round1.json")
REGEN_PATH = os.path.join(ROOT, "tools", "model_compare_results", "_regenerated.json")
OUT_PATH = os.path.join(ROOT, "tools", "llm_sentences.py")

# Words excluded from this dataset:
# - "a", "cry", "lady", "noisy", "rest", "smile", "english": dropped from
#   the word list entirely in the 2026-07-22 Oxford-3000-A1 cross-check
#   pass (see NOTES.md section 1 / tools/wordlist.py's docstring) -- these
#   headwords no longer exist in the seed at all, so their LLM content
#   (even though some of it originally passed QC, e.g. "a") is dropped too.
#
# NOTE: "bag", "day", "evening", "name", "night", "orange", "page", "window",
# "different" USED to be excluded here (gemini-3.6-flash_round1.json's
# content for them failed the varied-forms QC check / used an invalid
# derived-lemma cloze_target). As of the 2026-07-22 regeneration pass
# (tools/_regenerate_llm.py, once the API key was topped up) all 9 passed
# cleanly on the first retry -- see REGENERATED below, which merges their
# new content into `data` before this EXCLUDE filter runs. They are no
# longer excluded. See NOTES.md section 4.
EXCLUDE = {"a", "cry", "lady", "noisy", "rest", "smile", "english"}

# Manual corrections found during the human spot-check (NOTES.md section 4)
# of the raw gemini-3.6-flash_round1.json th_text -- real generation glitches
# (a stray syllable, a Cyrillic "three" instead of Thai, a dropped verb, a
# dropped subject pronoun, a double negative flipping the meaning, and a
# handful of stray mid-sentence spaces), not stylistic rewrites. Keyed by
# (lowercased headword, rank).
MANUAL_FIXES = {
    ("happy", 2): "ตอนนี้เธอดูมีความสุขมากกว่าสัปดาห์ที่แล้ว",
    ("beautiful", 3): "เสียงของเธอไพเราะกว่าเสียงของฉัน",
    ("come", 2): "กรุณากลับบ้านเร็วหน่อยนะคืนนี้",
    ("garden", 2): "พวกเขาไปเที่ยวสวนสาธารณะหลายแห่งทุกฤดูร้อน",
    ("home", 2): "พวกเขาสร้างบ้านใหม่หลายหลังในเมืองนี้",
    ("school", 2): "มีโรงเรียนประถมศึกษาสามแห่งในเขตนี้",
    ("sea", 5): "พวกเขาอยู่ในหมู่บ้านเล็กๆ ริมทะเล",
    ("want", 4): "เขาไม่อยากออกไปเล่นข้างนอกวันนี้",
    ("write", 1): "เขาเขียนจดหมายรักอันแสนเศร้าถึงแฟนสาวของเขา",
    ("rest", 4): "คุณจำเป็นต้องพักเท้าของคุณตอนนี้",
    ("start", 3): "ดูสิ ฝนกำลังเริ่มตกหนักแล้ว!",
    ("study", 4): "ฉันวางแผนที่จะเรียนวิทยาศาสตร์ที่มหาวิทยาลัย",
    ("thank", 1): "เธอขอบคุณคุณหมอด้วยน้ำตาแห่งความซาบซึ้งใจ",
    ("tree", 1): "เด็กชายนั่งใต้ต้นไม้และร้องไห้อย่างขมขื่น",
    ("tree", 5): "พวกเขาปลูกต้นแอปเปิลเล็กๆ ต้นหนึ่งเมื่อวานนี้",
    ("door", 5): "เธอยืนอยู่ข้างๆ ประตูหน้า",
}

with open(IN_PATH, encoding="utf-8") as f:
    data = json.load(f)

# Merge in the 2026-07-22 regeneration pass (tools/_regenerate_llm.py) for the
# 9 words that failed QC in the original round-1 run (varied-forms / invalid
# cloze-lemma) -- this time the Gemini API key had credits and all 9 passed
# validate_item() cleanly on the first attempt. See NOTES.md section 4.
REGENERATED = {}
if os.path.exists(REGEN_PATH):
    with open(REGEN_PATH, encoding="utf-8") as f:
        REGENERATED = json.load(f)
    # index by lowercased headword, same shape as items in `data`
    regen_by_hw = {hw.lower(): item for hw, item in REGENERATED.items()}
    # replace/insert into `data` (data is a list of dicts with "headword")
    existing_hws = {item["headword"].lower() for item in data}
    for hw, item in regen_by_hw.items():
        if hw in existing_hws:
            data = [item if d["headword"].lower() == hw else d for d in data]
        else:
            data.append(item)

HEADER = '''# -*- coding: utf-8 -*-
"""
LLM-generated example_sentences (5/word) + grammar_note_th, keyed by
lowercased headword -- mirrors the DATA-dict-keyed-by-headword pattern in
thai_data.py.

SOURCE: tools/model_compare_results/gemini-3.6-flash_round1.json, a complete
(160/160 word) run from the model-selection experiment in
tools/model_compare.py. gemini-3.6-flash was chosen over gemini-3.5-flash-lite
(cheaper but only 34-56% varied-forms QC compliance) after a 2-round,
3-model A/B comparison -- see tools/model_compare_results/summary.json for
the full numbers and NOTES.md section 1 for the rationale.

Every entry here was validated word-by-word against SPEC.md section 5's QC
standard: exactly 5 sentences, rank 1 is_emotional=true, cloze_target a
verbatim (case-insensitive) substring of en_text, and >=3 distinct inflected
forms across the 5 sentences for POS that support inflection (verbs/nouns/
adjectives -- determiners/prepositions/conjunctions/pronouns/non-gradable
adverbs are exempt since they structurally cannot vary form).

A manual spot-check read of the Thai translations (NOTES.md section 4) also
caught 16 real generation glitches across ~14 words -- a stray syllable, a
literal Cyrillic "три" instead of Thai "สาม", a couple of dropped
verbs/subject pronouns, one double-negative that flipped a sentence's
meaning, and several stray mid-sentence spaces. These are corrected in
MANUAL_FIXES in tools/_gen_llm_sentences.py and already applied to the
th_text below -- see that dict for the exact before/after list.

9 words failed that check in the raw round-1 model output (countable nouns
that only reached 2 distinct forms -- singular/plural -- instead of the
achievable 3+ via a possessive form, plus "different" which used an invalid
derived-lemma cloze_target "difference"): bag, day, evening, name, night,
orange, page, window, different. A first regeneration attempt
(tools/_regenerate_llm.py) hit a depleted Gemini API key (429
RESOURCE_EXHAUSTED) before it could retry them cleanly, so an earlier
version of this file left them out entirely (build_dataset.py fell back to
its SENT_TEMPLATES generator for those 9 only).

**Update (2026-07-22, API key topped up):** re-ran tools/_regenerate_llm.py
with a valid key -- all 9 words passed validate_item() cleanly on the FIRST
retry attempt this time (no further API issues). Their content is stored in
tools/model_compare_results/_regenerated.json and merged into `data` below
(see the REGENERATED merge step above this HEADER in
tools/_gen_llm_sentences.py) before EXCLUDE is applied. As a result this
file now covers ALL 153 words in the seed -- build_dataset.py's
SENT_TEMPLATES fallback is no longer exercised for any word in the current
build (it remains in the code as a defensive fallback only). See NOTES.md
section 4 for the before/after QC detail per word.

`cloze_target` is kept per-sentence (not pre-resolved to start/end offsets)
so build_dataset.py can compute cloze_start/cloze_end itself the same way
it already does for template sentences (case-insensitive substring search,
verified against en_text) -- keeping one code path for that computation.

Regenerate this file: python tools/_gen_llm_sentences.py
(reads tools/model_compare_results/gemini-3.6-flash_round1.json +
tools/model_compare_results/_regenerated.json)
"""

# word (lowercased headword) -> dict(sentences=[dict(rank, en_text, th_text,
#                                    cloze_target, is_emotional), ...],
#                                    grammar_note_th=str)
DATA = {
'''

lines = [HEADER]
for item in data:
    hw = item["headword"].lower()
    if hw in EXCLUDE:
        continue
    sents = item["sentences"]
    gn = item["grammar_note_th"]
    lines.append(f"{hw!r}: dict(\n")
    lines.append("    sentences=[\n")
    for s in sents:
        th_fixed = MANUAL_FIXES.get((hw, s["rank"]), s["th_text"])
        lines.append(
            "        dict(rank={rank!r}, en_text={en!r}, th_text={th!r}, "
            "cloze_target={ct!r}, is_emotional={em!r}),\n".format(
                rank=s["rank"],
                en=s["en_text"],
                th=th_fixed,
                ct=s["cloze_target"],
                em=1 if s["is_emotional"] else 0,
            )
        )
    lines.append("    ],\n")
    lines.append(f"    grammar_note_th={gn!r},\n")
    lines.append("),\n")
lines.append("}\n")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("".join(lines))

n_written = sum(1 for item in data if item["headword"].lower() not in EXCLUDE)
print(f"Wrote {OUT_PATH} with {n_written} words (excluded {len(EXCLUDE)}: {sorted(EXCLUDE)})")
