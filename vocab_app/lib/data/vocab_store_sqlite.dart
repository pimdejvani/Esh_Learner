/// SQLite implementation of [VocabStore] (production). On first launch,
/// copies the bundled read-only content seed (assets/seed/vocab.db) into
/// the app's writable documents directory, then layers app-state tables
/// (srs_state, reviews_log, daily_stats, settings) on top via numbered
/// migrations. Pattern borrowed from Gymmer_App's workout_store_sqlite.dart.
library;

import 'dart:io';

import 'package:flutter/services.dart' show rootBundle;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'migrations/migration_runner.dart';
import 'vocab_store.dart';

class VocabStoreSqlite implements VocabStore {
  VocabStoreSqlite._(this._db);

  final Database _db;

  static Future<VocabStoreSqlite> open({String dbFileName = 'vocab.db'}) async {
    final docsDir = await getApplicationDocumentsDirectory();
    final dbPath = p.join(docsDir.path, dbFileName);

    if (!await File(dbPath).exists()) {
      final bytes = await rootBundle.load('assets/seed/vocab.db');
      await File(
        dbPath,
      ).writeAsBytes(bytes.buffer.asUint8List(), flush: true);
    }

    final db = await openDatabase(dbPath);
    await runMigrations(db);
    return VocabStoreSqlite._(db);
  }

  @override
  Future<VocabStoreState> load() async {
    final wordRows = await _db.query('words', orderBy: 'freq_rank ASC');
    final words = wordRows.map(Word.fromMap).toList();

    final srsRows = await _db.query('srs_state');
    final srsStates = {
      for (final r in srsRows) r['word_id'] as int: SrsState.fromMap(r),
    };

    final settingRows = await _db.query('settings');
    final settings = {
      for (final r in settingRows)
        r['key'] as String: (r['value'] as String?) ?? '',
    };

    return VocabStoreState(
      words: words,
      srsStates: srsStates,
      settings: settings,
    );
  }

  @override
  Future<WordBundle> loadWordBundle(int wordId) async {
    final bundles = await loadWordBundles([wordId]);
    return bundles.first;
  }

  @override
  Future<List<WordBundle>> loadWordBundles(List<int> wordIds) async {
    if (wordIds.isEmpty) return [];
    final placeholders = List.filled(wordIds.length, '?').join(',');

    final wordRows = await _db.query(
      'words',
      where: 'id IN ($placeholders)',
      whereArgs: wordIds,
    );
    final wordsById = {
      for (final r in wordRows) r['id'] as int: Word.fromMap(r),
    };

    // All senses (not just is_core) so the full dictionary entry (word_
    // detail_page, SPEC.md 9b layer 2) can group every sense by POS. The
    // core sense used by games/layer-1 is derived from this same list
    // instead of a second query.
    final senseRows = await _db.query(
      'senses',
      where: 'word_id IN ($placeholders)',
      whereArgs: wordIds,
      orderBy: 'sense_rank ASC',
    );
    final sensesByWord = <int, List<Sense>>{};
    for (final r in senseRows) {
      final s = Sense.fromMap(r);
      sensesByWord.putIfAbsent(s.wordId, () => []).add(s);
    }
    final coreSenseByWord = {
      for (final entry in sensesByWord.entries)
        entry.key: entry.value.firstWhere(
          (s) => s.isCore,
          orElse: () => entry.value.first,
        ),
    };

    final formRows = await _db.query(
      'word_forms',
      where: 'word_id IN ($placeholders)',
      whereArgs: wordIds,
    );
    final formsByWord = <int, List<WordForm>>{};
    for (final r in formRows) {
      final f = WordForm.fromMap(r);
      formsByWord.putIfAbsent(f.wordId, () => []).add(f);
    }

    final sentRows = await _db.query(
      'example_sentences',
      where: 'word_id IN ($placeholders)',
      whereArgs: wordIds,
      orderBy: 'rank ASC',
    );
    final sentByWord = <int, List<ExampleSentence>>{};
    for (final r in sentRows) {
      final s = ExampleSentence.fromMap(r);
      sentByWord.putIfAbsent(s.wordId, () => []).add(s);
    }

    final relRows = await _db.query(
      'related_words',
      where: 'word_id IN ($placeholders)',
      whereArgs: wordIds,
    );
    final relByWord = <int, List<RelatedWord>>{};
    for (final r in relRows) {
      final rel = RelatedWord.fromMap(r);
      relByWord.putIfAbsent(rel.wordId, () => []).add(rel);
    }

    return wordIds.where(wordsById.containsKey).map((id) {
      return WordBundle(
        word: wordsById[id]!,
        coreSense: coreSenseByWord[id]!,
        senses: sensesByWord[id] ?? [],
        forms: formsByWord[id] ?? [],
        sentences: sentByWord[id] ?? [],
        related: relByWord[id] ?? [],
      );
    }).toList();
  }

  @override
  Future<void> upsertSrsState(SrsState state) async {
    await _db.insert(
      'srs_state',
      state.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  @override
  Future<void> logReview(ReviewLogEntry entry) async {
    await _db.insert('reviews_log', entry.toMap());
  }

  @override
  Future<List<ReviewLogEntry>> loadRecentReviews({required DateTime since}) async {
    final rows = await _db.query(
      'reviews_log',
      where: 'ts >= ?',
      whereArgs: [since.millisecondsSinceEpoch],
      orderBy: 'ts ASC',
    );
    return rows.map(ReviewLogEntry.fromMap).toList();
  }

  @override
  Future<Set<String>> loadPassedWordGamePairs() async {
    // Only correct answers AFTER the word's latest Again count — one
    // wrong answer resets that word's whole row of the mastery grid.
    final rows = await _db.rawQuery(
      "SELECT DISTINCT r.word_id, r.game_type FROM reviews_log r "
      "WHERE r.rating != 'again' AND r.ts > COALESCE("
      "  (SELECT MAX(l.ts) FROM reviews_log l "
      "   WHERE l.word_id = r.word_id AND l.rating = 'again'), -1)",
    );
    return {
      for (final r in rows) '${r['word_id']}:${r['game_type']}',
    };
  }

  @override
  Future<Map<int, int>> loadCorrectStreaks() async {
    final rows = await _db.rawQuery(
      "SELECT r.word_id, COUNT(*) AS streak FROM reviews_log r "
      "WHERE r.rating != 'again' AND r.ts > COALESCE("
      "  (SELECT MAX(l.ts) FROM reviews_log l "
      "   WHERE l.word_id = r.word_id AND l.rating = 'again'), -1) "
      "GROUP BY r.word_id",
    );
    return {
      for (final r in rows) r['word_id'] as int: r['streak'] as int,
    };
  }

  @override
  Future<void> saveSetting(String key, String value) async {
    await _db.insert('settings', {
      'key': key,
      'value': value,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  @override
  Future<DailyStats?> loadDailyStats(String date) async {
    final rows = await _db.query(
      'daily_stats',
      where: 'date = ?',
      whereArgs: [date],
    );
    if (rows.isEmpty) return null;
    return DailyStats.fromMap(rows.first);
  }

  @override
  Future<void> upsertDailyStats(DailyStats stats) async {
    await _db.insert(
      'daily_stats',
      stats.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  @override
  Future<Map<String, DailyStats>> loadDailyStatsRange(
    DateTime from,
    DateTime to,
  ) async {
    String fmt(DateTime d) =>
        '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    final rows = await _db.query(
      'daily_stats',
      where: 'date >= ? AND date <= ?',
      whereArgs: [fmt(from), fmt(to)],
    );
    return {
      for (final r in rows) r['date'] as String: DailyStats.fromMap(r),
    };
  }

  @override
  Future<List<Topic>> loadTopics() async {
    final rows = await _db.query('topics', orderBy: 'id ASC');
    return rows.map(Topic.fromMap).toList();
  }

  @override
  Future<Set<int>> loadWordIdsForTopic(int topicId) async {
    final rows = await _db.query(
      'word_topics',
      columns: ['word_id'],
      where: 'topic_id = ?',
      whereArgs: [topicId],
    );
    return rows.map((r) => r['word_id'] as int).toSet();
  }

  @override
  Future<Map<int, List<RelatedWord>>> loadAllRelatedWords() async {
    final rows = await _db.query('related_words');
    final map = <int, List<RelatedWord>>{};
    for (final r in rows) {
      final rel = RelatedWord.fromMap(r);
      map.putIfAbsent(rel.wordId, () => []).add(rel);
    }
    return map;
  }

  @override
  Future<void> close() => _db.close();
}
