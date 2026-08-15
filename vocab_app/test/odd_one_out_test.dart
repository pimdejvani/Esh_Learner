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
);

RelatedWord _rel(
  int wordId,
  int relatedWordId, {
  String type = 'association',
  bool giveaway = false,
  double closeness = 0.5,
}) => RelatedWord(
  id: relatedWordId,
  wordId: wordId,
  relatedWordId: relatedWordId,
  relatedHeadword: 'w$relatedWordId',
  relationType: type,
  closeness: closeness,
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
    test('keeps the hub and member relations for a sourced explanation', () {
      final round = buildOddOneOutRound(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: relatedByWord,
      );
      expect(round, isNotNull);
      expect(round!.hubWordId, 1);
      expect(round.groupWords.map((word) => word.id), [2, 3, 4]);
      expect(round.memberRelations.map((row) => row.relatedWordId), [2, 3, 4]);
    });

    test(
      'the reveal uses the stored explanation, falling back to the type',
      () {
        // The authored explanation wins whenever the content build wrote one.
        expect(
          oddOneOutRelationText(
            hub: _word(1, 'day'),
            member: _word(2, 'measure'),
            relationType: 'hypernym',
            explanationTh: 'measure เป็นหน่วยที่ใช้วัด day',
          ),
          'measure เป็นหน่วยที่ใช้วัด day',
        );
        // Rows written before explanations were stored still read sensibly.
        expect(
          oddOneOutRelationText(
            hub: _word(1, 'day'),
            member: _word(2, 'measure'),
            relationType: 'hypernym',
          ),
          'measure เป็นประเภทหนึ่งของ day',
        );
      },
    );

    test('collapses members that share one reason into a single line', () {
      // The classic case from the screenshots: three rows saying the very
      // same thing about career, differing only in the member they name.
      const reason = 'เป็นคำที่คนมักนึกถึงคู่กันในเรื่องเส้นทางอาชีพ';
      final hub = _word(1, 'career');
      final members = [_word(2, 'job'), _word(3, 'work'), _word(4, 'money')];
      final lines = oddOneOutReasonLines(
        hub: hub,
        members: members,
        relations: [
          for (final m in members)
            RelatedWord(
              id: m.id,
              wordId: 1,
              relatedWordId: m.id,
              relatedHeadword: m.headword,
              relationType: 'association',
              closeness: 0.5,
              isGiveaway: false,
              explanationTh: 'career กับ ${m.headword} $reason',
            ),
        ],
      );
      expect(lines, ['career กับ job, work, money $reason']);
    });

    test('keeps genuinely different reasons on their own lines', () {
      final hub = _word(1, 'car');
      final members = [_word(2, 'wheel'), _word(3, 'drive')];
      final lines = oddOneOutReasonLines(
        hub: hub,
        members: members,
        relations: [
          _rel(1, 2, type: 'part_of'),
          _rel(1, 3, type: 'used_for'),
        ],
      );
      expect(lines, [
        'wheel เป็นส่วนหนึ่งของ car',
        'drive ใช้คู่กับ car',
      ]);
    });

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

    test('no longer falls back below 3 group members — 2 strong members '
        'means no Odd round (revision 2026-07-24)', () {
      final twoMember = {
        1: [_rel(1, 2), _rel(1, 3)],
      };
      final group = buildOddOneOutGroup(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: twoMember,
        groupSize: 3,
      );
      expect(group, isNull);
    });

    test('weak association ties below minCloseness do not count as '
        'same-group (consistent coherence bar, revision 2026-07-24)', () {
      // Hub has 3 members but one tie is weak (0.01 < 0.03 default bar)
      // -> only 2 qualify -> no round.
      final mixed = {
        1: [_rel(1, 2), _rel(1, 3), _rel(1, 4, closeness: 0.01)],
      };
      final group = buildOddOneOutGroup(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: mixed,
      );
      expect(group, isNull);
    });

    test('typed category data (hypernym) qualifies regardless of '
        'closeness', () {
      final typed = {
        1: [
          _rel(1, 2, type: 'hypernym', closeness: 0.001),
          _rel(1, 3, type: 'hypernym', closeness: 0.001),
          _rel(1, 4, type: 'hypernym', closeness: 0.001),
        ],
      };
      final group = buildOddOneOutGroup(
        target: _word(5, 'cat'),
        pool: pool,
        relatedByWord: typed,
      );
      expect(group, isNotNull);
      expect(group!.map((w) => w.id).toSet(), {2, 3, 4});
    });

    test('strict early-game mode needs MORE THAN 2 qualifying groups '
        '(revision 2026-07-24)', () {
      final bigPool = [for (var i = 1; i <= 12; i++) _word(i, 'w$i')];
      Map<int, List<RelatedWord>> hubs(int count) => {
        // Hub h relates to 3 members each, none of them word 12.
        for (var h = 0; h < count; h++)
          h + 1: [
            _rel(h + 1, (h * 3 + 2) % 11 + 1),
            _rel(h + 1, (h * 3 + 3) % 11 + 1),
            _rel(h + 1, (h * 3 + 4) % 11 + 1),
          ],
      };
      final target = _word(12, 'odd');
      // 2 groups only -> strict refuses.
      expect(
        buildOddOneOutGroup(
          target: target,
          pool: bigPool,
          relatedByWord: hubs(2),
          strict: true,
        ),
        isNull,
      );
      // Same data, non-strict -> fine.
      expect(
        buildOddOneOutGroup(
          target: target,
          pool: bigPool,
          relatedByWord: hubs(2),
        ),
        isNotNull,
      );
      // 3 groups -> strict allows.
      expect(
        buildOddOneOutGroup(
          target: target,
          pool: bigPool,
          relatedByWord: hubs(3),
          strict: true,
        ),
        isNotNull,
      );
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
