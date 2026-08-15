# -*- coding: utf-8 -*-
"""Source-first dictionary-entry merge probe for three user-selected words.

This is intentionally isolated from the production DB.  It proves whether a
rerunnable pipeline can create the proposed flashcard payload without a human
copying and formatting dictionary entries.

Sources:
  * Kaikki/Wiktextract (English Wiktionary): POS, glosses, forms, derived terms,
    related terms, IPA and source examples.
  * wiktapi.dev (English Wiktionary): Thai translation candidates.
  * Tatoeba: short licensed example sentences when available.
  * Datamuse: ranked related-word candidates (advisory, not definitions).
  * Gemini: constrained Thai rendering and fallback example creation only;
    it may not invent lexical structure, forms, families, or source claims.

Usage: python tools/dictionary_merge_probe.py
Output: tools/dictionary_probe_results/merged_entries.json
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "tools" / "dictionary_probe_results"
WORDS = ("capricious", "Capricorn", "capriole")
KAIKKI_URLS = {
    "capricious": "https://kaikki.org/dictionary/English/meaning/c/ca/capricious.jsonl",
    "Capricorn": "https://kaikki.org/dictionary/English/meaning/C/Ca/Capricorn.jsonl",
    "capriole": "https://kaikki.org/dictionary/English/meaning/c/ca/capriole.jsonl",
}
ALLOWED_POS = {"adj", "adv", "noun", "verb", "name"}
THAI_RE = re.compile(r"[\u0E00-\u0E7F]")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_json(url: str):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Esh-Learner-dictionary-probe/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def get_jsonl(url: str) -> list[dict]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Esh-Learner-dictionary-probe/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return [
            json.loads(line)
            for line in response.read().decode("utf-8").splitlines()
            if line.strip()
        ]


def unique(items):
    seen = set()
    return [item for item in items if item and not (item in seen or seen.add(item))]


def extract_kaikki(word: str) -> dict:
    entries = []
    for raw in get_jsonl(KAIKKI_URLS[word]):
        if raw.get("word") != word or raw.get("lang_code") != "en":
            continue
        pos = raw.get("pos")
        if pos not in ALLOWED_POS:
            continue
        senses = []
        for sense in raw.get("senses", []):
            glosses = sense.get("glosses") or []
            if not glosses:
                continue
            senses.append(
                {
                    "english_gloss": glosses[-1],
                    "tags": sense.get("tags") or [],
                }
            )
        if not senses:
            continue
        family_stem = word.lower()[: min(6, len(word))]
        derived = unique(item.get("word") for item in raw.get("derived", []))
        # Wiktionary's "derived" section can include compounds and phrases
        # (for example "Tropic of Capricorn").  The requested flashcard
        # section is morphological word family, so expose only direct-looking
        # single-token derivatives to the renderer.
        direct_family = [
            term
            for term in derived
            if " " not in term and term.lower().startswith(family_stem)
        ]
        entries.append(
            {
                "pos": pos,
                "senses": senses,
                "forms": [
                    {"form": form.get("form"), "tags": form.get("tags") or []}
                    for form in raw.get("forms", [])
                    if form.get("form") and "symbol" not in (form.get("tags") or [])
                ],
                "derived": direct_family,
                "related": unique(
                    item.get("word") for item in raw.get("related", [])
                ),
                "ipa": next(
                    (sound.get("ipa") for sound in raw.get("sounds", []) if sound.get("ipa")),
                    None,
                ),
            }
        )
    return {"entries": entries, "source": KAIKKI_URLS[word]}


def extract_thai_translations(word: str) -> list[dict]:
    url_word = urllib.parse.quote(word, safe="")
    data = get_json(
        f"https://api.wiktapi.dev/v1/en/word/{url_word}/translations"
    )
    result = []
    for group in data.get("translations", []):
        if group.get("lang_code") != "en":
            continue
        for item in group.get("translations", []):
            if item.get("code") == "th" and item.get("word"):
                result.append(
                    {
                        "pos": group.get("pos"),
                        "sense": item.get("sense"),
                        "thai": item.get("word"),
                    }
                )
    return result


def extract_tatoeba(word: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "lang": "eng",
            "q": word,
            "sort": "relevance",
            "limit": 10,
            "showtrans": "all",
        }
    )
    data = get_json(f"https://api.tatoeba.org/v1/sentences?{params}")
    exact = re.compile(rf"\b{re.escape(word)}(?:s|ed|ing)?\b", re.IGNORECASE)
    result = []
    for item in data.get("data", []):
        text = item.get("text", "")
        if not exact.search(text) or not 2 <= len(text.split()) <= 18:
            continue
        result.append(
            {
                "text": text,
                "id": item.get("id"),
                "license": item.get("license"),
                "owner": item.get("owner"),
            }
        )
    return result


def extract_datamuse(word: str) -> list[dict]:
    params = urllib.parse.urlencode({"ml": word, "md": "p", "max": 12})
    data = get_json(f"https://api.datamuse.com/words?{params}")
    return [
        {"word": item.get("word"), "score": item.get("score"), "tags": item.get("tags", [])}
        for item in data
        if item.get("word") and item.get("word").lower() != word.lower()
    ]


PROMPT = """You are a Thai lexicographic renderer. Convert the SOURCE JSON below into the exact output schema. Do not add lexical facts.

Rules:
1. One output object per input word, same order.
2. Thai meanings must be short dictionary bullets, normally 2-8 Thai words. Preserve separate source senses and POS. Remove only senses tagged archaic/obsolete or clearly unsuitable for modern learners.
3. If a matching wiktapi Thai candidate exists, prefer its wording. Otherwise translate the supplied English Wiktionary gloss faithfully and set meaning_origin to "model_translation_of_wiktionary_gloss". source_gloss MUST be copied character-for-character from one supplied Kaikki english_gloss, even when the Thai wording comes from wiktapi.
4. word_family_and_forms may contain ONLY supplied Kaikki forms and derived terms. A derived term that changes POS must have its own POS and a short Thai meaning based on its morphology plus the supplied headword senses. Never invent a family member.
5. related_words: choose at most 3 semantically useful learner-facing items from supplied Kaikki or Datamuse candidates. Semantic usefulness is more important than source order; reject merely etymological neighbours. Do not include symbols. Thai explanations must be short.
6. Choose one supplied Tatoeba sentence if it clearly demonstrates a listed modern sense. Otherwise create one short example strictly demonstrating a supplied sense and mark source as "generated_from_sense". Translate it naturally into Thai.
7. thai_reading is a Thai-script rendering of supplied IPA. Use hyphens between syllables and provide a 1-based stress_index.
8. Never output symbol metadata. Return JSON only.

Schema:
[
  {
    "headword": "...",
    "thai_reading": "...",
    "stress_index": 1,
    "parts_of_speech": [
      {"pos": "adj", "meanings": [{"thai": "...", "meaning_origin": "wiktapi|model_translation_of_wiktionary_gloss", "source_gloss": "..."}]}
    ],
    "word_family_and_forms": [
      {"word": "...", "kind": "inflection|derived", "pos": "...", "thai": "...", "source": "kaikki"}
    ],
    "related_words": [
      {"word": "...", "thai": "...", "source": "kaikki|datamuse"}
    ],
    "example": {"en": "...", "th": "...", "source": "tatoeba:<id>|generated_from_sense", "license": "...|generated"}
  }
]

SOURCE JSON:
{source_json}
"""


def render_with_model(source_records: list[dict]) -> list[dict]:
    key = load_env(ROOT / ".env").get("API_KEY") or os.environ.get("API_KEY")
    if not key:
        raise RuntimeError("No API_KEY in .env")
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=PROMPT.replace(
            "{source_json}",
            json.dumps(source_records, ensure_ascii=False, indent=2),
        ),
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


def validate(source_records: list[dict], rendered: list[dict]) -> list[str]:
    errors = []
    source_by_word = {item["headword"]: item for item in source_records}
    rendered_by_word = {item.get("headword"): item for item in rendered}
    if set(rendered_by_word) != set(source_by_word):
        errors.append("headword set/order mismatch")
    for word, item in rendered_by_word.items():
        source = source_by_word.get(word)
        if not source:
            continue
        source_forms = {
            form["form"]
            for entry in source["kaikki"]["entries"]
            for form in entry["forms"]
        }
        source_derived = {
            term
            for entry in source["kaikki"]["entries"]
            for term in entry["derived"]
        }
        for family in item.get("word_family_and_forms", []):
            value = family.get("word")
            if value not in source_forms | source_derived:
                errors.append(f"{word}: invented family/form {value!r}")
        allowed_related = {
            term
            for entry in source["kaikki"]["entries"]
            for term in entry["related"]
        } | {term["word"] for term in source["datamuse"]}
        for related in item.get("related_words", []):
            if related.get("word") not in allowed_related:
                errors.append(f"{word}: invented related word {related.get('word')!r}")
        if not item.get("parts_of_speech"):
            errors.append(f"{word}: no POS groups")
        for group in item.get("parts_of_speech", []):
            for meaning in group.get("meanings", []):
                thai = meaning.get("thai", "")
                if not THAI_RE.search(thai):
                    errors.append(f"{word}: non-Thai meaning {thai!r}")
                if len(thai.split()) > 12:
                    errors.append(f"{word}: meaning too long {thai!r}")
                glosses = {
                    sense["english_gloss"]
                    for entry in source["kaikki"]["entries"]
                    for sense in entry["senses"]
                }
                if meaning.get("source_gloss") not in glosses:
                    errors.append(f"{word}: meaning not linked to an exact source gloss")
        example = item.get("example", {})
        if not example.get("en") or not THAI_RE.search(example.get("th", "")):
            errors.append(f"{word}: invalid example")
        source_label = example.get("source", "")
        if source_label.startswith("tatoeba:"):
            allowed_ids = {str(s["id"]) for s in source["tatoeba"]}
            if source_label.split(":", 1)[1] not in allowed_ids:
                errors.append(f"{word}: unknown Tatoeba example id")
    return errors


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for word in WORDS:
        print(f"Fetching structured sources for {word}...", flush=True)
        records.append(
            {
                "headword": word,
                "kaikki": extract_kaikki(word),
                "wiktapi_thai": extract_thai_translations(word),
                "tatoeba": extract_tatoeba(word),
                "datamuse": extract_datamuse(word),
            }
        )
    (OUT_DIR / "source_records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Rendering source records into flashcard schema...", flush=True)
    rendered = render_with_model(records)
    errors = validate(records, rendered)
    result = {
        "entries": rendered,
        "validation": {"passed": not errors, "errors": errors},
    }
    (OUT_DIR / "merged_entries.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
