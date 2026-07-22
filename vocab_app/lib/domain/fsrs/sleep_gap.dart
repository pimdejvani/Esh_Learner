/// Sleep-anchored minimum gap (SPEC.md 6.2). A card reviewed for the first
/// time never comes due again the same day — it's forced to the next
/// morning's anchor hour so the first re-review always happens after sleep.
library;

/// Local hour (0-23) new cards become due the next day.
const int kMorningAnchorHour = 8;

/// Given the moment [now] a brand-new card was first shown, returns the
/// due timestamp for its first review: tomorrow at [kMorningAnchorHour]
/// local time (never today, regardless of what time `now` is).
DateTime sleepGapDueAt(DateTime now, {int anchorHour = kMorningAnchorHour}) {
  final tomorrow = DateTime(now.year, now.month, now.day + 1, anchorHour);
  return tomorrow;
}

/// Applies the sleep-gap floor to a FSRS-computed [candidateDueAt] for a
/// card's *first* post-intro review: if FSRS alone would schedule it later
/// than the sleep-anchored minimum, FSRS wins (it's already conservative
/// enough); if FSRS would schedule it earlier (e.g. same day), the sleep
/// gap wins.
DateTime applySleepGap(
  DateTime now,
  DateTime candidateDueAt, {
  int anchorHour = kMorningAnchorHour,
}) {
  final minimum = sleepGapDueAt(now, anchorHour: anchorHour);
  return candidateDueAt.isBefore(minimum) ? minimum : candidateDueAt;
}
