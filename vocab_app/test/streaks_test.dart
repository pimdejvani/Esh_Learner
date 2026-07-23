import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/streaks.dart';

void main() {
  test('dayStreak counts consecutive kept days ending today', () {
    final now = DateTime(2026, 7, 22);
    final kept = {
      dateKey(now),
      dateKey(now.subtract(const Duration(days: 1))),
      dateKey(now.subtract(const Duration(days: 2))),
    };
    expect(dayStreak(kept, now: now), 3);
  });

  test('an unkept today does not break a streak that continued yesterday', () {
    final now = DateTime(2026, 7, 22);
    final kept = {
      dateKey(now.subtract(const Duration(days: 1))),
      dateKey(now.subtract(const Duration(days: 2))),
    };
    expect(dayStreak(kept, now: now), 2);
  });

  test('a gap breaks the streak', () {
    final now = DateTime(2026, 7, 22);
    final kept = {
      dateKey(now),
      dateKey(now.subtract(const Duration(days: 2))), // gap at day-1
    };
    expect(dayStreak(kept, now: now), 1);
  });

  test('monthHeatmap fills every day of the month, defaulting to 0', () {
    final anchor = DateTime(2026, 2, 15);
    final heat = monthHeatmap({'2026-02-10': 5}, anchor);
    expect(heat.length, 28); // 2026 is not a leap year
    expect(heat['2026-02-10'], 5);
    expect(heat['2026-02-01'], 0);
  });

  group('logicalDateKey (3am day-boundary, SPEC.md 6.2 revision)', () {
    test('a session just after midnight still belongs to the day before', () {
      final justAfterMidnight = DateTime(2026, 7, 23, 1, 30);
      expect(logicalDateKey(justAfterMidnight), '2026-07-22');
    });

    test('a session right at the 3am boundary already belongs to today', () {
      final atBoundary = DateTime(2026, 7, 23, 3, 0);
      expect(logicalDateKey(atBoundary), '2026-07-23');
    });

    test('a normal daytime session maps to the plain calendar date', () {
      final noon = DateTime(2026, 7, 23, 12);
      expect(logicalDateKey(noon), '2026-07-23');
    });
  });
}
