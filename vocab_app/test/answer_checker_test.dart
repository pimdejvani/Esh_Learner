import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/models/srs_state.dart';

void main() {
  final checker = const AnswerChecker();

  group('AnswerChecker.check', () {
    test('exact match (slow) grades Good', () {
      final r = checker.check(
        userInput: 'answer',
        expected: 'answer',
        elapsedMs: 5000,
      );
      expect(r.verdict, AnswerVerdict.correct);
      expect(r.rating, Rating.good);
    });

    test('exact match answered fast grades Easy', () {
      final r = checker.check(
        userInput: 'answer',
        expected: 'answer',
        elapsedMs: 1200,
      );
      expect(r.rating, Rating.easy);
    });

    test('case/whitespace differences still count as exact match', () {
      final r = checker.check(userInput: '  Answer  ', expected: 'answer');
      expect(r.verdict, AnswerVerdict.correct);
    });

    test('single-letter typo on a long word (>4 chars) grades Hard, not Again', () {
      // "answar" is one substitution (e -> a) away from "answer".
      final r = checker.check(userInput: 'answar', expected: 'answer');
      expect(r.verdict, AnswerVerdict.almostTypo);
      expect(r.rating, Rating.hard);
    });

    test('single-letter typo on a short word (<=4 chars) does NOT get typo tolerance', () {
      // "cot" is Levenshtein distance 1 from "cat" but "cat" is only 3
      // chars (<=4), so the typo-tolerance gate must not apply.
      final r = checker.check(userInput: 'cot', expected: 'cat');
      expect(r.verdict, AnswerVerdict.wrong);
      expect(r.rating, Rating.again);
    });

    test('distance-2 typo on a long word is graded wrong, not almost', () {
      final r = checker.check(userInput: 'anwr', expected: 'answer');
      expect(r.verdict, AnswerVerdict.wrong);
      expect(r.rating, Rating.again);
    });

    test('completely wrong answer grades Again', () {
      final r = checker.check(userInput: 'banana', expected: 'answer');
      expect(r.rating, Rating.again);
    });
  });

  group('AnswerChecker.capForHint', () {
    test('hint usage caps a correct Good/Easy down to Hard', () {
      expect(checker.capForHint(Rating.easy, usedHint: true), Rating.hard);
      expect(checker.capForHint(Rating.good, usedHint: true), Rating.hard);
    });

    test('hint usage does not upgrade an Again into Hard', () {
      expect(checker.capForHint(Rating.again, usedHint: true), Rating.again);
    });

    test('no hint used leaves rating untouched', () {
      expect(checker.capForHint(Rating.easy, usedHint: false), Rating.easy);
    });
  });
}
