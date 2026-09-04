import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import grammar_explanation_pipeline as pipeline
from grammar_explanation_pipeline import (
    load_generation_policy,
    load_existing,
    ranges,
    validate_explanations,
    validate_input_items,
    validate_loopback_endpoint,
    validate_text,
)


class GrammarExplanationPipelineTests(unittest.TestCase):
    def make_item(self, seq=1, headword="word"):
        return {
            "seq": seq,
            "headword": headword,
            "forms": [headword],
            "sentences": [
                {"rank": rank, "sense_id": rank, "pos": "noun", "target": headword,
                 "sentence": f"This sentence uses {headword} in context {rank}.", "gloss": "ความหมาย"}
                for rank in range(1, 6)
            ],
        }

    def valid_response(self):
        explanations = [
            "คำนี้เป็นคำนามเอกพจน์และเป็นประธานของประโยค จึงใช้รูปพื้นฐานตามที่ปรากฏ",
            "คำนี้ทำหน้าที่เป็นกรรมตรงของกริยา โดยรูปเอกพจน์สอดคล้องกับสิ่งที่กล่าวถึง",
            "คำนี้ตามหลังคำบุพบทและเป็นส่วนเติมเต็ม จึงคงรูปคำนามเอกพจน์ไว้",
            "คำนี้อยู่หลัง determiner และขยายใจความหลักในฐานะคำนามนับได้เอกพจน์",
            "คำนี้เป็นส่วนของ noun phrase ที่ทำหน้าที่บอกข้อมูลใหม่ จึงใช้รูปเอกพจน์",
        ]
        return json.dumps({"explanations": [
            {"rank": rank, "input_ok": True, "input_error": "",
             "explanation_th": explanations[rank - 1]}
            for rank in range(1, 6)
        ]}, ensure_ascii=False)

    def run_args(self, input_path, output_dir, **overrides):
        values = {"input": input_path, "output_dir": output_dir,
                  "endpoint": "http://127.0.0.1:8080/v1", "model": "test-model",
                  "max_tokens": 1000, "retries": 1, "breaker": 5,
                  "reasoning_effort": "low", "critic_mode": "none"}
        values.update(overrides)
        return argparse.Namespace(**values)

    def write_input(self, directory, items):
        path = directory / "input-source.jsonl"
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items), encoding="utf-8")
        return path

    def test_ranges(self):
        self.assertEqual({1, 2, 3, 8}, ranges("1-3,8"))

    def test_external_policy_carries_the_user_adjustable_production_gates(self):
        policy, raw = load_generation_policy(pipeline.DEFAULT_POLICY_FILE)
        self.assertTrue(raw)
        self.assertEqual("2026-08-30-v4", policy["policy_version"])
        self.assertEqual(0.8, policy["production_gates"]["semantic_pass_rate_min"])
        self.assertEqual(0.98, policy["production_gates"]["deterministic_acceptance_rate_min"])
        self.assertEqual(2.9, policy["production_gates"]["accepted_words_per_minute_min"])
        self.assertIn("คำกริยาวิเศษ(?!ณ์)", policy["validator_rules"]["banned_regexes"])
        self.assertEqual(90, policy["validator_rules"]["max_common_prefix_chars"])

    def test_rejects_invalid_external_policy_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "policy.json"
            path.write_text('{"schema_version":1}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "policy schema"):
                load_generation_policy(path)

    def test_valid_five_rows(self):
        raw = json.loads(self.valid_response())
        rows, errors = validate_explanations(raw)
        self.assertEqual(5, len(rows))
        self.assertEqual([], errors)

    def test_rejects_cross_reference_and_missing_rank(self):
        raw = {"explanations": [
            {"rank": rank, "input_ok": True, "input_error": "", "explanation_th": "คำนี้มีหน้าที่เหมือนประโยคก่อนหน้าและใช้รูปตามโครงสร้าง"}
            for rank in range(1, 5)
        ]}
        _, errors = validate_explanations(raw)
        self.assertIn("ranks", errors)
        self.assertTrue(any(error.endswith("cross-reference") for error in errors))

    def test_rejects_expanded_cross_references_and_near_template_copy(self):
        self.assertIn("cross-reference", validate_text("คำนี้มีหน้าที่เหมือนประโยคแรกและใช้รูปตามโครงสร้างที่กล่าวไว้"))
        self.assertIn("cross-reference", validate_text("คำนี้เป็นคำนามเหมือนใน previous sentence และอ้างรูปเดิมจากตัวอย่างนั้น"))
        raw = {"explanations": [
            {"rank": rank, "input_ok": True, "input_error": "",
             "explanation_th": f"คำนี้ทำหน้าที่เป็นคำนามและใช้รูปเอกพจน์ตามโครงสร้างของประโยค ลำดับ {rank}"}
            for rank in range(1, 6)
        ]}
        _, errors = validate_explanations(raw)
        self.assertIn("template-copy:all", errors)

    def test_allows_two_identical_explanations_for_identical_grammar(self):
        texts = [
            "คำนี้เป็นคำนามเอกพจน์และทำหน้าที่เป็นกรรมตรงของกริยาในประโยค",
            "คำนี้เป็นประธานของประโยคคำถามและใช้รูปเดิมตามหน้าที่ของคำสรรพนาม",
            "คำนี้ขยายคำนามหลักในวลีและแสดงลักษณะของสิ่งที่กล่าวถึง",
            "คำนี้เป็นกรรมของบุพบทและเชื่อมความหมายกับส่วนหน้าของประโยค",
            "คำนี้เป็นกริยาหลักรูปอดีตเพราะมีเหตุการณ์เกิดขึ้นและจบไปแล้ว",
        ]
        rows = [
            {"rank": rank, "input_ok": True, "input_error": "", "explanation_th": texts[rank - 1]}
            for rank in range(1, 6)
        ]
        rows[4]["explanation_th"] = rows[1]["explanation_th"]
        _, errors = validate_explanations({"explanations": rows})
        self.assertNotIn("duplicate-explanation", errors)
        self.assertNotIn("template-copy:all", errors)

    def test_rejects_non_thai_and_thin(self):
        self.assertEqual(["too-short", "no-thai"], validate_text("short"))

    def test_rejects_observed_nonsense_grammar_terms(self):
        self.assertIn(
            "nonsense-grammar-term",
            validate_text("คำนี้เป็นคำนามที่ไม่ต้องมีคำบุคคลและใช้เป็นประธานของประโยค"),
        )
        self.assertIn(
            "nonsense-grammar-term",
            validate_text("acting เป็นกริยาช่วยในรูป gerund และทำหน้าที่เป็นกิจกรรมในประโยค"),
        )
        self.assertIn(
            "nonsense-grammar-term",
            validate_text("to attract เป็นกริยาไม่มี to ที่ใช้เพื่อบอกจุดประสงค์ของการกระทำ"),
        )
        self.assertIn(
            "nonsense-grammar-term",
            validate_text("anyway ใช้เป็น副คำและอยู่ในตำแหน่ง末尾เพื่อขยายความหมายของประโยค"),
        )
        self.assertIn(
            "nonsense-grammar-term",
            validate_text("ancient เป็นคำคุณศัพท์กำหนดคำนาม tree และบอกว่าต้นไม้นั้นเก่าแก่มาก"),
        )
        self.assertIn(
            "nonsense-grammar-term",
            validate_text("anyway เป็นคำกริยาวิเศษที่ใช้บอกว่ายังทำสิ่งนั้นต่อไปแม้มีอุปสรรค"),
        )
        self.assertNotIn(
            "nonsense-grammar-term",
            validate_text("anyway เป็นคำวิเศษณ์ที่ขยายใจความของประโยคและบอกว่ายังทำต่อแม้มีอุปสรรค"),
        )
        self.assertIn(
            "nonsense-grammar-term",
            validate_text("the เป็นคำบุพบทที่กำหนดคำนาม fridge ให้เป็นตู้เย็นเฉพาะเครื่อง"),
        )
        self.assertIn(
            "nonsense-grammar-term",
            validate_text("biologies เป็นคำนามนับไม่ได้พหูพจน์และเป็นกรรมของกริยา present ในประโยค"),
        )

    def test_input_grounding_rejects_observed_copula_num_and_one_hallucinations(self):
        item = self.make_item(headword="billion")
        for sentence in item["sentences"]:
            sentence.update({"pos": "num", "target": "billion", "sentence": "Billions of people arrived."})
        raw = json.loads(self.valid_response())
        raw["explanations"][0]["explanation_th"] = "billion เป็นคำนามนับได้และใช้กับ one เพื่อบอกจำนวนที่มีค่ามาก"
        raw["explanations"][1]["explanation_th"] = "billion เป็นคำบอกจำนวนส่วนเติมเต็มหลัง is เพื่อระบุจำนวนในประโยค"
        _, errors = validate_explanations(raw, input_item=item)
        self.assertIn("rank-1:pos-conflict-num-as-noun", errors)
        self.assertIn("rank-1:unsupported-token-one", errors)
        self.assertIn("rank-2:unsupported-copula-is", errors)

    def test_input_grounding_requires_predicate_adjective_complement(self):
        item = self.make_item(headword="bright")
        item["sentences"][0].update({
            "pos": "adj", "target": "bright", "sentence": "The sun is bright today."
        })
        raw = json.loads(self.valid_response())
        raw["explanations"][0]["explanation_th"] = (
            "bright เป็นคำคุณศัพท์ขยายคำนาม sun และบอกลักษณะว่าสว่างในวันนี้"
        )
        _, errors = validate_explanations(raw, input_item=item)
        self.assertIn("rank-1:predicate-adjective-not-complement", errors)

        raw["explanations"][0]["explanation_th"] = (
            "bright เป็นคำคุณศัพท์ส่วนเติมเต็มประธานหลัง is เพื่อบอกลักษณะของ The sun"
        )
        _, errors = validate_explanations(raw, input_item=item)
        self.assertNotIn("rank-1:predicate-adjective-not-complement", errors)

    def test_accepts_longer_grounded_explanation_within_tolerance(self):
        text = (
            "คำว่า accident เป็นคำนามนับได้เอกพจน์และเป็นส่วนหลักของวลี an accident "
            "โดยใช้ an เพราะกล่าวถึงอุบัติเหตุหนึ่งเหตุการณ์แบบไม่เฉพาะเจาะจง"
        )
        self.assertEqual([], validate_text(text))

    def test_rejects_duplicate_rank(self):
        raw = {"explanations": [
            {"rank": 1, "input_ok": True, "input_error": "", "explanation_th": "คำนี้ทำหน้าที่เป็นคำกริยาและใช้รูปตามโครงสร้างของประโยคนี้โดยตรง"}
            for _ in range(5)
        ]}
        _, errors = validate_explanations(raw)
        self.assertIn("duplicate-rank:1", errors)
        self.assertIn("ranks", errors)

    def test_input_error_is_quarantined(self):
        raw = {"explanations": [
            {"rank": rank, "input_ok": rank != 2,
             "input_error": "ประโยคขาดกริยาหลัก" if rank == 2 else "",
             "explanation_th": "ประโยคนี้มีข้อมูลเพียงพอสำหรับตรวจหน้าที่และรูปคำตามหลักไวยากรณ์"}
            for rank in range(1, 6)
        ]}
        _, errors = validate_explanations(raw)
        self.assertTrue(any("rank-2:input-error:" in error for error in errors))

    def test_rejects_tsv_delimiters_bool_rank_and_extra_fields(self):
        self.assertIn("unsafe-tsv-character", validate_text("คำอธิบายภาษาไทยที่ยาวเพียงพอและมีแท็บ\tซึ่งทำให้ไฟล์เสีย"))
        raw = {"explanations": [
            {"rank": rank, "input_ok": True, "input_error": "", "explanation_th":
             "คำนี้ทำหน้าที่เป็นคำนามในบริบทและใช้รูปตามโครงสร้างของประโยค"}
            for rank in [True, 2, 3, 4, 5]
        ]}
        _, errors = validate_explanations(raw)
        self.assertIn("schema-row", errors)
        raw["extra"] = True
        self.assertEqual(([], ["schema"]), validate_explanations(raw))

    def test_invalid_legacy_row_is_not_existing(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "rows.tsv").write_text(
                "word\t1\tคำนี้อ้างถึงประโยคก่อนหน้าและจึงต้องไม่ถือว่าเป็นข้อมูลที่สมบูรณ์\n",
                encoding="utf-8",
            )
            existing, anomalies = load_existing(directory)
            self.assertNotIn(("word", 1), existing)
            self.assertTrue(any(row["code"] == "cross-reference" for row in anomalies))

    def test_input_schema_rejects_duplicate_rank(self):
        item = self.make_item()
        item["sentences"][-1]["rank"] = 4
        with self.assertRaisesRegex(ValueError, "ranks must be exactly 1-5"):
            validate_input_items([item])

    def test_endpoint_is_loopback_only(self):
        self.assertEqual("http://127.0.0.1:8080/v1", validate_loopback_endpoint("http://127.0.0.1:8080/v1/"))
        with self.assertRaisesRegex(ValueError, "loopback"):
            validate_loopback_endpoint("https://example.com/v1")

    def test_crash_after_checkpoint_resumes_without_duplicate_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = self.write_input(directory, [self.make_item()])
            output_dir = directory / "run"
            real_materialize = pipeline.materialize_artifacts
            calls = 0

            def crash_after_commit(connection, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("simulated crash")
                return real_materialize(connection, destination)

            with mock.patch.object(pipeline, "call_model", return_value=(self.valid_response(), {}, 0.1)), \
                    mock.patch.object(pipeline, "materialize_artifacts", side_effect=crash_after_commit):
                with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                    pipeline.run(self.run_args(input_path, output_dir))
            with mock.patch.object(pipeline, "call_model") as model_call, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, pipeline.run(self.run_args(input_path, output_dir)))
                model_call.assert_not_called()
            rows = (output_dir / "accepted.tsv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(5, len(rows))
            self.assertEqual(1, len((output_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()))

    def test_resume_rejects_mismatched_model_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = self.write_input(directory, [self.make_item()])
            output_dir = directory / "run"
            with mock.patch.object(pipeline, "call_model", return_value=(self.valid_response(), {}, 0.1)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, pipeline.run(self.run_args(input_path, output_dir)))
            with self.assertRaisesRegex(ValueError, "configuration does not match"):
                pipeline.run(self.run_args(input_path, output_dir, model="different-model"))

    def test_resume_rejects_changed_reasoning_effort(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = self.write_input(directory, [self.make_item()])
            output_dir = directory / "run"
            with mock.patch.object(pipeline, "call_model", return_value=(self.valid_response(), {}, 0.1)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, pipeline.run(self.run_args(input_path, output_dir)))
            with self.assertRaisesRegex(ValueError, "configuration does not match"):
                pipeline.run(self.run_args(input_path, output_dir, reasoning_effort="medium"))

    def test_quarantine_is_terminal_on_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = self.write_input(directory, [self.make_item()])
            output_dir = directory / "run"
            invalid = json.dumps({"explanations": [
                {"rank": rank, "input_ok": True, "input_error": "", "explanation_th": "สั้น"}
                for rank in range(1, 6)
            ]}, ensure_ascii=False)
            with mock.patch.object(pipeline, "call_model", return_value=(invalid, {}, 0.1)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(3, pipeline.run(self.run_args(input_path, output_dir, retries=0)))
            with mock.patch.object(pipeline, "call_model") as model_call, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(3, pipeline.run(self.run_args(input_path, output_dir, retries=0)))
                model_call.assert_not_called()
            quarantine = [json.loads(line) for line in (output_dir / "quarantine.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual("quarantine", quarantine[0]["status"])

    def test_breaker_reports_incomplete_and_pending(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            items = [self.make_item(1, "one"), self.make_item(2, "two")]
            input_path = self.write_input(directory, items)
            output_dir = directory / "run"
            with mock.patch.object(pipeline, "call_model", side_effect=OSError("offline")), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(2, pipeline.run(self.run_args(input_path, output_dir, retries=0, breaker=1)))
            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["complete"])
            self.assertEqual(1, summary["counts"]["pending"])
            self.assertIn("request/schema", summary["breaker_reason"])

    def test_resume_rejects_changed_validator_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = self.write_input(directory, [self.make_item()])
            output_dir = directory / "run"
            with mock.patch.object(pipeline, "call_model", return_value=(self.valid_response(), {}, 0.1)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, pipeline.run(self.run_args(input_path, output_dir)))
            with mock.patch.object(pipeline, "VALIDATOR_VERSION", "changed"):
                with self.assertRaisesRegex(ValueError, "configuration does not match"):
                    pipeline.run(self.run_args(input_path, output_dir))

    def test_single_writer_lock_rejects_concurrent_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            with pipeline.single_writer_lock(output_dir):
                with self.assertRaisesRegex(RuntimeError, "already in use"):
                    with pipeline.single_writer_lock(output_dir):
                        self.fail("second writer acquired the lock")

    def test_input_quarantine_metrics_are_disjoint_and_counted_in_rate(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            items = [self.make_item(1, "one"), self.make_item(2, "two")]
            input_path = self.write_input(directory, items)
            output_dir = directory / "run"
            input_error = json.dumps({"explanations": [
                {"rank": rank, "input_ok": rank != 1,
                 "input_error": "ประโยคขาดกริยาหลัก" if rank == 1 else "",
                 "explanation_th": "ประโยคนี้มีข้อมูลเพียงพอสำหรับตรวจหน้าที่และรูปคำตามหลักไวยากรณ์"}
                for rank in range(1, 6)
            ]}, ensure_ascii=False)
            with mock.patch.object(pipeline, "call_model", side_effect=[
                    (self.valid_response(), {}, 0.1), (input_error, {}, 0.1)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(3, pipeline.run(self.run_args(input_path, output_dir, retries=0)))
            summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(0, summary["quarantine_words_this_run"])
            self.assertEqual(1, summary["input_quarantine_words_this_run"])
            self.assertEqual(2, summary["terminal_words_cumulative"])
            self.assertEqual(0.5, summary["deterministic_acceptance_rate"])

    def test_retry_receives_previous_raw_output_and_validator_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = self.write_input(directory, [self.make_item()])
            output_dir = directory / "run"
            invalid = self.valid_response().replace("คำนี้เป็นคำนาม", "คำนี้มีคำบุคคล", 1)
            with mock.patch.object(pipeline, "call_model", side_effect=[
                    (invalid, {}, 0.1), (self.valid_response(), {}, 0.1)]) as model_call, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, pipeline.run(self.run_args(input_path, output_dir, retries=1)))
            self.assertIsNone(model_call.call_args_list[0].args[6])
            repair = model_call.call_args_list[1].args[6]
            self.assertEqual(invalid, repair["raw"])
            self.assertTrue(any("nonsense-grammar-term" in value for value in repair["errors"]))

    def test_rewrite_critic_reviews_a_draft_before_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            input_path = self.write_input(directory, [self.make_item()])
            output_dir = directory / "run"
            with mock.patch.object(pipeline, "call_model", side_effect=[
                    ("draft", {"total_tokens": 10}, 0.2),
                    (self.valid_response(), {"total_tokens": 20}, 0.3),
                    ]) as model_call, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, pipeline.run(self.run_args(
                    input_path, output_dir, retries=0, critic_mode="rewrite"
                )))
            self.assertEqual(2, model_call.call_count)
            critic_context = model_call.call_args_list[1].args[6]
            self.assertEqual("draft", critic_context["raw"])
            self.assertIn("adversarial grammar critic", critic_context["instruction"])


if __name__ == "__main__":
    unittest.main()
