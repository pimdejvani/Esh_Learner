import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/session_engine.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';

Word _word(int id, {int freq = 0}) => Word(
  id: id,
  headword: 'w$id',
  cefr: 'A1',
  freqRank: freq,
  thaiReading: 'w$id',
  stressIndex: 1,
  ipa: '',
  translationSource: '',
  translationLicense: '',
  hasPhoto: false,
);

SrsState _due(int id, DateTime dueAt, {CardState state = CardState.learning}) =>
    SrsState(
      wordId: id,
      state: state,
      stability: 5,
      difficulty: 5,
      dueAt: dueAt,
      lastReview: dueAt.subtract(const Duration(days: 3)),
      reps: 2,
      lapses: 0,
      lastDirection: Direction.enTh,
    );

void main() {
  final engine = SessionEngine();
  final now = DateTime(2026, 7, 22, 12);

  group('priority ordering', () {
    test('overdue reviews come before new cards', () {
      final words = [_word(1), _word(2)];
      final srs = {
        1: _due(1, now.subtract(const Duration(days: 1))),
      };
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 8,
        newIntroducedToday: 0,
      );
      expect(queue.first.wordId, 1);
      expect(queue.first.source, QueueSource.overdueReview);
      expect(queue.any((i) => i.wordId == 2 && i.source == QueueSource.newCard), isTrue);
    });

    test('most-overdue word is scheduled before a less-overdue word', () {
      final words = [_word(1), _word(2)];
      final srs = {
        1: _due(1, now.subtract(const Duration(hours: 1))),
        2: _due(2, now.subtract(const Duration(days: 5))),
      };
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 0,
        newIntroducedToday: 0,
      );
      final overdueOnly = queue.where((i) => i.source == QueueSource.overdueReview).toList();
      expect(overdueOnly.first.wordId, 2);
    });

    test('new-card cap limits how many new cards enter the queue', () {
      final words = List.generate(10, (i) => _word(i, freq: i));
      final queue = engine.buildQueue(
        words: words,
        srsStates: {},
        now: now,
        newCardCap: 3,
        newIntroducedToday: 0,
      );
      final newCards = queue.where((i) => i.source == QueueSource.newCard).toList();
      expect(newCards.length, 3);
      // Should take lowest freq_rank first.
      expect(newCards.map((i) => i.wordId), [0, 1, 2]);
    });

    test('newIntroducedToday reduces remaining cap', () {
      final words = List.generate(5, (i) => _word(i, freq: i));
      final queue = engine.buildQueue(
        words: words,
        srsStates: {},
        now: now,
        newCardCap: 3,
        newIntroducedToday: 2,
      );
      final newCards = queue.where((i) => i.source == QueueSource.newCard).toList();
      expect(newCards.length, 1);
    });

    test(
      'cap never dead-ends the queue: once the cap is used up for the day, '
      'remaining new words still fill in rather than ending the session',
      () {
        final words = List.generate(5, (i) => _word(i, freq: i));
        final queue = engine.buildQueue(
          words: words,
          srsStates: {},
          now: now,
          newCardCap: 2,
          // Cap already fully used (e.g. earlier rebuilds this session
          // already introduced 2 words, which flip to CardState.learning
          // and drop out of newCandidates on the next rebuild — simulated
          // here directly via newIntroducedToday). With no overdue/practice
          // content, remainingCap alone would leave the queue empty; the
          // fallback should surface the rest instead of ending the session.
          newIntroducedToday: 2,
        );
        expect(queue, isNotEmpty);
        final newCards = queue.where((i) => i.source == QueueSource.newCard).toList();
        expect(newCards.length, 5);
        expect(newCards.map((i) => i.wordId), [0, 1, 2, 3, 4]);
      },
    );

    test('cap is respected as-is when other content already fills the queue', () {
      final words = List.generate(5, (i) => _word(i, freq: i));
      final srs = {0: _due(0, now.subtract(const Duration(hours: 1)))};
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 2,
        newIntroducedToday: 0,
      );
      final newCards = queue.where((i) => i.source == QueueSource.newCard).toList();
      // Word 0 already has SRS state so it's not a new candidate; of the
      // remaining 4, only 2 should be admitted since the queue is non-empty
      // (the overdue review) and the fallback shouldn't kick in.
      expect(newCards.length, 2);
    });
  });

  group('interleaving', () {
    test('same word never appears twice in a row when multiple words are due', () {
      final words = [_word(1), _word(2), _word(3)];
      // Word 1 has 3 overdue "duplicate" entries simulated via distinct due
      // times all before now; the interleave logic groups by word id, so
      // with only 1 srs row per word this test instead checks ordering
      // across 3 different due words stays spread (not clumped by insert
      // order artifacts).
      final srs = {
        1: _due(1, now.subtract(const Duration(days: 1))),
        2: _due(2, now.subtract(const Duration(days: 1))),
        3: _due(3, now.subtract(const Duration(days: 1))),
      };
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 0,
        newIntroducedToday: 0,
      );
      final ids = queue.map((i) => i.wordId).toList();
      for (var i = 1; i < ids.length; i++) {
        expect(ids[i], isNot(ids[i - 1]));
      }
    });
  });

  group('bidirectional tracking', () {
    test('direction flips relative to last_direction instead of repeating', () {
      final words = [_word(1)];
      final srs = {
        1: _due(1, now.subtract(const Duration(days: 1))),
      };
      srs[1] = srs[1]!.copyWith(lastDirection: Direction.enTh);
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 0,
        newIntroducedToday: 0,
      );
      expect(queue.first.direction, Direction.thEn);
    });

    test('a word with no prior direction defaults to en->th', () {
      final words = [_word(1)];
      final srs = {
        1: SrsState(
          wordId: 1,
          state: CardState.learning,
          stability: 5,
          difficulty: 5,
          dueAt: now.subtract(const Duration(days: 1)),
          lastReview: now.subtract(const Duration(days: 4)),
          reps: 2,
          lapses: 0,
          lastDirection: null,
        ),
      };
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 0,
        newIntroducedToday: 0,
      );
      expect(queue.first.direction, Direction.enTh);
    });
  });

  group('game selection ladder', () {
    test('new words map to flashcard (first-meet round, no separate intro)', () {
      expect(gamesForState(CardState.newState), [GameType.flashcard]);
    });

    test('learning words map to flashcard/Matching/Odd One Out', () {
      expect(
        gamesForState(CardState.learning).toSet(),
        {GameType.flashcard, GameType.matching, GameType.oddOneOut},
      );
    });

    test('young words map to Cloze + Word Association (Phase 2 ladder)', () {
      expect(
        gamesForState(CardState.young).toSet(),
        {GameType.cloze, GameType.wordAssociation},
      );
    });

    test('mature words map to Dictation + Word Scramble (Phase 2 ladder)', () {
      expect(
        gamesForState(CardState.mature).toSet(),
        {GameType.dictation, GameType.wordScramble},
      );
    });
  });

  group('continuous-play loop (SPEC.md 7 revision 2026-07-23)', () {
    test('new-card items are flashcard rounds, not a separate intro type', () {
      final queue = engine.buildQueue(
        words: [_word(1)],
        srsStates: {},
        now: now,
        newCardCap: 3,
        newIntroducedToday: 0,
      );
      expect(queue.single.source, QueueSource.newCard);
      expect(queue.single.gameType, GameType.flashcard);
    });

    test('extra practice includes learning words (loop never dead-ends early)', () {
      // All words already met today (learning, not due) — the old
      // young/mature-only pool would be empty here and end the session.
      final words = List.generate(4, (i) => _word(i, freq: i));
      final srs = {
        for (final w in words)
          w.id: _due(w.id, now.add(const Duration(days: 2))),
      };
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 8,
        newIntroducedToday: 8,
      );
      final practice =
          queue.where((i) => i.source == QueueSource.extraPractice).toList();
      expect(practice.length, 4);
    });

    test('practice cycle plays a random 3-6 games, flashcard always first, '
        'in cycle order (revision 2026-07-24: no longer all 7 every cycle)', () {
      final words = List.generate(40, (i) => _word(i, freq: i));
      final srs = {
        for (final w in words)
          w.id: _due(w.id, now.add(const Duration(days: 2))),
      };
      // Randomized game selection — assert the invariants over many builds.
      for (var trial = 0; trial < 50; trial++) {
        final queue = engine.buildQueue(
          words: words,
          srsStates: srs,
          now: now,
          newCardCap: 8,
          newIntroducedToday: 8,
        );
        final practice =
            queue.where((i) => i.source == QueueSource.extraPractice).toList();

        // Compress the game sequence into consecutive runs.
        final runGames = <GameType>[];
        final runLengths = <int>[];
        for (final item in practice) {
          if (runGames.isNotEmpty && runGames.last == item.gameType) {
            runLengths[runLengths.length - 1]++;
          } else {
            runGames.add(item.gameType);
            runLengths.add(1);
          }
        }
        // 3-6 games per cycle, flashcard always leading.
        expect(runGames.length, inInclusiveRange(3, 6));
        expect(runGames.first, GameType.flashcard);
        // The chosen games keep kPracticeGameCycle's order (strictly
        // increasing cycle indexes = ordered subset, no repeats).
        final idxs = runGames.map(kPracticeGameCycle.indexOf).toList();
        for (var i = 1; i < idxs.length; i++) {
          expect(idxs[i], greaterThan(idxs[i - 1]));
        }
        for (var i = 0; i < runGames.length; i++) {
          if (runGames[i] == GameType.flashcard) {
            // Flashcard blocks: 4-8 cards (triangular, revision 2026-07-23).
            expect(runLengths[i], inInclusiveRange(4, 8));
          } else {
            expect(runLengths[i], inInclusiveRange(2, 4));
          }
        }
        // Every round uses a distinct word.
        expect(
          practice.map((i) => i.wordId).toSet().length,
          practice.length,
        );
      }
    });

    test('new words are served inside the flashcard block, not as a '
        'separate up-front segment (revision 2026-07-24)', () {
      // 10 practice words + 5 brand-new, cap 3: the queue's flashcard
      // block opens with the new cards (limited by the block's 40%
      // share since practice words exist) then tops up with practice
      // flashcards; every new card must come before any non-flashcard
      // game.
      final words = List.generate(15, (i) => _word(i, freq: i));
      final srs = {
        for (var i = 5; i < 15; i++)
          i: _due(i, now.add(const Duration(days: 2))),
      };
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 3,
        newIntroducedToday: 0,
      );
      final newItems =
          queue.where((i) => i.source == QueueSource.newCard).toList();
      // Block is 4-8 cards; 40% share -> 1-3 new, lowest freq_rank first.
      expect(newItems.length, inInclusiveRange(1, 3));
      expect(
        newItems.map((i) => i.wordId),
        [0, 1, 2].take(newItems.length),
      );
      for (final item in newItems) {
        expect(item.gameType, GameType.flashcard);
      }
      final firstNonFlashcard =
          queue.indexWhere((i) => i.gameType != GameType.flashcard);
      final lastNew = queue.lastIndexWhere(
        (i) => i.source == QueueSource.newCard,
      );
      if (firstNonFlashcard != -1) {
        expect(lastNew, lessThan(firstNonFlashcard));
      }
    });

    test('new-word share of the flashcard block scales with recent '
        'accuracy: high -> up to 40%, low -> zero (revision 2026-07-24)', () {
      // 20 practice words + 30 brand new, generous cap.
      final words = List.generate(50, (i) => _word(i, freq: i));
      final srs = {
        for (var i = 30; i < 50; i++)
          i: _due(i, now.add(const Duration(days: 2))),
      };
      for (var trial = 0; trial < 30; trial++) {
        // High accuracy: some new words, never more than 40% of the block.
        final hot = engine.buildQueue(
          words: words,
          srsStates: srs,
          now: now,
          newCardCap: 15,
          newIntroducedToday: 0,
          recentAccuracy: 0.95,
        );
        final newCount =
            hot.where((i) => i.source == QueueSource.newCard).length;
        final blockLen = hot
            .takeWhile((i) => i.gameType == GameType.flashcard)
            .length;
        expect(newCount, greaterThanOrEqualTo(1));
        expect(newCount, lessThanOrEqualTo((0.4 * blockLen).floor()));

        // Low accuracy: no new words at all, even with cap available.
        final cold = engine.buildQueue(
          words: words,
          srsStates: srs,
          now: now,
          newCardCap: 15,
          newIntroducedToday: 0,
          recentAccuracy: 0.5,
        );
        expect(
          cold.where((i) => i.source == QueueSource.newCard).length,
          0,
        );
      }
    });

    test('share is ignored when there is nothing to review — a fresh '
        'install still gets new words up to the cap', () {
      final words = List.generate(10, (i) => _word(i, freq: i));
      final queue = engine.buildQueue(
        words: words,
        srsStates: {},
        now: now,
        newCardCap: 3,
        newIntroducedToday: 0,
        recentAccuracy: 0.2, // terrible accuracy but nothing to mix with
      );
      expect(
        queue.where((i) => i.source == QueueSource.newCard).length,
        3,
      );
    });

    test('practiceWeight scales with FSRS difficulty (hard words drawn '
        'more, easy words less)', () {
      expect(
        practiceWeight(0, difficulty: 9),
        greaterThan(practiceWeight(0, difficulty: 5)),
      );
      expect(
        practiceWeight(0, difficulty: 2),
        lessThan(practiceWeight(0, difficulty: 5)),
      );
      // Difficulty never resurrects a fully-faded word above a fresh one.
      expect(
        practiceWeight(9, difficulty: 10),
        lessThan(practiceWeight(0, difficulty: 5)),
      );
    });

    test('a high-difficulty word is drawn more often than an equal-streak '
        'easy word', () {
      final pool = [_word(1), _word(2)];
      final random = Random(7);
      var hardFirst = 0;
      for (var i = 0; i < 300; i++) {
        final sample = weightedPracticeSample(
          pool: pool,
          streaks: {1: 0, 2: 0},
          count: 1,
          random: random,
          difficulties: {1: 9.0, 2: 2.0},
        );
        if (sample.single.id == 1) hardFirst++;
      }
      // Expected ratio 9:2 -> ~82% of draws.
      expect(hardFirst, greaterThan(200));
    });

    test('practice slots target words still missing that game\'s cell', () {
      // Both words in the practice pool. Word 1 already passed flashcard
      // (slot 0's game) in the current clean round; word 2 hasn't — the
      // flashcard slot must pick word 2 regardless of random weighting.
      final words = [_word(1), _word(2)];
      final srs = {
        1: _due(1, now.add(const Duration(days: 2))),
        2: _due(2, now.add(const Duration(days: 2))),
      };
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 8,
        newIntroducedToday: 8,
        passedPairs: {'1:${GameType.flashcard.name}'},
      );
      final practice =
          queue.where((i) => i.source == QueueSource.extraPractice).toList();
      expect(practice.first.gameType, GameType.flashcard);
      expect(practice.first.wordId, 2);
    });

    test('weightedPracticeSample includes every word when pool <= count', () {
      final pool = List.generate(4, (i) => _word(i));
      final sample = weightedPracticeSample(
        pool: pool,
        streaks: {0: 100, 1: 0, 2: 50, 3: 3},
        count: 10,
        random: Random(1),
      );
      expect(sample.map((w) => w.id).toSet(), {0, 1, 2, 3});
    });

    test('a high-streak word is drawn far less often than a fresh one', () {
      // Word 0: streak 0 (full weight). Word 1: huge streak (~zero
      // weight). Over many draws of 1-of-2, word 0 should dominate.
      final pool = [_word(1), _word(0)]; // heavy word listed FIRST
      final streaks = {0: 0, 1: 1000000};
      final random = Random(42);
      var word0First = 0;
      for (var i = 0; i < 200; i++) {
        final sample = weightedPracticeSample(
          pool: pool,
          streaks: streaks,
          count: 1,
          random: random,
        );
        if (sample.single.id == 0) word0First++;
      }
      expect(word0First, greaterThan(195));
    });

    test('first session of the day always opens with a flashcard round', () {
      // A due mature word would normally get Dictation/Scramble first.
      final words = [_word(1)];
      final srs = {
        1: _due(1, now.subtract(const Duration(hours: 5)),
            state: CardState.mature),
      };
      final queue = engine.buildQueue(
        words: words,
        srsStates: srs,
        now: now,
        newCardCap: 0,
        newIntroducedToday: 0,
        firstSessionOfDay: true,
      );
      expect(queue.first.gameType, GameType.flashcard);
      // Source/word are preserved — only the game is overridden.
      expect(queue.first.source, QueueSource.overdueReview);
      expect(queue.first.wordId, 1);
    });
  });

  group('focus topic bias (SPEC.md 6.4)', () {
    test('is a no-op on new-card ordering when no focus topic is set', () {
      final words = List.generate(6, (i) => _word(i, freq: i));
      final withoutBias = engine.buildQueue(
        words: words,
        srsStates: {},
        now: now,
        newCardCap: 3,
        newIntroducedToday: 0,
      );
      final withEmptyBias = engine.buildQueue(
        words: words,
        srsStates: {},
        now: now,
        newCardCap: 3,
        newIntroducedToday: 0,
        focusTopicWordIds: const {},
      );
      expect(
        withoutBias.map((i) => i.wordId).toList(),
        withEmptyBias.map((i) => i.wordId).toList(),
      );
      // Default (no bias) new-card order still follows freq_rank.
      expect(withoutBias.map((i) => i.wordId), [0, 1, 2]);
    });

    test('biases new words in the focus topic to the front of the queue', () {
      final words = List.generate(6, (i) => _word(i, freq: i));
      final queue = engine.buildQueue(
        words: words,
        srsStates: {},
        now: now,
        newCardCap: 3,
        newIntroducedToday: 0,
        // Word 5 has the worst freq_rank but is in the focus topic, so it
        // should be introduced ahead of non-focus words 1 and 2.
        focusTopicWordIds: {5},
      );
      expect(queue.map((i) => i.wordId), [5, 0, 1]);
    });
  });
}
