import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import merge_sentence_explanations as subject


NOTES = {
    1: "คำนี้เป็นคำนามและทำหน้าที่เป็นประธานของประโยค โดยกล่าวถึงสิ่งสำคัญที่อยู่ตรงนี้อย่างชัดเจน",
    2: "ผู้พูดใช้คำนี้เป็นกรรมตรงหลังกริยา เพื่อระบุสิ่งที่เขามองเห็นในสถานการณ์ปัจจุบัน",
    3: "ในวลีนี้คำเป้าหมายเป็นคำนามเอกพจน์ตามหลังคำนำหน้านาม และช่วยบอกว่าสิ่งใดถูกกล่าวถึง",
    4: "คำเป้าหมายอยู่หลังคำบุพบทจึงเป็นส่วนเติมเต็มของบุพบท และระบุจุดที่การกระทำมุ่งไปหา",
    5: "รูปนี้ใช้เป็นคำนามในส่วนท้ายของประโยค เพื่อบอกข้อมูลหลักที่ผู้พูดต้องการยืนยันให้ชัดเจน",
}


def write_word(path: Path, word: str, notes: dict[int, str] | None, changed_rank: int = 0) -> None:
    lines = [f"@ {word}"]
    for rank in range(1, 6):
        sentence = f"The {word} is visible near the old tree {rank}."
        if rank == changed_rank:
            sentence = f"A {word} remains visible beside the old tree {rank}."
        fields = [str(rank), str(100 + rank), "noun", word, "1" if rank == 1 else "0",
                  sentence, "คำแปลภาษาไทย", (notes or {}).get(rank, "")]
        lines.append("\t".join(fields))
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


class MergeSentenceExplanationsTest(unittest.TestCase):
    def test_reuse_requires_all_six_source_fields_to_match(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_dir = root / "old"; old_dir.mkdir()
            new_dir = root / "new"; new_dir.mkdir()
            write_word(old_dir / "all.txt", "alpha", NOTES)
            write_word(new_dir / "all.txt", "alpha", None)
            rules = subject.load_generation_policy(subject.DEFAULT_POLICY_FILE)[0]["validator_rules"]
            old = subject.parse_drafts(old_dir)
            current = subject.parse_drafts(new_dir)
            self.assertEqual(len(subject.reusable_explanations(current, old, rules)), 5)

            # Every listed binding field matters; changing en_text alone makes
            # precisely that row stale.
            (new_dir / "all.txt").unlink()
            write_word(new_dir / "all.txt", "alpha", None, changed_rank=3)
            reused = subject.reusable_explanations(subject.parse_drafts(new_dir), old, rules)
            self.assertNotIn(("alpha", 3), reused)
            self.assertEqual(len(reused), 4)

    def test_invalid_old_note_is_not_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_dir = root / "old"; old_dir.mkdir()
            new_dir = root / "new"; new_dir.mkdir()
            bad = dict(NOTES); bad[2] = "สั้น"
            write_word(old_dir / "all.txt", "alpha", bad)
            write_word(new_dir / "all.txt", "alpha", None)
            rules = subject.load_generation_policy(subject.DEFAULT_POLICY_FILE)[0]["validator_rules"]
            reused = subject.reusable_explanations(
                subject.parse_drafts(new_dir), subject.parse_drafts(old_dir), rules
            )
            self.assertNotIn(("alpha", 2), reused)
            self.assertEqual(len(reused), 4)

    def test_checkpointed_generation_fills_only_stale_row_and_preserves_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            fake_staging = Path(temp) / "staging"; fake_staging.mkdir()
            old_dir = Path(temp) / "old"; old_dir.mkdir()
            translated = Path(temp) / "translated"; translated.mkdir()
            write_word(old_dir / "all.txt", "alpha", NOTES)
            write_word(old_dir / "all.txt", "beta", NOTES)
            write_word(translated / "all.txt", "alpha", None)
            write_word(translated / "all.txt", "beta", None, changed_rank=3)
            output = fake_staging / "run"
            calls: list[list[tuple[str, int]]] = []

            def fake_generator(rows, _errors):
                calls.append([(row.headword, row.rank) for row in rows])
                return {"explanations": [
                    {"headword": row.headword, "rank": row.rank,
                     "explanation_th": "beta เป็นคำนามและทำหน้าที่เป็นประธานของกริยา remains เพื่อชี้ถึงสิ่งที่ยังมองเห็นอยู่ใกล้ต้นไม้เก่า"}
                    for row in rows
                ]}

            args = argparse.Namespace(
                translated_dir=translated, output_dir=output, old_candidate_dir=old_dir,
                policy_file=subject.DEFAULT_POLICY_FILE, model=subject.DEFAULT_MODEL,
                batch_rows=50, workers=2, max_attempts=2, api_key=None,
            )
            with mock.patch.object(subject, "STAGING", fake_staging):
                manifest = subject.run_merge(args, generator=fake_generator)
                self.assertTrue(manifest["complete"], manifest)
                self.assertEqual(manifest["counts"]["reused"], 9)
                self.assertEqual(manifest["counts"]["generated"], 1)
                self.assertEqual(calls, [[("beta", 3)]])

                source_lines = (translated / "all.txt").read_text(encoding="utf-8").splitlines()
                output_lines = (output / "merged/all.txt").read_text(encoding="utf-8").splitlines()
                for source, merged in zip(source_lines, output_lines):
                    if source.startswith("@ "):
                        self.assertEqual(source, merged)
                    else:
                        self.assertEqual(source.split("\t")[:7], merged.split("\t")[:7])
                        self.assertTrue(merged.split("\t")[7])

                # A resumed invocation is fully checkpointed and performs no API call.
                subject.run_merge(args, generator=lambda *_: self.fail("generator called on resume"))


if __name__ == "__main__":
    unittest.main()
