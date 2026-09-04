from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from local_vocab_pipeline.pipeline import (  # noqa: E402
    CRITIC_PROMPT,
    PROMPT,
    build_run,
    compact_evidence,
    run_worker,
    status_report,
    word_prompt,
    normalize_candidate_targets,
    validate_candidate,
    verify_result,
    verify_manifest,
)
from local_vocab_pipeline.semantic import (  # noqa: E402
    _audit_payload,
    _deterministic_findings,
    _feedback_constraint_errors,
    _failed_check_findings,
    _lock_unflagged_rows,
    build_blind_calibration,
    semantic_revalidate,
    validate_calibration,
)


class QueueClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    def __call__(self, messages, schema):
        self.calls += 1
        self.prompts.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_candidate(target="tests", sense_id=11, pos="verb", sentence_prefix="We"):
    sentences = [
        f"{sentence_prefix} remember how patience tests every careful learner.",
        f"The teacher tests our progress after lunch.",
        f"This simple exercise tests both speed and accuracy.",
        f"A quiet week tests whether the new routine works.",
        f"Good feedback tests the idea before anyone spends money.",
    ]
    return {
        "headword": "test",
        "decision": "repair",
        "reason": "Corrected the assigned sentence.",
        "rows": [
            {"rank": rank, "sense_id": sense_id, "pos": pos, "target": target, "memorable": int(rank == 1), "sentence": text}
            for rank, text in enumerate(sentences, 1)
        ],
    }


class LocalVocabularyPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "evidence.db"
        con = sqlite3.connect(self.db)
        con.executescript("""
        CREATE TABLE words(id INTEGER PRIMARY KEY, headword TEXT, cefr_first TEXT, source_rank INTEGER);
        CREATE TABLE source_senses(id INTEGER PRIMARY KEY, word_id INTEGER, pos TEXT, gloss TEXT, tags_json TEXT, source_name TEXT);
        CREATE TABLE source_forms(id INTEGER PRIMARY KEY, word_id INTEGER, form_text TEXT, pos TEXT, tags_json TEXT, source_name TEXT);
        CREATE TABLE source_examples(id INTEGER PRIMARY KEY, word_id INTEGER, pos TEXT, sense_gloss TEXT, example_text TEXT, example_type TEXT, source_name TEXT);
        INSERT INTO words VALUES(1,'test','A2',1);
        INSERT INTO source_senses VALUES(11,1,'verb','to examine or try something','[]','fixture');
        INSERT INTO source_forms VALUES(21,1,'tests','verb','[]','fixture');
        INSERT INTO source_examples VALUES(31,1,'verb','to examine or try something','She tests the alarm.','quotation','fixture');
        """)
        con.commit(); con.close()
        self.manifest = self.root / "manifest.txt"
        self.manifest.write_text("# seq\tpriority\tsource_rank\theadword\tsource_file\tdeterministic_errors\n1\tfailed\t1\ttest\tdraft.txt\trank 2: placeholder sentence\n", encoding="utf-8")
        self.drafts = self.root / "drafts"; self.drafts.mkdir()
        candidate = make_candidate()
        candidate["rows"][1]["sentence"] = "The test is important."
        candidate["rows"][1]["target"] = "test"
        candidate["rows"][1]["decision"] = "repair"
        block = "@ test\n" + "\n".join(f"{r['rank']}\t{r['sense_id']}\t{r['pos']}\t{r['target']}\t{r['memorable']}\t{r['sentence']}" for r in candidate["rows"]) + "\n"
        (self.drafts / "draft.txt").write_text(block, encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def build(self, name="run", *, critic_pass=False):
        run = self.root / name
        build_run(run, self.db, self.manifest, self.drafts, 1, 1, config={"critic_pass": critic_pass})
        return run

    def record(self, run):
        return json.loads((run / "input" / "evidence.jsonl").read_text(encoding="utf-8"))

    def canonical_preserving_candidate(self, run):
        record = self.record(run)
        candidate = {"headword": "test", "decision": "repair", "reason": "Fixed rank 2.", "rows": [dict(row) for row in record["canonical"]]}
        candidate["rows"][1] = make_candidate(target="test", sentence_prefix="We")["rows"][1]
        candidate["rows"][1]["sentence"] = "We use this test to check progress after lunch."
        return candidate

    def test_builder_is_complete_and_checksummed(self):
        run = self.build()
        self.assertEqual([], verify_manifest(run / "input", run / "input" / "manifest.sha256"))
        self.assertTrue((run / "state" / "run.sqlite").exists())
        self.assertEqual("built", status_report(run)["status"])
        config = json.loads((run / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(2, config["max_model_retries"])
        self.assertEqual(64, len(config["evidence_db_sha256"]))

    def test_builder_does_not_promote_rank_one_to_explicit_primary(self):
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO source_senses VALUES(12,1,'verb','to evaluate carefully','[]','fixture')")
        con.executemany(
            "INSERT INTO source_examples VALUES(?,?,?,?,?,?,?)",
            [(40 + index, 1, "verb", "to evaluate carefully", f"Example {index}", "example", "fixture")
             for index in range(5)],
        )
        con.commit(); con.close()
        run = self.build("popular-build")
        self.assertEqual(12, self.record(run)["evidence"]["safe_profile"]["sense_id"])

    def test_validation_rejects_unsupported_sense_form_and_absent_target(self):
        run = self.build()
        record = self.record(run)
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1].update({"sense_id": 999, "target": "invented", "sentence": "Nothing useful appears here."})
        errors = validate_candidate(candidate, record)
        self.assertTrue(any("unsupported sense_id" in error for error in errors))
        self.assertTrue(any("unsupported target form" in error for error in errors))
        self.assertTrue(any("absent as a complete word" in error for error in errors))

    def test_validation_rejects_serialization_artifact_in_sentence(self):
        run = self.build("artifact")
        record = self.record(run)
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1]["sentence"] = "The teacher tests us.},{"
        self.assertTrue(any("Thai, Markdown" in error for error in validate_candidate(candidate, record)))

    def test_validation_rejects_observed_grammar_red_flags(self):
        run = self.build("grammar-red-flags")
        record = self.record(run)
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1]["sentence"] = "The bus arrives soon than we expected and tests our patience."
        self.assertTrue(any("grammar/naturalness red flag" in error for error in validate_candidate(candidate, record)))

    def test_validation_rejects_verbatim_safe_gloss_echo(self):
        run = self.build("gloss-echo")
        record = self.record(run)
        record["evidence"]["safe_profile"]["gloss"] = "without fail"
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1]["sentence"] = "The teacher tests us without fail."
        self.assertTrue(any("echoes the safe gloss verbatim" in error for error in validate_candidate(candidate, record)))

    def test_unique_source_form_in_sentence_normalizes_declared_target(self):
        run = self.build("normalize")
        record = self.record(run)
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1].update({"target": "test", "sentence": "The teacher tests our progress after lunch."})
        changes = normalize_candidate_targets(candidate, record)
        self.assertEqual("tests", candidate["rows"][1]["target"])
        self.assertEqual([{"rank": 2, "from": "test", "to": "tests"}], changes)

    def test_malformed_json_retries_then_accepts(self):
        run = self.build()
        good = self.canonical_preserving_candidate(run)
        client = QueueClient(["not json", json.dumps(good)])
        result = run_worker(run, client, ignore_resources=True)
        self.assertEqual("completed", result["status"])
        self.assertEqual(1, result["counts"]["accepted"])
        self.assertEqual(2, client.calls)
        self.assertIn("@ test", (run / "output" / "accepted_six_field.txt").read_text(encoding="utf-8"))

    def test_critic_pass_audits_and_replaces_generator_candidate(self):
        run = self.build("critic", critic_pass=True)
        generated = self.canonical_preserving_candidate(run)
        corrected = self.canonical_preserving_candidate(run)
        corrected["rows"][1]["sentence"] = "The teacher uses this test before the students arrive."
        client = QueueClient([json.dumps(generated), json.dumps(corrected)])
        result = run_worker(run, client, ignore_resources=True)
        self.assertEqual(2, client.calls)
        self.assertEqual(1, result["counts"]["accepted"])
        saved = json.loads(next((run / "output" / "accepted").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual(corrected["rows"][1]["sentence"], saved["rows"][1]["sentence"])
        self.assertIn("final quality gate", CRITIC_PROMPT)

    def test_semantic_revalidation_repairs_then_checks_in_clean_context(self):
        run = self.build("semantic")
        candidate = self.canonical_preserving_candidate(run)
        accepted = run / "output" / "accepted"
        accepted.mkdir(parents=True, exist_ok=True)
        (accepted / "0001_test.json").write_text(json.dumps(candidate), encoding="utf-8")
        calibration = self.root / "calibration.json"
        calibration.write_text(json.dumps({
            "schema_version": 1, "run_id": "fixture", "seq_start": 1, "seq_end": 1,
            "words": [{"seq": 1, "headword": "test", "issues": [
                {"rank": 2, "severity": "hard", "codes": ["FIXTURE"], "reason": "Repair this row."}
            ]}],
        }), encoding="utf-8")
        repaired = self.canonical_preserving_candidate(run)
        audit_repair = {"headword": "test", "decision": "repair", "severity": "hard", "reason": "Repaired rank 2.",
                        "issues": [{"rank": 2, "severity": "hard", "code": "FIXTURE", "reason": "Original was weak."}],
                        "rows": repaired["rows"]}
        audit_pass = {"headword": "test", "decision": "pass", "severity": "pass", "reason": "No hard defects remain.",
                      "issues": [], "rows": repaired["rows"]}
        client = QueueClient([json.dumps(audit_repair), json.dumps(audit_pass)])
        output = self.root / "semantic-output"
        result = semantic_revalidate(run, calibration, output, client=client, config={"batch_size": 1})
        self.assertTrue(result["ok"])
        self.assertTrue(result["ready_for_blind_gate"])
        self.assertEqual(2, client.calls)
        self.assertEqual(1, len(list((output / "accepted").glob("*.json"))))

    def test_semantic_revalidation_can_start_from_prior_semantic_candidate(self):
        run = self.build("semantic-source")
        original = self.canonical_preserving_candidate(run)
        (run / "output" / "accepted" / "0001_test.json").write_text(json.dumps(original), encoding="utf-8")
        prior = self.canonical_preserving_candidate(run)
        prior["rows"][1]["sentence"] = "The prior reviewer sentence contains this test."
        source_dir = self.root / "prior-semantic" / "accepted"
        source_dir.mkdir(parents=True)
        (source_dir / "0001_test.json").write_text(json.dumps({"candidate": prior, "report": {}}), encoding="utf-8")
        calibration = self.root / "calibration-semantic-source.json"
        calibration.write_text(json.dumps({
            "schema_version": 1, "run_id": "fixture", "seq_start": 1, "seq_end": 1,
            "words": [{"seq": 1, "headword": "test", "issues": [
                {"rank": 2, "severity": "hard", "codes": ["FIXTURE"], "reason": "Repair this row."}
            ]}],
        }), encoding="utf-8")
        repaired = self.canonical_preserving_candidate(run)
        audit_repair = {"headword": "test", "decision": "repair", "severity": "hard", "reason": "Repaired.",
                        "issues": [{"rank": 2, "severity": "hard", "code": "FIXTURE", "reason": "Fixed."}],
                        "rows": repaired["rows"]}
        audit_pass = {"headword": "test", "decision": "pass", "severity": "pass", "reason": "Clean.",
                      "issues": [], "rows": repaired["rows"]}
        client = QueueClient([json.dumps(audit_repair), json.dumps(audit_pass)])
        result = semantic_revalidate(run, calibration, self.root / "semantic-source-output",
                                     source_candidate_dir=source_dir, client=client)
        self.assertTrue(result["ok"])
        first_prompt = json.loads(client.prompts[0][1]["content"])
        self.assertEqual(prior["rows"][1]["sentence"], first_prompt["candidate_to_validate"]["rows"][1]["sentence"])

    def test_calibration_does_not_hardcode_repair_batch_size(self):
        calibration = {"seq_start": 1, "seq_end": 2, "words": [
            {"seq": 1, "headword": "one", "issues": []},
            {"seq": 2, "headword": "two", "issues": []},
        ]}
        validate_calibration(calibration)

    def test_semantic_repair_preserves_unflagged_ranks_byte_for_byte(self):
        previous = make_candidate()
        repaired = make_candidate(sentence_prefix="They")
        expected_rank_one = dict(repaired["rows"][0])
        _lock_unflagged_rows(previous, repaired, {1})
        self.assertEqual(expected_rank_one, repaired["rows"][0])
        self.assertEqual(previous["rows"][1:], repaired["rows"][1:])

    def test_semantic_loop_turns_deterministic_errors_into_rank_findings(self):
        findings = _deterministic_findings(["rank 5: target is absent as a complete word", "global error"])
        self.assertEqual([5], [finding["rank"] for finding in findings])
        self.assertEqual(["DETERMINISTIC_VALIDATION"], findings[0]["codes"])

    def test_feedback_constraint_rejects_repeated_phrasal_sense_drift(self):
        candidate = make_candidate()
        candidate["rows"][1]["sentence"] = "The teacher tests to the old rule again."
        errors = _feedback_constraint_errors(candidate, [{
            "rank": 2,
            "codes": ["SYSTEMIC_PHRASAL_SENSE_DRIFT"],
            "reason": "The particle creates a different lexical sense.",
        }])
        self.assertEqual(["rank 2: human-rejected target-plus-particle lexical construction is still present"], errors)

    def test_semantic_payload_excludes_multiword_inflection_targets(self):
        run = self.build("semantic-targets")
        record = self.record(run)
        record["evidence"]["forms"].append({"pos": "verb", "form_text": "more tests"})
        payload = json.loads(_audit_payload(record, self.canonical_preserving_candidate(run), []))
        allowed = payload["required_row_constraints"][0]["allowed_targets"]
        self.assertIn("tests", allowed)
        self.assertNotIn("more tests", allowed)

    def test_failed_structured_check_becomes_repair_finding(self):
        findings = _failed_check_findings({"checks": [{
            "rank": 3, "gloss_match": True, "grammar_natural": False,
            "target_pos_match": True, "learner_safe": True, "reason": "Agreement is wrong.",
        }]})
        self.assertEqual(["GRAMMAR_OR_NATURALNESS"], findings[0]["codes"])

    def test_clean_reviewer_repair_is_final_after_deterministic_pass(self):
        run = self.build("semantic-clean-repair")
        candidate = self.canonical_preserving_candidate(run)
        (run / "output" / "accepted" / "0001_test.json").write_text(json.dumps(candidate), encoding="utf-8")
        calibration = self.root / "calibration-clean-repair.json"
        calibration.write_text(json.dumps({
            "schema_version": 1, "run_id": "fixture", "seq_start": 1, "seq_end": 1,
            "words": [{"seq": 1, "headword": "test", "issues": [
                {"rank": 2, "severity": "hard", "codes": ["FIXTURE"], "reason": "Repair this row."}
            ]}],
        }), encoding="utf-8")
        audit = {"headword": "test", "decision": "repair", "severity": "hard", "reason": "Corrected input.",
                 "issues": [{"rank": 2, "severity": "hard", "code": "FIXTURE", "reason": "Input was weak."}],
                 "rows": candidate["rows"]}
        client = QueueClient([json.dumps(audit), json.dumps(audit)])
        result = semantic_revalidate(run, calibration, self.root / "semantic-clean-repair-output",
                                     client=client, config={"batch_size": 1})
        self.assertTrue(result["ok"])
        self.assertEqual(2, client.calls)

    def test_blind_selector_uses_unexcluded_candidates_without_word_hardcoding(self):
        run = self.build("blind-selector")
        candidate = self.canonical_preserving_candidate(run)
        (run / "output" / "accepted" / "0001_test.json").write_text(json.dumps(candidate), encoding="utf-8")
        output = self.root / "blind.json"
        selected = build_blind_calibration(run, [], output, 1)
        self.assertEqual("blind_audit", selected["mode"])
        self.assertEqual([1], [word["seq"] for word in selected["words"]])
        self.assertTrue(output.exists())

    def test_non_string_model_content_retries_without_crashing(self):
        run = self.build("non-string")
        good = self.canonical_preserving_candidate(run)
        client = QueueClient([None, json.dumps(good)])
        result = run_worker(run, client, ignore_resources=True)
        self.assertEqual(1, result["counts"]["accepted"])
        self.assertEqual(2, client.calls)

    def test_three_bad_attempts_quarantine(self):
        run = self.build()
        client = QueueClient(["{", "[]", "{}"])
        result = run_worker(run, client, ignore_resources=True)
        self.assertEqual(3, client.calls)
        self.assertEqual(1, result["counts"]["quarantine"])
        files = list((run / "output" / "quarantine").glob("*.json"))
        self.assertEqual(1, len(files))
        self.assertIn("errors", json.loads(files[0].read_text(encoding="utf-8")))

    def test_resume_does_not_generate_accepted_word_twice(self):
        run = self.build()
        good = self.canonical_preserving_candidate(run)
        first = QueueClient([json.dumps(good)])
        run_worker(run, first, ignore_resources=True)
        second = QueueClient([])
        result = run_worker(run, second, ignore_resources=True)
        self.assertEqual(0, second.calls)
        self.assertEqual(1, result["counts"]["accepted"])
        self.assertEqual(1, len(list((run / "output" / "accepted").glob("*.json"))))
        self.assertTrue(verify_result(run)["ok"])

    def test_checksum_tamper_stops_before_model(self):
        run = self.build()
        with (run / "input" / "prompt.txt").open("a", encoding="utf-8") as handle:
            handle.write("tamper")
        client = QueueClient([])
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            run_worker(run, client, ignore_resources=True)
        self.assertEqual(0, client.calls)

    def test_config_tamper_stops_before_model(self):
        run = self.build()
        config_path = run / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["temperature"] = 0.9
        config_path.write_text(json.dumps(config), encoding="utf-8")
        client = QueueClient([])
        with self.assertRaisesRegex(ValueError, "config checksum mismatch"):
            run_worker(run, client, ignore_resources=True)
        self.assertEqual(0, client.calls)

    def test_canonical_good_ranks_are_immutable(self):
        run = self.build()
        record = self.record(run)
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][0]["sentence"] = "Patience tests us all."
        errors = validate_candidate(candidate, record)
        self.assertIn("rank 1: valid canonical rank changed", errors)

    def test_compaction_exposes_only_one_safe_generation_profile(self):
        senses = [
            {"id": index, "pos": "noun", "gloss": f"noun {index}", "tags_json": "[]", "source_name": "fixture"}
            for index in range(1, 31)
        ]
        senses += [
            {"id": 100, "pos": "verb", "gloss": "common verb", "tags_json": "[]", "source_name": "fixture"},
            {"id": 101, "pos": "adj", "gloss": "old adjective", "tags_json": '["archaic"]', "source_name": "fixture"},
        ]
        compact = compact_evidence({"headword": "test", "senses": senses, "forms": [], "examples": []}, [], None)
        self.assertEqual([1], [sense["id"] for sense in compact["senses"]])
        self.assertEqual({"sense_id": 1, "pos": "noun", "target": "test", "gloss": "noun 1", "exact_target": False}, compact["safe_profile"])

    def test_compaction_keeps_bad_canonical_evidence_but_filters_bad_fillers(self):
        evidence = {
            "headword": "test",
            "senses": [
                {"id": 1, "pos": "verb", "gloss": "common", "tags_json": "[]", "source_name": "fixture"},
                {"id": 2, "pos": "verb", "gloss": "old", "tags_json": '["obsolete"]', "source_name": "fixture"},
                {"id": 3, "pos": "verb", "gloss": "niche", "tags_json": '["Internet"]', "source_name": "fixture"},
            ],
            "forms": [
                {"form_text": "tests", "pos": "verb", "tags_json": "[]", "source_name": "fixture"},
                {"form_text": "testeth", "pos": "verb", "tags_json": '["archaic"]', "source_name": "fixture"},
                {"form_text": "test-net", "pos": "verb", "tags_json": '["Internet"]', "source_name": "fixture"},
            ],
            "examples": [],
        }
        canonical = [{"rank": 1, "sense_id": 2, "pos": "verb", "target": "testeth", "memorable": 1, "sentence": "A judge testeth it."}]
        compact = compact_evidence(evidence, canonical, None)
        self.assertIn(2, {sense["id"] for sense in compact["senses"]})
        self.assertNotIn(3, {sense["id"] for sense in compact["senses"]})
        self.assertIn("testeth", {form["form_text"] for form in compact["forms"]})
        self.assertIn("test-net", {form["form_text"] for form in compact["forms"]})

    def test_validation_rejects_explicitly_restricted_sense_and_form(self):
        run = self.build()
        record = self.record(run)
        record["evidence"]["senses"].append({
            "id": 12, "pos": "verb", "gloss": "old sense", "tags_json": '["obsolete"]',
            "source_name": "fixture",
        })
        record["evidence"]["forms"].append({
            "form_text": "testeth", "pos": "verb", "tags_json": '["archaic"]',
            "source_name": "fixture",
        })
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1].update({"sense_id": 12, "target": "testeth", "sentence": "The old rule testeth our patience."})
        errors = validate_candidate(candidate, record)
        self.assertTrue(any("learner-unsuitable sense (obsolete)" in error for error in errors))
        self.assertTrue(any("learner-unsuitable target form (archaic)" in error for error in errors))

    def test_domain_and_variant_tags_are_not_automatically_restricted(self):
        evidence = {
            "headword": "website",
            "senses": [{"id": 1, "pos": "noun", "gloss": "a site on the web", "tags_json": '["Internet", "alt-of"]', "source_name": "fixture"}],
            "forms": [], "examples": [],
        }
        compact = compact_evidence(evidence, [], None)
        self.assertEqual("preferred", compact["senses"][0]["learner_suitability"])
        self.assertEqual(1, compact["safe_profile"]["sense_id"])

    def test_core_number_sense_beats_earlier_niche_noun(self):
        evidence = {
            "headword": "thirty",
            "senses": [
                {"id": 1, "pos": "noun", "gloss": "a 30-second commercial", "tags_json": "[]", "source_name": "fixture"},
                {"id": 2, "pos": "num", "gloss": "the number 30", "tags_json": "[]", "source_name": "fixture"},
            ],
            "forms": [], "examples": [],
        }
        compact = compact_evidence(evidence, [], 1)
        self.assertEqual({"sense_id": 2, "pos": "num", "target": "thirty", "gloss": "the number 30", "exact_target": False}, compact["safe_profile"])

    def test_core_article_sense_beats_earlier_adverb(self):
        evidence = {
            "headword": "the",
            "senses": [
                {"id": 1, "pos": "adv", "gloss": "with a comparative", "tags_json": "[]", "source_name": "fixture"},
                {"id": 2, "pos": "article", "gloss": "the definite article", "tags_json": "[]", "source_name": "fixture"},
            ],
            "forms": [], "examples": [],
        }
        compact = compact_evidence(evidence, [], 1)
        self.assertEqual({"sense_id": 2, "pos": "article", "target": "the", "gloss": "the definite article", "exact_target": False}, compact["safe_profile"])

    def test_learner_example_support_beats_unconfirmed_rank_one(self):
        evidence = {
            "headword": "coach",
            "senses": [
                {"id": 1, "pos": "noun", "gloss": "a horse-drawn vehicle", "tags_json": "[]", "source_name": "fixture"},
                {"id": 2, "pos": "noun", "gloss": "a trainer or instructor", "tags_json": "[]", "source_name": "fixture"},
            ],
            "forms": [],
            "examples": [
                {"pos": "noun", "sense_gloss": "a trainer or instructor", "example_text": f"Coach example {index}",
                 "example_type": "example", "source_name": "fixture"}
                for index in range(5)
            ],
        }
        canonical = [{"rank": 1, "sense_id": 1, "pos": "noun", "target": "coach", "memorable": 1,
                      "sentence": "The horse pulled the coach."}]
        compact = compact_evidence(evidence, canonical, None)
        self.assertEqual(2, compact["safe_profile"]["sense_id"])

    def test_lexical_sense_beats_unconfirmed_form_of_fallback(self):
        evidence = {
            "headword": "clothing",
            "senses": [
                {"id": 1, "pos": "verb", "gloss": "present participle of clothe",
                 "tags_json": '["form-of", "participle", "present"]', "source_name": "fixture"},
                {"id": 2, "pos": "noun", "gloss": "articles worn on the body", "tags_json": "[]", "source_name": "fixture"},
            ],
            "forms": [], "examples": [],
        }
        canonical = [{"rank": 1, "sense_id": 1, "pos": "verb", "target": "clothing", "memorable": 1,
                      "sentence": "She is clothing the baby."}]
        compact = compact_evidence(evidence, canonical, None)
        self.assertEqual(2, compact["safe_profile"]["sense_id"])

    def test_curated_override_beats_harder_early_sense(self):
        evidence = {
            "headword": "thanks",
            "senses": [
                {"id": 1, "pos": "noun", "gloss": "an expression of gratitude", "tags_json": "[]", "source_name": "fixture"},
                {"id": 67932, "pos": "intj", "gloss": "used to express gratitude", "tags_json": "[]", "source_name": "fixture"},
            ],
            "forms": [], "examples": [],
        }
        compact = compact_evidence(evidence, [], 1)
        self.assertEqual(67932, compact["safe_profile"]["sense_id"])

    def test_thing_override_requires_exact_headword(self):
        evidence = {
            "headword": "thing",
            "senses": [{"id": 41267, "pos": "noun", "gloss": "an individual object", "tags_json": "[]", "source_name": "fixture"}],
            "forms": [], "examples": [],
        }
        compact = compact_evidence(evidence, [], None)
        self.assertTrue(compact["safe_profile"]["exact_target"])

    def test_determiner_must_modify_a_noun_phrase(self):
        run = self.build("det-function")
        record = self.record(run)
        record["evidence"]["safe_profile"].update({"pos": "det", "target": "this"})
        record["evidence"]["senses"][0]["pos"] = "det"
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1].update({"pos": "det", "target": "this", "sentence": "This is easy."})
        errors = validate_candidate(candidate, record)
        self.assertIn("rank 2: determiner target does not directly modify a noun phrase", errors)

    def test_their_requires_explicit_plural_owner(self):
        run = self.build("their-owner")
        record = self.record(run)
        record["evidence"]["safe_profile"].update({"pos": "det", "target": "their"})
        record["evidence"]["senses"][0]["pos"] = "det"
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1].update({"pos": "det", "target": "their", "sentence": "She saw their dog near the park."})
        self.assertTrue(any("no explicit plural owner antecedent" in error for error in validate_candidate(candidate, record)))

    def test_observed_unsafe_trivia_is_rejected(self):
        run = self.build("trivia")
        record = self.record(run)
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1]["sentence"] = "The flag of the United States has thirteen stars during this test."
        self.assertTrue(any("unsupported factual trivia" in error for error in validate_candidate(candidate, record)))

    def test_editable_rank_must_use_safe_pos_and_headword(self):
        run = self.build("safe-profile")
        record = self.record(run)
        record["evidence"]["senses"].append({
            "id": 12, "pos": "noun", "gloss": "an examination", "tags_json": "[]",
            "source_name": "fixture", "learner_suitability": "preferred", "restriction_tags": [],
        })
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1].update({"sense_id": 12, "pos": "noun", "target": "test", "sentence": "The test was easy."})
        self.assertIn("rank 2: must use the safe generation profile", validate_candidate(candidate, record))
        candidate["rows"][1].update({"sense_id": 11, "pos": "verb", "target": "tests", "sentence": "The teacher tests us."})
        self.assertNotIn("rank 2: must use the safe generation profile", validate_candidate(candidate, record))

    def test_editable_rank_allows_supported_alternate_sense_in_safe_pos(self):
        run = self.build("safe-alternate")
        record = self.record(run)
        record["evidence"]["senses"].append({
            "id": 12, "pos": "verb", "gloss": "to challenge", "tags_json": "[]",
            "source_name": "fixture", "learner_suitability": "preferred", "restriction_tags": [],
        })
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1].update({"sense_id": 12, "pos": "verb", "target": "test", "sentence": "Difficult days test our patience."})
        self.assertNotIn("rank 2: must use the safe generation profile", validate_candidate(candidate, record))

    def test_prompt_payload_names_editable_ranks_and_safe_profile(self):
        run = self.build("explicit-editable")
        record = self.record(run)
        payload = json.loads(word_prompt(record, "audit_repair", [], None))
        self.assertEqual([2], payload["editable_ranks"])
        self.assertEqual(record["evidence"]["safe_profile"], payload["safe_profile"])
        self.assertEqual([1, 3, 4, 5], [row["rank"] for row in payload["locked_canonical"]])

    def test_prompt_hides_canonical_when_all_ranks_are_editable(self):
        run = self.build("hide-editable")
        record = self.record(run)
        record["deterministic_errors"] = ""
        payload = json.loads(word_prompt(record, "audit_repair", [], None))
        self.assertEqual([1, 2, 3, 4, 5], payload["editable_ranks"])
        self.assertEqual([], payload["locked_canonical"])

    def test_prompt_prefers_reliable_common_reuse_over_forced_coverage(self):
        self.assertIn("Reliability is more important than sense coverage", PROMPT)
        self.assertIn("sense diversity is not a goal", PROMPT)
        self.assertIn("silently verify each sentence against the exact gloss", PROMPT)
        self.assertIn("unverifiable trivia", PROMPT)

    def test_global_deterministic_error_allows_all_ranks_to_change(self):
        run = self.build("global-error")
        record = self.record(run)
        record["deterministic_errors"] = "English sentences must be unique | rank 2: placeholder sentence"
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][0]["sentence"] = "Patience tests us all."
        self.assertNotIn("rank 1: valid canonical rank changed", validate_candidate(candidate, record))

    def test_mixed_rank_types_are_rejected_without_crashing(self):
        run = self.build()
        record = self.record(run)
        candidate = self.canonical_preserving_candidate(run)
        candidate["rows"][1]["rank"] = "2"
        errors = validate_candidate(candidate, record)
        self.assertTrue(any("rank must be an integer" in error for error in errors))

    def test_generate_manifest_uses_its_own_schema(self):
        manifest = self.root / "generate.txt"
        manifest.write_text(
            "# seq\tsource_rank\tword_id\theadword\tcefr\tprimary_sense_id\tprimary_pos\n"
            "1\t1\t1\ttest\tA2\t11\tverb\n",
            encoding="utf-8",
        )
        run = self.root / "generate-run"
        build_run(run, self.db, manifest, self.drafts, 1, 1, mode="generate")
        record = self.record(run)
        self.assertEqual(1, record["source_rank"])
        self.assertEqual("", record["source_file"])
        self.assertEqual("", record["deterministic_errors"])
        self.assertEqual(11, record["primary_sense_id"])
        self.assertEqual("verb", record["primary_pos"])

    def test_review_reports_exclude_completed_words(self):
        reports = self.root / "reports"; reports.mkdir()
        (reports / "sol_review_0001_0001.tsv").write_text("test\tpass\talready reviewed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no unreviewed words"):
            build_run(self.root / "excluded", self.db, self.manifest, self.drafts, 1, 1, review_report_dir=reports)


if __name__ == "__main__":
    unittest.main()
