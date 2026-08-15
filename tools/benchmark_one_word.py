# -*- coding: utf-8 -*-
"""Run one source-grounded, full-word content benchmark against one Gemini model.

Each invocation makes exactly one API request and writes the raw response,
usage metadata, latency, estimated paid-tier cost, and deterministic QC results.
The prompt and source payload are identical across models.

Usage:
    python tools/benchmark_one_word.py --model gemini-3.6-flash
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "tools" / "dictionary_probe_results" / "source_records.json"
OUT_DIR = ROOT / "tools" / "one_word_benchmark_results"
WORD = "capriole"
USD_TO_THB = 33.165  # BOT weighted-average interbank rate, checked 2026-08-13.
REFERENCE_STRESS_INDEX = 1  # Cambridge: /ˈkæp.ri.əʊl/, /ˈkæp.ri.oʊl/.

# Standard synchronous paid-tier prices in USD per 1M tokens.
PRICES = {
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.6-flash": {"input": 1.50, "output": 7.50},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
}

THAI_RE = re.compile(r"[\u0e00-\u0e7f]")
FORBIDDEN_CROSS_SENTENCE_REFERENCES = (
    "ประโยคก่อน",
    "ประโยคถัด",
    "ประโยคที่ 1",
    "ประโยคที่ 2",
    "ประโยคที่ 3",
    "ประโยคที่ 4",
    "ประโยคที่ 5",
    "ตัวอย่างก่อน",
    "จากตัวอย่างอื่น",
)


PROMPT = """You create production-ready content for a Thai English-learning app.
Render only facts grounded in SOURCE JSON. You may translate supplied English
glosses, write learner examples/collocations from those senses, and explain why
the supplied related candidates are connected. Do not invent a sense, POS,
word form, related word, source, or pronunciation source.

Return one JSON object only, with this exact schema:
{
  "headword": "capriole",
  "thai_reading": "...",
  "stress_index": 1,
  "reading_origin": "model_pronunciation_inference",
  "parts_of_speech": [
    {
      "pos": "noun|verb",
      "countability": "countable|uncountable|null",
      "meanings": [
        {
          "thai": "short Thai dictionary meaning",
          "source_gloss": "exact copy of one supplied english_gloss",
          "meaning_origin": "model_translation_of_wiktionary_gloss"
        }
      ],
      "collocation_en": "short natural collocation",
      "collocation_th": "natural Thai translation",
      "flashcard_example": {
        "en": "one short example for this POS",
        "th": "natural Thai translation",
        "cloze_target": "exact headword form appearing in en"
      }
    }
  ],
  "word_family_and_forms": [
    {
      "word": "exact supplied form or derived term",
      "kind": "inflection|derived",
      "pos": "noun|verb|...",
      "meaning_th": null,
      "form_note_th": "short note; inflections with unchanged meaning need no repeated translation",
      "source": "kaikki"
    }
  ],
  "related_words": [
    {
      "word": "exact supplied related candidate",
      "pos": "noun|verb|...",
      "meaning_th": "short Thai meaning",
      "relation_keyword": "one short Thai keyword",
      "relationship_th": "standalone Thai explanation of how this word relates to capriole",
      "source": "kaikki|datamuse"
    }
  ],
  "cloze_examples": [
    {
      "rank": 1,
      "pos": "noun|verb",
      "en_text": "short learner-friendly sentence",
      "th_text": "natural Thai translation",
      "cloze_target": "exact inflected form appearing in en_text",
      "is_emotional": true,
      "explanation_th": "standalone explanation using only this sentence's context: what it means, why this word/form fits, and brief grammar if useful"
    }
  ]
}

Rules:
1. Include every supplied modern POS and every supplied modern sense exactly
   once. Copy each source_gloss character-for-character from SOURCE JSON.
2. Thai meanings must be concise flashcard text. Multiple meanings within one
   POS remain separate array items so the app can display them comma-separated.
3. Give exactly one flashcard example per POS. It must unambiguously demonstrate
   that POS and one supplied sense.
4. Include each unique supplied inflected form once. Do not translate an
   inflection as if it were a new lexical meaning. There are no supplied derived
   family members, so do not invent any.
5. Select exactly 3 useful related words only from supplied Datamuse candidates.
   Give each a POS, Thai meaning, relation keyword, and a truthful standalone
   relationship explanation. Reject an item if the connection would be weak.
6. Give exactly 5 cloze_examples. Across them cover both POS and at least 3
   distinct supplied forms. Rank 1 must be emotionally engaging. Every
   cloze_target must occur verbatim in en_text.
7. Every explanation_th must stand alone. Never refer to another sentence,
   sentence number, prior example, or information not visible in that sentence.
8. Keep examples understandable to an A2/B1 learner except for the target word.
9. Kaikki has no IPA for this record. Infer a Thai-script reading from the
   headword, label it model_pronunciation_inference, and do not claim a source.
10. No IPA, CEFR, symbol metadata, markdown, or commentary.

SOURCE JSON:
{source_json}
"""


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def source_record() -> dict:
    records = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    return next(item for item in records if item["headword"] == WORD)


def int_value(obj, name: str) -> int:
    value = getattr(obj, name, None)
    return int(value or 0)


def validate(output: object, source: dict) -> dict:
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    if not isinstance(output, dict):
        check("json_object", False, "response is not an object")
        return {"passed": False, "score": 0, "max_score": 100, "checks": checks}

    entries = source["kaikki"]["entries"]
    expected_pos = {entry["pos"] for entry in entries}
    expected_glosses = {
        sense["english_gloss"]
        for entry in entries
        for sense in entry["senses"]
    }
    source_forms = {
        form["form"] for entry in entries for form in entry.get("forms", [])
    }
    source_related = {item["word"] for item in source["datamuse"]}

    pos_rows = output.get("parts_of_speech", [])
    actual_pos = {row.get("pos") for row in pos_rows if isinstance(row, dict)}
    actual_glosses = [
        meaning.get("source_gloss")
        for row in pos_rows
        if isinstance(row, dict)
        for meaning in row.get("meanings", [])
        if isinstance(meaning, dict)
    ]
    thai_meanings = [
        meaning.get("thai", "")
        for row in pos_rows
        if isinstance(row, dict)
        for meaning in row.get("meanings", [])
        if isinstance(meaning, dict)
    ]
    check("headword", output.get("headword") == WORD)
    check("all_pos", actual_pos == expected_pos, f"expected={sorted(expected_pos)} actual={sorted(str(x) for x in actual_pos)}")
    check(
        "all_source_glosses_exactly_once",
        len(actual_glosses) == len(expected_glosses)
        and set(actual_glosses) == expected_glosses,
    )
    check(
        "short_thai_meanings",
        len(thai_meanings) == len(expected_glosses)
        and all(THAI_RE.search(value or "") and len(value) <= 80 for value in thai_meanings),
    )
    check(
        "reading_labeled_as_inference",
        bool(THAI_RE.search(output.get("thai_reading", "")))
        and output.get("reading_origin") == "model_pronunciation_inference",
    )
    check(
        "stress_matches_dictionary_reference",
        output.get("stress_index") == REFERENCE_STRESS_INDEX,
    )
    check(
        "countability_json_type",
        all(
            row.get("countability") in {None, "countable", "uncountable"}
            and (row.get("pos") == "noun" or row.get("countability") is None)
            for row in pos_rows
            if isinstance(row, dict)
        ),
    )

    flashcard_examples = [
        row.get("flashcard_example") for row in pos_rows if isinstance(row, dict)
    ]
    check(
        "one_flashcard_example_per_pos",
        len(flashcard_examples) == len(expected_pos)
        and all(
            isinstance(example, dict)
            and example.get("cloze_target")
            and example["cloze_target"] in example.get("en", "")
            and THAI_RE.search(example.get("th", ""))
            for example in flashcard_examples
        ),
    )
    check(
        "collocation_per_pos",
        len(pos_rows) == len(expected_pos)
        and all(
            row.get("collocation_en") and THAI_RE.search(row.get("collocation_th", ""))
            for row in pos_rows
            if isinstance(row, dict)
        ),
    )

    forms = output.get("word_family_and_forms", [])
    actual_forms = {item.get("word") for item in forms if isinstance(item, dict)}
    check(
        "forms_source_faithful",
        actual_forms == source_forms
        and len(forms) == len(source_forms)
        and all(item.get("source") == "kaikki" for item in forms if isinstance(item, dict)),
        f"expected={sorted(source_forms)} actual={sorted(str(x) for x in actual_forms)}",
    )
    expected_form_pos: dict[str, set[str]] = {}
    for entry in entries:
        for form in entry.get("forms", []):
            expected_form_pos.setdefault(form["form"], set()).add(entry["pos"])
    actual_form_pos: dict[str, set[str]] = {}
    for item in forms:
        if not isinstance(item, dict):
            continue
        actual_form_pos.setdefault(item.get("word"), set()).update(
            str(item.get("pos", "")).split("|")
        )
    check(
        "form_pos_coverage",
        actual_form_pos == expected_form_pos,
        f"expected={expected_form_pos} actual={actual_form_pos}",
    )

    related = output.get("related_words", [])
    check(
        "three_sourced_related_words",
        len(related) == 3
        and len({item.get("word") for item in related if isinstance(item, dict)}) == 3
        and all(
            item.get("word") in source_related and item.get("source") == "datamuse"
            for item in related
            if isinstance(item, dict)
        ),
    )
    check(
        "related_words_explained",
        len(related) == 3
        and all(
            item.get("pos")
            and THAI_RE.search(item.get("meaning_th", ""))
            and THAI_RE.search(item.get("relation_keyword", ""))
            and len(item.get("relationship_th", "")) >= 12
            and THAI_RE.search(item.get("relationship_th", ""))
            for item in related
            if isinstance(item, dict)
        ),
    )
    source_related_pos = {
        item["word"]: {
            {"n": "noun", "v": "verb", "adj": "adj", "adv": "adv"}[tag]
            for tag in item.get("tags", [])
            if tag in {"n", "v", "adj", "adv"}
        }
        for item in source["datamuse"]
    }
    check(
        "related_pos_source_grounded",
        all(
            set(str(item.get("pos", "")).split("|"))
            <= source_related_pos.get(item.get("word"), set())
            for item in related
            if isinstance(item, dict)
        ),
    )

    cloze = output.get("cloze_examples", [])
    targets = {
        item.get("cloze_target") for item in cloze if isinstance(item, dict)
    }
    check("five_cloze_examples", len(cloze) == 5)
    check(
        "cloze_targets_verbatim",
        len(cloze) == 5
        and all(
            item.get("cloze_target")
            and item["cloze_target"] in item.get("en_text", "")
            for item in cloze
            if isinstance(item, dict)
        ),
    )
    check(
        "cloze_covers_pos_and_forms",
        {item.get("pos") for item in cloze if isinstance(item, dict)} == expected_pos
        and len(targets) >= 3
        and targets <= source_forms | {WORD},
        f"targets={sorted(str(x) for x in targets)}",
    )
    check(
        "rank1_emotional",
        any(item.get("rank") == 1 and item.get("is_emotional") is True for item in cloze if isinstance(item, dict)),
    )
    explanations = [
        item.get("explanation_th", "") for item in cloze if isinstance(item, dict)
    ]
    check(
        "independent_thai_explanations",
        len(explanations) == 5
        and all(THAI_RE.search(value) and len(value) >= 30 for value in explanations)
        and not any(term in value for value in explanations for term in FORBIDDEN_CROSS_SENTENCE_REFERENCES),
    )
    check(
        "cloze_pos_matches_own_explanation",
        all(
            not (
                (item.get("pos") == "noun" and "กริยา" in item.get("explanation_th", ""))
                or (item.get("pos") == "verb" and "คำนาม" in item.get("explanation_th", ""))
            )
            for item in cloze
            if isinstance(item, dict)
        ),
    )

    # Equal-weight deterministic score: 13 checks, normalized to 100.
    passed_count = sum(item["passed"] for item in checks)
    score = round(100 * passed_count / len(checks), 1)
    return {
        "passed": passed_count == len(checks),
        "score": score,
        "max_score": 100,
        "checks": checks,
    }


def run(model: str) -> Path:
    if model not in PRICES:
        raise SystemExit(f"Unsupported benchmark model: {model}")
    api_key = load_env(ROOT / ".env").get("API_KEY") or os.environ.get("API_KEY")
    if not api_key:
        raise SystemExit("No API_KEY found")

    source = source_record()
    prompt = PROMPT.replace(
        "{source_json}", json.dumps(source, ensure_ascii=False, indent=2)
    )
    client = genai.Client(api_key=api_key)
    started = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    latency_seconds = time.perf_counter() - started

    parse_error = None
    try:
        parsed = json.loads(response.text)
    except Exception as exc:  # preserve raw text so format failures are inspectable
        parsed = None
        parse_error = f"{type(exc).__name__}: {exc}"

    usage = response.usage_metadata
    prompt_tokens = int_value(usage, "prompt_token_count")
    candidate_tokens = int_value(usage, "candidates_token_count")
    thought_tokens = int_value(usage, "thoughts_token_count")
    output_billable_tokens = candidate_tokens + thought_tokens
    price = PRICES[model]
    cost_usd = (
        prompt_tokens * price["input"]
        + output_billable_tokens * price["output"]
    ) / 1_000_000
    cost_thb = cost_usd * USD_TO_THB

    result = {
        "model": model,
        "word": WORD,
        "run_type": "one_standard_synchronous_request",
        "temperature": 0.1,
        "latency_seconds": round(latency_seconds, 3),
        "usage": {
            "prompt_tokens": prompt_tokens,
            "candidate_tokens": candidate_tokens,
            "thought_tokens": thought_tokens,
            "billable_output_tokens": output_billable_tokens,
            "total_tokens_reported": int_value(usage, "total_token_count"),
        },
        "pricing": {
            "input_usd_per_1m": price["input"],
            "output_usd_per_1m_including_thinking": price["output"],
            "usd_to_thb": USD_TO_THB,
            "estimated_cost_usd": round(cost_usd, 8),
            "estimated_cost_thb": round(cost_thb, 6),
        },
        "parse_error": parse_error,
        "qc": validate(parsed, source) if parsed is not None else {
            "passed": False,
            "score": 0,
            "max_score": 100,
            "checks": [{"name": "valid_json", "passed": False, "detail": parse_error}],
        },
        "output": parsed,
        "raw_response": response.text if parsed is None else None,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{model}.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "model": model,
                "latency_seconds": result["latency_seconds"],
                "usage": result["usage"],
                "estimated_cost_thb": result["pricing"]["estimated_cost_thb"],
                "qc_score": result["qc"]["score"],
                "output_path": str(out_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return out_path


def rescore_existing() -> None:
    source = source_record()
    for out_path in sorted(OUT_DIR.glob("*.json")):
        result = json.loads(out_path.read_text(encoding="utf-8"))
        if result.get("word") != WORD or result.get("output") is None:
            continue
        result["qc"] = validate(result["output"], source)
        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{result['model']}: {result['qc']['score']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(PRICES))
    parser.add_argument("--rescore-existing", action="store_true")
    args = parser.parse_args()
    if args.rescore_existing:
        rescore_existing()
    elif args.model:
        run(args.model)
    else:
        parser.error("provide --model or --rescore-existing")
