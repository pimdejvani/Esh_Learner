"""Apply reviewed learner-text corrections, failing on changed source context."""
import json
import sqlite3
from pathlib import Path

CORRECTIONS = Path(__file__).resolve().parent.parent / "content" / "editorial_corrections.json"


def apply_corrections(drafts: dict, thai_senses: dict, source, thai_words: dict | None = None, path: Path = CORRECTIONS) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    seen = set()
    for correction in data["sentences"]:
        key = correction["headword"], correction["rank"]
        if key in seen:
            raise ValueError(f"duplicate editorial correction: {key}")
        seen.add(key)
        rows = [row for row in drafts.get(key[0], []) if row["rank"] == key[1]]
        if len(rows) != 1 or rows[0]["en_text"] != correction["expected_en"]:
            raise ValueError(f"editorial English context changed: {key}")
        row = rows[0]
        updates = correction["updates"]
        if set(updates) - {"en_text", "th_text", "explanation_th", "sense_id", "pos"}:
            raise ValueError(f"unsupported editorial field: {key}")
        if "sense_id" in updates:
            sense = source.execute(
                "SELECT w.headword,s.pos FROM source_senses s JOIN words w ON w.id=s.word_id WHERE s.id=?",
                (updates["sense_id"],),
            ).fetchone()
            if sense is None or sense[0].casefold() != key[0] or sense[1] != updates.get("pos", row["pos"]):
                raise ValueError(f"editorial sense evidence mismatch: {key}")
        row.update(updates)
        row["explanation_source"] = data["review_source"]
    for correction in data["senses"]:
        sid = correction["source_sense_id"]
        evidence = source.execute("SELECT gloss FROM source_senses WHERE id=?", (sid,)).fetchone()
        if evidence is None or evidence[0] != correction["expected_gloss"]:
            raise ValueError(f"editorial sense context changed: {sid}")
        thai_senses[sid] = {
            "meaning_th": correction["meaning_th"],
            "meaning_source": data["review_source"],
        }
    for correction in data.get("words", []):
        row = (thai_words or {}).get(correction["headword"])
        if row is None or row.get("thai_reading") != correction["expected_reading"]:
            raise ValueError(f"editorial reading context changed: {correction['headword']}")
        row["thai_reading"] = correction["thai_reading"]


def verify_corrections(db, path: Path = CORRECTIONS) -> None:
    """Reject a rebuilt artifact that loses any reviewed correction."""
    data = json.loads(path.read_text(encoding="utf-8"))
    db.row_factory = sqlite3.Row
    for correction in data["sentences"]:
        row = db.execute(
            "SELECT e.*,s.source_sense_id,s.pos FROM example_sentences e "
            "JOIN words w ON w.id=e.word_id JOIN senses s ON s.id=e.sense_id "
            "WHERE w.headword=? AND e.rank=?", (correction["headword"], correction["rank"]),
        ).fetchone()
        for field, expected in correction["updates"].items():
            column = "source_sense_id" if field == "sense_id" else field
            if row is None or row[column] != expected:
                raise ValueError(f"editorial regression: {correction['headword']} rank {correction['rank']} {field}")
    for correction in data["senses"]:
        row = db.execute("SELECT gloss_en,meaning_th FROM senses WHERE source_sense_id=?", (correction["source_sense_id"],)).fetchone()
        if row is None or tuple(row) != (correction["expected_gloss"], correction["meaning_th"]):
            raise ValueError(f"editorial sense regression: {correction['source_sense_id']}")
    for correction in data.get("words", []):
        row = db.execute("SELECT thai_reading FROM words WHERE headword=?", (correction["headword"],)).fetchone()
        if row is None or row[0] != correction["thai_reading"]:
            raise ValueError(f"editorial reading regression: {correction['headword']}")
