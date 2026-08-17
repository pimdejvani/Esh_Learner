#!/usr/bin/env python3
"""Validate English cloze drafts and translate them to Thai without an LLM API.

The input may use the six-field English-only format in
``terra_english_format.md`` or the existing eight-field compact format.  For
eight-field input, existing Thai text is deliberately ignored so translations
can be regenerated.  Output always uses compact format v2 and is written to a
separate directory; source drafts and content databases are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "terra_english_drafts"
DEFAULT_OUTPUT = ROOT / "data" / "terra_translated_drafts"
# A machine without the 377 MB data lake (cloud session, CI runner) points this
# at the portable slice from tools/export_evidence_db.py instead.
SOURCE_DB = Path(os.environ.get("ESH_SOURCE_DB") or ROOT / "data" / "vocabulary_source.db")
DEFAULT_CACHE = ROOT / "data" / "translation_cache.db"
TEST_FILE_MARKERS = ("test", "hard30")
PLACEHOLDER_PATTERNS = (
    re.compile(r"\b(?:is|are|was|were) important\b", re.I),
    re.compile(r"\bthis (?:word|sentence)\b", re.I),
)


@dataclass(frozen=True)
class DraftSentence:
    rank: int
    sense_id: int
    pos: str
    target: str
    memorable: bool
    en_text: str


@dataclass(frozen=True)
class TranslationItem:
    text: str
    context: str


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without replacing process variables."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def parse_draft(path: Path) -> tuple[dict[str, list[DraftSentence]], list[str]]:
    entries: dict[str, list[DraftSentence]] = {}
    errors: list[str] = []
    headword: str | None = None
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("@ "):
            headword = raw[2:].strip().casefold()
            if not headword:
                errors.append(f"{path.name}:{number}: empty headword")
            else:
                entries.setdefault(headword, [])
            continue
        if headword is None:
            errors.append(f"{path.name}:{number}: row before headword")
            continue
        fields = raw.split("\t")
        if len(fields) not in (6, 8):
            errors.append(f"{path.name}:{number}: expected 6 or 8 tab-separated fields")
            continue
        rank, sense_id, pos, target, memorable, en_text = fields[:6]
        try:
            item = DraftSentence(
                rank=int(rank),
                sense_id=int(sense_id),
                pos=pos.strip(),
                target=target.strip(),
                memorable={"0": False, "1": True}[memorable],
                en_text=en_text.strip(),
            )
        except (ValueError, KeyError):
            errors.append(f"{path.name}:{number}: invalid rank/sense_id/memorable")
            continue
        entries[headword].append(item)
    return entries, errors


def target_occurs(target: str, sentence: str) -> bool:
    pattern = rf"(?<![A-Za-z]){re.escape(target)}(?![A-Za-z])"
    return bool(re.search(pattern, sentence, re.I))


def validate_entry(
    db: sqlite3.Connection, headword: str, rows: list[DraftSentence]
) -> tuple[list[str], dict[int, str]]:
    errors: list[str] = []
    glosses: dict[int, str] = {}
    word = db.execute(
        "SELECT id,headword FROM words WHERE lower(headword)=?", (headword,)
    ).fetchone()
    if word is None:
        return ["unknown headword"], glosses
    if len(rows) != 5:
        errors.append("must contain exactly 5 sentences")
    if sorted(row.rank for row in rows) != [1, 2, 3, 4, 5]:
        errors.append("ranks must be exactly 1..5")
    if len({row.en_text.casefold() for row in rows}) != len(rows):
        errors.append("English sentences must be unique")
    memorable = [row.rank for row in rows if row.memorable]
    if memorable != [1]:
        errors.append("only rank 1 must be marked memorable")

    allowed: dict[str, set[str]] = {}
    for sense in db.execute(
        "SELECT DISTINCT pos FROM source_senses WHERE word_id=?", (word["id"],)
    ):
        allowed.setdefault(sense["pos"], set()).add(word["headword"].casefold())
    for form in db.execute(
        "SELECT form_text,pos FROM source_forms WHERE word_id=?", (word["id"],)
    ):
        allowed.setdefault(form["pos"], set()).add(form["form_text"].casefold())

    for row in rows:
        sense = db.execute(
            "SELECT word_id,pos,gloss FROM source_senses WHERE id=?", (row.sense_id,)
        ).fetchone()
        if sense is None or sense["word_id"] != word["id"]:
            errors.append(f"rank {row.rank}: sense_id is not for this headword")
        elif sense["pos"] != row.pos:
            errors.append(f"rank {row.rank}: POS does not match sense_id")
        else:
            glosses[row.sense_id] = sense["gloss"]
        if row.target.casefold() not in allowed.get(row.pos, set()):
            errors.append(f"rank {row.rank}: unsupported target form")
        if not target_occurs(row.target, row.en_text):
            errors.append(f"rank {row.rank}: target is absent as a complete word")
        if any(pattern.search(row.en_text) for pattern in PLACEHOLDER_PATTERNS):
            errors.append(f"rank {row.rank}: placeholder sentence")
    return errors, glosses


class TranslationCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS translations (
            provider TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            text_hash TEXT NOT NULL,
            context_hash TEXT NOT NULL,
            source_text TEXT NOT NULL,
            context TEXT NOT NULL,
            translated_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(provider,source_lang,target_lang,text_hash,context_hash)
            )"""
        )
        self.db.commit()

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def get(self, provider: str, item: TranslationItem) -> str | None:
        row = self.db.execute(
            """SELECT translated_text FROM translations
            WHERE provider=? AND source_lang='en' AND target_lang='th'
              AND text_hash=? AND context_hash=?""",
            (provider, self._hash(item.text), self._hash(item.context)),
        ).fetchone()
        return row[0] if row else None

    def put(self, provider: str, item: TranslationItem, translated: str) -> None:
        self.db.execute(
            """INSERT OR REPLACE INTO translations VALUES
            (?,'en','th',?,?,?,?,?,?)""",
            (
                provider,
                self._hash(item.text),
                self._hash(item.context),
                item.text,
                item.context,
                translated,
                now(),
            ),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()


def post_json(url: str, headers: dict[str, str], payload: object) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise
        except urllib.error.URLError:
            pass
        if attempt < 2:
            time.sleep(2**attempt)
    raise RuntimeError(f"translation request failed after retries: {url}")


class AzureTranslator:
    name = "azure"

    def __init__(self) -> None:
        self.key = os.environ.get("AZURE_TRANSLATOR_KEY", "")
        self.region = os.environ.get("AZURE_TRANSLATOR_REGION", "")
        self.endpoint = os.environ.get(
            "AZURE_TRANSLATOR_ENDPOINT", "https://api.cognitive.microsofttranslator.com"
        ).rstrip("/")
        if not self.key:
            raise RuntimeError("AZURE_TRANSLATOR_KEY is missing")

    def translate(self, items: list[TranslationItem]) -> list[str]:
        url = self.endpoint + "/translate?" + urllib.parse.urlencode(
            {"api-version": "3.0", "from": "en", "to": "th"}
        )
        headers = {"Ocp-Apim-Subscription-Key": self.key}
        if self.region:
            headers["Ocp-Apim-Subscription-Region"] = self.region
        outputs: list[str] = []
        batch: list[TranslationItem] = []
        chars = 0

        def flush() -> None:
            nonlocal batch, chars
            if not batch:
                return
            result = post_json(url, headers, [{"Text": item.text} for item in batch])
            if not isinstance(result, list) or len(result) != len(batch):
                raise RuntimeError("Azure returned an unexpected response")
            outputs.extend(str(row["translations"][0]["text"]) for row in result)
            batch, chars = [], 0

        for item in items:
            if batch and (len(batch) >= 1000 or chars + len(item.text) > 45_000):
                flush()
            batch.append(item)
            chars += len(item.text)
        flush()
        return outputs


class DeepLTranslator:
    name = "deepl"

    def __init__(self) -> None:
        self.key = os.environ.get("DEEPL_AUTH_KEY", "")
        if not self.key:
            raise RuntimeError("DEEPL_AUTH_KEY is missing")
        self.endpoint = os.environ.get(
            "DEEPL_ENDPOINT", "https://api-free.deepl.com/v2/translate"
        )

    def translate(self, items: list[TranslationItem]) -> list[str]:
        outputs: list[str] = []
        headers = {"Authorization": f"DeepL-Auth-Key {self.key}"}
        # Context differs per sentence, so each fallback request is isolated.
        for item in items:
            result = post_json(
                self.endpoint,
                headers,
                {
                    "text": [item.text],
                    "source_lang": "EN",
                    "target_lang": "TH",
                    "context": item.context,
                },
            )
            outputs.append(str(result["translations"][0]["text"]))
        return outputs


def provider(name: str):
    if name == "azure":
        return AzureTranslator()
    if name == "deepl":
        return DeepLTranslator()
    raise ValueError(f"unknown provider: {name}")


def translate_with_fallback(
    items: list[TranslationItem], order: list[str], cache: TranslationCache
) -> tuple[list[str], dict[str, int]]:
    results: list[str | None] = [None] * len(items)
    usage: dict[str, int] = {}
    for provider_name in order:
        pending: list[int] = []
        for index, item in enumerate(items):
            if results[index] is not None:
                continue
            cached = cache.get(provider_name, item)
            if cached is not None:
                results[index] = cached
                usage[provider_name + "_cache"] = usage.get(provider_name + "_cache", 0) + 1
            else:
                pending.append(index)
        if not pending:
            break
        try:
            engine = provider(provider_name)
            translated = engine.translate([items[index] for index in pending])
            if len(translated) != len(pending):
                raise RuntimeError("translation count mismatch")
            for index, value in zip(pending, translated, strict=True):
                value = value.strip()
                if not value or not re.search(r"[ก-๙]", value):
                    raise RuntimeError(f"{provider_name} returned non-Thai output")
                results[index] = value
                cache.put(provider_name, items[index], value)
                usage[provider_name] = usage.get(provider_name, 0) + 1
        except Exception as exc:  # provider failure must allow the next fallback
            print(f"provider {provider_name} unavailable: {exc}", file=sys.stderr)
    missing = [i for i, value in enumerate(results) if value is None]
    if missing:
        raise RuntimeError(f"no translation provider completed {len(missing)} text items")
    return [str(value) for value in results], usage


def explanation_en(headword: str, row: DraftSentence, gloss: str) -> str:
    return (
        f'In this sentence, "{row.target}" is used as {row.pos} for the headword '
        f'"{headword}" and expresses this dictionary sense: {gloss}'
    )


def translation_items(
    headword: str, rows: list[DraftSentence], glosses: dict[int, str]
) -> list[TranslationItem]:
    items: list[TranslationItem] = []
    for row in sorted(rows, key=lambda value: value.rank):
        gloss = glosses[row.sense_id]
        context = f"Headword: {headword}. Part of speech: {row.pos}. Dictionary sense: {gloss}"
        items.append(TranslationItem(row.en_text, context))
        items.append(TranslationItem(explanation_en(headword, row, gloss), context))
    return items


def render_entry(
    headword: str, rows: list[DraftSentence], translations: list[str]
) -> str:
    lines = [f"@ {headword}"]
    ordered = sorted(rows, key=lambda value: value.rank)
    for index, row in enumerate(ordered):
        thai_sentence = translations[index * 2]
        thai_explanation = translations[index * 2 + 1]
        fields = (
            str(row.rank),
            str(row.sense_id),
            row.pos,
            row.target,
            "1" if row.memorable else "0",
            row.en_text,
            thai_sentence,
            thai_explanation,
        )
        lines.append("\t".join(fields))
    return "\n".join(lines)


def iter_files(directory: Path, include_test: bool) -> Iterable[Path]:
    for path in sorted(directory.glob("*.txt")):
        if not include_test and any(marker in path.name.casefold() for marker in TEST_FILE_MARKERS):
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--providers", default="azure,deepl")
    parser.add_argument("--limit-words", type=int, default=0)
    parser.add_argument(
        "--headwords",
        default="",
        help="comma-separated headwords to translate (useful for a small test run)",
    )
    parser.add_argument("--include-test", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    provider_order = [value.strip().casefold() for value in args.providers.split(",") if value.strip()]
    if not provider_order:
        parser.error("--providers must not be empty")
    selected_headwords = {
        value.strip().casefold() for value in args.headwords.split(",") if value.strip()
    }

    source = sqlite3.connect(f"file:{SOURCE_DB.as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    valid: list[tuple[Path, str, list[DraftSentence], dict[int, str]]] = []
    parse_errors: list[str] = []
    validation_errors: list[str] = []
    for path in iter_files(args.input_dir, args.include_test):
        entries, errors = parse_draft(path)
        parse_errors.extend(errors)
        for headword, rows in entries.items():
            if selected_headwords and headword not in selected_headwords:
                continue
            errors, glosses = validate_entry(source, headword, rows)
            if errors:
                validation_errors.extend(f"{path.name}:{headword}: {error}" for error in errors)
            else:
                valid.append((path, headword, rows, glosses))
    source.close()
    if selected_headwords:
        missing = selected_headwords - {headword for _, headword, _, _ in valid}
        if missing:
            parser.error(f"headwords not found or invalid: {', '.join(sorted(missing))}")
    if args.limit_words:
        valid = valid[: args.limit_words]

    text_items = sum((translation_items(headword, rows, glosses) for _, headword, rows, glosses in valid), [])
    print(
        f"files={len(list(iter_files(args.input_dir, args.include_test)))} "
        f"valid_words={len(valid)} invalid={len(validation_errors)} parse_errors={len(parse_errors)} "
        f"texts={len(text_items)} chars={sum(len(item.text) for item in text_items)}"
    )
    for error in (parse_errors + validation_errors)[:50]:
        print(error, file=sys.stderr)
    if len(parse_errors) + len(validation_errors) > 50:
        print(f"... {len(parse_errors) + len(validation_errors) - 50} more errors", file=sys.stderr)
    if args.dry_run:
        return 1 if parse_errors else 0

    cache = TranslationCache(args.cache)
    rendered_by_file: dict[Path, list[str]] = {}
    usage_total: dict[str, int] = {}
    try:
        for path, headword, rows, glosses in valid:
            items = translation_items(headword, rows, glosses)
            translated, usage = translate_with_fallback(items, provider_order, cache)
            rendered_by_file.setdefault(path, []).append(render_entry(headword, rows, translated))
            for key, value in usage.items():
                usage_total[key] = usage_total.get(key, 0) + value
    finally:
        cache.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for source_path, blocks in rendered_by_file.items():
        (args.output_dir / source_path.name).write_text("\n".join(blocks) + "\n", encoding="utf-8")
    print(f"wrote_words={len(valid)} output={args.output_dir} usage={usage_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
