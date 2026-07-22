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
}
