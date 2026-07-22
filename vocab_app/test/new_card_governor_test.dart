import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/new_card_governor.dart';
import 'package:vocab_app/models/srs_state.dart';

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
}
