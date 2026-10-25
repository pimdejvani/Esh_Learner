import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';
import 'package:vocab_app/data/content_reseed.dart';
import 'package:vocab_app/data/migrations/migration_runner.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('bundled seed installs offline and preserves progress on reseed', (tester) async {
    final docs = await getApplicationDocumentsDirectory();
    final temporary = await Directory(docs.path).createTemp('seed_install_');
    final path = p.join(temporary.path, 'vocab.db');
    try {
      final installed = await installOrReseed(path);
      expect(installed.fromVersion, 0);
      expect(installed.toVersion, 4);
      var db = await openDatabase(path);
      expect(Sqflite.firstIntValue(await db.rawQuery('SELECT count(*) FROM words')), 2967);
      expect(Sqflite.firstIntValue(await db.rawQuery('SELECT count(*) FROM example_sentences')), 14835);
      expect(Sqflite.firstIntValue(await db.rawQuery('SELECT count(*) FROM words WHERE is_test_only=1')), 0);
      await runMigrations(db);
      await db.insert('settings', {'key': 'seed_smoke_marker', 'value': 'keep'});
      final word = (await db.query('words', limit: 1)).single;
      await db.insert('srs_state', {
        'word_id': word['id'], 'state': 'review', 'stability': 12.5,
        'difficulty': 5.0, 'due_at': 1234567890, 'reps': 3, 'lapses': 1,
      });
      await db.update('content_meta', {'value': '2'}, where: 'key=?', whereArgs: ['content_version']);
      await db.close();
      final upgraded = await installOrReseed(path);
      expect(upgraded.fromVersion, 2);
      expect(upgraded.toVersion, 4);
      db = await openDatabase(path);
      expect((await db.query('srs_state')).single['stability'], 12.5);
      expect((await db.query('settings', where: 'key=?', whereArgs: ['seed_smoke_marker'])).single['value'], 'keep');
      expect(Sqflite.firstIntValue(await db.rawQuery('SELECT count(*) FROM words')), 2967);
      await db.close();
      expect((await installOrReseed(path)).reseeded, isFalse);
    } finally {
      await temporary.delete(recursive: true);
    }
  });
}
