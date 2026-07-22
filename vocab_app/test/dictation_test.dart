import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/games/dictation.dart';
import 'package:vocab_app/models/srs_state.dart';

void main() {
  group('DictationHint.syllableSkeleton', () {
    test('derives syllable count from thai_reading hyphen splits', () {
      final syllables = DictationHint.syllableSkeleton('answer', 'แอน-เซอร์');
      expect(syllables.length, 2);
      expect(syllables.join().length, 'answer'.length);
    });

    test('falls back to a single chunk when thai_reading has no hyphens', () {
      final syllables = DictationHint.syllableSkeleton('cat', 'แคท');
      expect(syllables, ['cat']);
    });

    test('clamps syllable count to the headword length (never more chunks than letters)', () {
      final syllables = DictationHint.syllableSkeleton('go', 'จี-โอ-เอ็กซ์-ทรา');
      expect(syllables.length, lessThanOrEqualTo('go'.length));
    });
  });

  group('DictationHint.stageText progressive reveal', () {
    const headword = 'travel';
    const thaiReading = 'แทร-เวิล';

    test('stage 0 (or below) shows nothing', () {
      expect(DictationHint.stageText(headword, thaiReading, 0), '');
      expect(DictationHint.stageText(headword, thaiReading, -1), '');
    });

    test('stage 1 is a syllable-boundary skeleton with letters hidden', () {
      final text = DictationHint.stageText(headword, thaiReading, 1);
      expect(text, contains('-'));
      expect(text.replaceAll('-', ''), '_' * headword.length);
    });

    test('stage 2 reveals exactly the first letter', () {
      final text = DictationHint.stageText(headword, thaiReading, 2);
      expect(text, 't${'_' * (headword.length - 1)}');
    });

    test('each later stage reveals one more letter than the last', () {
      final stage3 = DictationHint.stageText(headword, thaiReading, 3);
      final stage4 = DictationHint.stageText(headword, thaiReading, 4);
      expect(stage3, 'tr${'_' * (headword.length - 2)}');
      expect(stage4, 'tra${'_' * (headword.length - 3)}');
    });

    test('once every letter is revealed, the final stage falls back to a letter count', () {
      final max = DictationHint.maxStage(headword);
      final text = DictationHint.stageText(headword, thaiReading, max);
      expect(text, '${headword.length} ตัวอักษร');
    });

    test('maxStage is letters + 2 (syllable stage + one per letter + count stage)', () {
      expect(DictationHint.maxStage(headword), headword.length + 2);
    });

    test('an empty headword never crashes and yields no hint text', () {
      expect(DictationHint.stageText('', '', 1), '');
      expect(DictationHint.maxStage(''), 1);
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
