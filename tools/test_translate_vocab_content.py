from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_provider_circuit_opens_after_consecutive_failures(self) -> None:
        class FailingTranslator:
            def translate(self, items):
                raise RuntimeError("timeout")

        class WorkingTranslator:
            def translate(self, items):
                return ["คำแปล"] * len(items)

        calls = {"azure": 0, "deepl": 0}

        def fake_provider(name, workers=1):
            calls[name] += 1
            return FailingTranslator() if name == "azure" else WorkingTranslator()

        with tempfile.TemporaryDirectory() as directory:
            cache = subject.TranslationCache(Path(directory) / "cache.db")
            health = {}
            with patch.object(subject, "provider", side_effect=fake_provider):
                for number in range(3):
                    item = subject.TranslationItem(f"Sentence {number}", "context")
                    translated, _ = subject.translate_with_fallback(
                        [item], ["azure", "deepl"], cache, health, failure_limit=2
                    )
                    self.assertEqual(translated, ["คำแปล"])
            cache.close()

        self.assertEqual(calls["azure"], 2)
        self.assertEqual(calls["deepl"], 3)
        self.assertTrue(health["azure"].disabled)

    def test_deepl_workers_preserve_input_order(self) -> None:
        items = [
            subject.TranslationItem("one", "context one"),
            subject.TranslationItem("two", "context two"),
            subject.TranslationItem("three", "context three"),
        ]

        def fake_post_json(url, headers, payload):
            text = payload["text"][0]
            return {"translations": [{"text": f"แปล-{text}"}]}

        with patch.dict("os.environ", {"DEEPL_AUTH_KEY": "test"}):
            with patch.object(subject, "post_json", side_effect=fake_post_json):
                translated = subject.DeepLTranslator(workers=3).translate(items)

        self.assertEqual(translated, ["แปล-one", "แปล-two", "แปล-three"])

    def test_azure_workers_preserve_order_across_batches(self) -> None:
        items = [subject.TranslationItem(str(number), "context") for number in range(401)]

        def fake_post_json(url, headers, payload):
            return [
                {"translations": [{"text": f"แปล-{row['Text']}"}]}
                for row in payload
            ]

        with patch.dict("os.environ", {"AZURE_TRANSLATOR_KEY": "test"}):
            with patch.object(subject, "post_json", side_effect=fake_post_json):
                translated = subject.AzureTranslator(workers=3).translate(items)

        self.assertEqual(
            translated,
            [f"แปล-{number}" for number in range(401)],
        )


if __name__ == "__main__":
    unittest.main()
