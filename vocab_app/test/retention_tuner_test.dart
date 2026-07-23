import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/retention_tuner.dart';
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
  final tuner = const RetentionTuner();
  final now = DateTime(2026, 7, 22);

  test('accuracy well above target lowers requestRetention (harder)', () {
    final reviews = List.generate(
      20,
      (i) => _rev(Rating.easy, now.subtract(Duration(hours: i))),
    );
    final next = tuner.nextRetention(current: 0.88, reviews: reviews, now: now);
    expect(next, lessThan(0.88));
  });

  test('accuracy well below target raises requestRetention (easier)', () {
    final reviews = List.generate(
      20,
      (i) => _rev(i % 3 == 0 ? Rating.good : Rating.again, now.subtract(Duration(hours: i))),
    );
    final next = tuner.nextRetention(current: 0.88, reviews: reviews, now: now);
    expect(next, greaterThan(0.88));
  });

  test('accuracy within the desirable-difficulty band leaves retention unchanged', () {
    // Roughly 80% good rate, right on the ~80% target (product decision
    // 2026-07-23: user prefers the harder 80% zone over ~95%).
    final reviews = [
      for (var i = 0; i < 100; i++)
        _rev(i < 80 ? Rating.good : Rating.again, now.subtract(Duration(minutes: i))),
    ];
    final next = tuner.nextRetention(current: 0.80, reviews: reviews, now: now);
    expect(next, closeTo(0.80, 1e-9));
  });

  test('defaults target the ~80% zone, capped below 0.95', () {
    expect(tuner.targetAccuracy, closeTo(0.80, 1e-9));
    expect(tuner.initialRetention, closeTo(0.80, 1e-9));
    expect(tuner.maxRetention, lessThanOrEqualTo(0.90));
  });

  test('reviews older than 7 days are ignored by rollingAccuracy', () {
    final stale = [_rev(Rating.again, now.subtract(const Duration(days: 30)))];
    final acc = tuner.rollingAccuracy(stale, now);
    expect(acc, tuner.targetAccuracy); // no recent signal -> neutral default
  });

  test('retention stays within [minRetention, maxRetention]', () {
    var r = 0.88;
    final badReviews = List.generate(
      20,
      (i) => _rev(Rating.again, now.subtract(Duration(hours: i))),
    );
    for (var i = 0; i < 50; i++) {
      r = tuner.nextRetention(current: r, reviews: badReviews, now: now);
    }
    expect(r, tuner.maxRetention);
  });
}
