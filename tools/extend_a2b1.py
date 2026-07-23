# -*- coding: utf-8 -*-
"""
Extension pipeline (2026-07-23, user request): add ~50 Oxford-3000 A2 words
and ~50 B1 words to the seed dataset, using the SAME real sources as the
Phase 1 pass (see NOTES.md):

  - Headwords + CEFR band: the Kolia951/The_Oxford_3000_CEFR JSON source
    (same file the 153 A1 words were cross-checked against).
  - Candidate ranking: SWOW-EN18 responseStats total response counts as a
    frequency proxy (real human association data already on disk) — the
    most-responded words are the most common/concrete, which also
    guarantees good SWOW coverage for Odd One Out / Word Association.
  - POS: WordNet most-frequent synset POS (nltk), a grammatical-fact
    judgment call per SPEC.md, manually overridable in POS_OVERRIDES.
  - meaning_th: real Wiktionary Thai translations via wiktapi.dev, exactly
    like the Phase 1 cross-check; the model only PICKS among the real
    candidates. Words with no Thai row are marked meaning_source="approx"
    (same flag mechanism as "make").
  - thai_reading / stress_index / ipa / collocations / example sentences /
    grammar notes: gemini-3.6-flash (same model that won the Phase 1
    model-compare), validated with the same QC rules
    (tools/_regenerate_llm.py's validate_item) plus metadata checks.

Resumable: each stage checkpoints to tools/ext_work/*.json.
Run:  python tools/extend_a2b1.py
Out:  tools/ext_a2b1.py  (WORDS_EXT / THAI_EXT / SENT_EXT / SWOW_EXT),
      consumed by the try/except-import merge shims at the bottom of
      wordlist.py / thai_data.py / llm_sentences.py / swow_associations.py.
Then: python tools/build_dataset.py  to rebuild the seed DB.
"""
import csv
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
WORK = TOOLS / "ext_work"
WORK.mkdir(exist_ok=True)
sys.path.insert(0, str(TOOLS))

from wordlist import WORDS  # noqa: E402  (already includes ext if rerun)

CEFR_URL = ("https://raw.githubusercontent.com/Kolia951/The_Oxford_3000_CEFR/"
            "main/package.txt")
SWOW_DIR = Path(r"C:\Users\pimde\Downloads\SWOW-EN18")
RESPONSE_STATS = SWOW_DIR / "responseStats.SWOW-EN.20180827.csv"
STRENGTH = SWOW_DIR / "strength.SWOW-EN.R123.20180827.csv"

PER_BAND_TARGET = 50
PER_BAND_BUFFER = 62  # extra candidates so QC drops don't leave us short

# Parallelism (2026-07-23: stages B/C redesigned to run concurrently per
# the user's standing bulk-task preference — see memory/NOTES.md):
B_WORKERS = 8   # simultaneous wiktapi HTTP fetches
C_WORKERS = 5   # simultaneous Gemini batch calls per round

# Hand overrides where WordNet's most-frequent-synset POS is wrong for the
# sense a learner drills first.
POS_OVERRIDES = {
    "cook": "v", "dance": "v", "dream": "v", "drive": "v", "practise": "v",
    "practice": "n", "travel": "v", "visit": "v", "wash": "v", "worry": "v",
}

WN_POS = {"n": "n", "v": "v", "a": "adj", "s": "adj", "r": "adv"}


def log(*a):
    print(*a, flush=True)


def http_json(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "vocab-app-pipeline"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(2 ** i)


# --------------------------------------------------------------------------
# Stage A: candidate selection
# --------------------------------------------------------------------------

def stage_a():
    out = WORK / "stageA.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    log("Stage A: fetching CEFR lists + ranking by SWOW response frequency...")
    cefr = http_json(CEFR_URL)
    existing = {w[0].lower() for w in WORDS}

    # SWOW response frequency (proxy for how common/concrete a word is).
    freq = {}
    with open(RESPONSE_STATS, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        word_col = next((c for c in cols if c.lower() in ("response", "word")), cols[0])
        # Explicit frequency column — the file's first (unnamed) column is a
        # row index whose values dwarf the real counts, so never max() over
        # every numeric column.
        freq_col = next((c for c in cols if c.lower() in ("freq.r123", "freq")),
                        None) or next(c for c in cols if "freq" in c.lower())
        for row in reader:
            w = (row.get(word_col) or "").strip().lower()
            if not w:
                continue
            try:
                n = float(row[freq_col])
            except (TypeError, ValueError):
                continue
            freq[w] = max(freq.get(w, 0), n)

    import nltk  # noqa: F401
    from nltk.corpus import wordnet as wn

    # The source lists a word under EVERY band one of its senses belongs
    # to (e.g. "face" appears in both A1 and B1). A learner meets the word
    # at its lowest band, so each band only picks words absent from all
    # lower bands.
    lower_bands = {"A2": {"A1"}, "B1": {"A1", "A2"}}

    def pick(band):
        lower = set()
        for lb in lower_bands[band]:
            lower.update(str(w).strip().lower() for w in cefr.get(lb, []))
        pool = []
        for w in cefr.get(band, []):
            lw = str(w).strip().lower()
            if not re.fullmatch(r"[a-z]+", lw):
                continue  # single plain words only
            if lw in existing or lw in lower:
                continue
            syns = wn.synsets(lw)
            if not syns:
                continue
            counts = {}
            for s in syns:
                counts[s.pos()] = counts.get(s.pos(), 0) + 1
            wnpos = max(counts, key=counts.get)
            pos = POS_OVERRIDES.get(lw, WN_POS.get(wnpos, "n"))
            pool.append({"headword": lw, "pos": pos, "cefr": band,
                         "swow_freq": freq.get(lw, 0)})
        pool.sort(key=lambda d: -d["swow_freq"])
        chosen = pool[:PER_BAND_BUFFER]
        log(f"  {band}: {len(pool)} eligible, keeping top {len(chosen)} "
            f"(freq {chosen[0]['swow_freq']:.0f}..{chosen[-1]['swow_freq']:.0f})")
        return chosen

    data = {"A2": pick("A2"), "B1": pick("B1")}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


# --------------------------------------------------------------------------
# Stage B: Wiktionary Thai translations (wiktapi.dev, same as Phase 1)
# --------------------------------------------------------------------------

POS_TO_WIKT = {"n": "noun", "v": "verb", "adj": "adj", "adv": "adv",
               "prep": "prep", "conj": "conj", "det": "det", "pron": "pron"}


def _fetch_translations(cand):
    """One wiktapi fetch + Thai-candidate extraction (runs on a worker
    thread — everything here is local to the call, no shared state)."""
    hw = cand["headword"]
    try:
        data = http_json(f"https://api.wiktapi.dev/v1/en/word/{hw}/translations")
    except Exception as e:
        return hw, {"candidates": [], "error": str(e)}
    wanted_pos = POS_TO_WIKT.get(cand["pos"], "")
    th_same_pos, th_any = [], []

    # wiktapi shape: list/dict of translation groups with pos + entries.
    def walk(node, pos_hint=""):
        if isinstance(node, dict):
            p = str(node.get("pos", pos_hint)).lower()
            if str(node.get("lang_code", "")).lower() == "th" and node.get("word"):
                (th_same_pos if wanted_pos and wanted_pos in p else th_any).append(
                    str(node["word"]))
            for v in node.values():
                walk(v, p)
        elif isinstance(node, list):
            for v in node:
                walk(v, pos_hint)
    walk(data)
    seen = set()
    cands = [w for w in th_same_pos + th_any
             if not (w in seen or seen.add(w))][:8]
    return hw, {"candidates": cands}


def stage_b(candidates):
    out = WORK / "stageB.json"
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    words = [c for band in candidates.values() for c in band]
    todo = [c for c in words if c["headword"] not in done]
    log(f"Stage B: wiktapi translations for {len(todo)} words "
        f"({len(done)} cached), {B_WORKERS} parallel workers...")
    lock = threading.Lock()
    n_done = 0
    with ThreadPoolExecutor(max_workers=B_WORKERS) as ex:
        futures = [ex.submit(_fetch_translations, c) for c in todo]
        for fut in as_completed(futures):
            hw, res = fut.result()
            with lock:
                done[hw] = res
                n_done += 1
                if res.get("error"):
                    log(f"  [{hw}] wiktapi error: {res['error']}")
                if n_done % 20 == 0:  # periodic checkpoint
                    out.write_text(json.dumps(done, ensure_ascii=False),
                                   encoding="utf-8")
                    log(f"  {n_done}/{len(todo)} fetched")
    out.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    n_empty = sum(1 for v in done.values() if not v.get("candidates"))
    log(f"Stage B done: {n_empty} words with no Thai row (will be approx-flagged)")
    return done


# --------------------------------------------------------------------------
# Stage C: Gemini content generation + QC
# --------------------------------------------------------------------------

PROMPT = """You are building content for a Thai-learner English vocabulary app (Oxford 3000). For EACH word below, produce a JSON object following this EXACT schema (no markdown fences, no commentary, just a JSON array):

[
  {{
    "headword": "answer",
    "meaning_th": "ตอบ",
    "meaning_source": "wiktionary",
    "thai_reading": "แอน-เซอะ",
    "stress_index": 1,
    "ipa": "/ˈɑːnsə/",
    "countable": null,
    "collocation_en": "answer the phone",
    "collocation_th": "รับโทรศัพท์",
    "sentences": [
      {{"rank": 1, "en_text": "...", "th_text": "...", "cloze_target": "answered", "is_emotional": true}},
      {{"rank": 2, ...}}, {{"rank": 3, ...}}, {{"rank": 4, ...}}, {{"rank": 5, ...}}
    ],
    "grammar_note_th": "..."
  }},
  ...
]

METADATA RULES:
- meaning_th: each word below lists REAL Wiktionary Thai translation candidates. You MUST pick the single candidate that best matches the word's most common everyday sense (the one a learner meets first). Set "meaning_source": "wiktionary". ONLY if the candidate list is empty, write the best natural Thai translation yourself and set "meaning_source": "approx".
- thai_reading: Thai-script transliteration of the ENGLISH pronunciation, syllables separated by hyphens (e.g. answer -> "แอน-เซอะ", beautiful -> "บิว-ทิ-ฟุล"). NOT the Thai meaning.
- stress_index: 1-based index of the stressed syllable in thai_reading.
- ipa: British-English IPA between slashes (e.g. "/ˈɑːnsə/").
- countable: for nouns only — 1 if countable, 0 if uncountable; null for every other part of speech.
- collocation_en: a short, high-frequency collocation/phrase using the headword; collocation_th: its natural Thai rendering.

SENTENCE RULES (violating these makes the output unusable):
1. Exactly 5 sentences per word. The 5 sentences must use deliberately DIFFERENT grammatical forms/structures of the headword (past tense, base/imperative, -ing form, present tense, to-infinitive, plural, possessive, comparative...) — AT LEAST 3 of the 5 cloze_target strings (case-insensitive) must be textually distinct.
2. rank=1 MUST be "is_emotional": true — a real-life, emotionally engaging situation, not a dry dictionary sentence. rank 2-5 may be false.
3. Surrounding vocabulary must be simple (A1-A2 level) — these are A2/B1 headwords for beginners; do not use advanced words around them.
4. "cloze_target" is the exact substring of en_text that is an INFLECTED FORM OF THE SAME HEADWORD/LEMMA. NEVER a different lemma. It must appear verbatim (case-insensitive) in en_text.
5. th_text is a natural Thai translation of en_text.
6. grammar_note_th: one Thai paragraph EXPLAINING WHY the different forms were used across the 5 sentences (reasoning, not labels), e.g. "ประโยคนี้พูดถึงเหตุการณ์ในอดีต จึงใช้ Past Simple ที่มีโครงสร้าง S + V2 ..."

Words (headword | part-of-speech | CEFR | real Wiktionary Thai candidates):
{word_lines}

Return ONLY the JSON array, nothing else."""

NO_INFLECT_POS = {"det", "prep", "conj", "interj", "pron", "phrase"}
THAI_RE = re.compile(r"[฀-๿]")


def validate_sentences(item, hw, pos):
    sents = item.get("sentences", [])
    if len(sents) != 5:
        return False, "not 5 sentences"
    if sorted(s.get("rank") for s in sents) != [1, 2, 3, 4, 5]:
        return False, "bad rank sequence"
    r1 = next((s for s in sents if s.get("rank") == 1), None)
    if not r1 or r1.get("is_emotional") is not True:
        return False, "rank1 not emotional"
    for s in sents:
        ct, en, th = s.get("cloze_target", ""), s.get("en_text", ""), s.get("th_text", "")
        if not ct or not re.search(re.escape(ct), en, re.IGNORECASE):
            return False, f"cloze_target {ct!r} not in en_text"
        stem = hw[:4] if len(hw) >= 4 else hw
        if stem.lower() not in ct.lower():
            return False, f"cloze_target {ct!r} not a form of {hw!r}"
        if not THAI_RE.search(th):
            return False, "th_text not Thai"
    if pos not in NO_INFLECT_POS:
        targets = {s.get("cloze_target", "").lower() for s in sents}
        if len(targets) < 3:
            return False, f"only {len(targets)} distinct forms"
    return True, "ok"


def validate_meta(item, wikt_cands):
    m = item.get("meaning_th", "")
    if not THAI_RE.search(m):
        return False, "meaning_th not Thai"
    src = item.get("meaning_source")
    if src == "wiktionary" and wikt_cands and m not in wikt_cands:
        return False, f"meaning_th {m!r} not among wiktionary candidates"
    if src not in ("wiktionary", "approx"):
        return False, f"bad meaning_source {src!r}"
    if wikt_cands and src == "approx":
        return False, "approx despite having wiktionary candidates"
    tr = item.get("thai_reading", "")
    if not THAI_RE.search(tr):
        return False, "thai_reading not Thai"
    si = item.get("stress_index")
    n_syll = len([p for p in tr.split("-") if p])
    if not isinstance(si, int) or not (1 <= si <= n_syll):
        return False, f"stress_index {si!r} out of range for {tr!r}"
    ipa = item.get("ipa", "")
    if not (isinstance(ipa, str) and ipa.startswith("/") and ipa.endswith("/")):
        return False, f"bad ipa {ipa!r}"
    if not item.get("collocation_en") or not THAI_RE.search(item.get("collocation_th", "")):
        return False, "bad collocations"
    return True, "ok"


def stage_c(candidates, translations):
    out = WORK / "stageC.json"
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}

    def load_env(path):
        env = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
        return env

    api_key = load_env(ROOT / ".env").get("API_KEY") or os.environ.get("API_KEY")
    if not api_key:
        sys.exit("No API_KEY in .env")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    model = "gemini-3.6-flash"

    words = [c for band in candidates.values() for c in band]
    by_hw = {c["headword"]: c for c in words}
    remaining = [c["headword"] for c in words if c["headword"] not in done]
    log(f"Stage C: generating content for {len(remaining)} words "
        f"({len(done)} already done)...")

    def build_prompt(hws):
        lines = []
        for hw in hws:
            c = by_hw[hw]
            cands = translations.get(hw, {}).get("candidates", [])
            lines.append(f"{hw} | {c['pos']} | {c['cefr']} | "
                         f"{', '.join(cands) if cands else '(none)'}")
        return PROMPT.format(word_lines="\n".join(lines))

    def call(hws, attempts=3):
        for attempt in range(attempts):
            try:
                resp = client.models.generate_content(
                    model=model, contents=build_prompt(hws),
                    config=types.GenerateContentConfig(temperature=0.8),
                )
                text = (resp.text or "").strip()
                text = re.sub(r"^```(json)?", "", text).strip()
                text = re.sub(r"```$", "", text).strip()
                return json.loads(text), None
            except Exception as e:
                log(f"    attempt {attempt+1} failed: {e}")
                time.sleep(3 * (attempt + 1))
        return None, "exhausted"

    for round_no in range(1, 4):
        if not remaining:
            break
        batches = [remaining[i:i + 5] for i in range(0, len(remaining), 5)]
        log(f"  --- round {round_no}: {len(remaining)} words in "
            f"{len(batches)} batches, {C_WORKERS} parallel calls ---")
        next_remaining = []
        # All batches of this round fly concurrently; validation of the
        # returned JSON is cheap and runs on the main thread as results
        # come in (each worker only talks to the API + parses).
        with ThreadPoolExecutor(max_workers=C_WORKERS) as ex:
            futures = {ex.submit(call, b): b for b in batches}
            for fut in as_completed(futures):
                batch = futures[fut]
                parsed, err = fut.result()
                if parsed is None:
                    log(f"    batch {batch} API-failed: {err}")
                    next_remaining.extend(batch)
                    continue
                parsed_by_hw = {str(p.get("headword", "")).lower(): p for p in parsed}
                for hw in batch:
                    item = parsed_by_hw.get(hw)
                    if item is None:
                        next_remaining.append(hw)
                        continue
                    pos = by_hw[hw]["pos"]
                    cands = translations.get(hw, {}).get("candidates", [])
                    ok1, r1 = validate_sentences(item, hw, pos)
                    ok2, r2 = validate_meta(item, cands)
                    if ok1 and ok2:
                        done[hw] = item
                        log(f"    [{hw}] PASSED")
                    else:
                        log(f"    [{hw}] FAILED: "
                            f"{r1 if not ok1 else ''} {r2 if not ok2 else ''}")
                        next_remaining.append(hw)
                out.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
        remaining = next_remaining
    out.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Stage C done: {len(done)} passed, {len(remaining)} unrecoverable: {remaining}")
    return done


# --------------------------------------------------------------------------
# Stage D: SWOW extension + write tools/ext_a2b1.py
# --------------------------------------------------------------------------

def stage_d(candidates, translations, content):
    # Final per-band pick: keep candidate (SWOW-frequency) order, take the
    # first PER_BAND_TARGET that passed every stage.
    final = {}
    for band, cands in candidates.items():
        picked = [c for c in cands if c["headword"] in content][:PER_BAND_TARGET]
        final[band] = picked
        log(f"Stage D: {band} -> {len(picked)} words")

    all_new = [c for band in ("A2", "B1") for c in final[band]]
    new_set = {c["headword"] for c in all_new}
    old_set = {w[0].lower() for w in WORDS if w[0].lower() not in new_set}
    vocab = old_set | new_set

    # SWOW: new words as cues -> top 6 in-vocab responses; old cues also
    # gain up to 2 strongest NEW-word responses (their existing top-6
    # snapshot rows stay untouched in swow_associations.py).
    log("Stage D: scanning SWOW strength file (~1.4M rows)...")
    new_cue_rows = {w: [] for w in new_set}
    old_to_new = {}
    with open(STRENGTH, encoding="utf-8", errors="replace", newline="") as f:
        # The SWOW strength file is TAB-delimited (unlike responseStats) and
        # effectively unquoted — a stray '"' in a response otherwise makes
        # the csv module accumulate a >131072-char "field" and blow up.
        csv.field_size_limit(1 << 30)
        reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        cols = reader.fieldnames or []
        cue_c = next(c for c in cols if c.lower() == "cue")
        resp_c = next(c for c in cols if c.lower() == "response")
        str_c = next(c for c in cols if "strength" in c.lower())
        for row in reader:
            cue = (row.get(cue_c) or "").strip().lower()
            resp = (row.get(resp_c) or "").strip().lower()
            if cue == resp or resp not in vocab:
                continue
            try:
                s = float(row[str_c])
            except (TypeError, ValueError):
                continue
            if cue in new_set:
                new_cue_rows[cue].append((resp, s))
            elif cue in old_set and resp in new_set:
                old_to_new.setdefault(cue, []).append((resp, s))

    swow_ext = {}
    for w, rows in new_cue_rows.items():
        rows.sort(key=lambda t: -t[1])
        if rows:
            swow_ext[w] = [(r, round(s, 6)) for r, s in rows[:6]]
    for w, rows in old_to_new.items():
        rows.sort(key=lambda t: -t[1])
        swow_ext.setdefault(w, [])
        swow_ext[w] = swow_ext.get(w, []) + [(r, round(s, 6)) for r, s in rows[:2]]
    no_swow = sorted(w for w in new_set if w not in swow_ext)
    log(f"Stage D: SWOW ext rows for {len(swow_ext)} cues; "
        f"new words with NO swow data: {no_swow}")

    # freq_rank continues after the existing list.
    base_rank = max(w[3] for w in WORDS if w[0].lower() not in new_set)
    words_ext, thai_ext, sent_ext, approx = [], {}, {}, []
    rank = base_rank
    for c in all_new:
        rank += 1
        hw = c["headword"]
        item = content[hw]
        words_ext.append((hw, c["pos"], c["cefr"], rank))
        thai_ext[hw] = dict(
            meaning_th=item["meaning_th"], thai_reading=item["thai_reading"],
            stress_index=item["stress_index"], ipa=item["ipa"],
            countable=item.get("countable"),
            collocation_en=item["collocation_en"],
            collocation_th=item["collocation_th"],
        )
        sent_ext[hw] = {"sentences": item["sentences"],
                        "grammar_note_th": item["grammar_note_th"]}
        if item.get("meaning_source") == "approx":
            approx.append(hw)

    out = TOOLS / "ext_a2b1.py"
    with open(out, "w", encoding="utf-8") as f:
        f.write('# -*- coding: utf-8 -*-\n')
        f.write('"""GENERATED by tools/extend_a2b1.py (2026-07-23) — do not hand-edit.\n\n')
        f.write(f'{len(final["A2"])} Oxford-3000 A2 words + {len(final["B1"])} B1 words '
                'extending the Phase 1 seed.\n'
                'Sources identical to Phase 1 (see extend_a2b1.py docstring): Oxford CEFR\n'
                'JSON headwords, SWOW-EN18 frequency ranking + associations, wiktapi.dev\n'
                'Wiktionary Thai meanings, gemini-3.6-flash readings/collocations/sentences\n'
                'validated with the Phase 1 QC rules.\n\n')
        f.write(f'meaning_source="approx" (no Wiktionary Thai row, model-translated,\n'
                f'same flag as "make"): {approx}\n'
                f'New words with no in-vocab SWOW rows (fall back like Phase 1): {no_swow}\n"""\n\n')
        f.write('WORDS_EXT = [\n')
        for t in words_ext:
            f.write(f'    {t!r},\n')
        f.write(']\n\nTHAI_EXT = {\n')
        for hw, d in thai_ext.items():
            f.write(f'{hw!r}: {d!r},\n')
        f.write('}\n\nSENT_EXT = {\n')
        for hw, d in sent_ext.items():
            f.write(f'{hw!r}: {d!r},\n')  # repr -> valid Python (True/None)
        f.write('}\n\nSWOW_EXT = {\n')
        for hw, rows in sorted(swow_ext.items()):
            f.write(f'{hw!r}: {rows!r},\n')
        f.write('}\n\nAPPROX_MEANINGS = ' + repr(sorted(approx)) + '\n')
    log(f"Stage D: wrote {out}")
    (WORK / "final_summary.json").write_text(json.dumps({
        "a2": [c["headword"] for c in final["A2"]],
        "b1": [c["headword"] for c in final["B1"]],
        "approx_meanings": approx, "no_swow": no_swow,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    candidates = stage_a()
    translations = stage_b(candidates)
    content = stage_c(candidates, translations)
    stage_d(candidates, translations, content)
    log("ALL DONE — next: python tools/build_dataset.py")


if __name__ == "__main__":
    main()
