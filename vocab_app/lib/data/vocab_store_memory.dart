/// In-memory implementation of [VocabStore] — used by widget/unit tests and
/// for quick dev iteration without touching sqflite. Pattern borrowed from
/// Gymmer_App's workout_store_memory.dart.
library;

import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'vocab_store.dart';

class VocabStoreMemory implements VocabStore {
  VocabStoreMemory({
    List<Word> words = const [],
    Map<int, List<Sense>> senses = const {},
    Map<int, List<WordForm>> forms = const {},
    Map<int, List<ExampleSentence>> sentences = const {},
    Map<int, List<RelatedWord>> related = const {},
    Map<String, String>? settings,
    List<Topic> topics = const [],
    Map<int, Set<int>> topicWordIds = const {},
  }) : _words = List.of(words),
       _senses = Map.of(senses),
       _forms = Map.of(forms),
       _sentences = Map.of(sentences),
       _related = Map.of(related),
       _settings = settings ?? {},
       _topics = List.of(topics),
       _topicWordIds = Map.of(topicWordIds);

  final List<Word> _words;
  final Map<int, List<Sense>> _senses;
  final Map<int, List<WordForm>> _forms;
  final Map<int, List<ExampleSentence>> _sentences;
  final Map<int, List<RelatedWord>> _related;
  final Map<int, SrsState> _srsStates = {};
  final List<ReviewLogEntry> _reviewLog = [];
  final Map<String, String> _settings;
  final Map<String, DailyStats> _dailyStats = {};
  final List<Topic> _topics;
  final Map<int, Set<int>> _topicWordIds;
  int _reviewIdCounter = 1;

  @override
  Future<VocabStoreState> load() async => VocabStoreState(
    words: List.of(_words),
    srsStates: Map.of(_srsStates),
    settings: Map.of(_settings),
  );

  @override
  Future<WordBundle> loadWordBundle(int wordId) async =>
      (await loadWordBundles([wordId])).first;

  @override
  Future<List<WordBundle>> loadWordBundles(List<int> wordIds) async {
    final byId = {for (final w in _words) w.id: w};
    return wordIds.where(byId.containsKey).map((id) {
      final senseList = _senses[id] ?? [];
      final core = senseList.firstWhere(
        (s) => s.isCore,
        orElse: () => senseList.first,
      );
      return WordBundle(
        word: byId[id]!,
        coreSense: core,
        senses: senseList,
        forms: _forms[id] ?? [],
        sentences: _sentences[id] ?? [],
        related: _related[id] ?? [],
      );
    }).toList();
  }

  @override
  Future<void> upsertSrsState(SrsState state) async {
    _srsStates[state.wordId] = state;
  }

  @override
  Future<void> logReview(ReviewLogEntry entry) async {
    _reviewLog.add(
      ReviewLogEntry(
        id: _reviewIdCounter++,
        wordId: entry.wordId,
        ts: entry.ts,
        rating: entry.rating,
        gameType: entry.gameType,
        direction: entry.direction,
        elapsedMs: entry.elapsedMs,
      ),
    );
  }

  @override
  Future<List<ReviewLogEntry>> loadRecentReviews({
    required DateTime since,
  }) async => _reviewLog.where((r) => !r.ts.isBefore(since)).toList();

  @override
  Future<void> saveSetting(String key, String value) async {
    _settings[key] = value;
  }

  @override
  Future<DailyStats?> loadDailyStats(String date) async => _dailyStats[date];

  @override
  Future<void> upsertDailyStats(DailyStats stats) async {
    _dailyStats[stats.date] = stats;
  }

  @override
  Future<Map<String, DailyStats>> loadDailyStatsRange(
    DateTime from,
    DateTime to,
  ) async {
    return {
      for (final e in _dailyStats.entries)
        if (!DateTime.parse(e.key).isBefore(from) &&
            !DateTime.parse(e.key).isAfter(to))
          e.key: e.value,
    };
  }

  @override
  Future<List<Topic>> loadTopics() async => List.of(_topics);

  @override
  Future<Set<int>> loadWordIdsForTopic(int topicId) async =>
      Set.of(_topicWordIds[topicId] ?? {});

  @override
  Future<Map<int, List<RelatedWord>>> loadAllRelatedWords() async =>
      {for (final e in _related.entries) e.key: List.of(e.value)};

  @override
  Future<void> close() async {}
}
