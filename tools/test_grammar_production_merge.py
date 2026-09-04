from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grammar_production_merge as subject


# --------------------------------------------------------------------------- #
# fixture builder                                                             #
# --------------------------------------------------------------------------- #
POS = "noun"


def source_obj(seq: int, headword: str, rank: int, target: str, sentence: str, sense: int) -> dict:
    source = {
        "rank": rank,
        "sense_id": sense,
        "pos": POS,
        "target": target,
        "sentence": sentence,
        "gloss": f"gloss for {headword} r{rank}",
    }
    return {
        "seq": seq,
        "headword": headword,
        "rank": rank,
        "candidate_state": "accepted",
        "source": source,
        "source_sha256": subject.source_dict_sha256(source),
        "candidate": f"cand {headword} {rank}",
        "candidate_sha256": subject.sha256_text(f"cand {headword} {rank}"),
    }


def write_review_dir(root: Path, reviewed: list[str], repairs: list[tuple[int, int, str, str]]) -> Path:
    """reviewed: headwords; repairs: (seq, rank, headword, sentence)."""
    review = root / "review"
    review.mkdir()
    cand_lines = []
    final_lines = []
    seq = 100
    seq_of = {}
    for headword in reviewed:
        seq_of[headword] = seq
        for rank in (1, 2, 3, 4, 5):
            target = headword if rank != 3 else headword + "s"
            sentence = f"The {target} number {rank} is here."
            cand_lines.append(json.dumps(source_obj(seq, headword, rank, target, sentence, 900 + rank), ensure_ascii=False))
            final_lines.append(f"{seq}\t{headword}\t{rank}\tคำอธิบายไทยของ {headword} อันดับ {rank}")
        seq += 25
    (review / "candidates.jsonl").write_text("\n".join(cand_lines) + "\n", encoding="utf-8")
    (review / "final.tsv").write_text("\n".join(final_lines) + "\n", encoding="utf-8")
    rep_lines = []
    for rseq, rrank, rhead, rsent in repairs:
        rep_lines.append(f"{rseq}\t{rhead}\t{rrank}\t{rsent}")
    (review / "source_repairs.tsv").write_text(("\n".join(rep_lines) + "\n") if rep_lines else "", encoding="utf-8")
    # provenance stubs used by pack
    (review / "manifest.json").write_text("{}\n", encoding="utf-8")
    (review / "decision_ledger.jsonl").write_text("{}\n", encoding="utf-8")
    return review, seq_of


def write_legacy(root: Path, sol_words: list[str], terra_words: list[str], expl_words: list[str],
                 bad_expl: dict[str, list[int]] | None = None):
    sol = root / "sol"; sol.mkdir()
    terra = root / "terra"; terra.mkdir()
    expl = root / "expl"; expl.mkdir()

    def block(headword: str, tag: str) -> str:
        lines = [f"@ {headword}"]
        for rank in (1, 2, 3, 4, 5):
            target = headword if rank != 3 else headword + "s"
            emo = "1" if rank == 1 else "0"
            sentence = f"A {target} from {tag} sits at {rank}."
            lines.append("\t".join([str(rank), str(500 + rank), POS, target, emo, sentence]))
        return "\n".join(lines)

    if sol_words:
        (sol / "sol_repair_0001.txt").write_text("\n".join(block(w, "sol") for w in sol_words) + "\n", encoding="utf-8")
    if terra_words:
        (terra / "terra_en_001.txt").write_text("\n".join(block(w, "terra") for w in terra_words) + "\n", encoding="utf-8")
    bad_expl = bad_expl or {}
    expl_lines = []
    for w in expl_words:
        ranks = bad_expl.get(w, [1, 2, 3, 4, 5])
        for rank in ranks:
            expl_lines.append(f"{w}\t{rank}\tอธิบาย legacy {w} อันดับ {rank}")
    (expl / "expl_0001.tsv").write_text("\n".join(expl_lines) + "\n", encoding="utf-8")
    return sol, terra, expl


def fake_translate(snapshot_dir: Path, out_dir: Path) -> None:
    """Emulate translate_vocab_content: copy fields 1-6 byte-for-byte, add a
    non-empty Thai field 7 and an empty field 8."""
    out_dir.mkdir(parents=True)
    for path in sorted(snapshot_dir.glob("*.txt")):
        lines = []
        for raw in path.read_text(encoding="utf-8").splitlines():
            if raw.startswith("@ ") or not raw.strip():
                lines.append(raw)
                continue
            fields = raw.split("\t")
            lines.append("\t".join(fields[:6] + ["แปลไทย", ""]))
        (out_dir / path.name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def snapshot_args(review, sol, terra, expl, out):
    ns = subject.build_parser().parse_args(
        ["snapshot", "--review-dir", str(review), "--legacy-draft-dir", str(sol),
         "--legacy-fallback-draft-dir", str(terra), "--legacy-expl-dir", str(expl), "--out-dir", str(out)]
    )
    return ns


# --------------------------------------------------------------------------- #
# tests                                                                        #
# --------------------------------------------------------------------------- #
class SnapshotAssemblyTest(unittest.TestCase):
    def _big_fixture(self, root: Path):
        # 15 reviewed (accepted + input/output quarantine states are semantic-
        # only; here they are all accepted rows in candidates), plus legacy.
        reviewed = [f"rev{i:02d}" for i in range(15)]
        # legacy-overlap: 'rev00' also appears as a legacy word -> reviewed wins.
        sol_words = [f"sol{i:02d}" for i in range(6)] + ["rev00"]
        terra_words = [f"ter{i:02d}" for i in range(6)] + [f"sol{i:02d}" for i in range(6)]
        expl_words = sol_words + [f"ter{i:02d}" for i in range(6)] + ["orphan_expl"]
        review, seq_of = write_review_dir(root, reviewed, repairs=[
            (seq_of_seq := 100, 2, "rev00", "The rev00 was repaired here now.")])
        sol, terra, expl = write_legacy(root, sol_words, terra_words, expl_words,
                                        bad_expl={"orphan_expl": [1, 2, 3]})
        return review, sol, terra, expl, reviewed, sol_words, terra_words

    def test_snapshot_end_to_end_and_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            review, sol, terra, expl, reviewed, sol_words, terra_words = self._big_fixture(root)
            out = root / "cand"
            rc = subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, out))
            self.assertEqual(rc, 0)
            manifest = json.loads((out / "snapshot_manifest.json").read_text(encoding="utf-8"))
            c = manifest["counts"]
            # 15 reviewed, 6 legacy-sol (rev00 excluded by precedence), 6 legacy-terra
            self.assertEqual(c["reviewed_words"], 15)
            self.assertEqual(c["legacy_sol_words"], 6)
            self.assertEqual(c["legacy_terra_words"], 6)
            self.assertEqual(c["merged_words"], 27)
            self.assertEqual(c["merged_rows"], 27 * 5)
            self.assertGreaterEqual(c["merged_words"], 25)  # >=25 words fixture
            # orphan_expl (only 3 ranks) is blocked, not fabricated
            self.assertTrue(any(b["headword"] == "orphan_expl" for b in manifest["blocked"]))
            self.assertEqual(manifest["repairs_applied"], 1)

    def test_repair_changes_only_sentence_and_breaks_old_binding(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            review, seq_of = write_review_dir(root, ["alpha"], repairs=[])
            sol, terra, expl = write_legacy(root, [], [], [])
            out = root / "cand"
            subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, out))
            index = json.loads((out / "snapshot_index.json").read_text(encoding="utf-8"))
            rec = index["alpha\t2"]
            self.assertFalse(rec["repaired"])
            self.assertEqual(rec["source_sha256_original"], rec["effective_source_sha256"])

            # now the same word with a repair on rank 2
            root2 = Path(d) / "run2"
            root2.mkdir()
            review2, _ = write_review_dir(root2, ["alpha"],
                                          repairs=[(100, 2, "alpha", "The alpha was mended cleanly.")])
            sol2, terra2, expl2 = write_legacy(root2, [], [], [])
            out2 = root2 / "cand"
            subject.cmd_snapshot(snapshot_args(review2, sol2, terra2, expl2, out2))
            index2 = json.loads((out2 / "snapshot_index.json").read_text(encoding="utf-8"))
            rec2 = index2["alpha\t2"]
            self.assertTrue(rec2["repaired"])
            # repair changed the sentence -> effective source hash differs from the
            # original candidate hash, so the OLD binding no longer holds.
            self.assertNotEqual(rec2["effective_source_sha256"], rec2["source_sha256_original"])
            # other ranks unchanged
            self.assertEqual(index2["alpha\t1"]["effective_source_sha256"],
                             index2["alpha\t1"]["source_sha256_original"])

    def test_repair_target_must_survive(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            review, _ = write_review_dir(root, ["bravo"],
                                         repairs=[(100, 1, "bravo", "This sentence dropped the word.")])
            sol, terra, expl = write_legacy(root, [], [], [])
            with self.assertRaises(subject.BuildError):
                subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, root / "cand"))

    def test_repair_out_of_scope_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            review, _ = write_review_dir(root, ["bravo"],
                                         repairs=[(99999, 1, "bravo", "The bravo is out of scope.")])
            sol, terra, expl = write_legacy(root, [], [], [])
            with self.assertRaises(subject.BuildError):
                subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, root / "cand"))

    def test_output_dir_must_not_exist(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            review, _ = write_review_dir(root, ["bravo"], repairs=[])
            sol, terra, expl = write_legacy(root, [], [], [])
            out = root / "cand"
            out.mkdir()
            with self.assertRaises(subject.BuildError):
                subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, out))

    def test_malformed_jsonl_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            review, _ = write_review_dir(root, ["bravo"], repairs=[])
            (review / "candidates.jsonl").write_text("{not json}\n", encoding="utf-8")
            sol, terra, expl = write_legacy(root, [], [], [])
            with self.assertRaises(json.JSONDecodeError):
                subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, root / "cand"))

    def test_malformed_repair_tsv_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            review, _ = write_review_dir(root, ["bravo"], repairs=[])
            (review / "source_repairs.tsv").write_text("100\tbravo\t1\n", encoding="utf-8")  # 3 cols
            sol, terra, expl = write_legacy(root, [], [], [])
            with self.assertRaises(subject.BuildError):
                subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, root / "cand"))


class ValidateTest(unittest.TestCase):
    def _valid_dir(self, root: Path) -> Path:
        d = root / "drafts"
        d.mkdir()
        rows = ["@ word"]
        for rank in (1, 2, 3, 4, 5):
            emo = "1" if rank == 1 else "0"
            rows.append("\t".join([str(rank), "10", POS, "word", emo, "The word is here.", "แปล", "อธิบาย"]))
        (d / "a.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
        return d

    def test_valid_passes(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._valid_dir(Path(t))
            self.assertEqual(subject.validate_dir(d, require_translation=True, require_explanation=True), [])

    def test_missing_key(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._valid_dir(Path(t))
            text = (d / "a.txt").read_text(encoding="utf-8").splitlines()
            (d / "a.txt").write_text("\n".join(text[:-1]) + "\n", encoding="utf-8")  # drop rank 5
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True)
            self.assertTrue(any("!= [1,2,3,4,5]" in e for e in errs))

    def test_duplicate_key(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._valid_dir(Path(t))
            with (d / "a.txt").open("a", encoding="utf-8") as h:
                h.write("2\t10\tnoun\tword\t0\tThe word is here again.\tแปล\tอธิบาย\n")
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True)
            self.assertTrue(any("duplicate rank" in e for e in errs))

    def test_invalid_rank(self):
        with tempfile.TemporaryDirectory() as t:
            d = root = Path(t) / "drafts"; d.mkdir()
            rows = ["@ word"]
            for rank in (0, 2, 3, 4, 5):  # rank 0 invalid
                emo = "1" if rank == 1 else "0"
                rows.append("\t".join([str(rank), "10", POS, "word", emo, "The word is here.", "แปล", "อธิบาย"]))
            (d / "a.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True)
            self.assertTrue(any("out of range" in e for e in errs))

    def test_emotional_rule(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._valid_dir(Path(t))
            text = (d / "a.txt").read_text(encoding="utf-8").replace(
                "2\t10\tnoun\tword\t0", "2\t10\tnoun\tword\t1")
            (d / "a.txt").write_text(text, encoding="utf-8")
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True)
            self.assertTrue(any("emotional==1" in e for e in errs))

    def test_target_absent(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._valid_dir(Path(t))
            text = (d / "a.txt").read_text(encoding="utf-8").replace("The word is here.", "Nothing matches.")
            (d / "a.txt").write_text(text, encoding="utf-8")
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True)
            self.assertTrue(any("absent as a whole word" in e for e in errs))

    def test_tab_count(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._valid_dir(Path(t))
            with (d / "a.txt").open("a", encoding="utf-8") as h:
                h.write("weird line without tabs\n")
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True)
            self.assertTrue(any("expected 7 tabs" in e for e in errs))

    def test_empty_translation_and_explanation(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "drafts"; d.mkdir()
            rows = ["@ word"]
            for rank in (1, 2, 3, 4, 5):
                emo = "1" if rank == 1 else "0"
                rows.append("\t".join([str(rank), "10", POS, "word", emo, "The word is here.", "", ""]))
            (d / "a.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True)
            self.assertTrue(any("field 7" in e for e in errs))
            self.assertTrue(any("field 8" in e for e in errs))

    def test_policy_fail(self):
        policy = {"validator_rules": {"banned_literals": ["คำบุคคล"], "banned_regexes": ["[\\u3040-\\u30ff]"]}}
        with tempfile.TemporaryDirectory() as t:
            d = Path(t) / "drafts"; d.mkdir()
            rows = ["@ word"]
            for rank in (1, 2, 3, 4, 5):
                emo = "1" if rank == 1 else "0"
                bad = "อธิบาย คำบุคคล" if rank == 1 else "アニメ explanation"
                rows.append("\t".join([str(rank), "10", POS, "word", emo, "The word is here.", "แปล", bad]))
            (d / "a.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True, policy=policy)
            self.assertTrue(any("banned literal" in e for e in errs))
            self.assertTrue(any("banned pattern" in e for e in errs))

    def test_sha_binding_mismatch(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            d = self._valid_dir(root)
            index = {}
            for rank in (1, 2, 3, 4, 5):
                emo = "1" if rank == 1 else "0"
                line = "\t".join([str(rank), "10", POS, "word", emo, "The word is here."])
                index[f"word\t{rank}"] = {"fields16_sha256": subject.sha256_text(line), "origin": "reviewed"}
            self.assertEqual(subject.validate_dir(d, require_translation=True, require_explanation=True,
                                                  snapshot_index=index), [])
            # tamper a sentence -> SHA mismatch
            text = (d / "a.txt").read_text(encoding="utf-8").replace("The word is here.", "The word is HERE.", 1)
            (d / "a.txt").write_text(text, encoding="utf-8")
            errs = subject.validate_dir(d, require_translation=True, require_explanation=True, snapshot_index=index)
            self.assertTrue(any("SHA mismatch" in e for e in errs))


class MergeTest(unittest.TestCase):
    def test_merge_precedence_and_byte_preservation(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            reviewed = [f"rev{i:02d}" for i in range(3)]
            sol_words = ["leg00", "rev00"]  # rev00 overlaps -> reviewed wins
            terra_words = ["ter00"]
            expl_words = ["leg00", "ter00", "rev00"]
            review, seq_of = write_review_dir(root, reviewed, repairs=[])
            sol, terra, expl = write_legacy(root, sol_words, terra_words, expl_words)
            out = root / "cand"
            subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, out))
            snap_dir = out / "snapshot"
            translated = root / "translated"
            fake_translate(snap_dir, translated)

            merged = root / "merged"
            ns = subject.build_parser().parse_args(
                ["merge", "--translated-dir", str(translated), "--snapshot-index", str(out / "snapshot_index.json"),
                 "--review-final", str(review / "final.tsv"), "--legacy-expl-dir", str(expl), "--out-dir", str(merged)]
            )
            self.assertEqual(subject.cmd_merge(ns), 0)

            # fields 1-7 byte-equivalent between translated and merged; field 8 filled
            for name in [p.name for p in translated.glob("*.txt")]:
                tin = (translated / name).read_text(encoding="utf-8").splitlines()
                tout = (merged / name).read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(tin), len(tout))
                for a, b in zip(tin, tout):
                    if a.startswith("@ ") or not a.strip():
                        self.assertEqual(a, b)
                        continue
                    fa, fb = a.split("\t"), b.split("\t")
                    self.assertEqual(fa[:7], fb[:7])   # 1-7 unchanged
                    self.assertTrue(fb[7].strip())     # field 8 present

            # reviewed rev00 explanation came from final.tsv, not legacy expl
            index = json.loads((out / "snapshot_index.json").read_text(encoding="utf-8"))
            self.assertEqual(index["rev00\t1"]["origin"], "reviewed")
            rev_text = (merged / "snapshot_reviewed.txt").read_text(encoding="utf-8")
            self.assertIn("คำอธิบายไทยของ rev00 อันดับ 1", rev_text)
            self.assertNotIn("อธิบาย legacy rev00", rev_text)

            # validate the merged output fully
            errs = subject.validate_dir(merged, require_translation=True, require_explanation=True,
                                        snapshot_index=index)
            self.assertEqual(errs, [])

    def test_merge_output_dir_must_not_exist(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            review, _ = write_review_dir(root, ["rev00"], repairs=[])
            sol, terra, expl = write_legacy(root, [], [], [])
            out = root / "cand"
            subject.cmd_snapshot(snapshot_args(review, sol, terra, expl, out))
            fake_translate(out / "snapshot", root / "translated")
            merged = root / "merged"; merged.mkdir()
            ns = subject.build_parser().parse_args(
                ["merge", "--translated-dir", str(root / "translated"),
                 "--snapshot-index", str(out / "snapshot_index.json"),
                 "--review-final", str(review / "final.tsv"), "--legacy-expl-dir", str(expl), "--out-dir", str(merged)]
            )
            with self.assertRaises(subject.BuildError):
                subject.cmd_merge(ns)


class RealDataAuditTest(unittest.TestCase):
    """Full deterministic audit against the REAL corpus (no fabrication)."""

    ROOT = Path(__file__).resolve().parent.parent
    REVIEW = ROOT / "staging/grammar_explanation_reviews/20260831-071557-grammar-26-2967-bd9cfe09ead9"

    def test_real_counts_reconcile(self):
        if not (self.REVIEW / "candidates.jsonl").exists():
            self.skipTest("real corpus not present")
        candidates = subject.load_candidates(self.REVIEW / "candidates.jsonl")
        repairs = subject.load_repairs(self.REVIEW / "source_repairs.tsv")
        sol = subject.parse_compact_dir(self.ROOT / "data/sol_review_drafts")
        terra = subject.parse_compact_dir(self.ROOT / "data/terra_english_drafts")
        expl = subject.load_explanations_dir(self.ROOT / "data/sol_review_explanations")
        asm = subject.assemble(candidates, repairs, sol, terra, expl)
        rows = sum(len(r) for r in asm.rows.values())
        words = len(asm.rows)
        for headword, ranks in asm.rows.items():
            self.assertEqual(sorted(ranks), [1, 2, 3, 4, 5], headword)
        self.assertEqual(rows, words * 5)
        # ACTUAL reconciled totals from the real files:
        self.assertEqual(words, 2965)
        self.assertEqual(rows, 14825)
        reviewed = {w for w, r in asm.rows.items() if r[1].origin == "reviewed"}
        self.assertEqual(len(reviewed), 1566)


if __name__ == "__main__":
    unittest.main()
