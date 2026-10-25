# Production corpus status

Updated: 2026-10-25 (Asia/Bangkok)

## Current state

The reviewed 2,967-word corpus is in production. The promoted run is
`staging/production_pipeline/20261025-161951-16260`; its `manifest.json`
records the input paths and SHA-256 hashes. Both production databases match
those hashes and carry `content_version=4`:

- `data/content_v2.db`: 2,967 words, 6,306 senses, 8,607 forms, 14,835
  example sentences, 16,886 related-word rows, 83 authored relation groups.
- `vocab_app/assets/seed/vocab.db`: the exported, content-only app seed with
  the same 2,967 words and 14,835 sentences.

English review gate: `2967/2967`, `errors=0`; 2,606 words use reviewed
overlays and 361 intentionally retain canonical content. All 14,835 sentence
translations came from the selected Azure path (mostly cache; no DeepL
fallback in the completed run). Thai metadata staging contains 2,837 new
readings and 6,076 new sense meanings, supplementing authored rows. The
explanation merge manifest reports 13,472 exactly bound reused explanations,
1,363 freshly generated explanations, zero pending and zero quarantined.

## Verification and promotion gates

- Reviewed English snapshot and translation dry-run: 2,967 words / 14,835
  sentences, no parse errors or invalid rows.
- Prepared Thai content verified against the current English fields; no stale
  sentence explanations accepted.
- `tools/validate_content_db.py` on staged and production content:
  `checks failed: 0`, `problems: 0`.
- Full-scope row-count and no-test-only gates passed for staged content and
  seed. The staged seed passed the playable and SQLite reseed tests before
  promotion. Production DB and seed hashes match the run manifest.
- Full Flutter test suite passes, including upgrade from the actual shipped
  130-word version-2 fixture. Python unit suite: 132 passed.
- Reviewed corrections: 115 sentence records, eight source-sense meanings,
  and three word readings; all match the generated artifact.
- Cloze boundaries checked across all 14,835 sentences: zero partial-word
  blanks after correcting the builder. SQLite integrity and foreign keys pass.

## Editorial review and release

Three disjoint samples covered 75 words, 157 senses, and 375 examples. Additional
searches checked 105 explanation-template candidates and cross-reference
patterns. Required findings from these reviews were corrected and independently
rechecked against a real version-4 candidate by the review sub-agent. This is
AI editorial review, not human review of the entire corpus.

Durable fixes live in `content/editorial_corrections.json`. The builder applies
them only when the original English and relevant source gloss/POS still match;
otherwise it fails. The production runner and package verifier check that every
reviewed field survives rebuilding/exporting. Version 4 triggers content reseed
for existing version-3 installations while preserving player progress.

Released **Esh 1.0.2 / build-2** from commit
`385872ee4bfc865ce5c674046487d84c85ab69d5`:

- [Published IPA and seed manifest](https://github.com/pimdejvani/Esh_Learner/releases/tag/build-2).
- [iOS CI run 40211549234](https://github.com/pimdejvani/Esh_Learner/actions/runs/40211549234):
  Flutter tests/analysis, native first installation and reseeding on an iPhone
  simulator, unsigned device build, packaged-seed gate, and publication all passed.
- [Vocabulary CI run 40211549223](https://github.com/pimdejvani/Esh_Learner/actions/runs/40211549223):
  passed after publishing the previously missing
  [review-only evidence asset](https://github.com/pimdejvani/Esh_Learner/releases/tag/vocab-evidence-v1).
- Downloaded the published IPA again and inspected its embedded SQLite seed:
  2,967 words, 14,835 sentences, version 4. Its seed hash matches the committed
  seed and published `seed-manifest.json`:
  `6c7de6196a0ad5eef872cc56119441a5186ff1b6bbaafa43328fc67584cb6b14`.
- IPA SHA-256:
  `4a376a55c3a952298a21037018faa956ef9c70955808bbf8c57e96c3739fe23f`;
  size 11,779,139 bytes, matching the generated SideStore `apps.json` for 1.0.2.

The simulator test uses actual iOS asset, filesystem, path-provider, and SQLite
plugins. The host regression separately upgrades the actual 130-word version-2
seed fixture and verifies retained reviews/settings. No physical-phone install
was performed in this workspace. The unsigned IPA is delivered through the
existing SideStore signing/installation workflow documented in README.md.

The app now builds Odd One Out rounds only from explainable authored groups
when groups exist. Words too short or otherwise unable to form a useful
scramble route to Dictation. This avoids assumptions that held only in the
earlier 100-word pilot.

## Re-run or continue

To rebuild from the completed staged Thai content without paying for another
translation run:

```powershell
python tools/run_production_after_review.py --prepared-translated-dir staging/production_finish_20260917/explanations_flash/merged --thai-dir staging/production_finish_20260917/content_th
```

The runner creates a new staging run, validates the whole corpus, tests the
staged seed, and promotes both databases only after every gate passes. To
translate fresh instead, omit `--prepared-translated-dir`; Azure is the
default provider, with bounded concurrent batches and a failure circuit.

## Remaining quality caveat

The recorded review gate measures manifest/overlay consistency and source
attestation; structural tests do not prove semantic correctness. All required
findings from the reviewed samples and targeted searches have been resolved,
but the entire 2,967-word corpus has not been individually read by a human or
semantically audited sentence by sentence. Do not describe it as fully
human-reviewed or error-free. Preserve the original version-3 findings in the
quality report for provenance; their resolution is the guarded version-4 data.
