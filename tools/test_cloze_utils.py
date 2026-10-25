import unittest
from cloze_utils import cloze_span, valid_cloze_span
from validate_content_db import CROSS_REFERENCE


class ClozeSpanTest(unittest.TestCase):
    def test_reference_detection_allows_real_row_number_context(self):
        self.assertIsNone(CROSS_REFERENCE.search('row หมายถึงแถวที่สามจากด้านหน้า'))
        self.assertIsNotNone(CROSS_REFERENCE.search('ต่างจากแถวอื่นที่เป็นกริยา'))
        self.assertIsNotNone(CROSS_REFERENCE.search('เช่นเดียวกับ r1'))
    def test_selects_whole_word_after_embedded_match(self):
        self.assertEqual((24, 28), cloze_span("Thailand is a beautiful land with warm people.", "land"))
        self.assertEqual((5, 7), cloze_span("When he arrived, we started dinner.", "he"))
        self.assertEqual((42, 45), cloze_span("After three days of rain, the first sunny day felt like a celebration.", "day"))

    def test_rejects_partial_missing_empty_and_invalid_offsets(self):
        self.assertEqual((-1, -1), cloze_span("Thailand", "land"))
        self.assertEqual((-1, -1), cloze_span("land", ""))
        for start, end in [(-1, 3), (0, 0), (0, 99), (4, 8)]:
            self.assertFalse(valid_cloze_span("Thailand", "land", start, end))

    def test_handles_capitals_multiword_targets_and_abbreviations(self):
        for text, target in [("LAND is precious.", "land"), ("It is more famous now.", "more famous"), ("We met in Feb. last year.", "Feb.")]:
            start, end = cloze_span(text, target)
            self.assertTrue(valid_cloze_span(text, target, start, end))
