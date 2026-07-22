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
OUT_PATH = os.path.join(ROOT, "tools", "llm_sentences.py")

# Words excluded from this dataset: gemini-3.6-flash_round1.json's content for
# these failed the varied-forms QC check (countable nouns that only reached 2
# distinct cloze forms) or used an invalid derived-lemma cloze_target
# ("different" -> "difference"). Regeneration was attempted
# (tools/_regenerate_llm.py) but the Gemini API key's prepayment credits were
# depleted (429 RESOURCE_EXHAUSTED) before a clean retry could complete.
# These 9 words are intentionally left OUT of DATA below so build_dataset.py's
# existing SENT_TEMPLATES fallback covers them instead. See NOTES.md.
EXCLUDE = {"bag", "day", "evening", "name", "night", "orange", "page", "window", "different"}

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

9 words that failed that check in the raw model output (countable nouns
that only reached 2 distinct forms -- singular/plural -- instead of the
achievable 3+ via a possessive form, plus "different" which used an invalid
derived-lemma cloze_target "difference") are intentionally NOT included
here; build_dataset.py falls back to its SENT_TEMPLATES generator for those.
A regeneration attempt (tools/_regenerate_llm.py) hit a depleted Gemini API
key (429 RESOURCE_EXHAUSTED) before it could retry them cleanly. See
NOTES.md for the exact word list and reasoning.

`cloze_target` is kept per-sentence (not pre-resolved to start/end offsets)
so build_dataset.py can compute cloze_start/cloze_end itself the same way
it already does for template sentences (case-insensitive substring search,
verified against en_text) -- keeping one code path for that computation.

Regenerate this file: python tools/_gen_llm_sentences.py
(reads tools/model_compare_results/gemini-3.6-flash_round1.json)
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
