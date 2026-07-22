// Integration test: opens the actual bundled seed DB (via sqflite_ffi, since
// plain `flutter test` runs on the Dart VM without a platform sqflite
// plugin) and exercises migrations + a couple of store reads directly
// against the seed schema built by tools/build_dataset.py.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:vocab_app/data/migrations/migration_runner.dart';

void main() {
  sqfliteFfiInit();
  databaseFactory = databaseFactoryFfi;

  test('seed DB has the expected content tables and >=150 A1 words', () async {
    final seedPath = 'assets/seed/vocab.db';
    expect(File(seedPath).existsSync(), isTrue,
        reason: 'run tools/build_dataset.py first');

    // Work on a throwaway copy so this test never mutates the seed asset.
    final tmpPath = '${Directory.systemTemp.path}/vocab_test_${DateTime.now().microsecondsSinceEpoch}.db';
    await File(seedPath).copy(tmpPath);
    final db = await databaseFactory.openDatabase(tmpPath);

    final words = await db.query('words');
    expect(words.length, greaterThanOrEqualTo(150));

    final senses = await db.query('senses');
    expect(senses.length, words.length); // one core sense per word in seed

    final sentences = await db.query('example_sentences');
    expect(sentences.length, words.length * 5);

    await runMigrations(db);
    final srsRows = await db.query('srs_state');
    expect(srsRows, isEmpty); // no reviews logged yet, table just needs to exist

    // settings table usable
    await db.insert('settings', {'key': 'new_card_cap', 'value': '8'});
    final settings = await db.query('settings');
    expect(settings.single['value'], '8');

    await db.close();
    await File(tmpPath).delete();
  });
}
