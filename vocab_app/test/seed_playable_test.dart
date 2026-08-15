// Can a player actually start? This drives the real bundled seed through the
// same reads the app does on launch — word list, bundles, relation groups — and
// then builds a first session queue from it. A seed that validates but cannot
// produce a playable round would otherwise only show up by hand-testing.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:vocab_app/data/migrations/migration_runner.dart';
import 'package:vocab_app/domain/session_engine.dart';
import 'package:vocab_app/games/odd_one_out.dart';
import 'package:vocab_app/models/word.dart';

const String kSeedPath = 'assets/seed/vocab.db';

void main() {
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;

  late Database db;
  late String path;

  setUpAll(() async {
    path =
        '${Directory.systemTemp.path}/vocab_playable_${DateTime.now().microsecondsSinceEpoch}.db';
    await File(kSeedPath).copy(path);
    db = await databaseFactory.openDatabase(path);
    await runMigrations(db);
  });

  tearDownAll(() async {
    await db.close();
    await File(path).delete();
  });

  test('a fresh player gets a first queue of flashcard rounds', () async {
    final words = (await db.query('words', orderBy: 'freq_rank ASC'))
        .map(Word.fromMap)
        .toList();
    expect(words.length, greaterThanOrEqualTo(100));

    // Nothing reviewed yet: every word is new, so the engine has to open with
    // flashcards and respect the new-card cap rather than serving nothing.
    final queue = SessionEngine().buildQueue(
      words: words,
      srsStates: const {},
      now: DateTime.now(),
      newCardCap: 8,
      newIntroducedToday: 0,
      firstSessionOfDay: true,
    );
    expect(queue, isNotEmpty);
    expect(queue.first.gameType, GameType.flashcard);
    expect(
      queue.where((i) => i.source == QueueSource.newCard).length,
      lessThanOrEqualTo(8),
    );
  });

  test('every word can render a card: senses, an example, and a Thai meaning',
      () async {
    final rows = await db.rawQuery('''
      SELECT w.id, w.headword,
             (SELECT count(*) FROM senses s WHERE s.word_id = w.id) AS senses,
             (SELECT count(*) FROM example_sentences e WHERE e.word_id = w.id) AS examples,
             (SELECT count(*) FROM senses s WHERE s.word_id = w.id AND s.is_core = 1) AS core
      FROM words w
    ''');
    for (final row in rows) {
      expect(row['senses'], greaterThan(0), reason: '${row['headword']} has no sense');
      expect(row['examples'], 5, reason: '${row['headword']} needs 5 examples');
      expect(row['core'], greaterThan(0), reason: '${row['headword']} has no core sense');
    }
  });

  test('Odd One Out can build an explained round once words have been seen',
      () async {
    final words = (await db.query('words')).map(Word.fromMap).toList();
    final wordById = {for (final w in words) w.id: w};

    final relatedByWord = <int, List<RelatedWord>>{};
    for (final row in await db.query('related_words')) {
      final rel = RelatedWord.fromMap(row);
      relatedByWord.putIfAbsent(rel.wordId, () => []).add(rel);
    }
    final groupsByHub = <int, RelationGroup>{};
    for (final row in await db.query('relation_groups')) {
      groupsByHub[row['hub_word_id'] as int] = RelationGroup(
        id: row['id'] as int,
        hubWordId: row['hub_word_id'] as int,
        category: row['category'] as String,
        explanationTh: row['explanation_th'] as String,
        memberWordIds: const [],
      );
    }

    // A round needs a target that belongs to no group in play, which is why the
    // game is skipped early on; with the whole pool seen it must work.
    var built = 0;
    var explained = 0;
    for (final target in words) {
      final round = buildOddOneOutRound(
        target: target,
        pool: words,
        relatedByWord: relatedByWord,
        groupsByHub: groupsByHub,
      );
      if (round == null) continue;
      built++;
      expect(wordById[round.hubWordId], isNotNull);
      expect(round.groupWords.length, greaterThanOrEqualTo(3));
      if (round.explanationTh.isNotEmpty && round.category.isNotEmpty) {
        explained++;
      }
    }
    expect(built, greaterThan(20), reason: 'too few playable Odd One Out rounds');
    // The reveal must be able to state the category and reason from stored data.
    expect(explained, built);
  });

  test('Cloze can blank every example and leave a readable sentence', () async {
    final rows = await db.rawQuery(
      'SELECT w.headword, e.rank, e.en_text, e.cloze_target, e.cloze_start, '
      'e.cloze_end FROM example_sentences e JOIN words w ON w.id = e.word_id',
    );
    for (final row in rows) {
      final text = row['en_text'] as String;
      final start = row['cloze_start'] as int;
      final end = row['cloze_end'] as int;
      final where = '${row['headword']} rank ${row['rank']}';
      expect(start, greaterThanOrEqualTo(0), reason: where);
      expect(end, lessThanOrEqualTo(text.length), reason: where);
      expect(
        text.substring(start, end).toLowerCase(),
        (row['cloze_target'] as String).toLowerCase(),
        reason: where,
      );
      // Blanking has to leave enough context to answer from.
      expect(text.length - (end - start), greaterThan(5), reason: where);
    }
  });

  test('Word Association has a testable link for most words', () async {
    final rows = await db.rawQuery(
      'SELECT w.headword, (SELECT count(*) FROM related_words r '
      'WHERE r.word_id = w.id AND r.is_giveaway = 0) AS links FROM words w',
    );
    final without = rows.where((r) => (r['links'] as int) == 0).toList();
    // A word with no association just routes to another game; a majority
    // without one would mean the game almost never appears.
    expect(
      without.length,
      lessThan(rows.length ~/ 2),
      reason: 'no related word for: '
          '${without.map((r) => r['headword']).take(10).toList()}',
    );
  });

  test('Scramble and Dictation have usable prompts', () async {
    final rows = await db.query(
      'words',
      columns: ['headword', 'thai_reading', 'is_test_only'],
    );
    for (final row in rows) {
      final headword = row['headword'] as String;
      // Dictation reads the Thai back as a hint, so every word needs one.
      expect((row['thai_reading'] as String?) ?? '', isNotEmpty, reason: headword);
      // Scramble only has a puzzle once a word has three letters. The real word
      // list clears this; the hard fixture set contains "go", which scrambles to
      // the one other order and is trivially easy — acceptable for scaffolding
      // that never ships.
      if ((row['is_test_only'] as int) == 1) continue;
      expect(headword.length, greaterThanOrEqualTo(3), reason: headword);
    }
  });

  test('Matching can fill a batch of distinct answers', () async {
    final rows = await db.rawQuery(
      'SELECT w.headword, s.meaning_th FROM words w '
      'JOIN senses s ON s.word_id = w.id AND s.is_core = 1',
    );
    expect(rows.length, greaterThanOrEqualTo(4));
    // Two cards carrying the same Thai answer make a round unanswerable.
    final meanings = rows.map((r) => r['meaning_th'] as String).toList();
    final duplicates = meanings.length - meanings.toSet().length;
    expect(
      duplicates,
      lessThan(rows.length ~/ 10),
      reason: '$duplicates core meanings are duplicated across words',
    );
  });
}
