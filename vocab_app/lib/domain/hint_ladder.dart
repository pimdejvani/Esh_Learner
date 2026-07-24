/// Unified progressive hint ladder for the typed-answer games — Dictation,
/// Cloze, Word Scramble (user request 2026-07-24, item 12). Replaces the
/// old per-game hint schemes with one fixed sequence, revealed one step at
/// a time (and, as with every hint, using ANY step caps the rating at Hard
/// via answer_checker.capForHint):
///
///   1. letter count
///   2. the closest meaning-related word the player already knows
///      (omitted when there is no known related word yet)
///   3. first letter
///   4. the Thai meaning
///   5. first AND last letter
///
/// …and no further hints beyond that ("จะไม่ใบ้ไปมากกว่านี้").
///
/// Kept as a pure function so it's unit-testable without a widget. [target]
/// is the exact string the player must type (headword, or the cloze
/// target's inflected form); [meaningTh] is the Thai gloss shown at step 4;
/// [similarKnownWord] is the step-2 clue (null/empty → that step is
/// dropped). Labels are English chrome (item 5); the meaning stays Thai
/// because it is content, not chrome.
List<String> buildHintLadder({
  required String target,
  required String meaningTh,
  String? similarKnownWord,
}) {
  final n = target.length;
  if (n == 0) return const [];
  final stages = <String>['$n letters'];
  if (similarKnownWord != null && similarKnownWord.trim().isNotEmpty) {
    stages.add('Similar word you know: ${similarKnownWord.trim()}');
  }
  stages.add('Starts with:  ${target[0]}${'·' * (n - 1)}');
  stages.add('Meaning:  $meaningTh');
  if (n > 1) {
    stages.add(
      'First & last:  ${target[0]}${'·' * (n - 2)}${target[n - 1]}',
    );
  }
  return stages;
}
