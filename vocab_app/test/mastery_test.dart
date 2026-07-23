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

  group('VocabStoreMemory.loadPassedWordGamePairs (lapse resets the row)', () {
    var tick = 0;
    Future<void> log(
      VocabStoreMemory store,
      Rating r,
      GameType g, {
      int wordId = 1,
    }) => store.logReview(
      ReviewLogEntry(
        wordId: wordId,
        ts: DateTime(2026, 7, 23).add(Duration(minutes: tick++)),
        rating: r,
        gameType: g.name,
        direction: Direction.enTh,
        elapsedMs: 0,
      ),
    );

    test('collects distinct post-lapse correct pairs', () async {
      final store = VocabStoreMemory(words: [_word(1)]);
      await log(store, Rating.good, GameType.cloze);
      await log(store, Rating.hard, GameType.dictation); // hard counts
      await log(store, Rating.easy, GameType.cloze); // duplicate -> one entry

      final pairs = await store.loadPassedWordGamePairs();
      expect(pairs, {
        masteryKey(1, GameType.cloze.name),
        masteryKey(1, GameType.dictation.name),
      });
    });

    test('one Again wipes ALL of that word\'s earlier passes, any game', () async {
      final store = VocabStoreMemory(words: [_word(1), _word(2)]);
      await log(store, Rating.good, GameType.cloze);
      await log(store, Rating.good, GameType.dictation);
      await log(store, Rating.good, GameType.flashcard, wordId: 2);
      // Wrong answer on word 1 in a DIFFERENT game than its passes:
      await log(store, Rating.again, GameType.matching);

      final pairs = await store.loadPassedWordGamePairs();
      // Word 1's entire row is gone; word 2 untouched.
      expect(pairs, {masteryKey(2, GameType.flashcard.name)});
    });

    test('passes re-earned after the lapse count again', () async {
      final store = VocabStoreMemory(words: [_word(1)]);
      await log(store, Rating.good, GameType.cloze);
      await log(store, Rating.again, GameType.cloze); // reset
      await log(store, Rating.good, GameType.dictation); // after reset

      final pairs = await store.loadPassedWordGamePairs();
      expect(pairs, {masteryKey(1, GameType.dictation.name)});
    });
  });

  group('correct streaks + practice down-weighting', () {
    test('loadCorrectStreaks counts passes since the last Again', () async {
      final store = VocabStoreMemory(words: [_word(1)]);
      var t = 0;
      Future<void> log(Rating r) => store.logReview(
        ReviewLogEntry(
          wordId: 1,
          ts: DateTime(2026, 7, 23).add(Duration(minutes: t++)),
          rating: r,
          gameType: GameType.flashcard.name,
          direction: Direction.enTh,
          elapsedMs: 0,
        ),
      );
      await log(Rating.good);
      await log(Rating.good);
      await log(Rating.again); // resets the streak
      await log(Rating.good);
      await log(Rating.hard);
      expect(await store.loadCorrectStreaks(), {1: 2});
    });

    test('practiceWeight decreases monotonically with streak', () {
      expect(practiceWeight(0), 1.0);
      expect(practiceWeight(4), closeTo(0.2, 1e-9));
      for (var s = 0; s < 30; s++) {
        expect(practiceWeight(s + 1), lessThan(practiceWeight(s)));
      }
    });
  });
}
