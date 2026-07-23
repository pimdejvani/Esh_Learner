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

  /// Distinct (word, game) pairs ever answered correctly (rating !=
  /// again), as `"$wordId:$gameType"` strings — the mastery grid behind
  /// the "You Pass" screen (domain/mastery.dart).
  Future<Set<String>> loadPassedWordGamePairs();

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

  Future<void> close();
}
