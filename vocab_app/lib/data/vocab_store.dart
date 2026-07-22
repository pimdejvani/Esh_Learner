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

  Future<void> saveSetting(String key, String value);

  Future<DailyStats?> loadDailyStats(String date);

  Future<void> upsertDailyStats(DailyStats stats);

  /// date -> streak_kept, for the heatmap/streak widgets.
  Future<Map<String, DailyStats>> loadDailyStatsRange(
    DateTime from,
    DateTime to,
  );

  Future<void> close();
}
