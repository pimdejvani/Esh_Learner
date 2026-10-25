import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from editorial_corrections import apply_corrections


class EditorialCorrectionsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "corrections.json"
        self.source = sqlite3.connect(":memory:")
        self.addCleanup(self.source.close)
        self.source.executescript("CREATE TABLE words(id INTEGER,headword TEXT); CREATE TABLE source_senses(id INTEGER,word_id INTEGER,pos TEXT,gloss TEXT); INSERT INTO words VALUES(1,'total'),(2,'other'); INSERT INTO source_senses VALUES(10,1,'adj','Entire'),(11,2,'adj','Other');")
        self.drafts = {"total": [{"rank": 1, "en_text": "The total cost rose.", "pos": "noun", "sense_id": 9}]}
        self.data = {"review_source": "review", "sentences": [{"headword": "total", "rank": 1, "expected_en": "The total cost rose.", "updates": {"sense_id": 10, "pos": "adj", "explanation_th": "ทั้งหมด"}}], "senses": [{"source_sense_id": 10, "expected_gloss": "Entire", "meaning_th": "ทั้งหมด"}]}

    def apply(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")
        meanings = {}
        drafts = copy.deepcopy(self.drafts)
        apply_corrections(drafts, meanings, self.source, path=self.path)
        return drafts, meanings

    def test_remaps_to_attested_sense_and_records_review_provenance(self):
        drafts, meanings = self.apply(self.data)
        self.assertEqual(10, drafts["total"][0]["sense_id"])
        self.assertEqual("review", drafts["total"][0]["explanation_source"])
        self.assertEqual("review", meanings[10]["meaning_source"])

    def test_rejects_changed_english_and_unrelated_senses(self):
        for change in ("english", "sense", "gloss", "duplicate"):
            data = copy.deepcopy(self.data)
            if change == "english":
                data["sentences"][0]["expected_en"] = "Different context"
            elif change == "sense":
                data["sentences"][0]["updates"]["sense_id"] = 11
            elif change == "gloss":
                data["senses"][0]["expected_gloss"] = "Different meaning"
            else:
                data["sentences"].append(copy.deepcopy(data["sentences"][0]))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.apply(data)
