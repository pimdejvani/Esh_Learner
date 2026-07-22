import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/fsrs/fsrs5.dart';
import 'package:vocab_app/domain/fsrs/sleep_gap.dart';
import 'package:vocab_app/models/srs_state.dart';

void main() {
  final scheduler = const FsrsScheduler();
  final now = DateTime(2026, 7, 22, 10);

  group('FsrsScheduler.review', () {
    test('first review with Good sets initial stability from weights', () {
      final initial = SrsState.initial(1, now);
      final result = scheduler.review(
        current: initial,
        rating: Rating.good,
        now: now,
        requestRetention: 0.88,
      );
      expect(result.stability, closeTo(kFsrs5DefaultWeights[2], 1e-9));
      expect(result.reps, 1);
      expect(result.lapses, 0);
      expect(result.dueAt.isAfter(now), isTrue);
    });

    test('Again on first review yields lower stability than Good', () {
      final initial = SrsState.initial(1, now);
      final again = scheduler.review(
        current: initial,
        rating: Rating.again,
        now: now,
        requestRetention: 0.88,
      );
      final good = scheduler.review(
        current: initial,
        rating: Rating.good,
        now: now,
        requestRetention: 0.88,
      );
      expect(again.stability, lessThan(good.stability));
    });

    test('Easy grants a longer next interval than Good', () {
      final initial = SrsState.initial(1, now);
      final easy = scheduler.review(
        current: initial,
        rating: Rating.easy,
        now: now,
        requestRetention: 0.88,
      );
      final good = scheduler.review(
        current: initial,
        rating: Rating.good,
        now: now,
        requestRetention: 0.88,
      );
      expect(easy.dueAt.isAfter(good.dueAt), isTrue);
    });

    test('repeated successful reviews grow stability (spacing effect)', () {
      var state = SrsState.initial(1, now);
      state = scheduler.review(
        current: state,
        rating: Rating.good,
        now: now,
        requestRetention: 0.88,
      );
      final afterFirst = state.stability;
      final later = now.add(Duration(days: (state.stability).ceil()));
      state = scheduler.review(
        current: state,
        rating: Rating.good,
        now: later,
        requestRetention: 0.88,
      );
      expect(state.stability, greaterThan(afterFirst));
    });

    test('lapse (Again) after maturity drops state back to learning', () {
      var state = SrsState.initial(1, now);
      // Simulate several good reviews to reach mature.
      var t = now;
      for (var i = 0; i < 6; i++) {
        state = scheduler.review(
          current: state,
          rating: Rating.good,
          now: t,
          requestRetention: 0.88,
        );
        t = state.dueAt.add(const Duration(hours: 1));
      }
      expect(state.state, CardState.mature);
      final lapsed = scheduler.review(
        current: state,
        rating: Rating.again,
        now: t,
        requestRetention: 0.88,
      );
      expect(lapsed.state, CardState.learning);
      expect(lapsed.lapses, 1);
    });

    test('higher requestRetention shortens the next interval', () {
      var state = SrsState.initial(1, now);
      state = scheduler.review(
        current: state,
        rating: Rating.good,
        now: now,
        requestRetention: 0.88,
      );
      final later = state.dueAt.add(const Duration(hours: 1));

      final loose = scheduler.review(
        current: state,
        rating: Rating.good,
        now: later,
        requestRetention: 0.75,
      );
      final strict = scheduler.review(
        current: state,
        rating: Rating.good,
        now: later,
        requestRetention: 0.95,
      );
      expect(strict.dueAt.isBefore(loose.dueAt), isTrue);
    });
  });

  group('retrievability', () {
    test('is 1.0 at t=0 and decays toward 0 as t grows', () {
      final r0 = scheduler.retrievability(0, 10);
      final r30 = scheduler.retrievability(30, 10);
      final r300 = scheduler.retrievability(300, 10);
      expect(r0, closeTo(1.0, 1e-9));
      expect(r30, lessThan(r0));
      expect(r300, lessThan(r30));
    });
  });

  group('sleep-anchored minimum gap', () {
    test('sleepGapDueAt always lands the next calendar day at anchor hour', () {
      final earlyMorning = DateTime(2026, 7, 22, 1);
      final lateNight = DateTime(2026, 7, 22, 23, 59);
      final d1 = sleepGapDueAt(earlyMorning);
      final d2 = sleepGapDueAt(lateNight);
      expect(d1.day, 23);
      expect(d1.hour, kMorningAnchorHour);
      expect(d2.day, 23);
      expect(d2.hour, kMorningAnchorHour);
    });

    test('applySleepGap never allows same-day due for a first review', () {
      final candidateSameDay = DateTime(2026, 7, 22, 18);
      final result = applySleepGap(now, candidateSameDay);
      expect(result.day, isNot(now.day));
    });

    test('applySleepGap keeps FSRS due date if already beyond the floor', () {
      final candidateFarFuture = DateTime(2026, 8, 1);
      final result = applySleepGap(now, candidateFarFuture);
      expect(result, candidateFarFuture);
    });
  });
}
