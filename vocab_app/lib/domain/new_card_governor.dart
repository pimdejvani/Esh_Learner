/// Adaptive new-card cap / chunking (SPEC.md 6.4). Starts at 8/day, raises
/// or lowers within [3,15] based on backlog size and recent accuracy.
library;

import 'package:vocab_app/models/srs_state.dart';

class NewCardGovernor {
  const NewCardGovernor({
    this.initialCap = 8,
    this.minCap = 3,
    this.maxCap = 15,
    this.backlogHighThreshold = 20,
    this.backlogLowThreshold = 5,
    this.goodAccuracy = 0.85,
  });

  final int initialCap;
  final int minCap;
  final int maxCap;

  /// Backlog (overdue reviews) at/above this -> shrink the cap.
  final int backlogHighThreshold;

  /// Backlog at/below this -> may grow the cap.
  final int backlogLowThreshold;

  /// Accuracy needed (rolling, last 7 days) to allow the cap to grow.
  final double goodAccuracy;

  double _accuracy(List<ReviewLogEntry> reviews, DateTime now) {
    final cutoff = now.subtract(const Duration(days: 7));
    final recent = reviews.where((r) => r.ts.isAfter(cutoff)).toList();
    if (recent.isEmpty) return 1.0; // no data yet -> don't punish
    final correct = recent
        .where((r) => r.rating == Rating.good || r.rating == Rating.easy)
        .length;
    return correct / recent.length;
  }

  /// Computes tomorrow's new-card cap given [currentCap], the count of
  /// currently overdue review items ([backlogCount]), and recent [reviews].
  int nextCap({
    required int currentCap,
    required int backlogCount,
    required List<ReviewLogEntry> reviews,
    required DateTime now,
  }) {
    final accuracy = _accuracy(reviews, now);
    int next = currentCap;
    if (backlogCount >= backlogHighThreshold) {
      next = currentCap - 2;
    } else if (backlogCount <= backlogLowThreshold && accuracy >= goodAccuracy) {
      next = currentCap + 1;
    } else if (accuracy < goodAccuracy - 0.10) {
      // struggling even without backlog pressure -> ease off new material
      next = currentCap - 1;
    }
    return next.clamp(minCap, maxCap);
  }
}
