import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_content_db as builder


class ContentWordsTest(unittest.TestCase):
    def test_loads_manifest_order_and_source_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.txt"
            manifest.write_text(
                "# seq\tpriority\tsource_rank\theadword\tsource_file\tdeterministic_errors\n"
                "1\tfailed\t239\tenjoy\ta.txt\tbad cloze\n"
                "2\taudit\t2967\tzone\tb.txt\t\n",
                encoding="utf-8",
            )

            self.assertEqual(
                [
                    {"source_rank": 239, "headword": "enjoy", "is_test_only": 0},
                    {"source_rank": 2967, "headword": "zone", "is_test_only": 0},
                ],
                builder.content_words(manifest),
            )

    def test_rejects_non_contiguous_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.txt"
            manifest.write_text("2\taudit\t1\tword\ta.txt\t\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "expected seq 1, got 2"):
                builder.content_words(manifest)

    def test_repository_manifest_is_the_full_reviewed_corpus(self):
        words = builder.content_words()

        self.assertEqual(2967, len(words))
        self.assertEqual(
            {"source_rank": 239, "headword": "enjoy", "is_test_only": 0}, words[0]
        )
        self.assertEqual(
            {"source_rank": 2967, "headword": "zone", "is_test_only": 0}, words[-1]
        )


if __name__ == "__main__":
    unittest.main()
