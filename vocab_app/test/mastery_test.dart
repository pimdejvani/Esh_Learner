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

/// Every (word, mastery game) pair for [words] — the fully-passed grid.
Set<String> _fullGrid(List<Word> words) => {
  for (final w in words)
    for (final g in kMasteryGames) masteryKey(w.id, g.name),
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

    test('masteryProgress counts passed cells over words x mastery games', () {
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
      expect(total, kMasteryGames.length);
    });

    test('only the 4 serious games count toward the grid', () {
      expect(kMasteryGames, [
        GameType.flashcard,
        GameType.matching,
        GameType.cloze,
        GameType.dictation,
      ]);
      // Passing every mastery game is enough — the streak-only games
      // (oddOneOut / wordAssociation / wordScramble) are not required.
      final words = [_word(1)];
      expect(
        fullMasteryReached(words: words, passedPairs: _fullGrid(words)),
        isTrue,
      );
    });
  });

  group('VocabStoreMemory.loadPassedWordGamePairs (a lapse resets EVERYTHING)', () {
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

    test('one Again on ANY word wipes the whole grid, all words all games', () async {
      final store = VocabStoreMemory(words: [_word(1), _word(2)]);
      await log(store, Rating.good, GameType.cloze);
      await log(store, Rating.good, GameType.dictation);
      await log(store, Rating.good, GameType.flashcard, wordId: 2);
      // Wrong answer on word 1 only — but the round is no longer clean,
      // so word 2's pass is wiped too (start the round over).
      await log(store, Rating.again, GameType.matching);

      expect(await store.loadPassedWordGamePairs(), isEmpty);
    });

    test('passes re-earned after the reset count toward the new round', () async {
      final store = VocabStoreMemory(words: [_word(1), _word(2)]);
      await log(store, Rating.good, GameType.cloze);
      await log(store, Rating.again, GameType.cloze); // reset everything
      await log(store, Rating.good, GameType.dictation); // new round
      await log(store, Rating.good, GameType.flashcard, wordId: 2);

      expect(await store.loadPassedWordGamePairs(), {
        masteryKey(1, GameType.dictation.name),
        masteryKey(2, GameType.flashcard.name),
      });
    });

    test('streak-only games neither fill cells nor reset the grid', () async {
      final store = VocabStoreMemory(words: [_word(1)]);
      await log(store, Rating.good, GameType.cloze); // mastery cell
      // Pass in a streak-only game -> no new cell:
      await log(store, Rating.good, GameType.wordScramble);
      // MISS in a streak-only game -> must NOT reset the round:
      await log(store, Rating.again, GameType.oddOneOut);

      expect(await store.loadPassedWordGamePairs(), {
        masteryKey(1, GameType.cloze.name),
      });
    });
  });

  group('correct streaks + practice down-weighting', () {
    test('loadCorrectStreaks counts passes since that word\'s own last Again '
        '(per-word — a miss on one word does NOT weaken another)', () async {
      final store = VocabStoreMemory(words: [_word(1), _word(2)]);
      var t = 0;
      Future<void> log(Rating r, {int wordId = 1}) => store.logReview(
        ReviewLogEntry(
          wordId: wordId,
          ts: DateTime(2026, 7, 23).add(Duration(minutes: t++)),
          rating: r,
          gameType: GameType.flashcard.name,
          direction: Direction.enTh,
          elapsedMs: 0,
        ),
      );
      await log(Rating.good, wordId: 2);
      await log(Rating.good, wordId: 2);
      await log(Rating.good, wordId: 2);
      await log(Rating.good);
      await log(Rating.good);
      await log(Rating.again); // resets word 1's streak ONLY
      await log(Rating.good);
      await log(Rating.hard);
      expect(await store.loadCorrectStreaks(), {1: 2, 2: 3});
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
