import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/games/odd_one_out.dart';
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
  bool giveaway = false,
}) => RelatedWord(
  id: relatedWordId,
  wordId: wordId,
  relatedWordId: relatedWordId,
  relationType: type,
  closeness: 0.5,
  isGiveaway: giveaway,
);

void main() {
  // school(1) -> student(2), teacher(3), book(4): a coherent "school" hub.
  // cat(5) has no ties to the school hub at all -> the genuine odd one out.
  final pool = [
    _word(1, 'school'),
    _word(2, 'student'),
    _word(3, 'teacher'),
    _word(4, 'book'),
    _word(5, 'cat'),
  ];
  final relatedByWord = {
    1: [_rel(1, 2), _rel(1, 3), _rel(1, 4)],
  };

  group('buildOddOneOutGroup', () {
    test('builds a group from words that all relate to a common hub', () {
      final group = buildOddOneOutGroup(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: relatedByWord,
      );
      expect(group, isNotNull);
      expect(group!.map((w) => w.id).toSet(), {2, 3, 4});
    });

    test('never includes the target itself in the group', () {
      final group = buildOddOneOutGroup(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: relatedByWord,
      );
      expect(group!.any((w) => w.id == 5), isFalse);
    });

    test('rejects a hub the target IS related to (not a fair odd-one-out)', () {
      // "student" is related to "school" -> can't be the odd one out
      // against the school hub's own members.
      final group = buildOddOneOutGroup(
        target: _word(2, 'student'),
        pool: pool,
        relatedByWord: relatedByWord,
        groupSize: 3,
      );
      expect(group, isNull);
    });

    test('returns null when no hub has enough qualifying members yet', () {
      final sparse = {
        1: [_rel(1, 2)], // only 1 member, below groupSize
      };
      final group = buildOddOneOutGroup(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: sparse,
        groupSize: 3,
      );
      expect(group, isNull);
    });

    test('falls back to a smaller group size (2) when 3 isn\'t reachable', () {
      final twoMember = {
        1: [_rel(1, 2), _rel(1, 3)],
      };
      final group = buildOddOneOutGroup(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: twoMember,
        groupSize: 3,
      );
      expect(group, isNotNull);
      expect(group!.length, 2);
    });

    test('excludes is_giveaway rows from candidate group members', () {
      final withGiveaway = {
        1: [_rel(1, 2, giveaway: true), _rel(1, 3), _rel(1, 4)],
      };
      final group = buildOddOneOutGroup(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: withGiveaway,
        groupSize: 2,
      );
      expect(group, isNotNull);
      expect(group!.any((w) => w.id == 2), isFalse);
    });
  });
}
