/// Abstract data-store interface (pattern borrowed from Gymmer_App's
/// WorkoutStore: abstract interface + sqlite impl + memory impl for
/// tests/dev). All reads/writes the app needs go through here so screens
/// and domain code never touch SQL directly.
library;

import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';

class VocabStoreState {
  const VocabStoreState({
    required this.words,
    required this.srsStates,
    required this.settings,
  });

  final List<Word> words;
  final Map<int, SrsState> srsStates; // wordId -> state
  final Map<String, String> settings;
}

abstract class VocabStore {
  /// Loads everything needed to boot the session engine: all words + their
  /// current SRS state + settings (new_card_cap, request_retention, ...).
  Future<VocabStoreState> load();

  /// Full bundle (senses/forms/sentences/related) for one word, used by
  /// intro cards, games, and the entry view.
  Future<WordBundle> loadWordBundle(int wordId);

  /// Bulk-load bundles (used by batch games like Matching).
  Future<List<WordBundle>> loadWordBundles(List<int> wordIds);

  Future<void> upsertSrsState(SrsState state);

  Future<void> logReview(ReviewLogEntry entry);

  Future<List<ReviewLogEntry>> loadRecentReviews({required DateTime since});

  /// Distinct (word, game) pairs answered correctly (rating != again)
  /// **in a mastery game** (domain/mastery.dart kMasteryGames: flashcard/
  /// matching/cloze/dictation) **since the most recent mastery-game Again
  /// anywhere**, as `"$wordId:$gameType"` strings — the "You Pass" clean-
  /// round grid. One wrong answer in a mastery game resets the entire
  /// grid; non-mastery games neither fill cells nor reset.
  Future<Set<String>> loadPassedWordGamePairs();

  /// Per-word current consecutive-correct streak: how many reviews the
  /// word has passed since its most recent Again (0 / absent = none or
  /// just lapsed). Used to progressively down-weight already-solid words
  /// in the extra-practice loop so post-lapse grinding doesn't waste time
  /// re-showing easy words (session_engine's weighted practice sample).
  Future<Map<int, int>> loadCorrectStreaks();

  Future<void> saveSetting(String key, String value);

  Future<DailyStats?> loadDailyStats(String date);

  Future<void> upsertDailyStats(DailyStats stats);

  /// date -> streak_kept, for the heatmap/streak widgets.
  Future<Map<String, DailyStats>> loadDailyStatsRange(
    DateTime from,
    DateTime to,
  );

  /// All rows in `topics` (SPEC.md section 4). Empty until the content
  /// pipeline populates it — callers must handle that gracefully (e.g. hide
  /// the focus-topic picker) rather than assume it's non-empty.
  Future<List<Topic>> loadTopics();

  /// Word ids in `word_topics` for one topic — used to bias new-word
  /// selection toward a user's chosen focus topic (SPEC.md 6.4).
  Future<Set<int>> loadWordIdsForTopic(int topicId);

  /// Every `related_words` row, keyed by `word_id` — used by Odd One Out
  /// (SPEC.md game 6) to find category "hub" words across the whole pool,
  /// not just the one word currently being tested.
  Future<Map<int, List<RelatedWord>>> loadAllRelatedWords();

  /// Every `relation_groups` row with its members. Odd One Out builds a round
  /// from one of these and explains the answer with the group's stored
  /// category and reason instead of inventing one after the fact.
  Future<List<RelationGroup>> loadRelationGroups();

  /// Ids of words that have senses under two or more parts of speech.
  /// Used only by the temporary multi-POS Flashcard hook
  /// (`domain/test_hooks.dart`) — delete with it.
  Future<Set<int>> loadMultiPosWordIds();

  /// `content_meta` as a plain map: content_version, built_at, licenses.
  /// The Credits page reads attribution from here instead of from per-word
  /// columns, because licensing applies to the whole content build.
  Future<Map<String, String>> loadContentMeta();

  Future<void> close();
}
