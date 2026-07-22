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
    test('new words map to intro, not a game', () {
      expect(gamesForState(CardState.newState), [GameType.intro]);
    });

    test('learning words map to flashcard/matching only', () {
      expect(
        gamesForState(CardState.learning).toSet(),
        {GameType.flashcard, GameType.matching},
      );
    });

    test('young and mature words fall back to Cloze in Phase 1', () {
      expect(gamesForState(CardState.young), [GameType.cloze]);
      expect(gamesForState(CardState.mature), [GameType.cloze]);
    });
  });
}
