import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_sentence_repairs as overlay


HEADER = [
    "seq", "headword", "rank", "sense_id", "pos", "target", "gloss",
    "original", "decision", "corrected_sentence", "reason",
]


class ApplySentenceRepairsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.snapshot = self.root / "snapshot"
        self.snapshot.mkdir()
        self.source = (
            b"# keep this header\r\n@ walk\r\n"
            b"1\t10\tverb\twalk\t1\tWe walk every day.\r\n"
            b"2\t11\tnoun\twalk\t0\tThe walk was long.\r\n"
        )
        (self.snapshot / "batch.txt").write_bytes(self.source)
        (self.snapshot / "notes.bin").write_bytes(b"unchanged\x00bytes")
        self.manifest = self.root / "manifest.tsv"
        self.manifest.write_text("7\tx\tx\twalk\tbatch.txt\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def write_repairs(self, **overrides):
        values = {
            "seq": "7", "headword": "walk", "rank": "1", "sense_id": "10",
            "pos": "verb", "target": "walk", "gloss": "move on foot",
            "original": "We walk every day.", "decision": "invalid",
            "corrected_sentence": "We walk to school every day.", "reason": "context",
        }
        values.update(overrides)
        path = self.root / "repairs.tsv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerow(values)
        return path

    def test_success_changes_only_sentence_bytes_and_copies_other_files(self):
        repairs = self.write_repairs()
        output = self.root / "output"
        result = overlay.run(self.snapshot, repairs, self.manifest, output)
        expected = self.source.replace(b"We walk every day.", b"We walk to school every day.")
        self.assertEqual(expected, (output / "batch.txt").read_bytes())
        self.assertEqual(b"unchanged\x00bytes", (output / "notes.bin").read_bytes())
        self.assertEqual(1, result["repaired_sentences"])
        self.assertEqual(1, result["changed_files"])

    def test_exact_metadata_mismatch_fails_without_output(self):
        repairs = self.write_repairs(pos="noun")
        output = self.root / "output"
        with self.assertRaisesRegex(ValueError, "metadata or original mismatch"):
            overlay.run(self.snapshot, repairs, self.manifest, output)
        self.assertFalse(output.exists())

    def append_repair(self, path, values):
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADER, delimiter="\t", lineterminator="\n")
            writer.writerow(values)

    def test_rejects_duplicate_mapping(self):
        repairs = self.write_repairs()
        self.append_repair(repairs, {
            "seq": "7", "headword": "walk", "rank": "1", "sense_id": "10",
            "pos": "verb", "target": "walk", "gloss": "move on foot",
            "original": "We walk every day.", "decision": "invalid",
            "corrected_sentence": "We walk home every day.", "reason": "duplicate",
        })
        with self.assertRaisesRegex(ValueError, "duplicate repair mapping"):
            overlay.load_repairs(repairs)

    def test_rejects_duplicate_correction(self):
        duplicate = "We walk and talk on the way to school every day."
        repairs = self.write_repairs(corrected_sentence=duplicate)
        self.append_repair(repairs, {
            "seq": "8", "headword": "talk", "rank": "1", "sense_id": "12",
            "pos": "verb", "target": "talk", "gloss": "speak",
            "original": "We talk every day.", "decision": "invalid",
            "corrected_sentence": duplicate, "reason": "duplicate",
        })
        with self.assertRaisesRegex(ValueError, "duplicate corrected sentence"):
            overlay.load_repairs(repairs)

    def test_rejects_embedded_tab_newline_and_missing_target(self):
        cases = {
            "tab": ({"reason": "bad\tfield"}, "embedded tab or newline"),
            "newline": ({"reason": "bad\nfield"}, "embedded tab or newline"),
            "target": ({"corrected_sentence": "We go to school every day."}, "lacks exact target"),
            "unchanged": ({"corrected_sentence": "We walk every day."}, "correction is unchanged"),
        }
        for name, (overrides, message) in cases.items():
            with self.subTest(name=name):
                repairs = self.write_repairs(**overrides)
                with self.assertRaisesRegex(ValueError, message):
                    overlay.load_repairs(repairs)

    def test_rejects_existing_output_directory(self):
        repairs = self.write_repairs()
        output = self.root / "output"
        output.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            overlay.run(self.snapshot, repairs, self.manifest, output)


if __name__ == "__main__":
    unittest.main()
