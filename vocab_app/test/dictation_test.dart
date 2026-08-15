import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/domain/hint_ladder.dart';
import 'package:vocab_app/models/srs_state.dart';

void main() {
  group('buildHintLadder (unified typed-game ladder, item 12)', () {
    test('full ladder order: count, similar, first letter, meaning, '
        'first & last', () {
      final ladder = buildHintLadder(
        target: 'travel',
        meaningTh: 'เดินทาง',
        similarKnownWord: 'trip',
      );
      expect(ladder.length, 5);
      expect(ladder[0], '6 letters');
      expect(ladder[1], contains('trip'));
      expect(ladder[2], startsWith('Starts with:'));
      expect(ladder[2], contains('t'));
      expect(ladder[3], contains('เดินทาง'));
      expect(ladder[4], contains('t')); // first
      expect(ladder[4], contains('l')); // and last
    });

    test('drops the similar-word step when none is known', () {
      final ladder = buildHintLadder(target: 'cat', meaningTh: 'แมว');
      expect(ladder.length, 4); // no step 2
      expect(ladder.any((s) => s.startsWith('Similar')), isFalse);
      expect(ladder.first, '3 letters');
    });

    test('dictation drops the translation step entirely', () {
      final ladder = buildHintLadder(
        target: 'light',
        meaningTh: 'แสง',
        similarKnownWord: 'lamp',
        includeMeaning: false,
      );
      expect(ladder.any((s) => s.contains('แสง')), isFalse);
      expect(ladder.any((s) => s.startsWith('Meaning')), isFalse);
      expect(ladder[0], '5 letters');
      expect(ladder[1], contains('lamp'));
    });

    test('a single-letter word has no first-and-last step', () {
      final ladder = buildHintLadder(target: 'a', meaningTh: 'x');
      expect(ladder.any((s) => s.startsWith('First & last')), isFalse);
    });

    test('an empty target yields no hints', () {
      expect(buildHintLadder(target: '', meaningTh: 'x'), isEmpty);
    });
  });

  group('answer checking + hint-usage cap (family B)', () {
    const checker = AnswerChecker();

    test('typing the exact word back fast grades Easy', () {
      final result = checker.check(userInput: 'travel', expected: 'travel', elapsedMs: 800);
      expect(result.verdict, AnswerVerdict.correct);
      expect(result.rating, Rating.easy);
    });

    test('a genuine single-substitution spelling slip grades Hard, not Again', () {
      // "trabel" is one substitution (v -> b) away from "travel".
      final result = checker.check(userInput: 'trabel', expected: 'travel');
      expect(result.verdict, AnswerVerdict.almostTypo);
      expect(result.rating, Rating.hard);
    });

    test('using any hint stage caps a correct answer at Hard', () {
      final result = checker.check(userInput: 'travel', expected: 'travel', elapsedMs: 500);
      expect(result.rating, Rating.easy);
      expect(checker.capForHint(result.rating, usedHint: true), Rating.hard);
    });

    test('a wrong answer stays Again even with a hint used', () {
      final result = checker.check(userInput: 'xyz', expected: 'travel');
      expect(result.rating, Rating.again);
      expect(checker.capForHint(result.rating, usedHint: true), Rating.again);
    });

    test('no hint used leaves a correct answer uncapped', () {
      final result = checker.check(userInput: 'travel', expected: 'travel', elapsedMs: 500);
      expect(checker.capForHint(result.rating, usedHint: false), Rating.easy);
    });
  });
}
