#!/usr/bin/env python3
"""Generate missing production Thai word readings and short sense meanings.

Existing authored rows are copied to a caller-owned staging directory and are
never sent to the model or changed.  Accepted model output is checkpointed after
every batch so an interrupted run can resume without paying for completed work.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import translate_vocab_content as drafts  # noqa: E402


MODEL = "gemini-2.5-flash-lite"
REPAIR_MODEL = "gemini-2.5-flash"
GENERATION_SOURCE = f"{MODEL}+{REPAIR_MODEL}-repair"
THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
WORD_HEADER = "headword|thai_reading|stress_index|reading_source"
SENSE_HEADER = "source_sense_id|headword|pos|meaning_th|meaning_source"


@dataclass(frozen=True)
class ReadingItem:
    headword: str
    ipa: str


@dataclass(frozen=True)
class SenseItem:
    source_sense_id: int
    headword: str
    pos: str
    gloss: str
    thai_candidates: tuple[str, ...]


def pipe_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {key: (value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(
                (line for line in handle if not line.startswith("#")), delimiter="|"
            )
        ]


def load_reviewed_corpus(directory: Path) -> tuple[set[str], set[int]]:
    headwords: set[str] = set()
    sense_ids: set[int] = set()
    for path in sorted(directory.glob("*.txt")):
        entries, errors = drafts.parse_draft(path)
        if errors:
            raise ValueError(f"{path}: {errors[0]}")
        for headword, rows in entries.items():
            key = headword.casefold()
            if key in headwords:
                raise ValueError(f"duplicate reviewed headword: {headword}")
            if len(rows) != 5:
                raise ValueError(f"{headword}: expected 5 reviewed sentences, got {len(rows)}")
            headwords.add(key)
            sense_ids.update(row.sense_id for row in rows)
    if not headwords:
        raise ValueError(f"no reviewed drafts found in {directory}")
    return headwords, sense_ids


def source_items(
    db_path: Path, headwords: set[str], sense_ids: set[int]
) -> tuple[dict[str, ReadingItem], dict[int, SenseItem]]:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in headwords)
        words = {
            row["headword"].casefold(): row
            for row in db.execute(
                f"SELECT id,headword FROM words WHERE lower(headword) IN ({placeholders})",
                tuple(sorted(headwords)),
            )
        }
        missing_words = sorted(headwords - set(words))
        if missing_words:
            raise ValueError(f"source DB missing words: {', '.join(missing_words[:10])}")

        readings: dict[str, ReadingItem] = {}
        for key, word in words.items():
            pronunciation = db.execute(
                "SELECT ipa FROM source_pronunciations WHERE word_id=? "
                "AND trim(ipa) != '' ORDER BY id LIMIT 1",
                (word["id"],),
            ).fetchone()
            readings[key] = ReadingItem(word["headword"], pronunciation["ipa"] if pronunciation else "")

        senses: dict[int, SenseItem] = {}
        for sense_id in sorted(sense_ids):
            sense = db.execute(
                "SELECT s.id,s.word_id,s.pos,s.gloss,w.headword FROM source_senses s "
                "JOIN words w ON w.id=s.word_id WHERE s.id=?",
                (sense_id,),
            ).fetchone()
            if sense is None or sense["headword"].casefold() not in headwords:
                raise ValueError(f"source DB missing or mismatched sense: {sense_id}")
            candidates: list[str] = []
            for row in db.execute(
                "SELECT translation FROM source_translations WHERE word_id=? "
                "AND pos=? AND language_code='th' ORDER BY id",
                (sense["word_id"], sense["pos"]),
            ):
                candidate = row["translation"].strip()
                if THAI_RE.search(candidate) and candidate not in candidates:
                    candidates.append(candidate)
            senses[sense_id] = SenseItem(
                sense_id,
                sense["headword"],
                sense["pos"],
                sense["gloss"],
                tuple(candidates[:20]),
            )
        return readings, senses
    finally:
        db.close()


def validate_reading(reading: str, stress_index: object) -> tuple[str, int]:
    reading = str(reading).strip()
    if "|" in reading or "\n" in reading or "\r" in reading:
        raise ValueError("thai_reading contains a file delimiter or newline")
    if not reading or not THAI_RE.search(reading):
        raise ValueError("thai_reading must contain Thai script")
    if re.search(r"[A-Za-z]", reading):
        raise ValueError("thai_reading must not contain Latin letters")
    syllables = [part.strip() for part in reading.split("-") if part.strip()]
    try:
        stress = int(stress_index)
    except (TypeError, ValueError) as exc:
        raise ValueError("stress_index must be an integer") from exc
    if not 1 <= stress <= len(syllables):
        raise ValueError(f"stress_index {stress} outside 1..{len(syllables)}")
    return reading, stress


def validate_meaning(meaning: str) -> str:
    meaning = str(meaning).strip()
    if "|" in meaning or "\n" in meaning or "\r" in meaning:
        raise ValueError("meaning_th contains a file delimiter or newline")
    if not meaning or not THAI_RE.search(meaning):
        raise ValueError("meaning_th must contain Thai script")
    if len(meaning) > 42:
        raise ValueError(f"meaning_th exceeds 42 characters: {meaning}")
    return meaning


def load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {"model": MODEL, "readings": {}, "senses": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("model") != MODEL:
        raise ValueError(f"checkpoint model is not {MODEL}")
    if not isinstance(data.get("readings"), dict) or not isinstance(data.get("senses"), dict):
        raise ValueError("invalid metadata checkpoint")
    return data


def save_checkpoint(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def request_payload(
    readings: list[ReadingItem],
    senses: list[SenseItem],
    reserved: dict[tuple[str, str], set[str]],
) -> dict:
    return {
        "readings": [
            {"headword": item.headword, "source_ipa": item.ipa or "(ไม่มี IPA ในแหล่งข้อมูล)"}
            for item in readings
        ],
        "senses": [
            {
                "source_sense_id": item.source_sense_id,
                "headword": item.headword,
                "pos": item.pos,
                "source_gloss_en": item.gloss,
                "source_thai_candidates": list(item.thai_candidates),
                "meanings_already_used_for_same_word_pos": sorted(
                    reserved.get((item.headword.casefold(), item.pos), set())
                ),
            }
            for item in senses
        ],
    }


def prompt_for(payload: dict) -> str:
    return """คุณกำลังเติม metadata สำหรับพจนานุกรมอังกฤษของผู้เรียนไทย
ตอบ JSON เท่านั้นในรูป {\"readings\": [...], \"senses\": [...]} และคืนทุกรายการที่รับมา exactly once

readings: คืน headword, thai_reading, stress_index โดยถอดเสียงอังกฤษเป็นอักษรไทย แบ่งพยางค์ด้วย - และใช้ source_ipa เป็นหลัก stress_index เริ่มที่ 1
senses: คืน source_sense_id, meaning_th โดยแปล source_gloss_en ให้ตรง sense และสั้นไม่เกิน 42 ตัวอักษร ใช้ candidate ได้เมื่อความหมายตรง ห้ามให้ meaning ซ้ำกันใน headword+pos เดียวกัน
ถ้า input array ใดว่าง output array นั้นต้องว่าง ห้ามสร้างรายการเพิ่มเอง
ห้ามเพิ่มคำอธิบาย ห้ามใช้อักษรละตินใน thai_reading

INPUT_JSON:
""" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class GeminiGenerator:
    def __init__(self, api_key: str):
        from google import genai
        from google.genai import types

        self.client = genai.Client(api_key=api_key)
        self.config = types.GenerateContentConfig(
            response_mime_type="application/json", temperature=0.1
        )

    def __call__(self, payload: dict) -> dict:
        model = REPAIR_MODEL if payload.get("correction_required") else MODEL
        response = self.client.models.generate_content(
            model=model, contents=prompt_for(payload), config=self.config
        )
        text = FENCE_RE.sub("", response.text.strip())
        # The API occasionally appends a second complete JSON value despite
        # response_mime_type.  Decode the first value and let exact-set
        # validation below prove that it contains the whole requested batch.
        value, _end = json.JSONDecoder().raw_decode(text)
        return value


def accept_response(
    response: dict,
    readings: list[ReadingItem],
    senses: list[SenseItem],
    reserved: dict[tuple[str, str], set[str]],
) -> tuple[dict[str, dict], dict[str, dict]]:
    reading_rows = response.get("readings") if isinstance(response, dict) else None
    sense_rows = response.get("senses") if isinstance(response, dict) else None
    if not isinstance(reading_rows, list) or not isinstance(sense_rows, list):
        raise ValueError("response must contain readings and senses arrays")

    expected_readings = {item.headword.casefold(): item for item in readings}
    # Some JSON models helpfully invent entries for an empty sibling array.
    # There is nothing to accept in that case, so ignore only that irrelevant
    # array while keeping exact-set validation whenever work was requested.
    if not expected_readings:
        reading_rows = []
    accepted_readings: dict[str, dict] = {}
    for row in reading_rows:
        key = str(row.get("headword", "")).casefold()
        if key not in expected_readings or key in accepted_readings:
            raise ValueError(f"unexpected or duplicate reading: {key}")
        raw_reading = str(row.get("thai_reading", "")).strip()
        raw_stress = row.get("stress_index")
        # If the model writes fewer hyphen-delimited syllables than it counted,
        # its index is structurally impossible.  Clamp only this upper-bound
        # mismatch; the resulting index identifies the final written syllable.
        # Other malformed values still fail the strict validator.
        syllable_count = len([part for part in raw_reading.split("-") if part.strip()])
        try:
            numeric_stress = int(raw_stress)
        except (TypeError, ValueError):
            numeric_stress = raw_stress
        if syllable_count and isinstance(numeric_stress, int) and numeric_stress > syllable_count:
            numeric_stress = syllable_count
        reading, stress = validate_reading(raw_reading, numeric_stress)
        accepted_readings[key] = {"thai_reading": reading, "stress_index": stress}
    if set(accepted_readings) != set(expected_readings):
        raise ValueError("response omitted one or more readings")

    expected_senses = {str(item.source_sense_id): item for item in senses}
    if not expected_senses:
        sense_rows = []
    accepted_senses: dict[str, dict] = {}
    batch_used = {key: set(values) for key, values in reserved.items()}
    for row in sense_rows:
        key = str(row.get("source_sense_id", ""))
        if key not in expected_senses or key in accepted_senses:
            raise ValueError(f"unexpected or duplicate sense: {key}")
        item = expected_senses[key]
        meaning = validate_meaning(row.get("meaning_th", ""))
        group = (item.headword.casefold(), item.pos)
        if meaning in batch_used.setdefault(group, set()):
            raise ValueError(f"duplicate meaning for {item.headword}/{item.pos}: {meaning}")
        batch_used[group].add(meaning)
        accepted_senses[key] = {"meaning_th": meaning}
    if set(accepted_senses) != set(expected_senses):
        raise ValueError("response omitted one or more senses")
    return accepted_readings, accepted_senses


def copy_canonical(canonical_dir: Path, staging_dir: Path) -> None:
    if staging_dir.resolve() == canonical_dir.resolve():
        raise ValueError("--thai-dir must not be the canonical data/content_th directory")
    staging_dir.mkdir(parents=True, exist_ok=True)
    for source in canonical_dir.iterdir():
        if source.is_file():
            destination = staging_dir / source.name
            if not destination.exists():
                shutil.copy2(source, destination)


def append_rows(path: Path, header: str, rows: list[str]) -> None:
    if not rows:
        return
    original = path.read_text(encoding="utf-8") if path.exists() else header + "\n"
    if not original.endswith("\n"):
        original += "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(original + "\n".join(rows) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def complete(
    readings: dict[str, ReadingItem],
    senses: dict[int, SenseItem],
    staging_dir: Path,
    generator: Callable[[dict], dict],
    *,
    batch_size: int = 40,
    retries: int = 3,
) -> tuple[int, int]:
    word_path = staging_dir / "words_th.txt"
    sense_path = staging_dir / "senses_th.txt"
    existing_words = {row["headword"].casefold(): row for row in pipe_rows(word_path)}
    existing_senses = {int(row["source_sense_id"]): row for row in pipe_rows(sense_path)}
    checkpoint_path = staging_dir / ".thai_metadata_checkpoint.json"
    checkpoint = load_checkpoint(checkpoint_path)

    for key, row in existing_words.items():
        validate_reading(row.get("thai_reading", ""), row.get("stress_index"))
    reserved: dict[tuple[str, str], set[str]] = {}
    for row in existing_senses.values():
        meaning = validate_meaning(row.get("meaning_th", ""))
        group = (row["headword"].casefold(), row["pos"])
        if meaning in reserved.setdefault(group, set()):
            raise ValueError(f"existing duplicate meaning for {group}: {meaning}")
        reserved[group].add(meaning)
    for key, row in checkpoint["readings"].items():
        if key in readings:
            reading, stress = validate_reading(
                row.get("thai_reading", ""), row.get("stress_index")
            )
            if key in existing_words:
                current = validate_reading(
                    existing_words[key].get("thai_reading", ""),
                    existing_words[key].get("stress_index"),
                )
                if (reading, stress) != current:
                    raise ValueError(f"checkpoint conflicts with staged reading: {key}")
    for sense_id, row in checkpoint["senses"].items():
        item = senses.get(int(sense_id))
        if item is None:
            continue
        meaning = validate_meaning(row.get("meaning_th", ""))
        numeric_id = int(sense_id)
        if numeric_id in existing_senses:
            if meaning != existing_senses[numeric_id]["meaning_th"]:
                raise ValueError(f"checkpoint conflicts with staged sense: {sense_id}")
            continue
        group = (item.headword.casefold(), item.pos)
        if meaning in reserved.setdefault(group, set()):
            raise ValueError(f"checkpoint duplicate meaning for {item.headword}/{item.pos}: {meaning}")
        reserved[group].add(meaning)

    pending_readings = [
        item for key, item in sorted(readings.items())
        if key not in existing_words and key not in checkpoint["readings"]
    ]
    pending_senses = [
        item for sense_id, item in sorted(senses.items())
        if sense_id not in existing_senses and str(sense_id) not in checkpoint["senses"]
    ]
    work: list[tuple[str, object]] = (
        [("reading", item) for item in pending_readings]
        + [("sense", item) for item in pending_senses]
    )
    if batch_size < 1 or retries < 1:
        raise ValueError("batch_size and retries must be positive")

    def process_batch(batch: list[tuple[str, object]], label: str) -> None:
        reading_batch = [item for kind, item in batch if kind == "reading"]
        sense_batch = [item for kind, item in batch if kind == "sense"]
        payload = request_payload(reading_batch, sense_batch, reserved)
        error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                accepted_readings, accepted_senses = accept_response(
                    generator(payload), reading_batch, sense_batch, reserved
                )
                break
            except Exception as exc:  # API, JSON and validation errors are retryable.
                error = exc
                if attempt < retries:
                    # Give the model the concrete validator failure; retrying an
                    # identical deterministic prompt tends to reproduce the same
                    # malformed stress index or duplicate meaning forever.
                    payload["correction_required"] = (
                        f"คำตอบก่อนหน้าไม่ผ่าน validation: {exc}. "
                        "สร้างผลลัพธ์ใหม่ทั้ง batch และแก้ข้อผิดพลาดนี้"
                    )
                    time.sleep(min(2 ** (attempt - 1), 4))
        else:
            # Same-word senses can be genuinely close.  Splitting lets each
            # accepted meaning enter `reserved` before the next sense is asked,
            # so the model receives the exact wording it must distinguish from.
            if len(batch) > 1:
                middle = len(batch) // 2
                process_batch(batch[:middle], f"{label}a")
                process_batch(batch[middle:], f"{label}b")
                return
            raise RuntimeError(
                f"metadata batch {label} failed after {retries} attempts: {error}"
            ) from error
        checkpoint["readings"].update(accepted_readings)
        checkpoint["senses"].update(accepted_senses)
        for sense_id, row in accepted_senses.items():
            item = senses[int(sense_id)]
            reserved.setdefault((item.headword.casefold(), item.pos), set()).add(row["meaning_th"])
        save_checkpoint(checkpoint_path, checkpoint)

    for offset in range(0, len(work), batch_size):
        batch = work[offset : offset + batch_size]
        process_batch(batch, str(offset // batch_size + 1))
        print(
            f"batch={offset // batch_size + 1}/{(len(work) + batch_size - 1) // batch_size} "
            f"checkpoint_readings={len(checkpoint['readings'])} "
            f"checkpoint_senses={len(checkpoint['senses'])}",
            flush=True,
        )

    new_word_rows: list[str] = []
    for key, item in sorted(readings.items()):
        if key in existing_words:
            continue
        row = checkpoint["readings"].get(key)
        if row is None:
            raise ValueError(f"missing generated reading: {item.headword}")
        reading, stress = validate_reading(row["thai_reading"], row["stress_index"])
        new_word_rows.append(f"{item.headword}|{reading}|{stress}|{GENERATION_SOURCE}")
    new_sense_rows: list[str] = []
    final_used = {key: set(values) for key, values in reserved.items()}
    # Remove checkpoint meanings from the duplicate set; add them once below in ID order.
    for sense_id, row in checkpoint["senses"].items():
        item = senses.get(int(sense_id))
        if item:
            final_used.setdefault((item.headword.casefold(), item.pos), set()).discard(row["meaning_th"])
    for sense_id, item in sorted(senses.items()):
        if sense_id in existing_senses:
            continue
        row = checkpoint["senses"].get(str(sense_id))
        if row is None:
            raise ValueError(f"missing generated sense: {sense_id}")
        meaning = validate_meaning(row["meaning_th"])
        group = (item.headword.casefold(), item.pos)
        if meaning in final_used.setdefault(group, set()):
            raise ValueError(f"duplicate final meaning for {item.headword}/{item.pos}: {meaning}")
        final_used[group].add(meaning)
        new_sense_rows.append(
            f"{sense_id}|{item.headword}|{item.pos}|{meaning}|{GENERATION_SOURCE}"
        )
    append_rows(word_path, WORD_HEADER, new_word_rows)
    append_rows(sense_path, SENSE_HEADER, new_sense_rows)

    final_words = {row["headword"].casefold(): row for row in pipe_rows(word_path)}
    final_senses = {int(row["source_sense_id"]): row for row in pipe_rows(sense_path)}
    missing_words = set(readings) - set(final_words)
    missing_senses = set(senses) - set(final_senses)
    if missing_words or missing_senses:
        raise ValueError(
            f"incomplete staged metadata: words={len(missing_words)} senses={len(missing_senses)}"
        )
    return len(new_word_rows), len(new_sense_rows)


def load_api_key() -> str:
    value = os.environ.get("GEMINI_API_KEY") or os.environ.get("API_KEY")
    env_path = ROOT / ".env"
    if not value and env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line.strip().startswith(("GEMINI_API_KEY=", "API_KEY=")):
                continue
            value = line.split("=", 1)[1].strip().strip("\"'")
            if value:
                break
    if not value:
        raise ValueError("GEMINI_API_KEY or API_KEY is required")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--english-dir", type=Path, required=True)
    parser.add_argument("--thai-dir", type=Path, required=True, help="caller-owned staging directory")
    parser.add_argument("--canonical-thai-dir", type=Path, default=ROOT / "data/content_th")
    parser.add_argument("--source-db", type=Path, default=ROOT / "data/vocabulary_source.db")
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    copy_canonical(args.canonical_thai_dir, args.thai_dir)
    headwords, sense_ids = load_reviewed_corpus(args.english_dir)
    readings, senses = source_items(args.source_db, headwords, sense_ids)
    added_words, added_senses = complete(
        readings,
        senses,
        args.thai_dir,
        GeminiGenerator(load_api_key()),
        batch_size=args.batch_size,
        retries=args.retries,
    )
    print(
        f"metadata=complete corpus_words={len(readings)} used_senses={len(senses)} "
        f"added_words={added_words} added_senses={added_senses} thai_dir={args.thai_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
