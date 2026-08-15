// Integration test against the real bundled seed (via sqflite_ffi, since plain
// `flutter test` runs on the Dart VM without a platform sqflite plugin). It
// checks the shape the app depends on — content schema v2 built by
// tools/build_content_db.py and exported by tools/export_app_seed.py — plus the
// content-version reseed that keeps a player's progress across a content update.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:vocab_app/data/content_reseed.dart';
import 'package:vocab_app/data/migrations/migration_runner.dart';

const String kSeedPath = 'assets/seed/vocab.db';

Future<String> copySeed(String label) async {
  final path =
      '${Directory.systemTemp.path}/vocab_${label}_${DateTime.now().microsecondsSinceEpoch}.db';
  await File(kSeedPath).copy(path);
  return path;
}

void main() {
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;

  setUpAll(() {
    expect(File(kSeedPath).existsSync(), isTrue,
        reason: 'run tools/build_content_db.py then tools/export_app_seed.py');
  });

  test('seed carries content schema v2 with per-sense examples and relations',
      () async {
    final path = await copySeed('seed');
    final db = await databaseFactory.openDatabase(path);

    final version = await db.query('content_meta',
        where: 'key = ?', whereArgs: ['content_version']);
    expect(version.single['value'], '2');

    final words = await db.query('words');
    expect(words.length, greaterThanOrEqualTo(100));

    // Several senses per word, each under a part of speech — the whole point
    // of v2, and what the Flashcard back and Dictionary render.
    final senses = await db.query('senses');
    expect(senses.length, greaterThan(words.length));
    final multiPos = await db.rawQuery(
      'SELECT word_id FROM senses GROUP BY word_id HAVING COUNT(DISTINCT pos) >= 2',
    );
    expect(multiPos.length, greaterThanOrEqualTo(10));

    // Five examples per word, every one tied to a sense and carrying its own
    // standalone explanation.
    final sentences = await db.query('example_sentences');
    expect(sentences.length, words.length * 5);
    final orphaned = await db.rawQuery(
      'SELECT e.id FROM example_sentences e '
      'LEFT JOIN senses s ON s.id = e.sense_id WHERE s.id IS NULL',
    );
    expect(orphaned, isEmpty);
    final unexplained = await db.rawQuery(
      "SELECT id FROM example_sentences WHERE trim(explanation_th) = ''",
    );
    expect(unexplained, isEmpty);

    // Forms are split into the two kinds a learner needs kept apart.
    final formTypes = await db.rawQuery(
      'SELECT DISTINCT form_type FROM word_forms ORDER BY form_type',
    );
    expect(formTypes.map((r) => r['form_type']), ['derived', 'inflection']);

    // Odd One Out reads its reason from the group it built the round from.
    final groups = await db.query('relation_groups');
    expect(groups.length, greaterThanOrEqualTo(3));
    final unexplainedGroups = await db.rawQuery(
      "SELECT id FROM relation_groups WHERE trim(explanation_th) = ''",
    );
    expect(unexplainedGroups, isEmpty);

    await db.close();
    await File(path).delete();
  });

  test('seed contains no player tables and migrations add them', () async {
    final path = await copySeed('migrate');
    final db = await databaseFactory.openDatabase(path);

    final tables = (await db.rawQuery(
      "SELECT name FROM sqlite_master WHERE type='table'",
    )).map((r) => r['name'] as String).toSet();
    expect(tables.intersection(kUserTables.toSet()), isEmpty,
        reason: 'the seed must ship content only');

    await runMigrations(db);
    expect(await db.query('srs_state'), isEmpty);
    await db.insert('settings', {'key': 'new_card_cap', 'value': '8'});
    expect((await db.query('settings')).single['value'], '8');

    await db.close();
    await File(path).delete();
  });

  test('reseed keeps the player rows and remaps them by headword', () async {
    // Stand in for an older install: same content, but version 1 and with the
    // player's own rows already in the file.
    final installed = await copySeed('installed');
    final old = await databaseFactory.openDatabase(installed);
    await runMigrations(old);
    await old.update('content_meta', {'value': '1'},
        where: 'key = ?', whereArgs: ['content_version']);
    final word = (await old.query('words', limit: 1)).single;
    final wordId = word['id'] as int;
    final headword = word['headword'] as String;
    // Give one word a review history, and point one row at a word id that the
    // new content will not contain.
    await old.insert('srs_state', {
      'word_id': wordId,
      'state': 'review',
      'stability': 12.5,
      'difficulty': 5.0,
      'due_at': 1234567890,
      'reps': 3,
      'lapses': 1,
    });
    await old.insert('reviews_log', {
      'word_id': wordId,
      'ts': 1234567890,
      'rating': 'good',
      'game_type': 'flashcard',
      'direction': 'en_th',
    });
    await old.insert('srs_state', {
      'word_id': 999999,
      'state': 'new',
      'stability': 0,
      'difficulty': 0,
      'due_at': 0,
    });
    await old.insert('settings', {'key': 'new_card_cap', 'value': '6'});
    await old.close();

    final outcome = await reseedIfNeeded(
      installed,
      writeSeed: (path) async => File(kSeedPath).copy(path).then((_) {}),
    );
    expect(outcome.reseeded, isTrue);
    expect(outcome.fromVersion, 1);
    expect(outcome.toVersion, 2);
    expect(outcome.rowsDropped, 1, reason: 'the unknown word cannot be kept');

    final fresh = await databaseFactory.openDatabase(installed);
    final newWordId = (await fresh.query('words',
            where: 'lower(headword) = ?', whereArgs: [headword.toLowerCase()]))
        .single['id'] as int;
    final srs = await fresh.query('srs_state');
    expect(srs.length, 1);
    expect(srs.single['word_id'], newWordId);
    expect(srs.single['stability'], 12.5);
    expect((await fresh.query('reviews_log')).single['word_id'], newWordId);
    expect((await fresh.query('settings')).single['value'], '6');
    expect(
      (await fresh.query('content_meta',
              where: 'key = ?', whereArgs: ['content_version']))
          .single['value'],
      '2',
    );

    await fresh.close();
    await File(installed).delete();
  });

  test('reseed does nothing when the installed content is current', () async {
    final installed = await copySeed('current');
    final db = await databaseFactory.openDatabase(installed);
    await runMigrations(db);
    await db.close();

    final outcome = await reseedIfNeeded(
      installed,
      writeSeed: (path) async => File(kSeedPath).copy(path).then((_) {}),
    );
    expect(outcome.reseeded, isFalse);
    expect(File('$installed.reseed').existsSync(), isFalse);

    await File(installed).delete();
  });
}
