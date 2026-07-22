/// Adaptive success-rate targeting (SPEC.md 6.3). Nudges `requestRetention`
/// based on rolling 7-day accuracy so the app sits in the ~85-90% desirable
/// difficulty zone instead of a fixed target forever.
library;

import 'package:vocab_app/models/srs_state.dart';

class RetentionTuner {
  const RetentionTuner({
    this.initialRetention = 0.88,
    this.minRetention = 0.75,
    this.maxRetention = 0.95,
    this.targetAccuracy = 0.875, // midpoint of desirable-difficulty band
    this.band = 0.03,
    this.step = 0.01,
  });

  final double initialRetention;
  final double minRetention;
  final double maxRetention;
  final double targetAccuracy;
  final double band;
  final double step;

  /// Rolling accuracy from the last 7 days of [reviews] (ratio of
  /// good/easy vs. all ratings). Reviews outside the window are ignored.
  double rollingAccuracy(List<ReviewLogEntry> reviews, DateTime now) {
    final cutoff = now.subtract(const Duration(days: 7));
    final recent = reviews.where((r) => r.ts.isAfter(cutoff)).toList();
    if (recent.isEmpty) return targetAccuracy; // no signal -> stay put
    final correct = recent
        .where((r) => r.rating == Rating.good || r.rating == Rating.easy)
        .length;
    return correct / recent.length;
  }

  /// Computes the next requestRetention given the [current] value and the
  /// accuracy signal. Accuracy well above target -> lower retention target
  /// (longer intervals, harder); well below -> raise it (more frequent
  /// review). Small steps, clamped to [minRetention, maxRetention].
  double nextRetention({
    required double current,
    required List<ReviewLogEntry> reviews,
    required DateTime now,
  }) {
    final accuracy = rollingAccuracy(reviews, now);
    double next = current;
    if (accuracy > targetAccuracy + band) {
      next = current - step;
    } else if (accuracy < targetAccuracy - band) {
      next = current + step;
    }
    return next.clamp(minRetention, maxRetention);
  }
}
