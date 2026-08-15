/// Temporary scaffolding for building content, not app behaviour.
///
/// **Delete this file and its call sites before the app ships.** It exists
/// because the Flashcard back has to render several parts of speech correctly
/// while the content is still being written, and waiting for a multi-POS word
/// to come up naturally makes that impossible to check on every run
/// (`after_revocab.md` item 7).
///
/// Forcing a word into the queue distorts the FSRS due-order and the new-card
/// governor, so it must never reach real learners. It is compiled out of
/// release builds by [kForceMultiPosFlashcard] and the seed that ships to users
/// is exported without the hard test words at all
/// (`tools/export_app_seed.py`, no `--include-test-words`).
library;

import 'package:flutter/foundation.dart' show kDebugMode;

/// Puts one word with two or more parts of speech at the front of every
/// session, as a Flashcard. Debug builds only.
const bool kForceMultiPosFlashcard = kDebugMode;
