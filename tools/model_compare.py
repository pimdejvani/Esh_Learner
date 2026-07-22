# -*- coding: utf-8 -*-
"""
Model-selection experiment for the LLM-generated portion of the content
pipeline (SPEC.md section 5, item 4): example_sentences (5/word, QC standard
in SPEC.md section 5) + grammar_note_th for word_forms.

Runs 2 rounds x 3 candidate Gemini models over the full 150-word A1 list
(chunked to keep prompts/outputs manageable and JSON-valid), then scores
each run against the QC rules programmatically and reports token cost.

Candidates chosen to skip the expensive frontier tier (gemini-3.1-pro-preview)
per user request ("ไม่ต้องเอาตัวแพงมาก"):
  - gemini-2.5-flash-lite   ($0.10 / $0.40 per 1M tok)  -- cheap baseline
  - gemini-3.5-flash-lite   ($0.30 / $2.50 per 1M tok)  -- new-gen cheap
  - gemini-3.6-flash        ($1.50 / $7.50 per 1M tok)  -- new-gen mid

Usage: python tools/model_compare.py
Reads GEMINI key from ../.env (key name: API_KEY).
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

# ---- load .env manually (no extra dep) ----
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

MODELS = {
    "gemini-2.5-flash-lite": {"in": 0.10, "out": 0.40},
    "gemini-3.5-flash-lite": {"in": 0.30, "out": 2.50},
    "gemini-3.6-flash": {"in": 1.50, "out": 7.50},
}

ROUNDS = 2
CHUNK_SIZE = 50

OUT_DIR = ROOT / "tools" / "model_compare_results"
OUT_DIR.mkdir(exist_ok=True)

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
1. Exactly 5 sentences per word. The 5 sentences must use deliberately DIFFERENT grammatical forms/structures of the headword (e.g. past tense, base/imperative, -ing form, present tense, to-infinitive) -- not 5 sentences that all use the same form.
2. rank=1 sentence MUST be "is_emotional": true -- a real-life, emotionally engaging situation, NOT a dry dictionary-style sentence. rank 2-5 can be is_emotional: false.
3. Every word surrounding the headword in each sentence must be simple A1/A2-level vocabulary a beginner already knows -- do not use advanced words.
4. "cloze_target" is the exact substring of en_text that is the inflected form of the headword used in that sentence (so the app can blank it out). It must appear verbatim in en_text.
5. th_text is a natural Thai translation of en_text (not word-for-word).
6. grammar_note_th: one Thai-language paragraph that EXPLAINS WHY the different forms were used across the 5 sentences (reasoning, not just labels like "past tense" -- explain the tense/reason and point out any irregular/spelling-change form), per this style:
   BAD: "Past tense เลยเป็น V2"
   GOOD: "ประโยคนี้พูดถึงเหตุการณ์ในอดีต จึงใช้ Past Simple ที่มีโครงสร้าง S + V2 ซึ่ง V2 ของ go คือ went (เป็นกริยาผิดปกติ ไม่เติม -ed)"

Words (headword | part-of-speech | Thai core meaning):
{word_lines}

Return ONLY the JSON array, nothing else.
"""


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def build_prompt(words_chunk):
    lines = []
    for hw, pos, cefr, rank in words_chunk:
        meaning = DATA.get(hw, {}).get("meaning_th", "")
        lines.append(f"{hw} | {pos} | {meaning}")
    return PROMPT_TEMPLATE.format(word_lines="\n".join(lines))


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def qc_score(parsed, expected_words):
    """Return dict of QC metrics for one chunk's parsed output."""
    issues = []
    got_words = {item.get("headword") for item in parsed} if isinstance(parsed, list) else set()
    missing = set(expected_words) - got_words
    if missing:
        issues.append(f"missing {len(missing)} words: {sorted(missing)[:5]}...")

    n_words = 0
    n_sent_count_ok = 0
    n_rank1_emotional = 0
    n_cloze_valid = 0
    n_varied_forms = 0
    total_sentences = 0

    for item in parsed if isinstance(parsed, list) else []:
        n_words += 1
        sents = item.get("sentences", [])
        total_sentences += len(sents)
        if len(sents) == 5:
            n_sent_count_ok += 1
        r1 = next((s for s in sents if s.get("rank") == 1), None)
        if r1 and r1.get("is_emotional") is True:
            n_rank1_emotional += 1
        cloze_ok = all(
            s.get("cloze_target") and s.get("cloze_target") in s.get("en_text", "")
            for s in sents
        )
        if cloze_ok and sents:
            n_cloze_valid += 1
        targets = {s.get("cloze_target", "").lower() for s in sents}
        if len(targets) >= 3:  # at least 3 distinct inflected forms among 5 sentences
            n_varied_forms += 1

    return {
        "n_words_returned": n_words,
        "n_expected": len(expected_words),
        "missing_words": len(missing),
        "pct_5_sentences": round(100 * n_sent_count_ok / max(n_words, 1), 1),
        "pct_rank1_emotional": round(100 * n_rank1_emotional / max(n_words, 1), 1),
        "pct_cloze_valid": round(100 * n_cloze_valid / max(n_words, 1), 1),
        "pct_varied_forms": round(100 * n_varied_forms / max(n_words, 1), 1),
        "issues": issues,
    }


def run():
    word_chunks = list(chunk(WORDS, CHUNK_SIZE))
    summary = {}

    for model_name, price in MODELS.items():
        summary[model_name] = {"rounds": []}
        for round_no in range(1, ROUNDS + 1):
            round_result = {
                "round": round_no,
                "chunks": [],
                "total_in_tok": 0,
                "total_out_tok": 0,
                "elapsed_s": 0.0,
                "parse_errors": 0,
            }
            all_parsed = []
            t0 = time.time()
            for ci, wc in enumerate(word_chunks):
                prompt = build_prompt(wc)
                try:
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(temperature=0.7),
                    )
                    text = resp.text or ""
                    usage = resp.usage_metadata
                    in_tok = getattr(usage, "prompt_token_count", 0) or 0
                    out_tok = getattr(usage, "candidates_token_count", 0) or 0
                    round_result["total_in_tok"] += in_tok
                    round_result["total_out_tok"] += out_tok
                    try:
                        parsed = extract_json(text)
                        all_parsed.extend(parsed)
                    except Exception as e:
                        round_result["parse_errors"] += 1
                        parsed = []
                        print(f"  [{model_name} r{round_no} chunk{ci}] JSON parse error: {e}")
                    round_result["chunks"].append(
                        {"chunk_idx": ci, "n_words": len(wc), "in_tok": in_tok, "out_tok": out_tok}
                    )
                    print(f"  [{model_name} r{round_no} chunk{ci}] ok, {len(wc)} words, {in_tok}in/{out_tok}out tok")
                except Exception as e:
                    round_result["parse_errors"] += 1
                    print(f"  [{model_name} r{round_no} chunk{ci}] API error: {e}")

            round_result["elapsed_s"] = round(time.time() - t0, 1)
            expected = [w[0] for w in WORDS]
            round_result["qc"] = qc_score(all_parsed, expected)
            round_result["cost_usd"] = round(
                round_result["total_in_tok"] / 1_000_000 * price["in"]
                + round_result["total_out_tok"] / 1_000_000 * price["out"],
                4,
            )

            out_file = OUT_DIR / f"{model_name}_round{round_no}.json"
            out_file.write_text(json.dumps(all_parsed, ensure_ascii=False, indent=2), encoding="utf-8")

            summary[model_name]["rounds"].append(round_result)
            print(
                f"[{model_name} round {round_no}] cost=${round_result['cost_usd']} "
                f"time={round_result['elapsed_s']}s qc={round_result['qc']}"
            )

    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n=== DONE. See tools/model_compare_results/summary.json ===")


if __name__ == "__main__":
    run()
