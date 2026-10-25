import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_thai_metadata as metadata


class ThaiMetadataValidationTest(unittest.TestCase):
    def test_reading_requires_thai_and_valid_one_based_stress(self):
        self.assertEqual(("อะ-เบาท์", 2), metadata.validate_reading("อะ-เบาท์", 2))
        with self.assertRaisesRegex(ValueError, "Thai script"):
            metadata.validate_reading("a-bout", 2)
        with self.assertRaisesRegex(ValueError, "outside"):
            metadata.validate_reading("อะ-เบาท์", 3)

    def test_meaning_requires_thai_and_maximum_42_characters(self):
        self.assertEqual("ละทิ้ง", metadata.validate_meaning(" ละทิ้ง "))
        with self.assertRaisesRegex(ValueError, "Thai script"):
            metadata.validate_meaning("abandon")
        with self.assertRaisesRegex(ValueError, "42"):
            metadata.validate_meaning("ก" * 43)

    def test_rejects_duplicate_same_word_and_pos_meaning(self):
        senses = [
            metadata.SenseItem(1, "bank", "noun", "financial institution", ("ธนาคาร",)),
            metadata.SenseItem(2, "bank", "noun", "a reserve", ()),
        ]
        response = {
            "readings": [],
            "senses": [
                {"source_sense_id": 1, "meaning_th": "ธนาคาร"},
                {"source_sense_id": 2, "meaning_th": "ธนาคาร"},
            ],
        }
        with self.assertRaisesRegex(ValueError, "duplicate meaning"):
            metadata.accept_response(response, [], senses, {})

    def test_clamps_impossible_model_stress_to_last_written_syllable(self):
        readings, senses = metadata.accept_response(
            {
                "readings": [
                    {"headword": "new", "thai_reading": "นิว", "stress_index": 2}
                ],
                "senses": [],
            },
            [metadata.ReadingItem("new", "/njuː/")],
            [],
            {},
        )
        self.assertEqual({"new": {"thai_reading": "นิว", "stress_index": 1}}, readings)
        self.assertEqual({}, senses)


class ThaiMetadataCompletionTest(unittest.TestCase):
    def make_stage(self, root: Path) -> Path:
        canonical = root / "canonical"
        canonical.mkdir()
        (canonical / "words_th.txt").write_text(
            "# existing comment\n" + metadata.WORD_HEADER +
            "\nkeep|คีพ|1|authored\n",
            encoding="utf-8",
        )
        (canonical / "senses_th.txt").write_text(
            metadata.SENSE_HEADER + "\n1|keep|verb|เก็บไว้|authored\n",
            encoding="utf-8",
        )
        (canonical / "forms_th.txt").write_text("unchanged\n", encoding="utf-8")
        stage = root / "stage"
        metadata.copy_canonical(canonical, stage)
        return stage

    def test_generates_only_missing_rows_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = self.make_stage(Path(directory))
            original_words = (stage / "words_th.txt").read_text(encoding="utf-8")
            seen = []

            def fake(payload):
                seen.append(payload)
                return {
                    "readings": [
                        {"headword": "new", "thai_reading": "นิว", "stress_index": 1}
                    ],
                    "senses": [
                        {"source_sense_id": 2, "meaning_th": "ใหม่"}
                    ],
                }

            added = metadata.complete(
                {
                    "keep": metadata.ReadingItem("keep", "/kiːp/"),
                    "new": metadata.ReadingItem("new", "/njuː/"),
                },
                {
                    1: metadata.SenseItem(1, "keep", "verb", "retain", ("เก็บไว้",)),
                    2: metadata.SenseItem(2, "new", "adj", "recent", ("ใหม่",)),
                },
                stage,
                fake,
                batch_size=10,
            )

            self.assertEqual((1, 1), added)
            self.assertEqual(1, len(seen))
            self.assertEqual([{"headword": "new", "source_ipa": "/njuː/"}], seen[0]["readings"])
            self.assertEqual([2], [row["source_sense_id"] for row in seen[0]["senses"]])
            self.assertEqual("recent", seen[0]["senses"][0]["source_gloss_en"])
            self.assertEqual(["ใหม่"], seen[0]["senses"][0]["source_thai_candidates"])
            self.assertTrue((stage / "words_th.txt").read_text(encoding="utf-8").startswith(original_words))
            self.assertEqual("unchanged\n", (stage / "forms_th.txt").read_text(encoding="utf-8"))

    def test_valid_checkpoint_resumes_without_model_call(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = self.make_stage(Path(directory))
            checkpoint = {
                "model": metadata.MODEL,
                "readings": {"new": {"thai_reading": "นิว", "stress_index": 1}},
                "senses": {"2": {"meaning_th": "ใหม่"}},
            }
            (stage / ".thai_metadata_checkpoint.json").write_text(
                json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8"
            )

            def should_not_run(_payload):
                raise AssertionError("model was called despite complete checkpoint")

            added = metadata.complete(
                {
                    "keep": metadata.ReadingItem("keep", "/kiːp/"),
                    "new": metadata.ReadingItem("new", "/njuː/"),
                },
                {
                    1: metadata.SenseItem(1, "keep", "verb", "retain", ()),
                    2: metadata.SenseItem(2, "new", "adj", "recent", ()),
                },
                stage,
                should_not_run,
            )
            self.assertEqual((1, 1), added)
            self.assertEqual(
                (0, 0),
                metadata.complete(
                    {
                        "keep": metadata.ReadingItem("keep", "/kiːp/"),
                        "new": metadata.ReadingItem("new", "/njuː/"),
                    },
                    {
                        1: metadata.SenseItem(1, "keep", "verb", "retain", ()),
                        2: metadata.SenseItem(2, "new", "adj", "recent", ()),
                    },
                    stage,
                    should_not_run,
                ),
            )

    def test_canonical_directory_cannot_be_used_as_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            canonical = Path(directory)
            with self.assertRaisesRegex(ValueError, "must not be the canonical"):
                metadata.copy_canonical(canonical, canonical)

    def test_retries_a_failed_batch_then_checkpoints_it(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = self.make_stage(Path(directory))
            attempts = 0

            def flaky(_payload):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise RuntimeError("temporary failure")
                return {
                    "readings": [
                        {"headword": "new", "thai_reading": "นิว", "stress_index": 1}
                    ],
                    "senses": [],
                }

            with patch.object(metadata.time, "sleep"):
                added = metadata.complete(
                    {"new": metadata.ReadingItem("new", "/njuː/")},
                    {},
                    stage,
                    flaky,
                    retries=2,
                )
            self.assertEqual(2, attempts)
            self.assertEqual((1, 0), added)


if __name__ == "__main__":
    unittest.main()
