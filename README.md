# Esh

An offline English/Thai vocabulary trainer for iPhone. Words are scheduled with
FSRS spaced repetition and practised through seven game types (flashcards,
cloze, dictation, matching, odd-one-out, word association, scramble) rather than
a single review screen.

Everything runs on-device. There is no account, no server, and no network call
at runtime — the vocabulary ships as a SQLite seed inside the app bundle and the
UI font is bundled rather than fetched.

The current build ships **130 words** (386 senses, 650 example sentences, 526
related words) as a first real-device test set.

## Layout

| Path | What it is |
|---|---|
| `vocab_app/` | The Flutter app |
| `tools/` | Python pipeline that generates the vocabulary and exports the app seed |
| `config/` | Pipeline policy files (e.g. `grammar_explanation_policy_v4.json`) |
| `data/` | Local pipeline input — mostly **not** in git (383 MB, rebuildable via `tools/`); the generated English drafts and their review trail are the tracked exception |
| `staging/` | Run-scoped review/production candidates — local only, not in git |
| `docs/` | All documentation (see below) |

---

## Documentation index

Docs were consolidated and restructured on **2026-09-05**: everything moved out
of the repo root into `docs/`, grouped by subject, and eight superseded
re-vocab/pilot-era files were merged into a single legacy archive. Nothing was
deleted — the historical text is preserved verbatim inside the archive.

### Start here

| Doc | What it answers |
|---|---|
| [`docs/NOTES.md`](docs/NOTES.md) | **The build log.** Chronological record of what was actually built, which data sources were used vs. approximated, what is deferred, and every deviation from the spec with its reasoning. Newest entries at the bottom. Read this first to understand how the project reached its current state. |
| [`docs/pipeline/PRODUCTION.md`](docs/pipeline/PRODUCTION.md) | **Where production stands.** Answers three questions: where things are now, what is left, and exactly what to run / edit / configure to continue. |

### The app

| Doc | What it answers |
|---|---|
| [`docs/app/SPEC.md`](docs/app/SPEC.md) | Full product & technical spec (Thai). Phased build plan, data model, screen-by-screen behaviour, and the rules each of the seven games follows. |
| [`docs/app/ALGORITHM.md`](docs/app/ALGORITHM.md) | Single source of truth for every number the app rolls, weights, or selects — randomness, word importance, FSRS scheduling, and word selection per game — each with the code location that implements it. |

### Content pipeline

| Doc | What it answers |
|---|---|
| [`docs/pipeline/next_grammar.md`](docs/pipeline/next_grammar.md) | **Current working authority for the grammar-explanation review.** Scope, the review rules, the per-row gate, and the hard constraints (no auto-promote, a validator pass is not a semantic pass, reviewed > legacy precedence). |
| [`docs/pipeline/PLAN_CONTENT_PIPELINE.md`](docs/pipeline/PLAN_CONTENT_PIPELINE.md) | Why sentence generation, translation, and grammar explanation are three separate jobs with three different cost profiles — and which engine each one belongs on. |
| [`docs/pipeline/grammar/GRAMMAR_EXPLANATION_LLM_SPEC.md`](docs/pipeline/grammar/GRAMMAR_EXPLANATION_LLM_SPEC.md) | The local-LLM pipeline that writes `example_sentences.explanation_th`: prompt contract, validation gates, and promotion rules. |
| [`docs/pipeline/grammar/GRAMMAR_EXPLANATION_IMPROVEMENT_LOG.md`](docs/pipeline/grammar/GRAMMAR_EXPLANATION_IMPROVEMENT_LOG.md) | Per-version record of what each prompt change was meant to fix and what it actually did — kept so prompts are not tuned from memory of one-off results. |
| [`docs/pipeline/qwen/LOCAL_QWEN_VOCAB_WORKFLOW.md`](docs/pipeline/qwen/LOCAL_QWEN_VOCAB_WORKFLOW.md) | Authority on the data and review side of local-Qwen generation: corpus status, what counts as done, and the review handoff. |
| [`docs/pipeline/qwen/LOCAL_QWEN_VALIDATION_AND_SERVER.md`](docs/pipeline/qwen/LOCAL_QWEN_VALIDATION_AND_SERVER.md) | Operational manual: where the files live, which command validates what, how to reach the VM, and how to call the local LLM API. |

### Data formats

| Doc | What it answers |
|---|---|
| [`docs/formats/terra_compact_format.md`](docs/formats/terra_compact_format.md) | The 8-field tab-separated draft format (rank, sense_id, pos, target, emotional, English sentence, Thai translation, Thai explanation) used by the generation and merge tools. **Live format — still enforced by the tools.** |
| [`docs/formats/terra_english_format.md`](docs/formats/terra_english_format.md) | The English-only draft variant, used when an agent should produce sentences without spending tokens on Thai. |

### Legacy

| Doc | What it answers |
|---|---|
| [`docs/legacy/REVOCAB_PILOT_2026-08.md`](docs/legacy/REVOCAB_PILOT_2026-08.md) | **Archive, not instructions.** Eight superseded docs from the re-vocab / pilot era (Aug 2026) merged into one file, each kept verbatim under its own `[ARCHIVED n/8]` heading: `re vocab.md`, `continue_revocab.md`, `after_revocab.md`, `done_vocab.md`, `test.md`, `terra_subagent.md`, `sol_subagent.md`, `CONTINUE_VOCAB_PROMPT.md`. Useful for tracing where a decision or a dataset came from; do not follow it as current procedure. |

---

## Running it during development

Requires Flutter 3.44.4 stable.

```bash
cd vocab_app && flutter run -d windows
```

On web and desktop the app draws itself inside a fixed 390x844 iPhone-sized
frame so the layout matches the phone. On iOS that wrapper is not applied.

Tests and analysis:

```bash
cd vocab_app && flutter analyze && flutter test
```

## How a build reaches the phone

There is no Mac and no paid Apple Developer account in this pipeline.
`.github/workflows/ios-build.yml` runs on every push to `master`:

1. **flutter-tests** (Linux) — `flutter analyze` and `flutter test`.
2. **build-ios** (macOS runner) — `flutter build ios --release --no-codesign`,
   then packages `Runner.app` into `Payload/` and zips it as `Esh.ipa` by hand,
   because without a signing identity `xcodebuild -exportArchive` cannot run.
3. **publish** (Linux) — attaches the IPA to a `build-<run number>` GitHub
   Release and regenerates `apps.json`, the SideStore source manifest.

The app version is the CI run number (`1.0.<run>`), so every push is strictly
newer than the last and the phone sees an update without any manual version bump.

The IPA is unsigned; **SideStore re-signs it on the phone** with a free Apple ID.
That is what removes the $99 Apple Developer requirement, at the cost of a
re-sign every 7 days.

## Installing on an iPhone from Windows

One-time setup:

1. Install **Apple Devices** from the Microsoft Store (it provides the USB
   device service) and **iloader**.
2. Use iloader to install **SideStore**, signing in with a free Apple ID.
3. On the phone: trust the developer app under Settings → General → VPN &
   Device Management, enable Developer Mode, and connect **LocalDevVPN**.
4. In SideStore → Sources → add:
   ```
   https://raw.githubusercontent.com/pimdejvani/Esh_Learner/master/apps.json
   ```
5. Install Esh from the **Browse tab** — not from a downloaded file, or it will
   not auto-update.
6. Turn on Background App Refresh so SideStore can re-sign before the 7-day
   signature expires.

After that, pushing to `master` is enough: CI builds, releases, and updates the
source, and the phone offers the new version.

## Regenerating the vocabulary

The seed at `vocab_app/assets/seed/vocab.db` is produced by the `tools/` chain:

```bash
python tools/build_vocab_library.py
python tools/select_pilot_100.py
python tools/build_content_db.py
python tools/translate_vocab_content.py
python tools/validate_content_db.py
python tools/export_app_seed.py
```

The current seed is the 100-word pilot set plus a 30-word hard fixture used for
testing. Before any release beyond personal use, re-export without the fixture
(`export_app_seed.py` without `--include-test-words`); the fixture's origin and
purpose are recorded in
[`docs/legacy/REVOCAB_PILOT_2026-08.md`](docs/legacy/REVOCAB_PILOT_2026-08.md) §5
(formerly `test.md`).

## Licence note

The bundled UI font, Plus Jakarta Sans, is under the SIL Open Font License —
see `vocab_app/assets/fonts/OFL.txt`.
