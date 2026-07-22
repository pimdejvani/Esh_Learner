import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/games/word_association.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';

Word _word(int id, String headword) => Word(
  id: id,
  headword: headword,
  cefr: 'A1',
  freqRank: id,
  thaiReading: headword,
  stressIndex: 1,
  ipa: '',
  translationSource: '',
  translationLicense: '',
  hasPhoto: false,
);

RelatedWord _rel(
  int wordId,
  int relatedWordId, {
  String type = 'association',
  double closeness = 0.5,
  bool giveaway = false,
}) => RelatedWord(
  id: relatedWordId,
  wordId: wordId,
  relatedWordId: relatedWordId,
  relationType: type,
  closeness: closeness,
  isGiveaway: giveaway,
);

void main() {
  group('pickAssociationTarget', () {
    test('prefers relation_type association among non-giveaway rows', () {
      final related = [
        _rel(1, 2, type: 'hypernym', closeness: 0.9),
        _rel(1, 3, type: 'association', closeness: 0.4),
      ];
      final pick = pickAssociationTarget(related);
      expect(pick!.relatedWordId, 3);
    });

    test('picks the highest-closeness candidate among the preferred type', () {
      final related = [
        _rel(1, 2, closeness: 0.3),
        _rel(1, 3, closeness: 0.9),
        _rel(1, 4, closeness: 0.6),
      ];
      final pick = pickAssociationTarget(related);
      expect(pick!.relatedWordId, 3);
    });

    test('excludes is_giveaway rows entirely', () {
      final related = [
        _rel(1, 2, closeness: 0.9, giveaway: true),
        _rel(1, 3, closeness: 0.2, giveaway: false),
      ];
      final pick = pickAssociationTarget(related);
      expect(pick!.relatedWordId, 3);
    });

    test('falls back to any non-giveaway type if no association rows exist', () {
      final related = [_rel(1, 2, type: 'hypernym', closeness: 0.7)];
      final pick = pickAssociationTarget(related);
      expect(pick!.relatedWordId, 2);
    });

    test('returns null when every candidate is a giveaway', () {
      final related = [_rel(1, 2, giveaway: true)];
      expect(pickAssociationTarget(related), isNull);
    });

    test('returns null for an empty related list', () {
      expect(pickAssociationTarget([]), isNull);
    });
  });

  group('buildAssociationOptions', () {
    test('always includes the correct word among the options', () {
      final correct = _word(1, 'dog');
      final pool = List.generate(10, (i) => _word(i + 10, 'w${i + 10}'));
      final options = buildAssociationOptions(
        correct: correct,
        pool: pool,
        excludeIds: {},
        random: Random(42),
      );
      expect(options.any((w) => w.id == correct.id), isTrue);
    });

    test('excludes ids in excludeIds from the distractor pool', () {
      final correct = _word(1, 'dog');
      final pool = [correct, _word(2, 'cat'), _word(3, 'school'), _word(4, 'book')];
      final options = buildAssociationOptions(
        correct: correct,
        pool: pool,
        excludeIds: {2}, // "cat" is already a related word, must not appear
        distractorCount: 5,
        random: Random(1),
      );
      expect(options.any((w) => w.id == 2), isFalse);
    });

    test('caps the option count at 1 correct + distractorCount', () {
      final correct = _word(1, 'dog');
      final pool = List.generate(20, (i) => _word(i + 10, 'w${i + 10}'));
      final options = buildAssociationOptions(
        correct: correct,
        pool: pool,
        excludeIds: {},
        distractorCount: 3,
        random: Random(7),
      );
      expect(options.length, 4);
    });
  });

  group('hint-usage caps the rating at Hard', () {
    // Word Association routes its final rating through
    // AnswerChecker.capForHint just like every other family-A game.
    const checker = AnswerChecker();

    test('a correct pick with a hint used caps Easy/Good down to Hard', () {
      expect(checker.capForHint(Rating.easy, usedHint: true), Rating.hard);
      expect(checker.capForHint(Rating.good, usedHint: true), Rating.hard);
    });

    test('a wrong pick stays Again even if a hint was used', () {
      expect(checker.capForHint(Rating.again, usedHint: true), Rating.again);
    });

    test('no hint used leaves the rating untouched', () {
      expect(checker.capForHint(Rating.easy, usedHint: false), Rating.easy);
    });
  });
}
