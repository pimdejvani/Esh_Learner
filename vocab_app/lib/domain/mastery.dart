/// Full-mastery "You Pass" condition (product decision 2026-07-23): the
/// player passes the whole app once **every word has been answered
/// correctly at least once in every game type** (rating hard/good/easy —
/// anything but Again — counts as a pass; derived from `reviews_log`).
/// When the condition first becomes true, play_screen shows the
/// full-screen YouPassPage exactly once (persisted via the
/// `you_pass_shown` setting).
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
