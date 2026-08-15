# RE Vocab — Continuation Guide

## Current objective

**Updated 2026-08-13.** The pilot phase is done: 100 real words plus a 30-word
hard test set are built, validated and shipped into the app seed as content
schema v2, and the app reads them (see `done_vocab.md` and `after_revocab.md`).
The app is no longer off-limits — content v2 and the Flutter layer moved together.

The next content objective is the **remaining corpus**: generate the 969
headwords in `data/terra_missing_manifest.txt`.  The manifest is the only
authority for Terra assignments; do not select ranges directly from the DB.

The user wants Terra/Codex generation only — never Gemini or another external
generation API.  Use the smallest practical token format for drafts.

## Current data state

- Source DB: `data/vocabulary_source.db`
- Source list: 2,967 unique Oxford-list headwords, all harvested successfully
- Normalized evidence currently includes source senses, forms, pronunciations,
  Thai translation candidates, and source examples.
- Source collection command: `python tools/build_vocab_library.py validate`
- Source collector: `tools/build_vocab_library.py`
- Existing app and unrelated worktree edits must remain untouched.

## Generated content state

- Canonical draft directory: `data/terra_english_drafts/`
- Canonical coverage: 2,967 unique headwords, 0 duplicate headwords, 0 parse errors
- Terra missing manifest: completed 969/969, remaining 0
- JSON, compact and retired legacy directories were consolidated and deleted on
  2026-08-13.  Do not recreate those parallel draft stores.
- Sol review manifest: `data/sol_review_manifest.txt` (2,967 words; 725
  deterministic-failure priority, then 2,242 semantic-audit priority)
- Source-fidelity validator: `tools/validate_vocab_generation.py`
- Generated-table contract: `tools/generate_source_cloze.py`
- **Content validator (schema v2): `tools/validate_content_db.py`** — the one that
  catches content a learner cannot use, not just content the source disagrees with
- Consolidation report: `data/draft_consolidation_report.txt`

Rebuild the immutable missing-word manifest:

```powershell
python tools/build_missing_draft_manifest.py
```

## Required generation format from now on

Do not use full JSON drafts for new generation. Terra now writes the six-field
English-only format documented in `terra_english_format.md`: one `@ headword`
header followed by five tab-separated sentence rows. Each row uses a numeric
`sense_id`, so the long dictionary gloss and all Thai text are omitted from
model output. `tools/translate_vocab_content.py` validates those facts against
the source DB, translates the accepted rows, and writes the eight-field compact
format to a separate directory without changing the source drafts.

The compact importer is implemented at `tools/import_terra_compact.py`. It:

1. Read translated eight-field files from `data/terra_translated_drafts/*.txt`.
2. Parse the header plus eight tab-separated fields per sentence.
3. Group five rows per headword.
4. Convert them to the existing generated-sentence table format.
5. Use the existing source-grounded validation logic before saving.
6. Be idempotent and require no API key, Gemini package, or network call.
7. Store failures as `failed`; continue importing later drafts.

The draft generator must use only the normalized source values:

- POS and `sense_gloss` must be exact DB values.
- `cloze_target` must be the headword or a source-supported form for that POS.
- Each headword has 5 unique lines/ranks 1–5; rank 1 is a memorable contextual
  sentence, not necessarily dramatic, and rank 2 must be an unambiguous Cloze.
- Terra does not write Thai. Azure Translator F0 is the primary translator;
  DeepL is the context-aware repair provider. Translation results are cached in
  `data/translation_cache.db` so identical work never consumes quota twice.

## Process order (locked)

1. Generate English-only Terra `.txt` drafts for every headword that does not yet
   have a completed five-sentence draft. **Do not import them to SQLite during
   this first pass.**
2. After all 2,967 first-pass drafts exist, parse every English draft and run
   deterministic validation in memory. Create a manifest of failed words.
3. Use `gpt-5.6-sol` medium subagents to review and repair that complete
   manifest. Do not start Sol while headwords are still missing.
4. Re-parse and validate the complete English corpus.
5. Translate accepted English sentences with Azure, then DeepL for failures;
   keep production and the 30 test-only words in separate directories/DBs.
6. Use `gpt-5.6-sol` medium to audit remaining translation/context failures.
7. Combine all compact drafts into one JSON export, preserving source IDs and
   validation status.  Then import the finalized JSON into SQLite in one build
   step.
8. Only after content is finalized, design/apply a separate extraction/export
   step for Flutter.  Do not modify `vocab_app` during this work.

## Commands and checks

Source integrity:

```powershell
python tools/build_vocab_library.py validate
```

Validate English-only drafts without using an API key or writing output:

```powershell
python tools/translate_vocab_content.py --input-dir data/terra_english_drafts --dry-run
```

Validate one Terra batch against its exact immutable assignment:

```powershell
python tools/validate_english_draft_batch.py data/terra_english_drafts/terra_missing_0001_0025.txt --seq-start 1 --seq-end 25
```

Translate after credentials have been added to `.env`:

```powershell
python tools/translate_vocab_content.py --input-dir data/terra_english_drafts
```

Validate already-imported output (after generation; do not make it block
first-pass generation):

```powershell
python tools/validate_vocab_generation.py --entry-table generation --run-id terra-source-cloze-v1 --status passed
```

## Cautions

- `re vocab.md` is the governing source-first policy.
- The 2,967 count is the unique-word count in the Oxford source used by this
  project; do not invent 33 words merely to make the number 3,000.
- Preserve all existing unrelated git changes.
- Every Terra assignment must use disjoint `seq` ranges from
  `data/terra_missing_manifest.txt`, with at most 25 words per agent turn.
- Terra generation does not access `.env`; only the translation step reads
  `AZURE_TRANSLATOR_KEY`/`AZURE_TRANSLATOR_REGION` and optional
  `DEEPL_AUTH_KEY`.
- The current parallel limit is 4 total agents, so use at most 3 Terra
  generators alongside the root agent.
