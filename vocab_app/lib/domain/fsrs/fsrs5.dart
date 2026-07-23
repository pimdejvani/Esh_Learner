/// FSRS-5 (Free Spaced Repetition Scheduler v5) — ported to Dart from the
/// public reference formulas (open-sourced by the FSRS project, e.g.
/// ts-fsrs / py-fsrs). Per-item stability/difficulty model, no fixed
/// intervals. See SPEC.md section 6.1.
///
/// Short-term/same-day re-review formulas (FSRS-5 w[17]/w[18]) are
/// intentionally NOT implemented. A card CAN legitimately come due again
/// the same day now (e.g. an early "Again" rating gives roughly a
/// half-day interval, SPEC.md 6.2 revision — no forced minimum gap
/// anymore), but we still use the standard long-term formula for that
/// case rather than the separate same-day model; documented as a known
/// simplification (see NOTES.md).
library;

import 'dart:math' as math;

import '../../models/srs_state.dart';

/// Default FSRS-5 weights (17 parameters, w[0]..w[16] used here; w17/w18
/// are the same-day terms we don't need — see doc comment above).
const List<double> kFsrs5DefaultWeights = [
  0.4072, 1.1829, 3.1262, 15.4722, 7.2102, 0.5316, 1.0651, 0.0234, 1.616,
  0.1544, 1.0824, 1.9813, 0.0953, 0.2975, 2.2042, 0.2407, 2.9466, 0.5034,
  0.6567,
];

const double kFsrsDecay = -0.5;
final double kFsrsFactor = 19 / 81; // 0.9 ^ (1/DECAY) - 1

double _clampD(double d) => d.clamp(1.0, 10.0);

int _ratingGrade(Rating r) {
  switch (r) {
    case Rating.again:
      return 1;
    case Rating.hard:
      return 2;
    case Rating.good:
      return 3;
    case Rating.easy:
      return 4;
  }
}

class FsrsScheduler {
  const FsrsScheduler({this.weights = kFsrs5DefaultWeights});

  final List<double> weights;

  double _initStability(int grade) => weights[grade - 1].clamp(0.1, 36500.0);

  double _initDifficulty(int grade) =>
      _clampD(weights[4] - (math.exp(weights[5] * (grade - 1))) + 1);

  /// Retrievability given elapsed days [t] since last review and current
  /// stability [s].
  double retrievability(double t, double s) {
    if (s <= 0) return 0;
    return math.pow(1 + kFsrsFactor * t / s, kFsrsDecay).toDouble();
  }

  double _nextDifficulty(double d, int grade) {
    final deltaD = -weights[6] * (grade - 3);
    final dPrime = d + deltaD * ((10 - d) / 9);
    final d0Easy = _initDifficulty(4);
    final meanReverted = weights[7] * d0Easy + (1 - weights[7]) * dPrime;
    return _clampD(meanReverted);
  }

  double _nextStabilityOnSuccess(double d, double s, double r, int grade) {
    final hardPenalty = grade == 2 ? weights[15] : 1.0;
    final easyBonus = grade == 4 ? weights[16] : 1.0;
    final double factor =
        (math.exp(weights[8]) *
                (11 - d) *
                math.pow(s, -weights[9]) *
                (math.exp((1 - r) * weights[10]) - 1) *
                hardPenalty *
                easyBonus)
            .toDouble();
    return s * (1 + factor);
  }

  double _nextStabilityOnFailure(double d, double s, double r) {
    return (weights[11] *
            math.pow(d, -weights[12]) *
            (math.pow(s + 1, weights[13]) - 1) *
            math.exp((1 - r) * weights[14]))
        .toDouble();
  }

  /// Applies a review [rating] to [current] state at time [now], returning
  /// the new SrsState with stability/difficulty/due_at all computed here
  /// (due_at from the target retention interval — no external floor).
  SrsState review({
    required SrsState current,
    required Rating rating,
    required DateTime now,
    required double requestRetention,
  }) {
    final grade = _ratingGrade(rating);
    final isFirstReview = current.reps == 0 && current.lastReview == null;

    double newS;
    double newD;
    if (isFirstReview) {
      newS = _initStability(grade);
      newD = _initDifficulty(grade);
    } else {
      final elapsedDays = current.lastReview == null
          ? 0.0
          : now.difference(current.lastReview!).inHours / 24.0;
      final r = retrievability(elapsedDays, current.stability);
      newD = _nextDifficulty(current.difficulty, grade);
      newS = rating == Rating.again
          ? _nextStabilityOnFailure(current.difficulty, current.stability, r)
          : _nextStabilityOnSuccess(current.difficulty, current.stability, r, grade);
    }
    newS = newS.clamp(0.1, 36500.0);

    final nextIntervalDays = intervalForStability(newS, requestRetention);
    final dueAt = now.add(Duration(minutes: (nextIntervalDays * 24 * 60).round()));

    CardState nextState;
    if (rating == Rating.again) {
      nextState = current.reps == 0 ? CardState.learning : CardState.learning;
      if (current.state == CardState.mature) {
        // lapse from mature drops back to learning per standard FSRS state model
        nextState = CardState.learning;
      }
    } else if (newS >= 21) {
      nextState = CardState.mature;
    } else if (isFirstReview) {
      nextState = CardState.learning;
    } else {
      nextState = CardState.young;
    }

    return current.copyWith(
      state: nextState,
      stability: newS,
      difficulty: newD,
      dueAt: dueAt,
      lastReview: now,
      reps: current.reps + 1,
      lapses: rating == Rating.again ? current.lapses + 1 : current.lapses,
    );
  }

  /// Days until retrievability drops to [requestRetention] for a card with
  /// stability [s].
  double intervalForStability(double s, double requestRetention) {
    final r = requestRetention.clamp(0.70, 0.99);
    final double days =
        ((s / kFsrsFactor) * (math.pow(r, 1 / kFsrsDecay) - 1)).toDouble();
    return days.clamp(0.0, 36500.0);
  }
}
