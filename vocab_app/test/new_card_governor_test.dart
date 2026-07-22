import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/new_card_governor.dart';
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

ReviewLogEntry _rev(Rating r, DateTime ts) => ReviewLogEntry(
  wordId: 1,
  ts: ts,
  rating: r,
  gameType: 'cloze',
  direction: Direction.enTh,
  elapsedMs: 1000,
);

void main() {
  final governor = const NewCardGovernor();
  final now = DateTime(2026, 7, 22);

  test('high backlog shrinks the cap', () {
    final next = governor.nextCap(
      currentCap: 8,
      backlogCount: 25,
      reviews: [],
      now: now,
    );
    expect(next, lessThan(8));
  });

  test('low backlog + good accuracy grows the cap', () {
    final reviews = List.generate(
      20,
      (i) => _rev(Rating.good, now.subtract(Duration(hours: i))),
    );
    final next = governor.nextCap(
      currentCap: 8,
      backlogCount: 2,
      reviews: reviews,
      now: now,
    );
    expect(next, greaterThan(8));
  });

  test('low backlog + poor accuracy does not grow the cap', () {
    final reviews = List.generate(
      20,
      (i) => _rev(i.isEven ? Rating.again : Rating.good, now.subtract(Duration(hours: i))),
    );
    final next = governor.nextCap(
      currentCap: 8,
      backlogCount: 2,
      reviews: reviews,
      now: now,
    );
    expect(next, lessThanOrEqualTo(8));
  });

  test('cap never drops below minCap or exceeds maxCap', () {
    var cap = 8;
    for (var i = 0; i < 30; i++) {
      cap = governor.nextCap(
        currentCap: cap,
        backlogCount: 100,
        reviews: [],
        now: now,
      );
    }
    expect(cap, governor.minCap);

    cap = 8;
    final greatReviews = List.generate(
      20,
      (i) => _rev(Rating.easy, now.subtract(Duration(hours: i))),
    );
    for (var i = 0; i < 30; i++) {
      cap = governor.nextCap(
        currentCap: cap,
        backlogCount: 0,
        reviews: greatReviews,
        now: now,
      );
    }
    expect(cap, governor.maxCap);
  });

  group('orderNewCandidates (SPEC.md 6.4 focus topic bias)', () {
    test('is a no-op when focusTopicWordIds is empty', () {
      final candidates = [_word(1), _word(2), _word(3)];
      final ordered = orderNewCandidates(candidates: candidates, focusTopicWordIds: {});
      expect(ordered, same(candidates));
    });

    test('moves focus-topic words to the front, preserving relative order', () {
      final candidates = [_word(1), _word(2), _word(3), _word(4)];
      final ordered = orderNewCandidates(
        candidates: candidates,
        focusTopicWordIds: {3, 4},
      );
      expect(ordered.map((w) => w.id), [3, 4, 1, 2]);
    });

    test('words not in the focus topic keep their original freq_rank order', () {
      final candidates = [_word(1), _word(2), _word(3), _word(4), _word(5)];
      final ordered = orderNewCandidates(
        candidates: candidates,
        focusTopicWordIds: {4},
      );
      expect(ordered.map((w) => w.id), [4, 1, 2, 3, 5]);
    });
  });
}
