/// Full-mastery "You Pass" condition (product decision 2026-07-23): the
/// player passes the whole app by completing **one clean round** — every
/// word answered correctly in every game type **with zero wrong answers
/// anywhere in between**. One Again on ANY word resets the ENTIRE grid
/// (all words, all games) and the round starts over; the counting exists
/// purely to finish that single flawless round. Rating hard/good/easy
/// counts as a pass. The stores' `loadPassedWordGamePairs()` implements
/// the reset by only counting passes after the latest Again anywhere in
/// `reviews_log`. When the condition first becomes true, play_screen
/// shows the full-screen YouPassPage exactly once (persisted via the
/// `you_pass_shown` setting). The practice loop softens the grind: slots
/// target still-missing cells, and per-word streak weighting
/// (session_engine's `practiceWeight`) keeps already-solid words from
/// hogging rounds after a reset.
library;

import 'package:vocab_app/domain/session_engine.dart';
import 'package:vocab_app/models/word.dart';

/// Canonical key for one (word, game) cell of the mastery grid. Matches
/// the format the stores' `loadPassedWordGamePairs()` implementations
/// emit: `"$wordId:$gameTypeName"` with [GameType.name] strings (the same
/// strings `reviews_log.game_type` stores).
String masteryKey(int wordId, String gameType) => '$wordId:$gameType';

/// True when every word in [words] has a passed cell for every [GameType].
bool fullMasteryReached({
  required List<Word> words,
  required Set<String> passedPairs,
}) {
  for (final w in words) {
    for (final g in GameType.values) {
      if (!passedPairs.contains(masteryKey(w.id, g.name))) return false;
    }
  }
  return true;
}

/// (passed cells, total cells) across the whole words × games grid — for
/// showing progress toward the You Pass screen.
(int, int) masteryProgress({
  required List<Word> words,
  required Set<String> passedPairs,
}) {
  var passed = 0;
  for (final w in words) {
    for (final g in GameType.values) {
      if (passedPairs.contains(masteryKey(w.id, g.name))) passed++;
    }
  }
  return (passed, words.length * GameType.values.length);
}
