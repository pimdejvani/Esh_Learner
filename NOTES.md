# NOTES — build log

Working dir: `C:\Users\pimde\Desktop\pimdej\English`. This is the single doc to read to
understand what happened. It covers: what data sources were actually used vs.
approximated, what's built/tested, what's explicitly deferred, and
deviations from SPEC.md with reasoning. Newest sections are at the bottom;
the **"Current status & remaining work"** section at the very end is the
quickest way to see where things stand.

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

**Update (2026-07-23, real SWOW-EN18 integration):** the one remaining
approximated field flagged by the 2026-07-22 pass below — `related_words`'
`association`/`closeness` data — is now real too. The user manually
completed smallworldofwords.org's name/email request form (which can't be
automated) and downloaded the actual SWOW-EN18 release to
`C:\Users\pimde\Downloads\SWOW-EN18\`. `strength.SWOW-EN.R123.20180827.csv`
(the cue→response associative-strength file, ~1.39M rows) was loaded and
filtered to rows where both `cue` and `response` are in this app's 153-word
seed. **All 153/153 words had enough real in-vocabulary SWOW data** (min 4,
max 28, avg ~14.3 candidate rows per word before capping) — so, unlike the
pass's own stated worry that some words might need to stay on the old
hand-curated fallback, **that fallback path ended up not being needed for
any word**. New file `tools/swow_associations.py` holds the real data (top
6 per word by real `R123.Strength`, used directly as `closeness` — no
longer a flat 0.5 placeholder); `build_dataset.py`'s `resolve_related()` now
sources every word's association rows from there, with `RELATED_FALLBACK`
kept only as a documented, currently-unused per-word exception mechanism
(`SWOW_FALLBACK_EXCEPTIONS`, empty today) in case a future word-list change
ever introduces a word SWOW has too little data for. `is_giveaway` is
still computed the same way (real WordNet synonym/antonym check), now
applied to the real SWOW pairs — this actually surfaced *more* real
giveaway pairs than before (75, up from 26), since the real data includes
antonym pairs (`hot`↔`cold`, `go`↔`come`, etc.) the old hand-curated set
didn't happen to include. Full detail in section 1's `related_words` row
below and in `tools/swow_associations.py`'s own docstring. Rebuilt the
DB (`QC pass: OK`), and `vocab_app`'s `flutter test` (91/91) and
`flutter analyze` were both re-run against it — see section 3.

**Update (2026-07-22, real-sourcing pass):** every field this document
previously flagged as "approximated" has now been re-done against a real
external source where one was fetchable, and precisely documented where it
still isn't. Short version (full detail in section 1's table, which has
been rewritten below):

1. **Word list**: cross-checked all 160 headwords against a real, fetched
   Oxford 3000 CEFR JSON on GitHub. 7 words weren't actually in the real A1
   band (5 were real Oxford words in the wrong band, 1 wasn't in the source
   at all, 1 — the article "a" — has no article entries in the source or a
   Thai translation either way, so it was dropped rather than swapped).
   **The corpus is now 153 words, not 160** — see `tools/wordlist.py`'s
   docstring for the exact 7 and why each one moved.
2. **Thai translations**: 152/153 `meaning_th` values are now a real word
   fetched from Wiktionary's own translation tables (via the wiktapi.dev
   mirror API), sense-matched against this app's own collocation for each
   word. 1 word (`make`) has no Thai translation in Wiktionary's data at
   all for any of its verb senses and is explicitly still flagged
   approximated in the DB (`translation_source`). The Wiktionary license
   field was also corrected: it's CC BY-SA **4.0**, not 3.0 as previously
   recorded.
3. **related_words**: `is_giveaway` is now a real, computed WordNet
   synonym/antonym check (was a hardcoded 0 for every row before). New
   `hypernym`/`part_of` rows were added from a real WordNet hypernym-path /
   holonym closure over the word set, for the Odd-One-Out game. SWOW-EN
   itself was not fetchable *automatically* this pass (confirmed: its
   GitHub repo `.gitignore`s the actual response/strength data files, only
   per-word summary stats are tracked) — `RELATED_FALLBACK`'s hand-curated
   association pairs remained the closeness/association-strength source at
   the time, exactly as SPEC.md sanctions for this documented case.
   **Superseded 2026-07-23**: the user manually completed
   smallworldofwords.org's request form and downloaded the real SWOW-EN18
   data — `association`/`closeness` is now real too, for all 153/153 words.
   See the 2026-07-23 update above and section 1's `related_words` row.
4. **9 fallback-template sentences**: regenerated with `gemini-3.6-flash`
   now that the API key has credits again. All 9 passed QC cleanly on the
   first retry. **All 153 words in the current seed now use real
   LLM-generated sentences — none fall back to the old templates.**

---

## 1. Dataset (`tools/`, output `vocab_app/assets/seed/vocab.db`)

Run with `python tools/build_dataset.py` (rerunnable, idempotent — rebuilds
the DB from scratch each time). Produces **153 words** (was 160 before the
2026-07-22 real-sourcing pass below dropped 7 that weren't verifiably A1 —
still comfortably over the ~150 target) covering Oxford 3000 A1 band.
Requires `nltk`'s `wordnet` corpus for the `related_words` step now (see
the `related_words` row below) — `pip install nltk && python -m nltk.downloader
wordnet`, one-time, no further internet access needed after that.

### What's REAL / sourced vs. what's APPROXIMATED — be precise here:

| Field | Status | Detail |
|---|---|---|
| Headwords + POS + CEFR band | **Word list + A1 band now REAL, machine-verified. POS tags remain hand-assigned (spec-sanctioned).** | `tools/wordlist.py`. Cross-checked all 160 originally-hand-typed headwords against a real, machine-fetched source: the "A1"/"A2"/"B1"/"B2" word-array JSON at `https://raw.githubusercontent.com/Kolia951/The_Oxford_3000_CEFR/main/package.txt` (892 words in its A1 array). 153/160 were confirmed present in the real A1 array verbatim. **7 were not**, and were handled per-word (documented in full in `wordlist.py`'s docstring): `cry`, `lady`, `noisy`, `rest`, `smile` are real Oxford words but the source lists them as A2, not A1 — dropped rather than mislabeled; `English` isn't in ANY band of this source at all (nationality adjectives seem excluded) — dropped; `a` also isn't in any band (unlike `the`, which is) — considered swapping for `the`, but Wiktionary has no Thai translation for either English article (Thai has no articles), so swapping wouldn't have fixed the *translation*-sourcing problem while still costing a word — dropped instead of swapped. **The corpus is now 153 words.** POS tags are still hand-assigned (the source has no POS field) — per SPEC.md this remains an explicitly allowed non-sourced human/LLM judgment call (grammatical fact, not translation/definition). `freq_rank` is this pipeline's own sequential ordering (renumbered 1..153), not a sourced frequency statistic. |
| `meaning_th` (Thai gloss) | **Real for 152/153 words, fetched from Wiktionary's own translation tables.** `thai_reading`, `ipa`, `collocation_en/th`, `countable` remain hand-authored (see reasoning below). | `tools/thai_data.py`. Fetched via `GET https://api.wiktapi.dev/v1/en/word/{word}/translations` (a free, no-key API that mirrors en.wiktionary.org's own Translations tables) for all 153 headwords — collected every `lang_code="th"` entry for the word's part of speech, then for each word picked the real Wiktionary Thai word using this priority: (1) exact match to a term already in the previous hand-authored gloss (validates it as real and preserves the original sense-priority ordering, e.g. `old`'s `แก่, เก่า` kept แก่ since it was listed first), (2) else the candidate that's a substring of this word's own `collocation_th` (the collocation demonstrates which sense the app actually drills — used to disambiguate 11 words whose old gloss was a compound/paraphrase not itself a separate Wiktionary translation entry: `after`, `again`, `beautiful`, `different`, `evening`, `eye`, `kitchen`, `light`, `live`, `sleep`, `talk`), (3) otherwise the first available real candidate. **113/152 already matched a real Wiktionary word exactly unchanged** (validates the original hand-typed data was largely accurate); **40 changed** to a different (still real) Wiktionary word after this cross-check. **1 word, `make`, has NO Thai translation in Wiktionary's data at all** for any of its (very polysemous) verb senses — a WebFetch double-check of the plain `en.wiktionary.org/wiki/make` page didn't turn up a clean answer either, so the previous hand-authored `"ทำ, สร้าง"` is kept **unchanged and still explicitly flagged approximated** (`words.translation_source = "Wiktionary (approximated)"` for this one word only; every other word now gets a clean `"Wiktionary"`). `translation_license` was also corrected from the previously-recorded `"CC BY-SA 3.0"` to the actual current license: **`"CC BY-SA 4.0"`** (verified against `en.wiktionary.org/wiki/Wiktionary:Copyrights`, which states Wiktionary content is dual-licensed CC BY-SA 4.0 + GFDL). `thai_reading`/`stress_index` are still derived by hand from `ipa` (a syllable-hyphenated Thai-script transliteration, more specific than wiktapi.dev's loose romanization) — wiktapi's `roman` field was used only to sanity-check sense/word correctness, not as the reading source, per this pass's instructions. `ipa`, `collocation_en/th`, `countable` are unchanged from before (still hand-authored/rule-checked, not separately re-sourced this pass — SPEC.md's allowed non-definitional human/LLM judgment). |
| `word_forms.form_text`/`form_type`/`is_irregular` | **Rule-generated (regex-based inflection rules + irregular-verb/plural lookup tables), unchanged** | `build_dataset.py` (`regular_past`, `ving`, `s3sg`, `plural`, `comparative`, `IRREGULAR_VERBS`, `IRREGULAR_PLURALS`). The inflected *forms themselves* are still computed this way for all 153 words (this part was never the flagged gap). |
| `example_sentences` (5/word) + `word_forms.grammar_note_th` | **Real gemini-3.6-flash-generated content for ALL 153/153 words** (was 151/160, with 9 on old templates) | `tools/llm_sentences.py`, sourced from `tools/model_compare_results/gemini-3.6-flash_round1.json` (the original 160-word run) merged with `tools/model_compare_results/_regenerated.json` (the 2026-07-22 regeneration pass, see below) via `tools/_gen_llm_sentences.py`. `build_dataset.py`'s `build_sentences()` prefers this dataset per headword — for a hit, it also overwrites `grammar_note_th` on every `word_forms` row for that word with the LLM's one richer paragraph, in the SPEC §9.2 "explain why" style. The old `SENT_TEMPLATES` + rule-based note mechanism is **no longer exercised for any word in the current build** — it remains in the code purely as a defensive fallback. **Model selection** (unchanged from before, kept for history): 3 Gemini models were A/B-tested 2 rounds each over the full 160-word list against the SPEC §5 QC rules — `gemini-2.5-flash-lite` was dead/retired (404s), `gemini-3.5-flash-lite` was cheap but only 34–56% compliant on the varied-forms rule, `gemini-3.6-flash` cost more (~$0.40–0.58/run, trivial in absolute terms) but hit 83–93% compliance. Full numbers in `tools/model_compare_results/summary.json`. **The 9-word gap is now closed:** `bag`, `day`, `evening`, `name`, `night`, `orange`, `page`, `window` (countable nouns that previously only reached singular/plural — 2 forms — instead of 3+ via a possessive) and `different` (previously used the invalid derived-lemma cloze target "difference") were regenerated via `tools/_regenerate_llm.py` with `gemini-3.6-flash` now that the API key has credits again — **all 9 passed the full QC check (exactly 5 sentences, rank1 emotional, valid verbatim cloze span, ≥3 distinct inflected forms) cleanly on the very first retry**, no further API errors. `different`'s regenerated sentences now correctly cycle `different` / `different` / `more different` / `most different` / `different` — real inflected/comparative forms of `different` itself, not the noun "difference". An automated post-generation scan (double-space check, non-Thai/non-ASCII-script check, cloze-substring verification) found **0 issues** across all 45 new sentences — no manual `MANUAL_FIXES`-style correction was needed for this batch (unlike the original 160-word run, which needed 16 fixes across 14 words — that correction record is untouched and still baked into `llm_sentences.py`). |
| `related_words` | **`is_giveaway` real (WordNet-computed). `hypernym`/`part_of` rows real (WordNet-derived). `association` pairs + their `closeness` are now ALSO real (SWOW-EN18, 2026-07-23) — the fallback caveat below is now historical.** | `build_dataset.py` + `tools/swow_associations.py`. **is_giveaway**: computed by checking real WordNet data (`nltk.corpus.wordnet`) for an actual synonym (shares a synset) or antonym (WordNet's curated antonym links) relation, restricted to the word's POS as used in this app — now applied to the real SWOW association pairs (see below), not the old hand-curated set. **75 of 913 association rows are real WordNet synonym/antonym pairs** and are flagged `is_giveaway=1` (up from 26/136 under the old hand-curated set — the real SWOW data includes more antonym pairs, e.g. `go`↔`come`, `hard`↔`easy`, `near`↔`far`, that weren't in the old manually-picked list). Everything else stays `is_giveaway=0`. **`hypernym`/`part_of` rows**: computed from each noun's primary WordNet sense's hypernym-path closure (IS-A, e.g. `bread` IS-A `food`) and holonym closure (part-of, e.g. `night` is part_of `day`), restricted to pairs where BOTH headwords are already in this app's 153-word set, skipping any pair already covered by an association row (now checked against the real SWOW pairs, not `RELATED_FALLBACK` — see the 2026-07-23 update below for why this shrank the hypernym/part_of row count) and excluding one documented sense mismatch (`fish`→`school`, in `build_dataset.py`'s `HYPERNYM_MERONYM_SENSE_MISMATCH_EXCLUDE` — WordNet's only holonym for `fish` is `school.n.07`, "a shoal", unrelated to this app's `school.n.01`, "an educational institution"). `is_giveaway=0` and `closeness=0.6` (flat placeholder — WordNet has no association-strength score) for all hypernym/part_of rows, unchanged from before. **Only 2 hypernym/part_of rows remain** (`milk`→`food` hypernym, `kitchen`→`home` part_of) — down from 7 previously, because the real SWOW data already connects most of the same pairs (`bread`↔`food`, `evening`↔`day`, `orange`↔`food`, `page`↔`paper`, `night`↔`day` are now real association rows instead, so the dedup logic correctly skips adding a redundant hypernym/part_of row for them). **association/closeness — REAL as of 2026-07-23.** Previously (2026-07-22 pass and earlier): SWOW-EN wasn't fetchable automatically — its GitHub repo (`SimonDeDeyne/SWOWEN-2018`) `.gitignore`s the actual response/strength files, only per-word summary stats are tracked — so `RELATED_FALLBACK`'s ~50 hand-picked pairs (136 rows) with a flat `closeness=0.5` were used, exactly the fallback path SPEC.md sanctions for this documented case. **That gap is now closed**: the user manually completed smallworldofwords.org's name/email request form (the one thing that can't be automated) and downloaded the real SWOW-EN18 release (De Deyne, Navarro, Perfors, Brysbaert & Storms, 2019, "The Small World of Words English word association norms for over 12,000 cue words," *Behavior Research Methods*) to `C:\Users\pimde\Downloads\SWOW-EN18\`. `tools/swow_associations.py` (new file, full methodology in its own docstring) loaded `strength.SWOW-EN.R123.20180827.csv` (the 2018-08-27 release's cue→response associative-strength file, ~1.39M rows — loading it with plain `pandas.read_csv(sep="\t")` silently dropped ~30% of rows because a few response fields contain literal `"` characters that the default CSV quoting rules mis-parse as multi-line records; fixed with `quoting=csv.QUOTE_NONE`, verified against `wc -l` before trusting the row count), filtered to rows where both `cue` and `response` are (case-insensitively) one of the 153 seed headwords, dropped self-loops, then for each word took its rows as cue sorted by real `R123.Strength` (SWOW's own conditional-probability score) descending and kept the top 6. **All 153/153 words had at least 2 real in-vocabulary associations** (min 4, max 28, avg ~14.3 candidates before capping) — so the per-word fallback-exception mechanism this task anticipated needing (`SWOW_FALLBACK_EXCEPTIONS` in `swow_associations.py`, checked by `build_dataset.py`'s `resolve_related()` before it would fall back to `RELATED_FALLBACK` for a specific word) **is not exercised by any word in the current list** — it's kept in place, empty, purely so the fallback still works unattended if a future word-list change ever adds a word SWOW has too little data for. Total real association rows in the built DB: **913** (up from 136), covering all 153 words (up from 64) — every word now has real association data, not just the ~40% the old hand-curated set happened to cover. Sample: `cat`'s real top rows are `dog` (0.2047), `house`/`hat`/`fish` (~0.0067), `food`/`home` (~0.0034) — vs. the old fallback's flat `cat → [dog(0.5), milk(0.5)]`. `RELATED_FALLBACK` itself is left in the code, now used only if `SWOW_FALLBACK_EXCEPTIONS` is ever non-empty. |
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
All pass on the current 153-word DB (see `tools/build_dataset.py` output:
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
`MANUAL_FIXES` in `tools/_gen_llm_sentences.py`. Nothing else in that
151-word LLM set read as unnatural on this pass; the 9 words that hadn't
been generated yet at that point were later regenerated cleanly (see the
2026-07-22 update in the `example_sentences` row above and section 4).

**Known remaining quality gap — corrected while touching this section
(2026-07-22):** an earlier version of this doc claimed ~15 function words
(`all`, `every`, `about`, `near`, `please`, `thank`, etc.) "used generic
templates" that could read as grammatically awkward. That claim was stale
even before this pass: those words were already in `llm_sentences.py` from
the original round-1 run (real LLM-generated content, e.g. `about`'s
sentences are "I am so worried about my sick dog." / "The movie is about a
young hero." / etc. — not template output), so `build_dataset.py`'s
`build_sentences()` was already preferring the LLM version for them, not
templates. Checked directly against the built DB while writing this
update to be sure, rather than repeating the old claim uncorrected. **With
the 9-word regeneration pass also done, `SENT_TEMPLATES` is no longer
exercised for any of the 153 words in the current build** — every word has
real LLM-generated `example_sentences`. The code path remains in
`build_dataset.py` only as a defensive fallback (e.g. if a future word were
added without LLM content prepared for it yet).

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
- `is_giveaway` (WordNet synonym/antonym flagging) — **now computed for
  real as of the 2026-07-22 dataset real-sourcing pass**, see section 1's
  `related_words` row for the full detail (26 of 136 association rows are
  real WordNet synonym/antonym pairs and are flagged `is_giveaway=1`; new
  `hypernym`/`part_of` rows were also added). This bullet is left here
  (rather than deleted) so the history of "not computed -> computed" is
  visible. Note: by the time of this update, `vocab_app/test/word_association_test.dart`
  and `vocab_app/test/odd_one_out_test.dart` already exist and pass, exercising
  `is_giveaway`-exclusion logic against the real seed DB — that Phase 2 UI
  work happened in parallel (a different agent's territory, `vocab_app/lib/**`,
  not touched by this pass) and both suites still pass (`flutter test`:
  91/91) against the real values computed here.
- Focus topic / `topics`/`word_topics` tables — created empty in the seed
  schema, never populated or read. Phase 2/3 per §11.
- Credits/Licenses page (mentioned in §5 copyright note) — not built. Should
  exist before any real distribution given the CC BY-SA/CC BY-NC data
  sources.

### Deviations from spec, with reasoning
1. **153 words instead of ~150** (was 160 until the 2026-07-22 real-sourcing
   pass dropped 7 that weren't verifiably Oxford 3000 A1 band — see section
   1). Slight overshoot to keep POS variety (some POS categories like
   `pron`/`conj`/`interj` needed a couple more entries to have any
   representation at all). Not meaningful in either direction; the pipeline
   is trivially rerunnable at a different count.
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

1. ~~**Dataset quality pass**: swap `tools/wordlist.py` for a real
   OUP-sourced list and `tools/thai_data.py` for real Wiktionary-fetched
   glosses...~~ **Done as of 2026-07-22** — see the "real-sourcing pass"
   update near the top of this file and section 1's table for the full
   account: word list cross-checked against a real Oxford 3000 CEFR source
   (153/160 words verified, 7 dropped), 152/153 Thai glosses fetched from
   real Wiktionary translation data, all 153 words now have real
   LLM-generated sentences (the last 9 were regenerated once API credits
   were restored), and `related_words`' `is_giveaway` + `hypernym`/`part_of`
   rows are now real WordNet-computed data. **What's still genuinely
   approximated/fallback, precisely**: `make`'s `meaning_th` (no Wiktionary
   Thai translation exists for it) — that's it. The other item this bullet
   used to list, `RELATED_FALLBACK`'s association pairs + flat `closeness`
   values, was resolved on 2026-07-23: the user manually downloaded the
   real SWOW-EN18 dataset and `tools/swow_associations.py` now supplies
   real association/closeness data for all 153/153 words — see the
   2026-07-23 update near the top of this file and section 1's
   `related_words` row. Nothing else in the dataset is silently
   approximated anymore.
2. **On-device verification**: run on an iOS simulator/device (`flutter run
   -d <ios-device>`) and walk the full loop described in SPEC.md §11's
   success criterion. Still not done, still the top real gap in this repo.
3. ~~**Phase 2**: wire the `hintWords` param...~~ **Done in parallel** — see
   the "Phase 2 build log" section below (a different agent's work, on
   `vocab_app/lib/**`, concurrent with this dataset-sourcing pass). The one
   item from this old bullet not covered by that section is `is_giveaway`
   WordNet flagging, which this pass (not Phase 2's UI work) implemented —
   see point 1 above and section 1.

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
  word's). Fine at 153-160 words (written when the seed was 160; a parallel
  pass later trimmed it to 153, see section 1 — the point about scale
  doesn't change either way); would want a narrower/lazier query if the
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
- **Addendum, added by the parallel dataset-sourcing pass (2026-07-22, not
  by this section's original author):** the `related_words` real-sourcing
  gap this section describes above (`is_giveaway` all-0, no
  `hypernym`/`part_of` rows, only `association`) is now partially closed —
  see section 1's `related_words` row for the full account. `is_giveaway`
  is now real (WordNet synonym/antonym check), and 7 real `hypernym`/
  `part_of` rows now exist alongside the `association` fallback rows. This
  doesn't fully resolve the "frequently can't build a round" issue noted
  above (still only ~140 relation rows total across 153 words, and SWOW-EN
  itself remains unfetchable — see section 1) but `flutter test`'s existing
  `word_association_test.dart`/`odd_one_out_test.dart` suites (91/91
  passing) already exercise the real is_giveaway values, not just
  hypothetical ones.
- **Addendum 2 (2026-07-23, dataset-sourcing pass, not this section's
  original author):** the data-sparsity half of the "frequently can't build
  a round" gap immediately above is now resolved at the data layer — the
  user manually downloaded the real SWOW-EN18 dataset and every word now
  has real association rows (913 total across all 153 words, up from ~140
  across 64 words). See the 2026-07-23 update near the top of this file and
  section 1's `related_words` row for the full account. This pass only
  touched `tools/*.py` and `vocab_app/assets/seed/vocab.db` — it did not
  touch `vocab_app/lib/**`, so whether Odd One Out / Word Association
  actually show up more often in the running app depends on that unedited
  game logic (`buildOddOneOutGroup`/`pickAssociationTarget`, both in
  `vocab_app/lib/games/`) behaving as documented against the richer data;
  `flutter test`'s existing suites for both (91/91 passing, unchanged count)
  already exercise it against the real values, but this pass did not add
  new test cases or do on-device verification of round frequency.

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

---

## UI design pass (2026-07-23, Phase 3 UI, `vocab_app/lib/**` only)

UX/logic was declared settled per SPEC.md section 13's ordering rule ("ทำ
UX ทั้งหมดให้เสร็จก่อน แล้วค่อยทำ UI") — all 7 games + hint system + word
detail + credits page are built and covered by `flutter test` (91/91, see
section 9 above) — so this pass replaces the Phase 1-2 placeholder theme
(`lib/theme/app_theme.dart`'s old plain `ColorScheme.fromSeed`) with a real
design-language theme, and audits every screen/game/widget to actually use
it instead of hardcoded colors. This pass only touched `vocab_app/lib/**`
(theme, screens, games, widgets) and `pubspec.yaml`/`pubspec.lock` (one new
dependency, `google_fonts`) — no changes to `tools/*.py`, the seed DB, or
domain logic (`lib/domain/**`, `lib/data/**`), which is why `flutter test`
still passes 91/91 unchanged.

### Design tokens — where they came from

Per SPEC.md section 13, the reference is the `meeting-iq` shadcn.io
template (`https://meetingiq.shadcn.io`). Rather than re-deriving tokens
from guesswork, the exact values below were extracted by inspecting the
**live rendered site** directly via browser devtools (computed CSS
variables + a follow-up screenshot pass that corrected two initial
misreadings — see the "corrections" note below) and used verbatim:

| Token | Light | Dark (derived — see note) |
|---|---|---|
| Page background | `#E9FBFF` | `#0A1418` |
| Card background | `#FFFFFF` | `#101B20` |
| Card border | thin (1px) solid `#010101`-ish | thin (1px) `#E9FBFF` @ ~17% alpha |
| Card radius | 12px | 12px |
| Primary accent | `#49ADFF` | `#49ADFF` (same — reads fine on dark) |
| Text | `#010101` | `#F2FBFD` |
| Muted surface | `#F5F5F5` | `#172226` |
| Muted text | `#737373` | `#93A3A8` |
| Buttons | pill (`StadiumBorder`), semibold, ~32px h-padding | same |
| Font | Plus Jakarta Sans (Google Fonts) | same |

The reference site didn't expose a dark variant in what was inspected
(SPEC.md section 13 says the *original* template has "dark/light ครบ", but
that wasn't reachable from the live inspection session) — the dark column
above is derived to follow the same structural language (thin light border
on dark card instead of thin dark border on white card, same accent,
same radius/pill-button treatment), not extracted from a real dark
snapshot. Documented here as the one token set that's a design judgment
call rather than a direct extraction, per the same honesty standard as
section 1's dataset table.

**Two corrections mid-pass**, from a later screenshot-based re-inspection
of the reference (the first devtools pass read computed CSS but missed
these) — both are baked into the current `app_theme.dart`, not the
originally-briefed values:
1. **Headings are bold, not regular.** The reference's big display/headline
   text (H1/H2-equivalent) is visually heavy (700-800 weight), not the
   originally-assumed "let size carry hierarchy, weight stays regular"
   reading. `AppTheme._buildTextTheme()` now sets `displayLarge/Medium/
   Small` to `FontWeight.w800` and `headlineLarge/Medium/Small` to `w700`;
   body text stays `w400`, buttons/labels/chips stay `w600`.
2. **There's a second, colorful card style** alongside the white/thin-
   border one — pastel tonal blocks (a family riffing on `#49ADFF`: light
   sky-blue, light lavender-blue, medium blue) each with a small black
   (light mode) / off-white (dark mode) rounded-square icon badge, used for
   at-a-glance highlight/summary sections, not dense content. Modeled as
   `lib/widgets/highlight_card.dart`'s `HighlightCard` + the `highlightSky/
   highlightLavender/highlightBlue/badgeBackground/badgeForeground` fields
   on the new `AppColors` theme extension (see below). Used for: the play
   screen's current-game-mode indicator (`_GameModeIndicator` in
   `play_screen.dart`, a `dense: true` `HighlightCard` shown above every
   non-intro round) and the progress page's 3-tile "at a glance" row
   (streak / due-today count / new-today count, top of `progress_page.dart`
   now instead of a single plain streak `ListTile`). Left as the clean
   white-bordered `Card` everywhere denser content lives (word detail
   entries, sentence lists, credits page, the games' own content cards) —
   judgment call per the brief's "don't force every card into one style"
   instruction.
3. **Floating pill nav.** The reference's persistent top/bottom chrome is
   itself a rounded-full bar with the same thin-border/white-bg treatment
   as its cards, floating with margin from the screen edge rather than a
   flush Material `AppBar`/`NavigationBar`. Applied to the app's root shell
   only (`main.dart`'s `_RootPage`, via the new `lib/widgets/
   floating_pill_bar.dart`'s `FloatingTopBar`/`FloatingBottomNav`) — pushed
   detail screens (`word_detail_page.dart`, `credits_page.dart`) keep a
   plain themed `AppBar` (flat, background-colored, no elevation, via the
   theme's `AppBarTheme`) since those aren't the persistent nav this
   pattern is meant for, and forcing the floating-pill treatment onto every
   pushed page seemed like overreach past what the reference actually
   shows.

### What changed, file by file

- **`lib/theme/app_theme.dart`** — full rewrite. Real `ThemeData` (light +
  dark) built from the tokens above: `ColorScheme` (explicit constructor,
  not `.fromSeed`, so the exact extracted hex values are used rather than
  algorithmically derived from a single seed color), `CardThemeData` with
  the thin-border/no-shadow/12px-radius look, pill-shaped `ElevatedButton`/
  `FilledButton`/`OutlinedButton`/`TextButton` themes, `ChipThemeData`,
  `InputDecorationTheme`, themed `AppBarTheme`/`NavigationBarTheme`/
  `TooltipTheme`/`SnackBarTheme`, and a `TextTheme` built from
  `GoogleFonts.plusJakartaSansTextTheme()` with the weight rhythm from
  correction #1 above. Also defines a new `AppColors` `ThemeExtension` —
  `success`/`warning`/`danger` (the four FSRS rating semantics every game
  needs a color for) plus the `highlightSky/Lavender/Blue` +
  `badgeBackground/Foreground` colorful-card family from correction #2 —
  with a `context.appColors` convenience accessor, so every game/screen
  reaches semantic colors through the theme instead of a hardcoded
  `Colors.red`/`Colors.green`/etc. literal.
- **New `lib/widgets/highlight_card.dart`** — `HighlightCard` (colorful
  pastel tile + icon badge, `dense` variant for inline indicators).
- **New `lib/widgets/floating_pill_bar.dart`** — `FloatingTopBar` +
  `FloatingBottomNav` for the root shell (correction #3).
- **New `lib/widgets/result_banner.dart`** — shared correct/almost/wrong
  feedback banner (colored per `AppColors`, animated fade+rise-in) used by
  Cloze/Word Scramble/Dictation, replacing 3 copies of the same unstyled
  ternary `Text`.
- **New `lib/widgets/staggered_entrance.dart`** — shared per-option
  fade+rise entrance animation for MCQ chip grids (Word Association, Odd
  One Out).
- **`lib/main.dart`** — root shell now uses `FloatingTopBar`/
  `FloatingBottomNav` instead of `AppBar`/`NavigationBar`.
- **`lib/games/flashcard_swipe.dart`** — see "Flashcard drag physics" below
  (the task's other headline requirement); also switched its 4 rating
  button colors from hardcoded `Colors.red/orange/green/blue` to
  `context.appColors.danger/warning/success` + `colorScheme.primary`.
- **`lib/games/cloze.dart` / `word_scramble.dart` / `dictation.dart`** —
  input↔result sections wrapped in `AnimatedSwitcher` (fade+size) instead
  of an instant `if/else` swap; result text replaced with the new
  `ResultBanner`; hint-reveal text also animates via a keyed
  `AnimatedSwitcher`. Word Scramble additionally renders its scrambled
  letters as individual `_LetterTile`s with a staggered pop-in
  (`TweenAnimationBuilder` + `easeOutBack`) instead of one static `Text`
  with manual spacing.
- **`lib/games/word_association.dart` / `odd_one_out.dart`** — MCQ chip
  grids now use `StaggeredEntrance` per option; correct/incorrect chip
  tinting switched from hardcoded `Colors.green`/`Colors.red` literals to
  `context.appColors.success`/`danger`; result section wrapped in
  `AnimatedSwitcher`.
- **`lib/games/matching.dart`** — matched-pair chip tinting switched from
  `Colors.green` to `context.appColors.success`, now transitions via
  `AnimatedContainer` instead of an instant color swap.
- **`lib/screens/progress_page.dart`** — top of the page is now a 3-tile
  `HighlightCard` row (streak / due-today / new-today) instead of a plain
  `ListTile` with a hardcoded `Colors.orange` fire icon; heatmap cells gained
  a staggered fade-in + `AnimatedContainer` color transition.
- **`lib/screens/word_detail_page.dart`** — the `is_core` star switched from
  `Colors.amber` to `context.appColors.warning`; the inflection-forms
  expand/collapse (`_InflectionRow`) now animates via `AnimatedSize` +
  `AnimatedRotation` on the chevron instead of an instant conditional
  render, per the brief's explicit callout of this widget as a motion
  candidate.
- **`lib/screens/word_intro_page.dart`** — the rank-1 example-sentence
  reveal (`OutlinedButton` → `Card`) now crossfades/grows via
  `AnimatedSwitcher` instead of an instant swap.
- **`lib/screens/play_screen.dart`** — new `_GameModeIndicator` (a dense
  `HighlightCard`, tone cycled by desirable-difficulty tier per SPEC.md
  section 7's ladder) shown above every non-intro round.
- **No changes needed**: `lib/widgets/word_result_card.dart` and
  `lib/screens/credits_page.dart` already read entirely from `Theme.of
  (context)`/`Card`/`Chip` (no hardcoded color literals to begin with, only
  `IrregularBadge`'s `scheme.errorContainer`/`onErrorContainer`, which is
  still theme-driven), so the new theme applies to them automatically
  without edits.
- **`pubspec.yaml`**: added `google_fonts: ^8.2.0` (`flutter pub add
  google_fonts`, resolved cleanly, no version conflicts against the
  existing dependency set).

### Flashcard drag physics — upgraded, did not already exist

**Checked the pre-pass implementation first, per the task's instruction.**
`lib/games/flashcard_swipe.dart` before this pass had **no drag gesture at
all** — reveal was a `FilledButton` tap, and rating (Again/Hard/Good/Easy)
was purely 4 static `IconButton`s with an instant `onRated` call. There was
no `GestureDetector`, no `Transform.translate`, no live finger-tracking of
any kind — the "swipe" in the class name and doc comment described the
*intended* SPEC.md section 6.1 interaction, not anything actually
implemented yet.

This pass adds real Tinder/Hinge-style drag-follow physics:
- `onPanUpdate` accumulates a live `_dragOffset`, and the revealed
  `WordResultCard` is wrapped in `Transform.translate(offset: _dragOffset)`
  + `Transform.rotate(angle: dragOffset.dx / 900)` — the card visibly
  translates and tilts under the finger in real time, not just at release.
- Two overlay stamps ("จำได้"/"ลืม", colored via `AppColors.success`/
  `danger`) fade in proportionally to drag distance as the user drags,
  giving live directional feedback.
- `onPanEnd` checks both distance (`>110px`) and velocity (`>650px/s`)
  thresholds (either one alone is enough, matching how real card-swipe UIs
  feel — a fast flick shouldn't need to travel as far as a slow drag): past
  threshold, the card animates the rest of the way off-screen in the drag
  direction (`Tween` + `Curves.easeIn`) and *then* calls `onRated`; below
  threshold, it snaps back to center with `Curves.elasticOut` (a visible
  spring-back, not an instant reset).
- The 4 rating buttons still exist (kept per SPEC.md 6.1's "ปุ่มเสริม" for
  Hard/Easy, which have no natural swipe direction) but Again/Good now
  route through the *same* `_flyOffAndRate` animation instead of firing
  `onRated` instantly, so button-tap and swipe feel like the same
  interaction language rather than two different response speeds.
- A `_resolved` guard flag prevents double-firing `onRated` if a drag
  release animation is already in flight when a button is somehow also
  tapped.

### Verification performed

- **`flutter analyze`: clean, 0 issues** (one deprecation warning surfaced
  mid-pass — `SizeTransition.axisAlignment` in `word_intro_page.dart` — and
  was fixed by dropping the now-redundant parameter rather than left as a
  lint).
- **`flutter test`: 91/91 passing, unchanged from before this pass** — this
  was a presentation-only pass (no `lib/domain/**`/`lib/data/**` edits), and
  no new widget tests were added (the repo has never had pumped widget
  tests for any game — see section 9's "Not done" note above, which is
  still accurate; this pass didn't change that, since verifying it was
  scoped to `flutter analyze`/`flutter test`/`flutter build web` per the
  task, not adding new test coverage).
- **`flutter build web`: succeeds** — same pre-existing non-fatal
  `flutter_tts` web-shim wasm-compat lint warnings as every prior build in
  this repo (see section 3's Phase 1 verification), no new errors from the
  theme/`google_fonts` changes.
- **Not done, same as every prior pass**: actual on-device/simulator visual
  verification (no iOS simulator/Android emulator/working desktop build in
  this environment — see section 3's "Not done" note, unchanged). The user
  will review the real rendered UI themselves in a browser per the task's
  own instruction; this pass's target was correct, compiling theme/widget
  code, not self-verified pixels.
- **Confirmed no account/auth UI exists anywhere** (`grep`-checked
  `lib/**` for login/account/password/auth-shaped identifiers — the only
  hits were `imageAuthor`/`translationSource` field names on
  `credits_page.dart`, false positives from "auth" being a substring of
  "Author"). Matches the task's expectation for a single-device, local-only
  app with no account system; no changes were needed here.

## Scheduling revision: no forced sleep-gap wait, 3am day boundary (2026-07-23)

User tested the desktop build and hit the sleep-gap wall almost immediately
(a handful of intro cards, then "เคลียร์หมดแล้ว เก่งมาก! กลับมาใหม่พรุ่งนี้"
with zero games played) — reasonable per the original spec, but the user
decided the design should change: **no fixed number of games/days per word
— if the user is ready to keep going, let them**, while still needing to
know when "today" rolls over, anchored at **3am** instead of midnight.

Changes (SPEC.md §6.2/§6.4 updated to match):

- **Removed the sleep-anchored floor entirely.** `lib/domain/fsrs/sleep_gap.dart`
  deleted; `play_screen.dart`'s `_handleIntroContinue`/`_handleRated` no
  longer override `dueAt` — it's whatever FSRS-5 computes natively (for a
  first "Good" that's ~3.9 days at the default 0.88 retention target; for an
  "Again" it's ~12h, so same-day re-review is now possible again, which
  `fsrs5.dart`'s doc comment now documents instead of claiming it's
  unreachable).
- **New-card cap no longer dead-ends a session.** `session_engine.dart`'s
  `buildQueue` still uses `new_card_cap` to pace an ordinary day, but if
  overdue + capped-new + extra-practice would leave the queue empty while
  un-introduced words remain, it now falls back to adding the rest rather
  than ending the session. The governor (backlog/accuracy-based cap
  adjustment) is unchanged — it's a pacing suggestion now, not a hard wall.
- **3am logical-day boundary**, added as `kDayBoundaryHour`/`logicalDate`/
  `logicalDateKey` in `streaks.dart`. Deliberately kept separate from the
  existing `dateKey`/`dayStreak`/`monthHeatmap` (which stay plain
  calendar-date math, since they iterate synthetic calendar grid dates, not
  real event timestamps) — `logicalDateKey` is only used at the handful of
  call sites that convert a genuine `DateTime.now()` for bookkeeping
  (`play_screen.dart`'s daily-stats keys, `progress_page.dart`'s streak
  cursor + "new words today" stat lookup). A session at 1am still counts
  toward yesterday; one after 3am already starts a new logical day.

### Verification performed

- `flutter analyze`: clean, 0 issues.
- `flutter test`: 93/93 passing (removed 3 stale `sleep_gap` tests from
  `fsrs5_test.dart` since that file no longer exists; added 2 new
  `session_engine_test.dart` cases covering the never-dead-ends fallback
  and confirming the cap is still respected when other content already
  fills the queue, plus 3 new `streaks_test.dart` cases for the 3am
  boundary).

## Intro card removed + continuous-play loop (2026-07-23, same session)

Follow-up product decision from the user right after the scheduling
revision above: **remove the separate new-word intro page entirely** — a
brand-new word is just a flashcard round now — and design the endless
session so play can genuinely continue for as long as the user wants,
with the day (post-3am boundary) always opening on a flashcard.

- **`word_intro_page.dart` deleted; `GameType.intro` removed from the
  enum.** New words enter `GameType.flashcard` directly with a new
  `isNewWord` mode on `FlashcardSwipeGame`: front = headword + TTS
  (auto-spoken once, preserving the old intro's dual-coding), reveal =
  the full `WordResultCard` back (reading/meaning/sentence/word-detail
  link), swipe labels change to **ขวา = รู้จัก (Good) / ซ้าย = ไม่รู้จัก
  (Again)**, Hard/Easy buttons hidden. That first swipe doubles as the
  word's first FSRS review — `play_screen._handleRated` now detects the
  absent SRS row (`isFirstEncounter`), counts `new_introduced` for the
  day, and logs the review, replacing the deleted
  `_handleIntroContinue`'s auto-"Good" (the rating is now the user's real
  answer instead of an assumed Good).
- **Continuous-play loop** (`session_engine.buildQueue`, SPEC.md §7
  updated): priority stays overdue → capped-new → extra practice →
  beyond-cap new words. Extra practice widened from young/mature-only to
  *any* word with SRS history not currently due (early on everything is
  learning — the old pool was empty exactly when the loop needed it) and
  now rotates deterministically through `kPracticeGameCycle`
  (flashcard → matching → oddOneOut → cloze → wordAssociation →
  wordScramble → dictation), wrapping back to flashcard, instead of
  random ladder-tier picks — per the user's "ทำ loop ทุกเกมแล้ว กลับมา
  flashcard ใหม่". Unbuildable rounds still fall back to flashcard at
  render time (existing `_fallbackToFlashcard` path).
- **Day opens with flashcard**: `buildQueue` gained
  `firstSessionOfDay` — when true (play_screen sets it when today's
  logical date has no `daily_stats` row yet, i.e. first entry after the
  3am boundary) the queue's first item is forced to
  `GameType.flashcard`, preserving word/source/direction. Consumed after
  the day's opening build.
- `_GameModeIndicator` shows "คำใหม่" (lavender) for a first-encounter
  flashcard and plain "Flashcard" (sky) otherwise.
- SPEC.md §1/§2 defaults/§3 tree/§7/§8/§9.1 all updated to match.

### Verification performed
- `flutter analyze`: clean, 0 issues.
- `flutter test`: **97/97 passing** — updated the ladder test (new →
  flashcard), added 4 new `session_engine_test.dart` cases: new-card
  items are flashcard rounds; extra practice includes learning words;
  practice rounds rotate through the full `kPracticeGameCycle` in order;
  `firstSessionOfDay` forces the opening item to flashcard while
  preserving word/source.

## "You Pass" full-mastery screen + practice-cycle order rationale (2026-07-23)

Two follow-ups in the same session:

- **"You Pass" screen** (user: "ถ้าฉันสามารถผ่านทุกคำในทุกเกมได้จะให้ขึ้น
  หน้าจอ You Pass"). Condition: every word answered correctly (rating ≠
  Again — Hard counts, it's still a correct answer) **at least once in
  every one of the 7 game types**, derived from `reviews_log` rather than
  new state: `loadPassedWordGamePairs()` on the store interface (SQLite:
  one `SELECT DISTINCT word_id, game_type ... WHERE rating != 'again'`;
  memory impl mirrors it) returns the passed cells of the words×games
  grid, and `domain/mastery.dart` (`fullMasteryReached` /
  `masteryProgress`) evaluates it. `play_screen._maybeCelebrateMastery`
  runs after each *correct* rating (skips on Again — an Again can never
  complete the grid; also skips once shown), and the first time the grid
  is complete it persists `you_pass_shown=1` and pushes the full-screen
  `screens/you_pass_page.dart` — trophy badge, "You Pass", "X คำ × 7
  เกม", staggered entrance, "เล่นต่อ" button popping back to the endless
  session. Fires exactly once per profile.
- **Practice-cycle order finalized** (user delegated the rotation order:
  "เกมเป็นคนกำหนดได้เลยเอาตามความเหมาะสมที่สอดคล้องกับวิจัย").
  `kPracticeGameCycle` now ramps shallow→deep per levels-of-processing /
  expanding-retrieval logic, with the rationale documented on the
  constant: flashcard (recognition) → matching (batched recognition) →
  oddOneOut (semantic categorization) → **wordAssociation (semantic
  network — moved before cloze)** → cloze (cued recall in context) →
  wordScramble (orthographic production) → dictation (full production
  from audio). Only change from the initial order: association now
  precedes cloze, since semantic-network retrieval is shallower than
  producing the word inside a sentence.

### Verification performed
- `flutter analyze`: clean, 0 issues.
- `flutter test`: **102/102 passing** — new `mastery_test.dart` (5 cases:
  full grid true; single missing cell false; fresh profile false;
  progress counting; memory-store pair collection ignoring Again and
  deduping repeats).

## Mastery rules v2: lapse resets the word's row + solid-word fade-out (2026-07-23)

User refinement of the "You Pass" rules immediately after v1 shipped:

- **A wrong answer resets the whole word, not just that game.** One
  Again on a word — in *any* game — wipes its entire mastery row (all 7
  cells) and it must re-earn every game from scratch. The goal is "keep
  looping until you can get through everything without a single miss".
  Implemented in `loadPassedWordGamePairs()` (both stores) by only
  counting correct answers with `ts >` the word's latest Again in
  `reviews_log` (SQLite: correlated `MAX(ts)` subquery; memory impl
  mirrors it). No schema change — still derived purely from the log.
- **Already-solid words fade out of the loop.** New store method
  `loadCorrectStreaks()` (passes since last Again, per word) feeds
  `buildQueue`'s new `correctStreaks` param; the extra-practice pick is
  now a **weighted sample without replacement**
  (`weightedPracticeSample`, weight `1/(1+streak)`) instead of a plain
  shuffle — a word on a 9-streak has 10% the draw weight of a fresh or
  just-lapsed word. Rationale (user): after a late-stage lapse, an
  unweighted loop would keep re-serving easy words and take forever to
  get back to the hard ones. Monotonic-decreasing weight documented on
  `practiceWeight`.
- `_maybeCelebrateMastery`'s skip-on-Again shortcut still holds (an
  Again can only shrink the grid). `you_pass_shown` once-ever unchanged.

**v3 correction (same day, user clarified intent):** the v2 per-word
reset was too narrow. The real rule: "You Pass" = **one clean round** —
every word × every game passed **with zero wrong answers anywhere in
between**. One Again on ANY word resets the ENTIRE grid (all words, all
games); the counting exists purely to finish that single flawless round.

- `loadPassedWordGamePairs()` (both stores) now only counts passes after
  the latest Again **anywhere** in `reviews_log` (global MAX(ts)
  subquery), not per-word.
- `loadCorrectStreaks()` deliberately stays **per-word** — the fade-out
  weighting measures how solid each word is, and missing word A must not
  make word B look weak (documented on both impls).
- The practice loop now actively drives round completion: `buildQueue`
  gained `passedPairs`, and each of the 10 practice slots narrows its
  candidates to words **still missing that slot's game cell** in the
  current round (falling back to any unused word when none are missing)
  before applying the `practiceWeight` sampling. Without this, after a
  late reset the loop would keep re-serving already-earned cells and a
  153×7=1071-cell clean round would be practically unreachable.
- Tests updated to the global-reset semantics + new targeting test
  (`flutter test`: 109/109; `flutter analyze` clean).

**v4 (same day): grid narrowed to the 4 "serious" games.** User decision:
the full 7-game clean round was statistically unreachable (0.99^1071 ≈
0.002%), so the mastery grid now counts only the games with unambiguous
right/wrong answers — **Flashcard, Matching, Cloze, Dictation**
(`kMasteryGames` in domain/mastery.dart, 153×4 = 612 cells at the time
— 253×4 = 1,012 after the same evening's A2/B1 extension). The other
three (Odd One Out / Word Association / Word Scramble) stay in the play
rotation but are **streak-only**: their passes don't fill grid cells and
their misses don't reset the round (both store impls filter
`reviews_log` by `kMasteryGameNames` for cells AND for the global-reset
Again lookup; streaks still count all 7 games). play_screen's
`_maybeCelebrateMastery` also short-circuits on non-mastery games;
YouPassPage shows "X คำ × 4 เกม". Tests: 111/111 (new cases: mastery
list is exactly the 4; streak-only passes add no cell; streak-only Again
does NOT reset the grid).

## 2026-07-23 (afternoon): play-test feedback rounds 1-6

Rapid feedback loop with the user playing the Windows build. Each round
committed separately — see git log between 53d8032 and this section's
commit. Summary of what changed:

- **Flashcard v2**: swipeable immediately (no reveal-button gate), tap
  flips to the answer (optional), only รู้จัก/ไม่รู้จัก everywhere
  (Hard/Easy buttons removed), first-encounter รู้จัก upgrades to
  Rating.easy. Stuck-invisible-card bug fixed (per-item KeyedSubtree —
  Flutter was reusing the previous card's flown-off-screen State).
- **Matching v2**: connect-the-lines — drag (or tap-tap) to link, lines
  drawn with a per-pair color from a 12-color palette, chip borders
  match their line color, tap a linked chip to break/redo the pair,
  "ตรวจคำตอบ" grades all at once (correct locks green, wrong turns red
  and stays editable). Ratings unchanged (Good/Hard, never Again).
  Batch: always 4-6 pairs (random), ≥2 of them the player's
  weakest-streak words.
- **Cloze**: sentence TTS button (pre-answer reads the blank as
  "blank"), center-aligned text, grammar reason card on reveal when the
  blank is an inflected form (283/362 inflected sentences covered via
  form-text matching; form_id was never populated by the pipeline).
- **Dictation**: slow-speech replay button (TtsService.speakSlow, rate
  0.22 vs 0.45). Credits page crash fixed (cascade-precedence bug
  sorting a const list).
- **Difficulty/pacing**: retention target moved to the ~80% zone
  (initial/target 0.80, range [0.70,0.90], one-time boot migration for
  stored >0.84 values). NewCardGovernor hot-streak burst: last-20
  accuracy ≥92% + no backlog → cap +3 per answer; same signal lets
  buildQueue top the queue up with beyond-cap new words to 40% share.
- **Practice loop shape**: each game in the cycle now runs 2-4 random
  consecutive rounds (distinct words); flashcard blocks are 4-8 cards
  with a triangular distribution (4 + d3 + d3 — user asked that middle
  counts be most likely). Play screen content centered, max-width 480
  (mobile-first).

## 2026-07-23 (evening): dataset extension — +50 A2, +50 B1 (253 total)

User request: "เพิ่มคำศัพท์ A2 มาสัก 50 คำ B1 50 คำ". Built
`tools/extend_a2b1.py`, a resumable 4-stage extension pipeline reusing
the exact Phase 1 sources:

- **Selection**: Oxford CEFR JSON (same Kolia951 source), each band
  EXCLUDING words listed in any lower band (the source lists a word
  under every band one of its senses belongs to — without this filter
  "face"/"head"/"now" showed up as B1). Candidates ranked by SWOW-EN18
  responseStats `Freq.R123` (real human-association frequency; also
  guarantees SWOW coverage). Top 62/band as buffer, first 50 passing
  all QC kept.
- **POS**: WordNet most-frequent synset POS (+ manual override map).
- **meaning_th**: real Wiktionary Thai rows via wiktapi.dev; the model
  only PICKS among them. 7 words had no Thai row and are approx-flagged
  like "make": round, rude, bright, calm, shiny, fancy, rough.
- **Readings/collocations/sentences/grammar notes**: gemini-3.6-flash,
  5-word batches, validated with the Phase 1 QC rules + new metadata
  checks (Thai-script reading, stress within syllable count, IPA shape,
  wiktionary-pick honesty). 9 words were dropped as "unrecoverable"
  purely because the cheap same-stem cloze check rejects legitimate
  irregular forms (armies, skies, knives, uglier, tinier, stuck, shied):
  army, sky, lost, broken, knife, ugly, tiny, stick, shy — future pass
  should teach the validator irregular inflection instead.
- **SWOW**: new words as cues get top-6 in-vocab rows (all 100/100 have
  real data); old A1 cues additionally gain up to 2 strongest new-word
  responses. Gotchas hit: the strength file is TAB-delimited (unlike
  responseStats) and effectively unquoted (needs QUOTE_NONE +
  field_size_limit); responseStats' first unnamed column is a row index
  that dwarfs the real Freq columns.
- **Merge**: generated `tools/ext_a2b1.py` (WORDS_EXT/THAI_EXT/
  SENT_EXT/SWOW_EXT), consumed by try/except-import shims appended to
  wordlist.py / thai_data.py / llm_sentences.py / swow_associations.py —
  build_dataset.py itself unchanged except widening the irregular
  verb/plural tables for A2/B1 coverage (break/broke, foot/feet, ...).
- **Result**: vocab.db rebuilt — 253 words (153 A1 + 50 A2 + 50 B1),
  1,265 sentences, 0 new words missing sentences or related_words, QC
  pass OK, `flutter test` 117/117. freq_rank continues 154..253 (A2
  before B1) so new-card introduction finishes A1 first.
- **Process debt noted**: stages B/C originally ran serially — fixed
  the same evening on the user's instruction ("แก้ตอนนี้เลย ออกแบบให้
  code ทำงาน parallel"): stage B = ThreadPoolExecutor(8) over per-word
  fetches (each worker fully self-contained, periodic checkpoint under
  a lock; 124 fetches 2.1s vs ~90s), stage C = 5 concurrent Gemini
  batch calls per retry round, JSON validation kept on the main thread.
  Rerun after the rewrite produced a byte-identical tools/ext_a2b1.py.

## 2026-07-24: practice-cycle v2 (3-6 games), new-words-in-flashcard-block, dictionary search tab

Three user requests, all in `session_engine.dart` + one new screen:

1. **Random 3-6 games per cycle** (was: all 7 every cycle). Count uses
   the same dice trick as the flashcard block size — `3 + d2 + d3`
   gives 3..6 with P(4)=P(5)=1/3 and the extremes at 1/6 ("สูตร
   สามเหลี่ยมเช่นกัน"). Flashcard is ALWAYS included and always first
   ("วนรอบเกมมาแล้ว กลับไปที่ flash card"); the other slots are drawn
   from the remaining six games but keep `kPracticeGameCycle`'s
   shallow→deep order among those chosen.
2. **New words are part of the flashcard block now** ("นับ new word
   เป็นกลุ่มเดียวกับรอบ flash card") — the standalone capped-new
   segment between overdue and practice is gone. Each flashcard
   block's 4-8 slots are filled by today's capped new words FIRST,
   then topped up with practice words. The queue-empty fallback
   (beyond-cap new words) and the hot-streak 40% top-up are unchanged.
   Gotcha: when the flashcard block runs out of BOTH new and practice
   words it `break`s to the next game rather than `break outer` —
   later games decide for themselves (a fresh install has zero
   practice words but must still serve new cards).
3. **Dictionary search tab** ("อยากให้มี feature หาคำศัพย์") — new
   `screens/dictionary_page.dart`, third nav tab (เล่น · ค้นหา ·
   ความก้าวหน้า). One search box filters live against headword, Thai
   reading, every sense's meaning_th, and inflected forms; rows show
   headword + CEFR chip + reading·core meaning + TTS button; tap opens
   the existing `WordDetailPage`. All bundles are loaded once on tab
   open (253 words ≈ 5 IN-clause queries) and filtered in memory.

Tests: the runs-compression test now asserts invariants over 50 random
builds (3-6 runs, flashcard first, strictly-increasing cycle indexes,
4-8/2-4 lengths, distinct words) instead of one exact sequence, plus a
new test that capped new cards sit inside the flashcard block before
any non-flashcard item. Suite 118/118, analyze clean.

---

## 2026-07-24 (2): SWOW re-rank, difficulty-weighted sampling, accuracy-scaled new-word share, 4-round cap reset

Four user requests in one batch:

1. **SWOW re-rank** ("คำใช้บ่อย rerank ด้วย swow") — the A1 chunk's
   freq_rank was the curated Oxford-list order, not a measured
   frequency; now the WHOLE 253-word list is ranked band-major
   (A1<A2<B1) by SWOW-EN18 responseStats Freq.R123, the same metric
   Stage A used for A2/B1. New A1 top: money, water, food, car, music.
   `tools/rerank_swow.py` (deterministic) generates
   `tools/swow_rerank.py` (RANKS dict); a shim at the end of
   wordlist.py remaps rank VALUES only — the WORDS list order (and so
   build_dataset's insert order and every word id srs_state references)
   is untouched. Seed vocab.db rebuilt, QC OK, ids verified stable
   (money id 93 / rank 1; pain still id 154).
   **Gotcha:** the app only copies the seed DB when the writable copy
   is MISSING (vocab_store_sqlite.open) — an existing install keeps its
   old content until its Documents/vocab.db is deleted. True for the
   A2/B1 extension too. A content-version reseed that preserves
   app-state tables is future work.
2. **FSRS difficulty joins the practice weight** — practiceWeight is
   now `(1/(1+streak)) × (difficulty/5)` (d∈[1,10], neutral 5): a
   word FSRS has learned is hard for this player is drawn ~1.8×, an
   easy one 0.4×. Applied in weightedPracticeSample (all practice
   rounds) and the Matching weakest-2 pick (same weight replaces the
   plain streak sort).
3. **New-word share per flashcard block scales with recent accuracy**
   (replaces the on/off hotStreak 40% queue-wide top-up):
   `share = 0.4 × clamp((acc20 − 0.5)/0.4)` — ≥90% right → 40% of the
   block is new words, 70% → 20%, ≤50% → none; no data yet → 40%.
   Share ignored when the practice pool is empty (fresh install: a mix
   ratio can't apply with nothing to mix), where the cap alone rules.
   Governor gained public `recentAccuracy()` (null under 10 samples);
   `isHotStreak`/burst cap growth unchanged.
4. **Every 4 completed flashcard rounds reset the day's new-word
   count** ("ไม่อยาก limit flash") — play_screen detects a flashcard
   block ending in _advance (leaving item is flashcard, next isn't),
   counts it in settings `fc_rounds` = "date:count"; on the 4th the
   day's introduced count is forgiven via `new_intro_forgiven` =
   "date:total" (daily_stats keeps the real total for stats; the
   effective count = stats − forgiven, clamped ≥0, re-derived on
   boot). Both keys self-reset when the logical date changes.

Suite 121/121, analyze clean.

### Play-test round 2 fixes (same day, after the DB reset)

- **Matching advanced the queue 4-6 items per round** — the real cause
  of "แต่ละรอบมีเกมเดียว / เหมือนกดเล่นอัตโนมัติ": _handleMatchingResult
  routed every pair's rating through _handleRated, and each of those
  ended with `_advance()`. One 5-pair matching round silently consumed
  5 queue items, skipping the games (and the folded-in new-word cards)
  behind it — which also made new words LOOK like they weren't part of
  the flashcard block. Fixed by splitting `_recordRating` (persist
  only) out of `_handleRated` (persist + advance): matching records
  all pairs then advances exactly once.
- **New-word indicator**: was replacing the game label with "คำใหม่";
  now shows the normal Flashcard mode card + a compact lavender
  "คำใหม่" badge beside it (user: a new word IS a flashcard, keep only
  the icon distinct).

### Odd One Out coherence pass (2026-07-24, user: "กลุ่มคำไม่ค่อยเหมือนกัน")

`buildOddOneOutGroup` rewritten around one consistent coherence bar:
- A row counts as same-group only if it's typed category data
  (hypernym/category/part_of) or its SWOW closeness ≥ **0.03** —
  chosen as ≈ the seed data's 75th percentile (distribution: min
  0.003, median 0.014, p75 0.034, p90 0.082); 68/253 hubs still have
  ≥3 strong in-vocab members at that bar.
- Minimum **3 group members**, the old fallback-to-2 removed.
- **Strict early-game mode** (play_screen passes
  `strict: srsStates.length <= 8`, ≈ the first 2 new-word blocks):
  requires >2 qualifying groups to exist or Odd is skipped entirely
  (falls back to flashcard as before). User picked this scope
  explicitly ("ช่วงเริ่มเล่นแอป").
- Groups scored by total closeness; a Random picks among the top ≤5 so
  rounds don't repeat the single strongest hub forever.

Suite 124/124.

---

## Current status & remaining work (as of 2026-07-23 evening)

**Where things stand:** Phase 1 + Phase 2 are fully built (all 7 games,
both hint families, full grammar notes, word detail page, focus topic,
credits). The dataset is **253 real-sourced words — 153 A1 + 50 A2 +
50 B1** (approx-flagged Thai glosses: "make" + the 7 adjectives listed
above). The meeting-iq UI design pass is applied. All 2026-07-23
product revisions are in: no intro card, no forced sleep-gap, 3am day
boundary, endless continuous-play loop with 2-4 rounds/game (flashcard
4-8 triangular), You Pass clean-round system (4 mastery games / 3
streak-only, global reset, missing-cell targeting + streak fade-out),
~80% retention zone, hot-streak burst + 40% new-word share, flashcard
v2 swipe-first UX, matching v2 connect-the-lines, centered mobile
layout — plus the 2026-07-24 batches (random 3-6 games per cycle, new
words folded into the flashcard block, dictionary search tab, SWOW
re-rank, difficulty-weighted sampling, accuracy-scaled new-word share,
4-round cap reset; see the sections above). `flutter analyze` clean;
`flutter test` 121/121; Windows desktop build works; repo is
github.com/pimdejvani/Esh_Learner (public).

**Remaining work, in recommended order:**

1. **User plays the current build and gives UI/feel feedback** — the
   evening batch hasn't been play-tested by a human yet: matching
   connect-the-lines v2, 4-8-card flashcard blocks, the 100 new A2/B1
   words, the ~80% retention zone, hot-streak burst + 40% new share.
   (`cd vocab_app; flutter run -d windows`)
2. **Show clean-round progress** — the You Pass grid fills silently;
   the player can't see "xxx/1,012" (253 words × 4 mastery games after
   the dataset extension) or notice a reset happened.
   `masteryProgress()` already computes the numbers; only the UI surface
   is undecided (play screen chip vs progress page card — user was asked
   but hasn't chosen yet).
3. **Scale dataset 253 → 3,000 words** (Phase 3, biggest job): the
   machinery now exists — `tools/extend_a2b1.py` did 100 words
   end-to-end (2026-07-23) and is resumable/rerunnable, and is now
   PARALLEL (same evening): stage B fans out over 8 worker threads
   (124 wiktapi fetches: ~90s serial → 2.1s) and stage C runs 5 Gemini
   batches concurrently per round with validation on the main thread;
   verified byte-identical ext output on rerun. Before the full run:
   (a) teach the cloze validator irregular inflections
   (armies/knives/stuck were wrongly rejected), (b) raise
   PER_BAND_TARGET / add B2. Real API cost.
4. **3D card-flip motion for Flashcard** (user request 2026-07-23, same
   tier as the 3,000-word job): tapping the card should show a real
   flip animation (rotateY via `AnimationController` +
   `Transform(Matrix4.rotationY)` with a perspective entry, swapping
   face at the 90° midpoint — the standard Flutter approach; research
   community packages e.g. `flip_card` vs hand-rolling before building).
   Today the tap swaps faces with a fade/scale AnimatedSwitcher only.
5. **Dictation: remove the Thai meaning from the game card** (user
   request 2026-07-23, same tier as the 3,000-word job): today the game
   shows `coreSense.meaningTh` under the listen buttons, which turns a
   pure listening/spelling task into a translation-assisted one. Drop it
   (keep audio + hints only); decide whether the reveal still shows the
   meaning via WordResultCard (it should — reveal is post-answer).
6. **Images** — schema fields (`has_photo`/`image_url`/license/author)
   exist but the Openverse/Wikimedia URL-resolution step was never run,
   and the app has no runtime image fetch/cache yet (SPEC.md decision #3).
7. **iOS build** — SPEC.md targets iOS-first but everything so far is
   verified on Windows/web only; needs a Mac/Xcode (not possible on this
   machine).
8. **Tune FSRS/governor from real logs** — blocked on accumulated play
   data, revisit after the user has played for a while.
9. **Backlog (explicitly deferred):** confusables ("อย่าสับสนกับ"), app
   name + logo, Android/iPad decision, multi-device sync, full XP/badge
   layer.

### Verification performed
- `flutter analyze`: clean, 0 issues.
- `flutter test`: **108/108 passing** — mastery_test reworked with real
  timestamp ordering (3 reset cases: post-lapse pairs only; Again in one
  game wipes passes earned in other games while other words keep theirs;
  re-earned passes count again) + streak counting + `practiceWeight`
  monotonicity; session_engine_test adds pool-smaller-than-count
  inclusion and a 200-draw statistical check that a streak-1M word
  almost never beats a streak-0 word (>195/200 with a fixed seed).
