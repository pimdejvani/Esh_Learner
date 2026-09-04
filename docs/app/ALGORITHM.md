# Esh_Learner — System Calculations Reference

Single source of truth for every number the app rolls, weights, or selects:
randomness, word importance, and word selection across all seven games.
Written 2026-07-24 (feedback item 16). Code references in parentheses.

---

## 1. The endless queue (`session_engine.dart` `buildQueue`)

Each refill produces an ordered list of `SessionItem`s. Priority:

1. **Overdue reviews** — words whose `dueAt <= now`, oldest-due first,
   then round-robin interleaved so the same word never repeats
   back-to-back (`_interleave`).
2. **Practice cycle** — a random selection of games (see §2), whose
   flashcard block also carries today's new words (see §4).
3. **Beyond-cap new words** — only if the queue would otherwise be empty
   (never a hard wall).

The first queue after the 3 AM logical-day boundary is forced to open
with a flashcard round.

---

## 2. Which games play this cycle (item, 2026-07-24)

- **Count:** `3 + d2 + d3` → **3–6 games**, triangular (P(4)=P(5)=⅓,
  P(3)=P(6)=⅙). (`d2 = nextInt(2)`, `d3 = nextInt(3)`.)
- **Flashcard is always included and always first.** The other slots are
  drawn uniformly from the remaining six games, then reordered to keep
  `kPracticeGameCycle`'s shallow→deep sequence: flashcard → matching →
  odd one out → word association → cloze → scramble → dictation.
- After the last game the cycle wraps back to flashcard.

### Rounds per game
- **Flashcard block:** `4 + d3 + d3` → **4–8 cards**, triangular (peak 6).
  Overridden during onboarding (§5) and on onboarding exit (fixed 8).
- **Other games:** `2 + d3` → **2–4 rounds**, uniform. **Early game**
  (< 40 words with any SRS history) shortens this to `1 + d2` → **1–2
  rounds** (item 18).

Each round uses a distinct word (`usedIds`).

---

## 3. Word importance & selection (practice rounds)

For every practice round the candidate word is drawn by a weighted
sample without replacement (`weightedPracticeSample`), weight:

```
weight(word) = 1 / (1 + correctStreak) × (difficulty / 5)
```

- **`correctStreak`** — consecutive correct answers since that word's own
  last "Again" (`loadCorrectStreaks`). A word you keep getting right fades
  out (streak 0 → ×1.0, 4 → ×0.2, 9 → ×0.1).
- **`difficulty`** — the FSRS per-word difficulty (1–10) — hard-for-you
  words surface more (item 15/2). `/5` centres it near 1.0.

Before weighting, candidates are narrowed to words still **missing that
game's cell** in the current clean-round "You Pass" grid (`passedPairs`)
when any exist, so the loop drives the round toward completion.

Words that supply EXTRA words to a game (matching pairs, odd-one-out
members, word-association options) are always drawn from **seen words
only** — never quiz with a word the player has never met.

---

## 4. New words

- **Daily cap** starts at 8, adapts in [3, 15] (`NewCardGovernor`):
  high backlog shrinks it; low backlog + good accuracy grows it;
  a **hot-streak burst** (last 20 reviews ≥ 92% accuracy, ≥ 10 samples,
  low backlog) grows it by +3 instead of +1.
- Cap resets its *effective* count to 0 every **4 completed flashcard
  rounds** in a day (so flashcards are never truly limited).
- **New words live inside the flashcard block** (not a separate segment).
  Block slots are filled by new words first, then practice words.
- **New-word share of a block** scales with recent accuracy:
  ```
  share = 0.5 × clamp((recentAccuracy − 0.5) / 0.4, 0, 1)
  ```
  → up to **50%** at accuracy ≥ 0.9, tapering to **0%** at ≤ 0.5
  (item 17). `null` accuracy (no data) counts as 0.5 share. When there
  is nothing to review at all, the block fills with new words up to the
  cap (a mix ratio is meaningless with nothing to mix).
- **New-word ordering:** normally easy→hard by `freq_rank`. On a **hot
  streak** (recentAccuracy ≥ 0.9) hardest-first instead, by proxy
  `CEFR band × 100000 + freq_rank` (item 15).

---

## 5. Onboarding ramp (`play_screen._onboardingRamp`, item 19)

While `onboarding_done` is unset:

- **First flashcard block = 10 all-new words.**
- Score **≥ 90%** on the recent window → next block another 10 (up to 3
  blocks / 30 words), then normal mode.
- First block that misses 90% → onboarding ends; that block is a fixed
  **8 cards** and new-word share reverts to the §4 calc.
- ≥ 30 learned words → onboarding ends unconditionally.

---

## 6. Flashcard EN/TH prompt mix (item 14)

Within a flashcard block, **review** cards get a randomized direction
mix; **new** cards always meet the player EN→TH:

- Count of EN→TH among the `n` review cards = `(nextInt(n+1) +
  nextInt(n+1)) ~/ 2` (triangular over 0..n).
- Those positions are chosen by shuffling the review indices — so a block
  is never all-Thai or all-English (`_mixFlashcardDirections`).

Direction otherwise alternates per word via `last_direction`.

---

## 7. Per-game selection specifics

- **Matching** (`_pickMatchingBatch`): 4–6 pairs (`4 + nextInt(3)`), at
  least 2 being the player's weakest (lowest streak×difficulty) seen
  words; fill order seed → 2 weakest → learning → by-weakness → any seen.
  Fewer than 4 seen words → the round becomes flashcard.
- **Odd One Out** (`buildOddOneOutGroup`): a word counts as same-group
  only if typed category data (hypernym/category/part_of) **or** SWOW
  `closeness ≥ 0.036`. Needs **≥ 3** members + 1 odd. Early game
  (≤ 8 words with history) also requires **> 2** qualifying groups or the
  game is skipped. Among qualifying groups the pick is **uniform random**.
  A wrong answer records "Again" for both the target and the picked word.
- **Word Association** (`pickAssociationTarget` / `buildAssociationOptions`):
  correct answer = strongest non-giveaway `association` row among seen
  related words; 3 distractors from seen words excluding the target's own
  related set.

---

## 8. Hint ladder (typed games — Dictation, Cloze, Word Scramble; item 12)

Fixed progressive sequence (`buildHintLadder`), one step per press, then
no more:

1. letter count
2. closest meaning-related word the player already knows
   (omitted if none)
3. first letter
4. Thai meaning
5. first & last letter

Using **any** step caps the eventual rating at **Hard** (`capForHint`),
even on a correct answer. Word Association keeps its own family-A
semantic hint (reveal successively weaker related words).

---

## 9. Scheduling & difficulty (FSRS-5)

- **Grades:** right swipe / correct = Good (Easy if fast or first-meet);
  wrong / "Again" = lapse (drops the card back to learning). Matching
  only ever emits Good/Hard (never Again).
- **`requestRetention`** targets ~0.80, adaptive in [0.70, 0.90]: recent
  accuracy above the 0.80±0.03 band lowers it (longer intervals, harder);
  below raises it (`RetentionTuner`). One-time boot migration snaps stored
  values > 0.84 down to 0.80.
- FSRS stability/difficulty per word drive `dueAt`; difficulty also feeds
  the practice weight (§3).

---

## 10. "You Pass" clean-round grid (`mastery.dart`)

- Grid = every word × the **4 mastery games** (Flashcard, Matching,
  Cloze, Dictation). A cell fills on a correct (non-Again) answer.
- **One Again in any mastery game wipes the whole grid.** The 3
  streak-only games (Odd One Out, Word Association, Word Scramble) neither
  fill cells nor reset it.
- Full grid → the "You Pass" celebration.
