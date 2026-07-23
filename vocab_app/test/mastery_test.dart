import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/data/vocab_store_memory.dart';
import 'package:vocab_app/domain/mastery.dart';
import 'package:vocab_app/domain/session_engine.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';

Word _word(int id) => Word(
  id: id,
  headword: 'w$id',
  cefr: 'A1',
  freqRank: id,
  thaiReading: 'w$id',
  stressIndex: 1,
  ipa: '',
  translationSource: '',
  translationLicense: '',
  hasPhoto: false,
);

/// Every (word, game) pair for [words] — the fully-passed grid.
Set<String> _fullGrid(List<Word> words) => {
  for (final w in words)
    for (final g in GameType.values) masteryKey(w.id, g.name),
};

void main() {
  group('fullMasteryReached ("You Pass" condition)', () {
    test('true when every word is passed in every game', () {
      final words = [_word(1), _word(2)];
      expect(
        fullMasteryReached(words: words, passedPairs: _fullGrid(words)),
        isTrue,
      );
    });

    test('false when a single (word, game) cell is missing', () {
      final words = [_word(1), _word(2)];
      final grid = _fullGrid(words)
        ..remove(masteryKey(2, GameType.dictation.name));
      expect(fullMasteryReached(words: words, passedPairs: grid), isFalse);
    });

    test('false on a fresh profile with no reviews at all', () {
      expect(
        fullMasteryReached(words: [_word(1)], passedPairs: {}),
        isFalse,
      );
    });

    test('masteryProgress counts passed cells over words x games', () {
      final words = [_word(1)];
      final grid = {
        masteryKey(1, GameType.flashcard.name),
        masteryKey(1, GameType.cloze.name),
      };
      final (passed, total) = masteryProgress(
        words: words,
        passedPairs: grid,
      );
      expect(passed, 2);
      expect(total, GameType.values.length);
    });
  });

  group('VocabStoreMemory.loadPassedWordGamePairs', () {
    test('collects distinct correct pairs and ignores Again ratings', () async {
      final store = VocabStoreMemory(words: [_word(1)]);
      final ts = DateTime(2026, 7, 23);
      Future<void> log(Rating r, GameType g) => store.logReview(
        ReviewLogEntry(
          wordId: 1,
          ts: ts,
          rating: r,
          gameType: g.name,
          direction: Direction.enTh,
          elapsedMs: 0,
        ),
      );
      await log(Rating.again, GameType.flashcard); // wrong -> doesn't count
      await log(Rating.good, GameType.cloze);
      await log(Rating.hard, GameType.dictation); // hard still counts as pass
      await log(Rating.easy, GameType.cloze); // duplicate pair -> one entry

      final pairs = await store.loadPassedWordGamePairs();
      expect(pairs, {
        masteryKey(1, GameType.cloze.name),
        masteryKey(1, GameType.dictation.name),
      });
    });
  });
}
