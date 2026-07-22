/// Typo-tolerant answer grading (SPEC.md section 2 "Default" table + 8b).
library;

import 'package:vocab_app/models/srs_state.dart';

enum AnswerVerdict { correct, almostTypo, wrong }

class AnswerCheckResult {
  const AnswerCheckResult({required this.verdict, required this.rating});

  final AnswerVerdict verdict;

  /// Suggested FSRS rating BEFORE any hint-usage cap is applied (caller
  /// applies [capForHint] separately, since hint usage is a game-level
  /// concern, not something the checker itself tracks).
  final Rating rating;
}

int _levenshtein(String a, String b) {
  if (a == b) return 0;
  if (a.isEmpty) return b.length;
  if (b.isEmpty) return a.length;
  final prev = List<int>.generate(b.length + 1, (i) => i);
  final curr = List<int>.filled(b.length + 1, 0);
  for (var i = 1; i <= a.length; i++) {
    curr[0] = i;
    for (var j = 1; j <= b.length; j++) {
      final cost = a[i - 1] == b[j - 1] ? 0 : 1;
      curr[j] = [
        curr[j - 1] + 1, // insertion
        prev[j] + 1, // deletion
        prev[j - 1] + cost, // substitution
      ].reduce((x, y) => x < y ? x : y);
    }
    for (var j = 0; j <= b.length; j++) {
      prev[j] = curr[j];
    }
  }
  return prev[b.length];
}

String normalize(String s) => s.trim().toLowerCase().replaceAll(RegExp(r'\s+'), ' ');

class AnswerChecker {
  const AnswerChecker({this.typoDistance = 1, this.minLengthForTypo = 4});

  final int typoDistance;
  final int minLengthForTypo;

  /// Checks [userInput] against [expected] (the target headword/form).
  /// Fast-exact-match -> Easy, normalized exact match -> Good,
  /// Levenshtein<=1 typo on words longer than [minLengthForTypo] -> Hard
  /// (per spec: "เกือบถูก" typo tolerance never counts as Again), otherwise
  /// wrong -> Again.
  ///
  /// [elapsedMs] lets fast, error-free answers get graded Easy — pass null
  /// to skip the speed bonus (e.g. non-timed games).
  AnswerCheckResult check({
    required String userInput,
    required String expected,
    int? elapsedMs,
    int fastThresholdMs = 3000,
  }) {
    final normUser = normalize(userInput);
    final normExpected = normalize(expected);

    if (normUser == normExpected) {
      final fast = elapsedMs != null && elapsedMs <= fastThresholdMs;
      return AnswerCheckResult(
        verdict: AnswerVerdict.correct,
        rating: fast ? Rating.easy : Rating.good,
      );
    }

    if (normExpected.length > minLengthForTypo) {
      final dist = _levenshtein(normUser, normExpected);
      if (dist <= typoDistance && dist > 0) {
        return const AnswerCheckResult(
          verdict: AnswerVerdict.almostTypo,
          rating: Rating.hard,
        );
      }
    }

    return const AnswerCheckResult(
      verdict: AnswerVerdict.wrong,
      rating: Rating.again,
    );
  }

  /// SPEC.md 8b: using a hint and still getting it right caps the rating at
  /// Hard (never Good/Easy), because retrieval effort was reduced.
  Rating capForHint(Rating rating, {required bool usedHint}) {
    if (!usedHint) return rating;
    if (rating == Rating.again) return rating; // wrong stays wrong
    if (rating == Rating.hard) return rating;
    return Rating.hard;
  }
}
