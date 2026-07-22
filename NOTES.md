# NOTES — Phase 1 build log

Working dir: `C:\Users\pimde\Desktop\pimdej\English`. This is the single doc to read to
understand what happened. It covers: what data sources were actually used vs.
approximated, what's built/tested, what's explicitly deferred to Phase 2/3, and
deviations from SPEC.md with reasoning.

**Update (2026-07-22):** the A/B test mentioned below (`tools/model_compare.py`,
results in `tools/model_compare_results/`) is done and its winner
(`gemini-3.6-flash`) has been integrated — see the `example_sentences` row in
the table in section 1 and section 4 for the full account. The paragraph
below is kept as-written for history (it describes the state *before* that
integration); don't take "possibly replace" as still open.

~~A parallel effort (run separately, not by this build) is A/B-testing 3 Gemini
models on the "generate 5 QC-standard sentences + grammar note" task, to
possibly replace the templated `example_sentences`/`grammar_note_th` content
below with LLM-generated content. That is a follow-up, independent of
everything in this document.~~

---

## 1. Dataset (`tools/`, output `vocab_app/assets/seed/vocab.db`)

Run with `python tools/build_dataset.py` (rerunnable, idempotent — rebuilds
the DB from scratch each time). Produces 160 words (target was ~150; slightly
over to have headroom for POS variety) covering Oxford 3000 A1 band.

### What's REAL / sourced vs. what's APPROXIMATED — be precise here:

| Field | Status | Detail |
|---|---|---|
| Headwords + POS + CEFR band | **Approximated, not machine-fetched** | `tools/wordlist.py`. Could not reliably batch-pull the official OUP Oxford 3000/5000 PDF or a GitHub CSV mirror through the tools available in this session. The 160 words are the well-documented, publicly known Oxford 3000 A1 core-beginner set, typed in by hand with POS tags. **Action item for a future pass:** replace `wordlist.py`'s `WORDS` list with a direct parse of the official OUP source — the rest of the pipeline doesn't need to change, it's a pure data swap. |
| `meaning_th` (Thai gloss), `thai_reading`, `ipa`, `collocation_en/th`, `countable` | **Hand-authored by the build author (Claude), not fetched from Wiktionary** | `tools/thai_data.py`. Could not reliably batch-fetch and parse 160 individual `en.wiktionary.org/wiki/<word>` pages within this session. Per SPEC.md §5 ("LLM/คน ทำแค่เลือก sense, จัด rank, mark is_core + เกลาให้กระชับ — ไม่ใช่แปลใหม่") this is explicitly an allowed human/LLM role, but the base data here was composed directly from standard EN-TH dictionary knowledge rather than traced to a specific fetched Wiktionary page. `words.translation_source` is deliberately stored as `"Wiktionary (approximated)"` (not a clean `"Wiktionary"`) so this distinction is visible in the DB itself, not just in this doc. **Action item:** swap in real Wiktionary-fetched glosses per word; the schema and pipeline already have the right shape for it. |
| `word_forms.form_text`/`form_type`/`is_irregular` | **Rule-generated (regex-based inflection rules + irregular-verb/plural lookup tables), unchanged** | `build_dataset.py` (`regular_past`, `ving`, `s3sg`, `plural`, `comparative`, `IRREGULAR_VERBS`, `IRREGULAR_PLURALS`). The inflected *forms themselves* are still computed this way for all 160 words (this part was never the flagged gap — see next row for `grammar_note_th`, which now mostly comes from the LLM instead). |
| `example_sentences` (5/word) + `word_forms.grammar_note_th` | **Real gemini-3.6-flash-generated content for 151/160 words** (was: template placeholders + mechanical per-form notes) | `tools/llm_sentences.py`, sourced from `tools/model_compare_results/gemini-3.6-flash_round1.json` (a complete 160/160-word run) via `tools/_gen_llm_sentences.py`. `build_dataset.py`'s `build_sentences()` prefers this dataset per headword — for a hit, it also overwrites `grammar_note_th` on every `word_forms` row for that word with the LLM's one richer paragraph (which already explains the reasoning across all 5 sentences' forms, in the SPEC §9.2 "explain why" style) instead of the old mechanical per-form template sentence. Falls back to the old `SENT_TEMPLATES` + rule-based note mechanism only when a word is missing from `llm_sentences.py`. **Model selection:** 3 Gemini models were A/B-tested 2 rounds each over the full 160-word list against the SPEC §5 QC rules (`tools/model_compare.py`) — `gemini-2.5-flash-lite` turned out to be a dead/retired model (404s), `gemini-3.5-flash-lite` is cheap ($0.18/run) but only hit 34–56% "≥3 distinct inflected forms per word" compliance, `gemini-3.6-flash` cost more ($0.40–0.58/run, still trivial in absolute terms — an estimated $10–15 even scaled to the full 3000-word Oxford list) but hit 83–93% compliance and 100% on the 5-sentences/rank-1-emotional checks. Full numbers in `tools/model_compare_results/summary.json`. **Per-word validation + fixes:** every one of the 160 words in the raw run was checked programmatically against the QC rules (exactly 5 sentences, rank1 `is_emotional=true`, `cloze_target` a case-insensitive substring of `en_text`, ≥3 distinct inflected forms across the 5 sentences for POS where inflection is possible — determiners/prepositions/conjunctions/pronouns/non-gradable adverbs/nationality adjectives are exempt since they structurally can't vary). **9 words failed** that check and could not be cleanly regenerated so they still use the old template mechanism end-to-end: `bag`, `day`, `evening`, `name`, `night`, `orange`, `page`, `window` (countable nouns that only reached singular/plural — 2 forms — instead of the achievable 3+ via a possessive form) and `different` (used the derived noun "difference" as an invalid cloze target instead of an actual inflected form). Regeneration was attempted for these 9 (`tools/_regenerate_llm.py`, same client pattern + retry/backoff) but the Gemini API key's prepayment credits were depleted (`429 RESOURCE_EXHAUSTED`) before a clean retry could land — falling back to templates for exactly these 9 words is the documented, anticipated fallback path, not a silent gap. A manual spot-check read of all 800 Thai sentences in the raw run (not just a 5–10-word sample) also caught **16 real generation glitches across 14 words** — a stray garbled syllable (`happy`), a literal Cyrillic "три" instead of Thai "สาม" (`school`), two dropped verbs/subject pronouns (`garden`, `write`, `tree`), one double-negative that flipped a sentence's meaning (`want`: "he doesn't want" became "he doesn't NOT want"), two stray parenthetical alt-glosses leaking into the translation (`beautiful`, `come`), and several stray mid-sentence spaces (`home`, `rest`, `start`, `study`, `thank`, `tree`, `door`) — all corrected via `MANUAL_FIXES` in `tools/_gen_llm_sentences.py` before being baked into `llm_sentences.py`. This was the single biggest content-quality gap flagged in the previous version of this doc; it is now addressed for 151/160 words, with the remaining 9 explicitly logged rather than silently left as-is. |
| `related_words` | **Small manually-curated fallback, not SWOW** | `RELATED_FALLBACK` dict in `build_dataset.py`, ~50 hand-picked association pairs restricted to word-pairs that are both in the 160-word seed (e.g. cat↔dog, school↔teacher↔student, family↔mother/father/brother/sister). SWOW-EN (smallworldofwords.org) is a downloadable research dataset but wasn't fetchable in this session. This is exactly the documented fallback SPEC.md itself sanctions ("ถ้าไม่ได้... ยอมรับให้ fallback เป็น manually-curated set... แต่บันทึกใน NOTES.md"). No WordNet-based `is_giveaway` flagging was done (all rows have `is_giveaway=0`) — Phase 2 territory anyway since hint system (§8b) isn't wired into the UI yet beyond a stub hook in `ClozeGame`. |
| Images (`has_photo`, `image_url`, etc.) | **All 0 / null — no Openverse/Wikimedia fetch attempted** | Explicitly spec-sanctioned scope cut: "it's fine if most of the 150-word seed just has has_photo=0". `lib/data/image_cache.dart` is fully implemented and unit-test-ready (injectable `HttpGet`) but has nothing in the seed to exercise it against yet. |

### QC pass actually performed (not skipped)
`build_dataset.py`'s `main()` runs an automated QC block after insert:
duplicate-headword check, cloze-span validity (`cloze_end > cloze_start`),
exactly-5-sentences-per-word check, dangling-FK check on `related_words`
(both directions), and a cloze-slice sanity check (each cloze span must be
made only of alphabetic word(s) + apostrophes, allowing a single interior
space so multi-word comparative forms like "more beautiful"/"most tired" —
legitimate grammatical variety introduced by the LLM content — pass, while
still catching genuinely broken/empty/punctuation-only spans; this check
was loosened from a stricter single-word-only version when the LLM content
first surfaced two real multi-word comparatives that are correct English).
All pass on the current 160-word DB (see `tools/build_dataset.py` output:
`QC pass: OK`).

I also did a **manual spot check** (not just automated) on ~10 words
(`go`, `cry`, `happy`, `answer`, `child`, plus others) by dumping their full
row set and reading every generated sentence/grammar note by eye. This
caught one real bug: `answer`'s `meaning_th` was `"คำตอบ, ตอบ"` (noun sense
listed first) which was leaking into verb-slot sentences as
*"She คำตอบ every morning..."* — nonsensical Thai. Fixed by reordering to
`"ตอบ, ตอบ, คำตอบ"` → `"ตอบ, คำตอบ"` (verb sense first) since the code picks
`meaning_th.split(',')[0]` for sentence substitution.

**Update (2026-07-22, LLM sentence integration):** did a second manual spot
check, this time reading **all 800** Thai sentences in the raw
`gemini-3.6-flash_round1.json` run (broader than the ~10-word sample above,
since this was the highest-value content to get right) plus an automated
scan for stray non-Thai/non-ASCII script characters and mid-sentence double
spaces to help triage. Found and fixed 16 real glitches across 14 words —
full list and rationale in the `example_sentences` row above and in
`MANUAL_FIXES` in `tools/_gen_llm_sentences.py`. Nothing else in the 151-word
LLM set read as unnatural on this pass; the 9 words still on templates carry
forward the same known-awkward-function-word caveat noted below.

**Known remaining quality gap (documented, not silently ignored):** function
words with generic templates (`a`, `all`, `every`, `about`, `near`, `please`,
`thank`, etc. — the `det`/`prep`/`interj` template families) produce
grammatically *serviceable but occasionally awkward* Thai/English pairings
(e.g. "I need a help with this." — "a" doesn't naturally combine with
uncountable "help"). These ~15 words, plus the 9 words listed in the
`example_sentences` row above that fell back to templates for a different
reason (varied-forms QC failure + depleted API credits), would benefit most
from a future hand review or another LLM regeneration pass once API access
is restored. Content nouns/verbs/adjectives (the bulk of the 160) read
naturally.

---

## 2. Flutter app (`vocab_app/`)

### Architecture — matches SPEC.md §3, borrowed from Gymmer_App's layering
```
lib/models/        Word, Sense, WordForm, ExampleSentence, RelatedWord, WordBundle,
                    SrsState, ReviewLogEntry, DailyStats (+ enums: CardState, Direction, Rating)
lib/data/
  vocab_store.dart          abstract interface (mirrors WorkoutStore pattern)
  vocab_store_sqlite.dart   production impl — copies bundled seed to app docs dir on
                             first launch, runs migrations on top
  vocab_store_memory.dart   in-memory impl for tests/dev
  migrations/migration_runner.dart   numbered migrations (0001_init — adds
                             srs_state/reviews_log/daily_stats/settings on top of the
                             read-only content tables already in the seed)
  image_cache.dart          runtime Openverse/Wikimedia fetch+cache (implemented, sparse data)
  tts_service.dart          flutter_tts wrapper
lib/domain/
  fsrs/fsrs5.dart            FSRS-5 core algorithm, ported from the public reference formulas
  fsrs/sleep_gap.dart        sleep-anchored minimum gap (§6.2)
  retention_tuner.dart       adaptive requestRetention (§6.3)
  new_card_governor.dart     adaptive new-card cap (§6.4)
  session_engine.dart        endless queue, priority/interleaving/bidirectional (§7)
  answer_checker.dart        typo-tolerant grading, Levenshtein-1 (§2 default table)
  streaks.dart                streak + heatmap math, pattern borrowed from Gymmer
lib/screens/        play_screen.dart, word_intro_page.dart, progress_page.dart,
                     word_detail_page.dart (Phase-2 stub, as instructed)
lib/games/           flashcard_swipe.dart, cloze.dart, matching.dart  (only these 3, per Phase 1 scope)
lib/widgets/         word_result_card.dart (§9b layer-1 mini dictionary entry)
lib/theme/           app_theme.dart (plain Material 3, per §13 "Phase 1-2 ใช้ UI เรียบง่าย")
```

### FSRS-5 — real algorithm, not a stub
`lib/domain/fsrs/fsrs5.dart` implements the actual FSRS-5 formulas (initial
stability/difficulty per rating, retrievability, mean-reverted difficulty
update, success/failure stability updates with hard-penalty/easy-bonus
terms, interval-from-target-retention), using the standard default weight
vector (`kFsrs5DefaultWeights`, 19 values). **One deliberate simplification:**
the same-day/short-term review formulas (FSRS-5 weights 17/18) are *not*
implemented, because SPEC.md's sleep-anchored minimum gap (§6.2) guarantees
a card is never reviewed twice in one calendar day — that code path is
unreachable in this app by construction, so it's a documented no-op rather
than a missing feature. Commented inline in the file.

### Session engine — real priority/interleaving logic, not hardcoded
`buildQueue()` in `session_engine.dart` computes overdue-first ordering
(oldest due date wins), caps new cards against `newCardCap -
newIntroducedToday`, round-robins across distinct due words so the same
word doesn't repeat back-to-back (interleaving), flips `last_direction`
per word each time it's reviewed (bidirectional EN/TH), and appends an
"extra practice" tail of young/mature words not yet due. Game-selection
ladder (`gamesForState`) matches SPEC.md §7's table with the one explicit,
documented Phase-1 fallback: young/mature both map to Cloze only (Word
Association/Dictation are Phase 2 and not built, so there's nothing else to
route them to yet).

### Adaptive governors — real adaptation, not fixed constants
- `retention_tuner.dart`: rolling 7-day accuracy vs. an 87.5% target band;
  nudges `requestRetention` by ±0.01/cycle, clamped to [0.75, 0.95].
- `new_card_governor.dart`: shrinks the cap by 2 when backlog ≥20, grows it
  by 1 when backlog ≤5 and accuracy ≥85%, shrinks by 1 if accuracy is
  struggling even without backlog pressure; clamped to [3, 15] per spec.

### answer_checker — real typo tolerance
Plain Levenshtein distance (iterative DP, no external package), gated to
words >4 chars per the spec default table; distance-1 typos on eligible
words grade `Hard` (never `Again`); exact match graded `Easy` if answered
within 3s else `Good`. `capForHint()` implements §8b's hint-usage cap
(correct-with-hint never exceeds `Hard`).

### What's stubbed / deferred to Phase 2+ (as instructed)
- `word_detail_page.dart` — Phase 2 full dictionary entry per §9b layer 2
  (all senses grouped by POS, inline word-forms, all 5 sentences). Current
  stub just reuses the layer-1 result card so the route exists.
- Games: Word Association, Word Scramble, Odd One Out, Dictation — not
  built (Phase 2 per §8).
- Hint system family B (Dictation spelling hints) — N/A, no Dictation game
  yet. Family A (semantic hint) has a UI hook in `ClozeGame` (`hintWords`
  param + `capForHint`) but `play_screen.dart` doesn't currently populate
  `hintWords` from `related_words` — wiring that up is a small Phase 2 task,
  the data (`RelatedWord` on `WordBundle`) is already loaded and available.
- `is_giveaway` (WordNet synonym/antonym flagging) — not computed; all
  `related_words` rows have `is_giveaway=0`. Low risk in Phase 1 since the
  hint UI isn't wired up yet anyway.
- Focus topic / `topics`/`word_topics` tables — created empty in the seed
  schema, never populated or read. Phase 2/3 per §11.
- Credits/Licenses page (mentioned in §5 copyright note) — not built. Should
  exist before any real distribution given the CC BY-SA/CC BY-NC data
  sources.

### Deviations from spec, with reasoning
1. **160 words instead of ~150.** Slight overshoot to keep POS variety
   (some POS categories like `pron`/`conj`/`interj` needed a couple more
   entries to have any representation at all). Not meaningful in either
   direction; the pipeline is trivially rerunnable at a different count.
2. **`vocab_store_sqlite.dart` opens the copied seed DB directly** (rather
   than a separate "app db" + "content db" split) — simpler for Phase 1
   single-device local storage, matches "bundle dataset สำเร็จรูป" + layer
   app-state tables on top via migrations. If multi-device sync is ever
   added (§12, explicitly open/deferred), this would likely need to split.
3. **Windows/Web platforms were added to the Flutter project** (in addition
   to the iOS/Android the spec calls out) purely as a local build/compile
   sanity check in an environment without an iOS toolchain or simulator —
   see Verification section below for exactly what that did and didn't
   prove. iOS remains the primary target; nothing app-specific depends on
   desktop/web.

---

## 3. Verification performed

- **`flutter analyze`: clean, 0 issues.**
- **`flutter test`: 44/44 passing**, covering:
  - `test/fsrs5_test.dart` — FSRS math: initial stability ordering across
    ratings (Again < Good < Easy), stability growth across repeated Good
    reviews (spacing effect), retrievability decay, lapse-from-mature drops
    to learning, higher requestRetention shortens interval, sleep-gap floor
    behavior (never same-day, doesn't shorten an already-later FSRS date).
  - `test/answer_checker_test.dart` — exact match timing→Easy/Good, typo
    tolerance gated correctly by word length, hint-usage rating cap.
  - `test/session_engine_test.dart` — overdue-before-new priority, most-
    overdue-first ordering, new-card cap arithmetic (including
    `newIntroducedToday` reducing remaining budget), interleaving
    (no-repeat), bidirectional direction flip, game-selection ladder per
    state.
  - `test/new_card_governor_test.dart` / `test/retention_tuner_test.dart` —
    adaptation direction under high/low backlog and good/bad accuracy,
    clamping at both ends.
  - `test/streaks_test.dart` — streak continuation/break rules, heatmap
    fills every day of a month.
  - `test/vocab_store_sqlite_test.dart` — **integration test against the
    actual built seed DB** (via `sqflite_common_ffi` since plain `flutter
    test` has no platform sqflite plugin): confirms ≥150 words, 1 core
    sense per word, exactly 5 sentences per word, and that migrations run
    cleanly on top of the content schema.
- **`flutter build web`: succeeds** (compiles to JS; only non-fatal wasm-
  compat lint warnings from the `flutter_tts` web shim, not errors). This
  confirms the full widget tree, all imports, and the domain/data layers
  compile together without errors.
- **`flutter build windows`: blocked by tooling, not app code** —
  `flutter_tts`'s Windows plugin CMake step requires `nuget.exe`, which
  isn't installed in this environment. This is an environment gap, not a
  bug in this codebase.
- **Not done: actually launching and clicking through the app** (no iOS
  simulator/device, no Android emulator, and the two available desktop/web
  paths each hit an unrelated tooling wall — nuget for Windows, and sqflite
  has no web storage backend at all so the app would spin forever on the
  loading screen if run in Chrome). **This is the one real gap**: manual
  on-device (or simulator) verification of the actual play loop — intro
  card → next-day due → flashcard/cloze/matching → streak increment — has
  NOT been done and should be the first thing done on a machine with an iOS
  simulator or a physical device.

---

## 4. How to pick this back up

1. **Dataset quality pass**: swap `tools/wordlist.py` for a real OUP-sourced
   list and `tools/thai_data.py` for real Wiktionary-fetched glosses — the
   pipeline's insert/QC code doesn't need to change, only these two data
   sources feeding it. (The third item that used to be listed here —
   replacing `SENT_TEMPLATES`-generated sentences with Gemini-generated ones
   — is done for 151/160 words, see the `example_sentences` row in section 1.
   Remaining: regenerate the 9 words still on templates — `bag`, `day`,
   `evening`, `name`, `night`, `orange`, `page`, `window`, `different` — once
   the Gemini API key's prepayment credits are topped up; rerun
   `tools/_regenerate_llm.py`, fold any newly-passing words into
   `tools/llm_sentences.py`, then rebuild.)
2. **On-device verification**: run on an iOS simulator/device (`flutter run
   -d <ios-device>`) and walk the full loop described in SPEC.md §11's
   success criterion.
3. **Phase 2**: wire the `hintWords` param already present in `ClozeGame`
   up to `related_words`; build the 4 remaining games; build the full
   `word_detail_page.dart`; add `is_giveaway` WordNet flagging; add the
   Credits/Licenses page.
