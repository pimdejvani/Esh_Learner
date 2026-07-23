/// Endless-queue session engine (SPEC.md section 7). Pulls "next item"
/// requests one at a time. Priority: overdue reviews (oldest-due first) >
/// practice cycle (random 3-6 games, flashcard always first — new cards
/// up to today's cap are served as cards INSIDE the flashcard blocks).
/// Interleaves across topics/words instead of grinding one word
/// repeatedly, and tracks last_direction per word so EN->TH/TH->EN
/// alternates instead of repeating.
library;

import 'dart:math';

import 'package:vocab_app/domain/new_card_governor.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';

enum GameType {
  flashcard,
  cloze,
  matching,
  wordAssociation,
  wordScramble,
  oddOneOut,
  dictation,
}

enum QueueSource { overdueReview, newCard, extraPractice }

class SessionItem {
  const SessionItem({
    required this.wordId,
    required this.gameType,
    required this.direction,
    required this.source,
    this.batchWordIds = const [],
  });

  final int wordId;
  final GameType gameType;
  final Direction direction;
  final QueueSource source;

  /// For batch games (Matching): the full set of word ids in the round.
  /// Empty for single-word games.
  final List<int> batchWordIds;
}

/// Maps a card's maturity state to the games allowed for it, per the
/// SPEC.md section 7 game-selection ladder table (2026-07-23 revision: the
/// separate "intro card" page was removed — a brand-new word IS a
/// flashcard round now: reveal the back, swipe right = รู้จัก (Good),
/// left = ไม่รู้จัก (Again), and that first swipe doubles as its first
/// FSRS review):
///
/// | state    | games                              |
/// |----------|-------------------------------------|
/// | new      | flashcard (first-meet, รู้จัก/ไม่รู้จัก) |
/// | learning | flashcard swipe · Matching · Odd One Out |
/// | young    | Cloze · Word Association              |
/// | mature   | Dictation · Word Scramble             |
List<GameType> gamesForState(CardState state) {
  switch (state) {
    case CardState.newState:
      return [GameType.flashcard];
    case CardState.learning:
      return [GameType.flashcard, GameType.matching, GameType.oddOneOut];
    case CardState.young:
      return [GameType.cloze, GameType.wordAssociation];
    case CardState.mature:
      return [GameType.dictation, GameType.wordScramble];
  }
}

/// Fixed rotation used by the extra-practice loop (SPEC.md 7 revision
/// 2026-07-23): once dues + capped-new are cleared and the user keeps
/// playing, practice rounds cycle through every game and wrap back around
/// to flashcard — "ทำ loop ทุกเกมแล้ว กลับมา flashcard ใหม่".
///
/// Order follows the desirable-difficulty / levels-of-processing gradient
/// the SPEC.md §7 ladder is built on, shallow→deep:
/// 1. flashcard        — pure recognition (lowest retrieval effort)
/// 2. matching         — recognition, batched (discriminating among pairs)
/// 3. oddOneOut        — semantic categorization (deeper: judge meaning)
/// 4. wordAssociation  — semantic-network retrieval (spreading activation)
/// 5. cloze            — cued recall in sentence context (retrieval w/ cues)
/// 6. wordScramble     — orthographic production (assemble the form)
/// 7. dictation        — full production from audio (hardest: no visual cue)
///
/// Ramping shallow→deep within one sitting mirrors expanding retrieval
/// practice: each successful shallower retrieval boosts accessibility for
/// the deeper one that follows. Unbuildable rounds (e.g. Odd One Out
/// without enough related_words) fall back to flashcard at render time in
/// play_screen.
const List<GameType> kPracticeGameCycle = [
  GameType.flashcard,
  GameType.matching,
  GameType.oddOneOut,
  GameType.wordAssociation,
  GameType.cloze,
  GameType.wordScramble,
  GameType.dictation,
];

/// Selection weight for one word in the extra-practice sample, given its
/// current consecutive-correct [streak] (correct answers since its last
/// Again) and its FSRS [difficulty] (1..10, initial ≈ 5). Two factors
/// multiplied:
/// - `1/(1+streak)` — a word you keep getting right gradually fades out
///   of the loop (streak 0 → 1.0, 4 → 0.2, 9 → 0.1), freeing rounds for
///   the words that actually need work (product decision 2026-07-23).
/// - `difficulty/5` (user request 2026-07-24 "เอาความยากของคำมา weight"):
///   FSRS already learns each word's difficulty from the player's own
///   answers — a hard word (d 9) is drawn ~1.8× a neutral one, an easy
///   word (d 2) only 0.4×. Words with no SRS row yet use the neutral 5.
double practiceWeight(int streak, {double difficulty = 5}) =>
    (1 / (1 + streak)) * (difficulty / 5);

/// Weighted sample without replacement of up to [count] words from
/// [pool], weighting each by [practiceWeight] of its streak. Words with
/// no entry in [streaks] count as streak 0 (full weight). When
/// `pool.length <= count` every word is still included (weights only
/// affect order); low-streak words are drawn earlier on average.
List<Word> weightedPracticeSample({
  required List<Word> pool,
  required Map<int, int> streaks,
  required int count,
  required Random random,
  Map<int, double> difficulties = const {},
}) {
  final remaining = List.of(pool);
  final out = <Word>[];
  while (out.length < count && remaining.isNotEmpty) {
    final weights = [
      for (final w in remaining)
        practiceWeight(
          streaks[w.id] ?? 0,
          difficulty: difficulties[w.id] ?? 5,
        ),
    ];
    var total = 0.0;
    for (final wt in weights) {
      total += wt;
    }
    var roll = random.nextDouble() * total;
    var idx = 0;
    for (; idx < remaining.length - 1; idx++) {
      roll -= weights[idx];
      if (roll <= 0) break;
    }
    out.add(remaining.removeAt(idx));
  }
  return out;
}

class SessionEngine {
  SessionEngine({Random? random}) : _random = random ?? Random();

  final Random _random;

  /// Builds the next queue snapshot. This is a pure function over the
  /// current store state — callers re-derive it whenever srs_state changes
  /// (after each review) rather than the engine holding mutable state
  /// itself, so it stays trivially testable.
  ///
  /// [now] current time. [newCardCap] today's remaining new-card budget.
  /// [newIntroducedToday] how many new cards already shown today.
  /// [focusTopicWordIds] (SPEC.md 6.4): word ids in the user's chosen focus
  /// topic, if any — biases which new words are introduced first without
  /// touching overdue-review ordering. Empty (the default) is a no-op, so
  /// omitting it keeps the plain freq_rank/CEFR new-card order.
  /// [firstSessionOfDay] (SPEC.md 7 revision 2026-07-23): true when this is
  /// the first queue built after the 3am logical-day boundary — the day
  /// always opens with a flashcard round, so the first item's game is
  /// forced to flashcard regardless of what the ladder picked.
  /// [correctStreaks] per-word consecutive-correct counts (store's
  /// `loadCorrectStreaks()`): down-weights already-solid words in the
  /// extra-practice sample via [practiceWeight].
  /// [passedPairs] the current clean-round "You Pass" grid (store's
  /// `loadPassedWordGamePairs()`, `"$wordId:$gameType"` keys): each
  /// practice slot prefers words still MISSING that slot's game cell, so
  /// the loop actively drives the round toward completion instead of
  /// re-serving cells that are already earned.
  /// [recentAccuracy] (user request 2026-07-24, replaces the old
  /// hotStreak queue-wide top-up): the player's recent answer accuracy
  /// (0..1, null = not enough data yet). It scales how much of each
  /// flashcard block may be NEW words — up to 40% of the block when
  /// accuracy is high (≥0.9), tapering to 0% at ≤0.5 ("ถ้าตอบถูกน้อย
  /// ก็ให้คำใหม่ออกมาลดลง"). Ignored when there is nothing to review
  /// (fresh install): a mix ratio is meaningless with nothing to mix.
  List<SessionItem> buildQueue({
    required List<Word> words,
    required Map<int, SrsState> srsStates,
    required DateTime now,
    required int newCardCap,
    required int newIntroducedToday,
    int matchingBatchSize = 6,
    Set<int> focusTopicWordIds = const {},
    bool firstSessionOfDay = false,
    Map<int, int> correctStreaks = const {},
    Set<String> passedPairs = const {},
    double? recentAccuracy,
  }) {
    final overdue = <_DueEntry>[];
    final newCandidates = <Word>[];

    for (final w in words) {
      final srs = srsStates[w.id];
      if (srs == null || srs.state == CardState.newState && srs.reps == 0) {
        newCandidates.add(w);
        continue;
      }
      if (!srs.dueAt.isAfter(now)) {
        overdue.add(_DueEntry(w, srs));
      }
    }

    // Oldest-due first (most overdue = highest priority).
    overdue.sort((a, b) => a.srs.dueAt.compareTo(b.srs.dueAt));
    // New cards by freq_rank / CEFR order (word list is already loaded in
    // that order by the store, but sort defensively).
    newCandidates.sort((a, b) => a.freqRank.compareTo(b.freqRank));

    final queue = <SessionItem>[];

    // Interleaving: instead of dumping all overdue words back-to-back,
    // round-robin through distinct words so repeats of the same word are
    // spaced out even within one sitting.
    final interleavedOverdue = _interleave(overdue);

    for (final entry in interleavedOverdue) {
      final games = gamesForState(entry.srs.state);
      final game = games[_random.nextInt(games.length)];
      final direction = _nextDirection(entry.srs.lastDirection);
      queue.add(
        SessionItem(
          wordId: entry.word.id,
          gameType: game,
          direction: direction,
          source: QueueSource.overdueReview,
        ),
      );
    }

    final orderedNewCandidates = orderNewCandidates(
      candidates: newCandidates,
      focusTopicWordIds: focusTopicWordIds,
    );

    final remainingCap =
        (newCardCap - newIntroducedToday).clamp(0, newCardCap);
    // How many new words have been queued so far. New words are no longer
    // a standalone segment — they're served as cards INSIDE the practice
    // cycle's flashcard blocks (user request 2026-07-24: "นับ new word
    // เป็นกลุ่มเดียวกับรอบ flash card").
    var newQueued = 0;

    // Extra practice (SPEC.md 7 revision 2026-07-23): any word that already
    // has SRS history and isn't due yet (learning included, not just
    // young/mature — early on everything is learning and the loop must not
    // dead-end) offered again if the user keeps playing after clearing
    // due + new. Games rotate through the full kPracticeGameCycle in
    // light→heavy order, wrapping back to flashcard, instead of being
    // limited to the word's ladder tier — practice rounds don't touch the
    // schedule hard anyway, and the variety is the point of the loop.
    final practicePool = words.where((w) {
      final s = srsStates[w.id];
      return s != null && s.reps > 0 && s.dueAt.isAfter(now);
    }).toList();

    // Games this cycle (user request 2026-07-24): instead of walking all
    // 7 games every cycle, each cycle plays a RANDOM 3-6 of them —
    // triangular-ish mid-heavy count via the same dice trick as the
    // flashcard block size: 3 + d2 + d3 gives 3..6 with P(4)=P(5)=1/3
    // and the extremes 3/6 at 1/6 each. Flashcard is ALWAYS included and
    // always first ("วนรอบเกมมาแล้ว ก็จะกลับไปที่ flash card"); the other
    // slots are drawn from the remaining six games, keeping
    // kPracticeGameCycle's shallow→deep order among those chosen.
    final gameCount = 3 + _random.nextInt(2) + _random.nextInt(3);
    final otherGames = kPracticeGameCycle
        .where((g) => g != GameType.flashcard)
        .toList()
      ..shuffle(_random);
    final chosen = otherGames.take(gameCount - 1).toSet();
    final cycleGames = [
      GameType.flashcard,
      ...kPracticeGameCycle.where(chosen.contains),
    ];

    // Walk this cycle's games; each game gets a RANDOM 2-4 consecutive
    // rounds (user request 2026-07-23 — "ไม่ได้มีแค่รอบเดียวต่อเกม
    // สุ่ม 2-4 รอบ") with a different word per round. For each round,
    // candidates are narrowed to words still MISSING that game's cell in
    // the current clean-round grid (passedPairs) when any exist — the
    // loop drives the "You Pass" round toward completion — then the pick
    // among candidates is weighted by practiceWeight so already-solid
    // words fade out and weak/lapsed words dominate.
    // New-word share of each flashcard block (user request 2026-07-24):
    // at most 40% of the block, scaled down by recent overall accuracy —
    // acc ≥ 0.9 → full 40%, linear taper, acc ≤ 0.5 → no new words.
    // No accuracy data yet (null) counts as "doing fine" → 40%. When the
    // practice pool is EMPTY (fresh install / nothing to review) the
    // share is ignored and the block fills with new words up to the cap:
    // a mix ratio can't apply when there's nothing to mix with.
    final newShare = recentAccuracy == null
        ? 0.4
        : 0.4 * (((recentAccuracy - 0.5) / 0.4).clamp(0.0, 1.0));

    // FSRS per-word difficulty (1..10) feeds the practice sampler so the
    // words the scheduler has learned are hard for THIS player surface
    // more often (user request 2026-07-24).
    final difficulties = {
      for (final e in srsStates.entries) e.key: e.value.difficulty,
    };

    final usedIds = <int>{};
    outer:
    for (final game in cycleGames) {
      // Flashcard blocks are longer: 4-8 cards, TRIANGULAR distribution
      // (user spec 2026-07-23: "โอกาสสุ่มยิ่งอยู่ตรงกลางค่าเฉลี่ยยิ่งออก
      // เยอะ"). Sum of two dice — the simplest bell-ish generator:
      // 4 + d3 + d3 gives 4..8 with P(6) highest (3/9), P(5)=P(7)=2/9,
      // and the extremes 4/8 rarest (1/9 each). Other games stay a
      // uniform 2-4 rounds.
      final rounds = game == GameType.flashcard
          ? 4 + _random.nextInt(3) + _random.nextInt(3)
          : 2 + _random.nextInt(3);
      // Per-block new-word budget: share of the block size, or cap-only
      // when there's no practice material to mix with.
      final maxNewThisBlock = game != GameType.flashcard
          ? 0
          : practicePool.isEmpty
              ? remainingCap
              : (rounds * newShare).floor();
      var newThisBlock = 0;
      for (var r = 0; r < rounds; r++) {
        // Flashcard-block slots are filled by today's capped new words
        // FIRST (within the block's share budget), then topped up with
        // practice words — a new word's first-meet card is just another
        // card in the block instead of a separate up-front segment
        // (user request 2026-07-24).
        if (game == GameType.flashcard &&
            newThisBlock < maxNewThisBlock &&
            newQueued < remainingCap &&
            newQueued < orderedNewCandidates.length) {
          final w = orderedNewCandidates[newQueued++];
          newThisBlock++;
          queue.add(
            SessionItem(
              wordId: w.id,
              gameType: GameType.flashcard,
              direction: Direction.enTh,
              source: QueueSource.newCard,
            ),
          );
          continue;
        }
        final unused =
            practicePool.where((w) => !usedIds.contains(w.id)).toList();
        if (unused.isEmpty) {
          // The flashcard block may simply be short on practice words
          // while later games can still break the whole cycle.
          if (game == GameType.flashcard) break;
          break outer;
        }
        final missingCell = unused
            .where((w) => !passedPairs.contains('${w.id}:${game.name}'))
            .toList();
        final candidates = missingCell.isNotEmpty ? missingCell : unused;
        final w = weightedPracticeSample(
          pool: candidates,
          streaks: correctStreaks,
          count: 1,
          random: _random,
          difficulties: difficulties,
        ).single;
        usedIds.add(w.id);
        final srs = srsStates[w.id]!;
        queue.add(
          SessionItem(
            wordId: w.id,
            gameType: game,
            direction: _nextDirection(srs.lastDirection),
            source: QueueSource.extraPractice,
          ),
        );
      }
    }

    // newCardCap paces an ordinary day, but it should never be a hard wall:
    // if everything else is exhausted and the user keeps playing, keep
    // introducing the rest of the word list rather than ending the session
    // while there's still content left (product decision 2026-07-23 —
    // "no fixed size, if the user's ready let them continue").
    if (queue.isEmpty) {
      for (final w in orderedNewCandidates.skip(newQueued)) {
        queue.add(
          SessionItem(
            wordId: w.id,
            gameType: GameType.flashcard,
            direction: Direction.enTh,
            source: QueueSource.newCard,
          ),
        );
      }
    }

    // The first session after the 3am day boundary always opens with a
    // flashcard round ("เริ่มวันด้วย flashcard เหมือนเดิม ในครั้งแรกที่เข้าแอป").
    if (firstSessionOfDay && queue.isNotEmpty &&
        queue.first.gameType != GameType.flashcard) {
      final first = queue.first;
      queue[0] = SessionItem(
        wordId: first.wordId,
        gameType: GameType.flashcard,
        direction: first.direction,
        source: first.source,
      );
    }

    return queue;
  }

  Direction _nextDirection(Direction? last) {
    if (last == null) return Direction.enTh;
    return last == Direction.enTh ? Direction.thEn : Direction.enTh;
  }

  /// Round-robins consecutive-different words so the same word doesn't
  /// appear back-to-back when several are due (interleaving, SPEC.md 7).
  List<_DueEntry> _interleave(List<_DueEntry> sorted) {
    if (sorted.length <= 2) return sorted;
    final buckets = <int, List<_DueEntry>>{};
    final order = <int>[];
    for (final e in sorted) {
      if (!buckets.containsKey(e.word.id)) order.add(e.word.id);
      buckets.putIfAbsent(e.word.id, () => []).add(e);
    }
    final out = <_DueEntry>[];
    var remaining = true;
    while (remaining) {
      remaining = false;
      for (final id in order) {
        final b = buckets[id]!;
        if (b.isNotEmpty) {
          out.add(b.removeAt(0));
          remaining = remaining || b.isNotEmpty;
        }
      }
    }
    return out;
  }
}

class _DueEntry {
  _DueEntry(this.word, this.srs);
  final Word word;
  final SrsState srs;
}
