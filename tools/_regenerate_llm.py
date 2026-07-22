# -*- coding: utf-8 -*-
"""
One-off regeneration pass for the ~9 words that failed the varied-forms /
cloze-validity QC check in tools/model_compare_results/gemini-3.6-flash_round1.json.
Not part of the rerunnable pipeline -- a scratch script whose output gets
folded into tools/llm_sentences.py by hand/via merge script.

Usage: python tools/_regenerate_llm.py
"""
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from wordlist import WORDS  # noqa: E402
from thai_data import DATA  # noqa: E402

from google import genai
from google.genai import types


def load_env(path):
    env = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


env = load_env(ROOT / ".env")
API_KEY = env.get("API_KEY") or os.environ.get("API_KEY")
if not API_KEY:
    sys.exit("No API_KEY found in .env")

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-3.6-flash"

# Words that failed QC in round1: countable nouns that only reached 2 distinct
# cloze forms (singular/plural) instead of the achievable 3+ (via possessive
# 's/'s' the way "cat"/"book" did in the same run), plus "different" which
# used an invalid derived-lemma cloze_target ("difference" is not an
# inflected form of "different").
TARGET_WORDS = ["bag", "day", "evening", "name", "night", "orange", "page", "window", "different"]

pos_map = {w[0].lower(): w[1] for w in WORDS}

PROMPT_TEMPLATE = """You are building example sentences for a Thai-learner English vocabulary app (Oxford 3000, A1 band). For EACH word below, produce a JSON object following this EXACT schema (no markdown fences, no commentary, just a JSON array):

[
  {{
    "headword": "answer",
    "sentences": [
      {{"rank": 1, "en_text": "...", "th_text": "...", "cloze_target": "answered", "is_emotional": true}},
      {{"rank": 2, ...}},
      {{"rank": 3, ...}},
      {{"rank": 4, ...}},
      {{"rank": 5, ...}}
    ],
    "grammar_note_th": "..."
  }},
  ...
]

STRICT RULES (violating these makes the output unusable):
1. Exactly 5 sentences per word. The 5 sentences must use deliberately DIFFERENT grammatical forms/structures of the headword (e.g. past tense, base/imperative, -ing form, present tense, to-infinitive, plural, possessive) -- not 5 sentences that all use the same form. AT LEAST 3 of the 5 cloze_target strings (case-insensitive) must be textually distinct from each other.
2. rank=1 sentence MUST be "is_emotional": true -- a real-life, emotionally engaging situation, NOT a dry dictionary-style sentence. rank 2-5 can be is_emotional: false.
3. Every word surrounding the headword in each sentence must be simple A1/A2-level vocabulary a beginner already knows -- do not use advanced words.
4. "cloze_target" is the exact substring of en_text that is an INFLECTED FORM OF THE SAME HEADWORD/LEMMA (e.g. for a noun: singular, plural, possessive singular 's, possessive plural s' -- for an adjective: base, comparative "more X", superlative "most X"). NEVER use a different word/lemma (e.g. do NOT use "difference" as the cloze_target for headword "different" -- that is a different word). It must appear verbatim (case-insensitive) in en_text.
5. th_text is a natural Thai translation of en_text (not word-for-word).
6. grammar_note_th: one Thai-language paragraph that EXPLAINS WHY the different forms were used across the 5 sentences (reasoning, not just labels), per this style:
   BAD: "Past tense เลยเป็น V2"
   GOOD: "ประโยคนี้พูดถึงเหตุการณ์ในอดีต จึงใช้ Past Simple ที่มีโครงสร้าง S + V2 ซึ่ง V2 ของ go คือ went (เป็นกริยาผิดปกติ ไม่เติม -ed)"

SPECIFIC GUIDANCE for these words: for countable nouns, deliberately use singular, plural (-s/-es), AND a possessive form (headword's / headwords') across the 5 sentences to reach 3+ distinct forms (example that already worked well: cat -> cat / cat / cats / cat's / cats'). For the adjective "different", use base "different" in some sentences and comparative "more different" / superlative "most different" in others -- do NOT switch to the noun "difference".

Words (headword | part-of-speech | Thai core meaning):
{word_lines}

Return ONLY the JSON array, nothing else.
"""


def build_prompt(words):
    lines = []
    for hw in words:
        pos = pos_map.get(hw, "")
        meaning = DATA.get(hw, {}).get("meaning_th", "")
        lines.append(f"{hw} | {pos} | {meaning}")
    return PROMPT_TEMPLATE.format(word_lines="\n".join(lines))


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def validate_item(item, hw):
    pos = pos_map.get(hw, "")
    sents = item.get("sentences", [])
    if len(sents) != 5:
        return False, "not 5 sentences"
    ranks = sorted(s.get("rank") for s in sents)
    if ranks != [1, 2, 3, 4, 5]:
        return False, f"bad rank sequence {ranks}"
    r1 = next((s for s in sents if s.get("rank") == 1), None)
    if not r1 or r1.get("is_emotional") is not True:
        return False, "rank1 not emotional"
    for s in sents:
        ct = s.get("cloze_target", "")
        en = s.get("en_text", "")
        if not ct or not re.search(re.escape(ct), en, re.IGNORECASE):
            return False, f"cloze_target {ct!r} not in en_text {en!r}"
        # reject derivational-lemma-switch cloze targets: require the cloze
        # target to share the headword's stem (first 4 chars) as a cheap
        # same-lemma sanity check
        stem = hw[:4] if len(hw) >= 4 else hw
        if stem.lower() not in ct.lower():
            return False, f"cloze_target {ct!r} doesn't look like a form of {hw!r}"
    targets = {s.get("cloze_target", "").lower() for s in sents}
    if len(targets) < 3:
        return False, f"only {len(targets)} distinct forms: {targets}"
    return True, "ok"


def call_with_retry(words, attempts=3):
    prompt = build_prompt(words)
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.8),
            )
            text = resp.text or ""
            parsed = extract_json(text)
            return parsed, None
        except Exception as e:
            last_err = e
            print(f"  attempt {attempt} failed: {e}")
            if attempt < attempts:
                time.sleep(2 ** attempt)
    return None, last_err


def main():
    results = {}
    failed = []

    remaining = list(TARGET_WORDS)
    for attempt_round in range(1, 4):
        if not remaining:
            break
        print(f"--- round {attempt_round}, words: {remaining} ---")
        parsed, err = call_with_retry(remaining, attempts=3)
        if parsed is None:
            print(f"  API call totally failed: {err}")
            continue
        by_hw = {p.get("headword", "").lower(): p for p in parsed}
        still_remaining = []
        for hw in remaining:
            item = by_hw.get(hw)
            if item is None:
                still_remaining.append(hw)
                continue
            ok, reason = validate_item(item, hw)
            if ok:
                results[hw] = item
                print(f"  [{hw}] PASSED")
            else:
                print(f"  [{hw}] FAILED: {reason}")
                still_remaining.append(hw)
        remaining = still_remaining

    failed = remaining
    out_path = ROOT / "tools" / "model_compare_results" / "_regenerated.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRegenerated {len(results)}/{len(TARGET_WORDS)} words -> {out_path}")
    if failed:
        print(f"STILL FAILED (will fall back to templates): {failed}")
    fail_path = ROOT / "tools" / "model_compare_results" / "_regen_failed.json"
    fail_path.write_text(json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
