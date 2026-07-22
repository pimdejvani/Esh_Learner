/// Endless-queue session engine (SPEC.md section 7). Pulls "next item"
/// requests one at a time. Priority: overdue reviews (oldest-due first) >
/// new cards (up to today's cap) > extra practice (young/mature words just
/// reviewed, light games only). Interleaves across topics/words instead of
/// grinding one word repeatedly, and tracks last_direction per word so
/// EN->TH/TH->EN alternates instead of repeating.
library;

import 'dart:math';

import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';

enum GameType { intro, flashcard, cloze, matching }

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
/// Phase 1 ladder in SPEC.md section 7 (Word Association / Scramble /
/// Odd One Out / Dictation are Phase 2 — young state falls back to Cloze
/// only, mature state also falls back to Cloze since Dictation isn't built
/// yet; that fallback is a deliberate, documented Phase 1 simplification).
List<GameType> gamesForState(CardState state) {
  switch (state) {
    case CardState.newState:
      return [GameType.intro];
    case CardState.learning:
      return [GameType.flashcard, GameType.matching];
    case CardState.young:
    case CardState.mature:
      return [GameType.cloze];
  }
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
  List<SessionItem> buildQueue({
    required List<Word> words,
    required Map<int, SrsState> srsStates,
    required DateTime now,
    required int newCardCap,
    required int newIntroducedToday,
    int matchingBatchSize = 6,
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

    var remainingCap = (newCardCap - newIntroducedToday).clamp(0, newCardCap);
    for (final w in newCandidates.take(remainingCap)) {
      queue.add(
        SessionItem(
          wordId: w.id,
          gameType: GameType.intro,
          direction: Direction.enTh,
          source: QueueSource.newCard,
        ),
      );
    }

    // Extra practice: young/mature words reviewed recently (last_review
    // set) offered again as light games if the user keeps playing after
    // clearing due + new. Doesn't touch schedule (game outcome still logs
    // for stats, but session_engine doesn't force it into the due path).
    final practicePool =
        words.where((w) {
          final s = srsStates[w.id];
          return s != null &&
              (s.state == CardState.young || s.state == CardState.mature) &&
              s.dueAt.isAfter(now);
        }).toList()..shuffle(_random);

    for (final w in practicePool.take(10)) {
      final srs = srsStates[w.id]!;
      final games = gamesForState(srs.state);
      queue.add(
        SessionItem(
          wordId: w.id,
          gameType: games[_random.nextInt(games.length)],
          direction: _nextDirection(srs.lastDirection),
          source: QueueSource.extraPractice,
        ),
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
