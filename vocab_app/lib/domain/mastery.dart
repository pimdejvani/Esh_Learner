/// Full-mastery "You Pass" condition (product decision 2026-07-23): the
/// player passes the whole app by completing **one clean round** — every
/// word answered correctly in every game in [kMasteryGames] **with zero
/// wrong answers in those games anywhere in between**. One Again on ANY
/// word *in a mastery game* resets the ENTIRE grid (all words, all
/// mastery games) and the round starts over; the counting exists purely
/// to finish that single flawless round. Rating hard/good/easy counts as
/// a pass. Non-mastery games are exempt both ways: no cells, no resets —
/// they only feed streaks. The stores' `loadPassedWordGamePairs()`
/// implements the reset by only counting mastery-game passes after the
/// latest mastery-game Again in `reviews_log`. When the condition first
/// becomes true, play_screen shows the full-screen YouPassPage exactly
/// once (persisted via the `you_pass_shown` setting). The practice loop
/// softens the grind: slots target still-missing cells, and per-word
/// streak weighting (session_engine's `practiceWeight`) keeps
/// already-solid words from hogging rounds after a reset.
library;

import 'package:vocab_app/domain/session_engine.dart';
import 'package:vocab_app/models/word.dart';

/// The games that count toward the "You Pass" grid (product decision
/// 2026-07-23): only the four "serious" games where the answer is an
/// unambiguous right/wrong. The other three (Odd One Out, Word
/// Association, Word Scramble) stay in the play rotation but only feed
/// the per-word streak used for practice weighting — their passes don't
/// fill grid cells and their misses don't reset the round.
const List<GameType> kMasteryGames = [
  GameType.flashcard,
  GameType.matching,
  GameType.cloze,
  GameType.dictation,
];

/// [kMasteryGames] as the `GameType.name` strings `reviews_log.game_type`
/// stores — for the store implementations' SQL/log filtering.
final Set<String> kMasteryGameNames = {
  for (final g in kMasteryGames) g.name,
};

/// Canonical key for one (word, game) cell of the mastery grid. Matches
/// the format the stores' `loadPassedWordGamePairs()` implementations
/// emit: `"$wordId:$gameTypeName"` with [GameType.name] strings (the same
/// strings `reviews_log.game_type` stores).
String masteryKey(int wordId, String gameType) => '$wordId:$gameType';

/// True when every word in [words] has a passed cell for every game in
/// [kMasteryGames].
bool fullMasteryReached({
  required List<Word> words,
  required Set<String> passedPairs,
}) {
  for (final w in words) {
    for (final g in kMasteryGames) {
      if (!passedPairs.contains(masteryKey(w.id, g.name))) return false;
    }
  }
  return true;
}

/// (passed cells, total cells) across the words × mastery-games grid —
/// for showing progress toward the You Pass screen.
(int, int) masteryProgress({
  required List<Word> words,
  required Set<String> passedPairs,
}) {
  var passed = 0;
  for (final w in words) {
    for (final g in kMasteryGames) {
      if (passedPairs.contains(masteryKey(w.id, g.name))) passed++;
    }
  }
  return (passed, words.length * kMasteryGames.length);
}
