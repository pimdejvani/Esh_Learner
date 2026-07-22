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

---

## Phase 2 build log

Everything in this section builds SPEC.md §11's Phase 2 scope on top of the
Phase 1 vertical slice above, per the same precision/honesty standard. Only
`vocab_app/lib/**`, `vocab_app/test/**`, and this section were touched — the
dataset/content side (`tools/*.py`, `vocab_app/assets/seed/vocab.db`) is a
different, parallel effort and isn't described here.

### 1. Four new games (`lib/games/`)

- **`word_association.dart`** — target word + 4-option multiple choice;
  correct answer is picked by `pickAssociationTarget()` (prefers
  `relation_type='association'`, always excludes `is_giveaway`, highest
  `closeness` wins among what's left). Distractor options come from
  `buildAssociationOptions()`, drawn from the full word pool minus the
  target and all its related words (so no distractor is ambiguously "also
  kind of right"). Correctness/rating is by id-equality, not
  `answer_checker.check()` string matching (there's no typed input here),
  but the final rating is still routed through `capForHint()`.
- **`word_scramble.dart`** — `scrambleWord()` shuffles the headword's
  letters (retries up to 20 times to avoid returning the original
  permutation by chance; length-<=1 words are returned as-is since no
  different permutation exists). Typed answer graded via the existing
  `answer_checker.check()` (typo tolerance included), rating capped via
  `capForHint()`.
- **`odd_one_out.dart`** — `buildOddOneOutGroup()` looks across *every*
  word's `related_words` rows (not just the target's) for a "hub" word
  whose related set has >= `groupSize` members that (a) aren't the target
  and (b) aren't themselves related to the target — that's the category
  the target genuinely doesn't belong to. Prefers `hypernym`/`category`/
  `part_of`-typed rows per spec, but **falls back to any non-giveaway
  relation type** (currently the *only* type in the seed is `association`,
  per the Phase 1 `RELATED_FALLBACK` dict — see section 1 above), and falls
  back from `groupSize=3` to `2` if 3 isn't reachable. Returns `null` when
  no hub qualifies at all; `play_screen.dart` falls back to Flashcard for
  that round rather than stalling the queue. No hint system (categorization
  recognition isn't one of SPEC.md 8b's two hint families).
- **`dictation.dart`** — TTS speaks the headword (via the existing
  `TtsService`), user types the spelling; graded via `answer_checker`. Also
  implements the **family-B spelling hint** (`DictationHint` class,
  runtime-generated, no new table): stage 1 is a syllable-boundary skeleton
  (letters hidden, hyphens shown) — the syllable *count* is derived from
  `thai_reading`'s hyphen-split count (English has no dedicated syllable
  field in the schema) and the headword is naively divided into that many
  roughly-equal chunks; stages 2..N reveal one more letter left-to-right
  per stage; the final stage (once every letter is already visible) is a
  bare letter-count, kept because SPEC.md 8b lists it as one of the three
  hint contents even though it adds little information by that point
  (documented simplification, not silently dropped).

### 2. Hint system (SPEC.md 8b), both families, fully wired

- **Family A (semantic)** — `play_screen.dart`'s `_semanticHints()` sources
  candidates from the already-loaded `WordBundle.related`, filters
  `is_giveaway`, sorts by `closeness` descending (strongest legitimate clue
  first), and is used by Cloze, Word Scramble, and Word Association. Word
  Association additionally excludes its own correct answer's word id from
  the hint pool (showing the MCQ's right answer as a "hint" would trivialize
  the round). **Progressive reveal**: Cloze's previously single-shot hint
  button (reveals every `hintWords` entry on one tap) was upgraded to
  tap-to-reveal-one-more, matching the new games and SPEC.md §12's "เปิดที
  ละขั้น" — this is the one small edit to already-shipped Phase 1 game code,
  done because the task explicitly called out wiring `hintWords` end-to-end.
- **Family B (spelling, Dictation only)** — see `DictationHint` above.
- **Rating cap** — every game (old and new) that supports a hint routes its
  final rating through `answer_checker.capForHint(usedHint: ...)` before
  calling `onRated`, so a correct-with-hint answer never exceeds Hard,
  consistently across all 7 games.

### 3. Irregular-form flagging (SPEC.md 9.2)

Added `IrregularBadge` (in `widgets/word_result_card.dart`, shared rather
than duplicated) — a small `errorContainer`-colored chip reading "ผิดปกติ"
next to any `WordForm` with `is_irregular = 1`; tapping it opens a dialog
with the full `grammar_note_th`. Wired into both places SPEC.md 9.2 asks
for it:
- **Layer 1** (`WordResultCard`) — if the currently-shown example sentence
  has a non-null `form_id`, the badge appears next to that sentence when
  the matching `WordForm.isIrregular` is true.
- **Layer 2** (`word_detail_page.dart`) — next to every irregular form in
  the inline verb-forms row, and next to every example sentence that used
  one.

### 4. Focus topic (SPEC.md 6.4 / 8)

- **Storage**: reuses the existing generic `settings` key/value table —
  `key='focus_topic'`, `value=<topic id as string>` (or absent/empty for
  "none"). No schema change needed.
- **UI**: `progress_page.dart` gained a `DropdownButton` topic picker,
  **hidden entirely** when `store.loadTopics()` returns empty (content
  pipeline hasn't populated `topics`/`word_topics` yet) — per the task's
  explicit "handle that gracefully" instruction, this degrades to simply
  not showing the picker rather than showing an empty/broken one.
- **Bias logic**: `new_card_governor.dart` gained a new top-level
  `orderNewCandidates()` function — a **stable partition** (not a re-sort):
  words whose id is in the focus-topic set move to the front, all other
  words keep their existing relative freq_rank/CEFR order untouched.
  `session_engine.buildQueue()` takes a new `focusTopicWordIds` parameter
  (default `{}`) and calls this right before capping new candidates at
  `newCardCap`. **Verified as a true no-op** when unset: a dedicated test
  (`session_engine_test.dart`, "focus topic bias") asserts the resulting
  queue is byte-for-byte identical with vs. without an explicitly-empty
  `focusTopicWordIds`, and all pre-existing Phase 1 session_engine tests
  (which never pass this parameter at all) still pass unmodified.
- `VocabStore` gained `loadTopics()` and `loadWordIdsForTopic(topicId)`
  (both sqlite + memory impls); `play_screen.dart` loads the focus topic's
  word-id set once at boot and threads it through `buildQueue()`.

### 5. Full `word_detail_page.dart` (SPEC.md 9b layer 2)

Replaces the Phase 1 stub. Header matches layer 1 (headword + TTS + Thai
reading with bold stress syllable, **no IPA** — confirmed `ipa` is still
never rendered anywhere in the app, only stored for internal use per spec).
Below that: every sense (not just the core one) grouped by POS and ordered
by `sense_rank`, each showing a CEFR badge + meaning + collocation
(`EN = TH`) when present, with the `is_core` sense starred (⭐). Verb-POS
groups (`pos == 'v'`) get an inline word-forms row ("form1 · form2 · form3"
style, in a fixed past/past_participle/ving/3sg preference order when
those types exist) with the shared `IrregularBadge` on irregular ones; tap
the row to expand every form's full `grammar_note_th`. All of the word's
`example_sentences` are listed at the bottom (not just one).

**Data-layer change needed to support this**: `WordBundle` only carried a
single `coreSense` in Phase 1 (the store only ever queried `senses WHERE
is_core=1`). Added a `senses: List<Sense>` field, and changed both store
implementations to query **all** senses per word (ordered by
`sense_rank`), deriving `coreSense` from that same list instead of a
second query. Today's seed only has 1 sense/word so this is invisible in
practice, but it's what makes the multi-sense grouping actually work
without further code changes once the content pipeline adds more senses
per word — consistent with the brief's "build against whatever's there
now" instruction.

**Tap-through wiring**: `WordResultCard` gained an optional
`onOpenDetail` callback (null hides the tap affordance). Every game that
shows a `WordResultCard` after answering (Flashcard, Cloze, Word Scramble,
Word Association, Dictation) and `word_intro_page.dart` now pass one that
pushes `WordDetailPage`, so SPEC.md 9b's "แตะการ์ดเพื่อเปิด entry เต็ม" is
actually reachable — this was a real gap in the Phase 1 stub (the route
existed but nothing in the running app ever navigated to it).

### 6. Credits/Licenses page (SPEC.md §5)

New `lib/screens/credits_page.dart`, reached via a ListTile on
`progress_page.dart`. Per the task's instruction, the "คำแปล" (translations)
and "รูปภาพ" (images) sections are populated from **distinct values actually
present in the loaded `words` list** (`translation_source`/
`translation_license`, `image_license`/`image_author`) rather than
hardcoded, so they track the content pipeline automatically. The "คำที่
เกี่ยวข้อง" (related words / SWOW+WordNet) section is **static text** —
documented as a deliberate deviation: `related_words` has no per-row
source/license column in the schema (SPEC.md §4), only a dataset-level
attribution documented in SPEC.md §5/13 and section 1 of this file, so
there's nothing per-word to query for that section specifically.

### 7. Game-selection ladder — Phase 1 placeholder replaced

`session_engine.dart`'s `gamesForState()` now matches SPEC.md §7's table
in full (previously young/mature both fell back to Cloze only, a
documented Phase 1 placeholder):

| state | Phase 1 | Phase 2 (now) |
|---|---|---|
| learning | flashcard, matching | flashcard, matching, **Odd One Out** |
| young | cloze only | cloze, **Word Association** |
| mature | cloze only | **Dictation**, **Word Scramble** |

**One resolved ambiguity worth flagging**: the task instructions explicitly
named the young/mature replacements but only said to "wire all 4 games
into the ladder... exactly per the §7 table" for Odd One Out's placement —
the table itself puts Odd One Out under **learning**, not young/mature, so
that's where it was added. This is the one row not explicitly called out
in the task text; resolved by following SPEC.md §7's table literally
since that's what "exactly per the table" points to, and it's also the
only way all 4 new games actually get used somewhere in the ladder.

`session_engine_test.dart`'s Phase 1 placeholder test ("young and mature
words fall back to Cloze in Phase 1") was replaced with three tests
matching the real ladder (learning/young/mature), plus two new tests for
the focus-topic bias no-op/bias behavior.

### 8. Known gaps / simplifications (documented, not silently skipped)

- **Odd One Out and Word Association frequently can't build a round yet**,
  because the current `related_words` data is the ~50-pair manually-curated
  Phase 1 fallback (section 1 above), not real SWOW/WordNet data — most
  words simply don't have enough related rows to form a 3+ member category
  or even a single non-giveaway association. `play_screen.dart` handles
  this by falling back to Flashcard for that round rather than stalling or
  crashing. **This should resolve itself with no code changes** once the
  content pipeline populates richer `related_words` data, per the task's
  explicit "build against whatever's there now" instruction — but it's
  worth knowing that on today's seed, these two games will show up rarely
  in practice despite being fully wired into the ladder.
- **`loadAllRelatedWords()` loads every `related_words` row into memory
  once at `PlayScreen` boot** (needed so Odd One Out can search across
  every word's related set for a category hub, not just the current
  word's). Fine at 160 words; would want a narrower/lazier query if the
  dataset grows to the full 3000-word Phase 3 scale.
- **No widget-level (pumped) tests for any of the 7 games**, old or new —
  this matches the existing Phase 1 pattern (there were no
  `cloze_test.dart`/`flashcard_swipe_test.dart`/`matching_test.dart` either);
  all game logic that has interesting behavior is factored into pure,
  directly-testable top-level functions (`scrambleWord`,
  `pickAssociationTarget`, `buildAssociationOptions`, `buildOddOneOutGroup`,
  `DictationHint.stageText`, plus the existing `answer_checker`), and those
  are what's unit-tested.
- **Word Association's "hint" is arguably redundant with the game itself**
  (the game already tests recognizing a related word; a "hint" that shows
  *another* related word is a fairly weak scaffold). Implemented anyway
  because the task explicitly listed Word Association under hint family A;
  kept simple (progressive reveal of secondary related words, excluding the
  correct answer) rather than inventing a different hint mechanism not in
  the spec.

### 9. Verification performed

- **`flutter analyze`: clean, 0 issues** (re-ran after every new file).
- **`flutter test`: 91/91 passing** — the Phase 1 44 plus new coverage in
  `test/word_association_test.dart`, `test/word_scramble_test.dart`,
  `test/odd_one_out_test.dart`, `test/dictation_test.dart` (game logic +
  hint-cap-to-Hard routing for each), plus additions to
  `test/session_engine_test.dart` (Phase 2 ladder, focus-topic bias) and
  `test/new_card_governor_test.dart` (`orderNewCandidates`).
- **Not done** (same gap as Phase 1, unchanged): on-device/simulator manual
  click-through. Still the top item for whoever has iOS tooling available —
  in particular the 4 new games' actual UI/UX (chip layout, hint button
  feel, dictation TTS timing) has only been exercised through pure-function
  unit tests, never rendered.
