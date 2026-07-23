/// Endless-queue session engine (SPEC.md section 7). Pulls "next item"
/// requests one at a time. Priority: overdue reviews (oldest-due first) >
/// new cards (up to today's cap) > extra practice (young/mature words just
/// reviewed, light games only). Interleaves across topics/words instead of
/// grinding one word repeatedly, and tracks last_direction per word so
/// EN->TH/TH->EN alternates instead of repeating.
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
/// Again). Monotonically decreasing: a word you keep getting right
/// gradually fades out of the loop (streak 0 → 1.0, 4 → 0.2, 9 → 0.1),
/// freeing rounds for the words that actually need work — otherwise a
/// late-stage lapse would restart the loop on easy words and take forever
/// to get back to the hard ones (product decision 2026-07-23).
double practiceWeight(int streak) => 1 / (1 + streak);

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
}) {
  final remaining = List.of(pool);
  final out = <Word>[];
  while (out.length < count && remaining.isNotEmpty) {
    final weights = [
      for (final w in remaining) practiceWeight(streaks[w.id] ?? 0),
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
  /// [hotStreak] (user request 2026-07-23 "ถ้าตอบถูกบ่อยมากๆ ให้แต่ละรอบ
  /// มีคำใหม่ได้ถึง 40%"): when the player's recent answers are
  /// near-perfect, top the queue up with extra beyond-cap new words,
  /// spread evenly, until new cards make up to 40% of the queue.
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
    bool hotStreak = false,
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

    var remainingCap = (newCardCap - newIntroducedToday).clamp(0, newCardCap);
    final cappedNew = orderedNewCandidates.take(remainingCap).toList();
    for (final w in cappedNew) {
      queue.add(
        SessionItem(
          wordId: w.id,
          gameType: GameType.flashcard,
          direction: Direction.enTh,
          source: QueueSource.newCard,
        ),
      );
    }

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

    // Walk the practice cycle game by game; each game gets a RANDOM 2-4
    // consecutive rounds (user request 2026-07-23 — "ไม่ได้มีแค่รอบเดียว
    // ต่อเกม สุ่ม 2-4 รอบ") with a different word per round. For each
    // round, candidates are narrowed to words still MISSING that game's
    // cell in the current clean-round grid (passedPairs) when any exist —
    // the loop drives the "You Pass" round toward completion — then the
    // pick among candidates is weighted by practiceWeight so
    // already-solid words fade out and weak/lapsed words dominate.
    final usedIds = <int>{};
    outer:
    for (final game in kPracticeGameCycle) {
      final rounds = 2 + _random.nextInt(3); // 2..4 rounds of this game
      for (var r = 0; r < rounds; r++) {
        final unused =
            practicePool.where((w) => !usedIds.contains(w.id)).toList();
        if (unused.isEmpty) break outer;
        final missingCell = unused
            .where((w) => !passedPairs.contains('${w.id}:${game.name}'))
            .toList();
        final candidates = missingCell.isNotEmpty ? missingCell : unused;
        final w = weightedPracticeSample(
          pool: candidates,
          streaks: correctStreaks,
          count: 1,
          random: _random,
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
      for (final w in orderedNewCandidates.skip(cappedNew.length)) {
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

    // Hot streak (user request 2026-07-23): answering nearly everything
    // right means the current material is too comfortable — top the queue
    // up with beyond-cap new words, spread evenly through it, until new
    // cards are up to 40% of the whole queue.
    if (hotStreak) {
      final currentNew =
          queue.where((i) => i.source == QueueSource.newCard).length;
      final nonNew = queue.length - currentNew;
      // Solve N/(nonNew+N) <= 0.40  ->  N <= (2/3)*nonNew.
      final targetNew = (nonNew * 2) ~/ 3;
      final alreadyQueuedNew = queue
          .where((i) => i.source == QueueSource.newCard)
          .map((i) => i.wordId)
          .toSet();
      final extras = orderedNewCandidates
          .where((w) => !alreadyQueuedNew.contains(w.id))
          .take((targetNew - currentNew).clamp(0, orderedNewCandidates.length))
          .toList();
      if (extras.isNotEmpty) {
        // Spread the extra new words evenly instead of dumping them at
        // the end: insert one every `gap` items from the back so earlier
        // review/practice ordering is preserved.
        final gap = (queue.length / (extras.length + 1)).ceil().clamp(1, 1 << 30);
        var insertAt = gap;
        for (final w in extras) {
          final item = SessionItem(
            wordId: w.id,
            gameType: GameType.flashcard,
            direction: Direction.enTh,
            source: QueueSource.newCard,
          );
          if (insertAt >= queue.length) {
            queue.add(item);
          } else {
            queue.insert(insertAt, item);
          }
          insertAt += gap + 1;
        }
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
