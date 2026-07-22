# -*- coding: utf-8 -*-
"""Scratch validation script (not part of pipeline) to check
gemini-3.6-flash_round1.json against SPEC.md section 5 QC rules, word by word.
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from wordlist import WORDS

ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_PATH = os.path.join(ROOT, "tools", "model_compare_results", "gemini-3.6-flash_round1.json")

with open(DATA_PATH, encoding="utf-8") as f:
    data = json.load(f)

by_hw = {item["headword"].lower(): item for item in data}
pos_map = {w[0].lower(): w[1] for w in WORDS}
expected = [w[0].lower() for w in WORDS]

# POS that can't meaningfully vary inflected form
NO_INFLECT_POS = {"det", "prep", "conj", "interj", "pron", "phrase"}

missing = [w for w in expected if w not in by_hw]
extra = [h for h in by_hw if h not in expected]

fail_5sent = []
fail_rank1 = []
fail_cloze = []
fail_varied = []
fail_rank_seq = []
dup_headwords = [h for h in by_hw if list(by_hw.keys()).count(h) > 1]

for hw in expected:
    item = by_hw.get(hw)
    if item is None:
        continue
    pos = pos_map.get(hw, "")
    sents = item.get("sentences", [])
    if len(sents) != 5:
        fail_5sent.append((hw, len(sents)))
        continue
    ranks = sorted(s.get("rank") for s in sents)
    if ranks != [1, 2, 3, 4, 5]:
        fail_rank_seq.append((hw, ranks))
    r1 = next((s for s in sents if s.get("rank") == 1), None)
    if not r1 or r1.get("is_emotional") is not True:
        fail_rank1.append(hw)
    import re as _re
    bad_cloze_sents = []
    for s in sents:
        ct = s.get("cloze_target", "")
        en = s.get("en_text", "")
        if not ct or not _re.search(_re.escape(ct), en, _re.IGNORECASE):
            bad_cloze_sents.append(s.get("rank"))
    if bad_cloze_sents:
        fail_cloze.append((hw, bad_cloze_sents))
    if pos not in NO_INFLECT_POS:
        targets = {s.get("cloze_target", "").lower() for s in sents}
        if len(targets) < 3:
            fail_varied.append((hw, sorted(targets)))

print("=== SUMMARY ===")
print("total expected:", len(expected), "total returned:", len(data))
print("missing:", missing)
print("extra:", extra)
print("dup headwords:", dup_headwords)
print()
print(f"fail_5sent ({len(fail_5sent)}):", fail_5sent)
print(f"fail_rank_seq ({len(fail_rank_seq)}):", fail_rank_seq)
print(f"fail_rank1_emotional ({len(fail_rank1)}):", fail_rank1)
print(f"fail_cloze ({len(fail_cloze)}):", fail_cloze)
print(f"fail_varied_forms (pos supports inflection) ({len(fail_varied)}):")
for hw, t in fail_varied:
    print("  ", hw, pos_map.get(hw), t)

# also write to a json report for programmatic reuse
report = {
    "missing": missing,
    "extra": extra,
    "fail_5sent": fail_5sent,
    "fail_rank_seq": fail_rank_seq,
    "fail_rank1": fail_rank1,
    "fail_cloze": fail_cloze,
    "fail_varied": fail_varied,
}
with open(os.path.join(ROOT, "tools", "model_compare_results", "_validation_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
