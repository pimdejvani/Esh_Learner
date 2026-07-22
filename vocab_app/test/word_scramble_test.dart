import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/games/word_scramble.dart';
import 'package:vocab_app/models/srs_state.dart';

void main() {
  group('scrambleWord', () {
    test('returns a permutation with the same letters', () {
      final scrambled = scrambleWord('answer', random: Random(1));
      expect(scrambled.split('')..sort(), 'answer'.split('')..sort());
    });

    test('differs from the original whenever a different permutation exists', () {
      for (var seed = 0; seed < 20; seed++) {
        final scrambled = scrambleWord('travel', random: Random(seed));
        expect(scrambled, isNot('travel'));
      }
    });

    test('a single-character word is returned unscrambled (no possible variation)', () {
      expect(scrambleWord('a', random: Random(1)), 'a');
    });

    test('an empty string is returned unscrambled', () {
      expect(scrambleWord('', random: Random(1)), '');
    });
  });

  group('answer checking (production task, reused from answer_checker)', () {
    const checker = AnswerChecker();

    test('typing the exact headword back grades correct', () {
      final result = checker.check(userInput: 'answer', expected: 'answer', elapsedMs: 5000);
      expect(result.verdict, AnswerVerdict.correct);
    });

    test('a genuine one-letter typo on the reproduced word grades Hard', () {
      // "answar" is a single substitution (e -> a) away from "answer".
      final result = checker.check(userInput: 'answar', expected: 'answer');
      expect(result.verdict, AnswerVerdict.almostTypo);
      expect(result.rating, Rating.hard);
    });

    test('hint usage caps a correct scramble answer at Hard', () {
      final result = checker.check(userInput: 'answer', expected: 'answer', elapsedMs: 500);
      expect(result.rating, Rating.easy);
      final capped = checker.capForHint(result.rating, usedHint: true);
      expect(capped, Rating.hard);
    });

    test('no hint used leaves a correct fast answer as Easy', () {
      final result = checker.check(userInput: 'answer', expected: 'answer', elapsedMs: 500);
      final capped = checker.capForHint(result.rating, usedHint: false);
      expect(capped, Rating.easy);
    });
  });
}
