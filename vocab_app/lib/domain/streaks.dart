/// Pure-Dart streak math for the Progress page. Pattern borrowed from
/// Gymmer_App's domain/streaks.dart (week-streak over workout days) but
/// adapted to this app's definition: a day "counts" only if the user
/// cleared all due words that day (SPEC.md section 10), not just opened
/// the app.
library;

DateTime _dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

String dateKey(DateTime d) {
  final x = _dateOnly(d);
  final mm = x.month.toString().padLeft(2, '0');
  final dd = x.day.toString().padLeft(2, '0');
  return '${x.year}-$mm-$dd';
}

/// Consecutive days (counting back from [now]) with `streak_kept == true`.
/// Today not having been kept yet doesn't break the streak (it just hasn't
/// been earned yet) — mirrors Gymmer's "current week may still be open"
/// rule, applied at day granularity.
int dayStreak(Set<String> streakKeptDates, {required DateTime now}) {
  var cursor = _dateOnly(now);
  if (!streakKeptDates.contains(dateKey(cursor))) {
    cursor = cursor.subtract(const Duration(days: 1));
  }
  var streak = 0;
  while (streakKeptDates.contains(dateKey(cursor))) {
    streak++;
    cursor = cursor.subtract(const Duration(days: 1));
  }
  return streak;
}

/// Heatmap cell data for a month grid: date -> review count that day.
Map<String, int> monthHeatmap(
  Map<String, int> reviewCountsByDate,
  DateTime monthAnchor,
) {
  final start = DateTime(monthAnchor.year, monthAnchor.month, 1);
  final end = DateTime(monthAnchor.year, monthAnchor.month + 1, 0);
  final out = <String, int>{};
  for (var d = start; !d.isAfter(end); d = d.add(const Duration(days: 1))) {
    out[dateKey(d)] = reviewCountsByDate[dateKey(d)] ?? 0;
  }
  return out;
}
