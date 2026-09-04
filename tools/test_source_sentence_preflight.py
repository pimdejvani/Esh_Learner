import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_sentence_preflight import contains_target, inspect, review_codes


class SourceSentencePreflightTests(unittest.TestCase):
    def item(self, sentences=None):
        values = sentences or [
            (1, "word", "This word appears in a natural sentence."),
            (2, "word", "A second word appears in this example."),
            (3, "word", "People use the word in daily speech."),
            (4, "word", "The word remains clear in this sentence."),
            (5, "word", "That final word completes the short example."),
        ]
        return {
            "seq": 1, "headword": "word", "forms": ["word"],
            "sentences": [
                {"rank": rank, "sense_id": rank, "pos": "noun", "target": target,
                 "sentence": sentence, "gloss": "a unit of language"}
                for rank, target, sentence in values
            ],
        }

    def test_target_uses_token_boundaries_and_casefolding(self):
        self.assertTrue(contains_target("Anybody can join.", "anybody"))
        self.assertTrue(contains_target("She answered, 'Nothing.'", "Nothing"))
        self.assertFalse(contains_target("A wording change helps.", "word"))
        self.assertFalse(contains_target("The speaker's warning helped.", "speaker"))

    def test_known_templates_route_to_review(self):
        self.assertIn("generic-habitual", review_codes("We write every day.", "write"))
        self.assertIn("generic-walk-home", review_codes("We walk among home.", "among"))
        self.assertIn("thin-copular", review_codes("It is bright.", "bright"))

    def test_target_absence_and_lowercase_initial_fail_deterministically(self):
        values = [
            (1, "word", "this sentence omits the required token."),
            (2, "word", "A word appears here naturally."),
            (3, "word", "The word is visible in this sentence."),
            (4, "word", "People repeat the word in class."),
            (5, "word", "That word ends the complete example."),
        ]
        findings, summary = inspect([self.item(values)])
        codes = {(row["severity"], row["code"]) for row in findings}
        self.assertIn(("error", "target-absent"), codes)
        self.assertIn(("error", "lowercase-initial"), codes)
        self.assertFalse(summary["deterministic_ready"])

    def test_duplicate_sentences_are_review_findings(self):
        item = self.item()
        item["sentences"][1]["sentence"] = item["sentences"][0]["sentence"]
        findings, summary = inspect([item])
        self.assertEqual(2, sum(row["code"] == "duplicate-sentence" for row in findings))
        self.assertTrue(summary["deterministic_ready"])


if __name__ == "__main__":
    unittest.main()
