from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import translate_vocab_content as subject


class TranslateVocabContentTest(unittest.TestCase):
    def test_parse_six_and_eight_field_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draft.txt"
            rows = [
                "@ test",
                "1\t10\tnoun\ttest\t1\tThis test feels fair.",
                "2\t10\tnoun\ttests\t0\tThe tests begin today.\tเก่า\tเก่า",
            ]
            path.write_text("\n".join(rows), encoding="utf-8")
            entries, errors = subject.parse_draft(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(entries["test"]), 2)
        self.assertEqual(entries["test"][1].target, "tests")

    def test_target_must_be_a_complete_word(self) -> None:
        self.assertTrue(subject.target_occurs("at", "Meet me at home."))
        self.assertFalse(subject.target_occurs("at", "Water is cold."))

    def test_cache_is_context_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = subject.TranslationCache(Path(directory) / "cache.db")
            one = subject.TranslationItem("The bank closed.", "financial institution")
            two = subject.TranslationItem("The bank was muddy.", "side of a river")
            cache.put("deepl", one, "ธนาคารปิด")
            self.assertEqual(cache.get("deepl", one), "ธนาคารปิด")
            self.assertIsNone(cache.get("deepl", two))
            cache.close()


if __name__ == "__main__":
    unittest.main()
