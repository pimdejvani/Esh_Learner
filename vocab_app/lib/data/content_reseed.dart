/// Replaces the content half of the app database when a build ships newer
/// content, without touching the player's progress.
///
/// The app database is one file holding two different things: content copied
/// from `assets/seed/vocab.db` (words, senses, examples, relations) and the
/// player's own rows (srs_state, reviews_log, daily_stats, settings). Before
/// this existed the only way to ship new content was to delete the file, which
/// threw away every review the player had ever done.
///
/// Reseeding instead starts from the new seed and copies the player's rows into
/// it, remapping `word_id` by **headword** — content ids are not stable across
/// builds, headwords are. Rows for words that no longer exist are dropped, which
/// is the honest outcome: there is nothing left to review.
library;

import 'dart:io';

import 'package:flutter/services.dart' show rootBundle;
import 'package:sqflite/sqflite.dart';

/// Tables owned by the player. Everything else in the file is content and is
/// replaced wholesale.
const List<String> kUserTables = [
  'srs_state',
  'reviews_log',
  'daily_stats',
  'settings',
  'schema_migrations',
];

/// Tables whose rows point at a content word and must be remapped.
const Set<String> kWordScopedTables = {'srs_state', 'reviews_log'};

class ReseedOutcome {
  const ReseedOutcome({
    required this.reseeded,
    required this.fromVersion,
    required this.toVersion,
    this.rowsKept = 0,
    this.rowsDropped = 0,
  });

  final bool reseeded;
  final int fromVersion;
  final int toVersion;
  final int rowsKept;
  final int rowsDropped;

  @override
  String toString() => reseeded
      ? 'reseeded $fromVersion -> $toVersion (kept $rowsKept rows, dropped $rowsDropped)'
      : 'no reseed needed (content_version $fromVersion)';
}

Future<int> _contentVersion(Database db) async {
  final tables = await db.rawQuery(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='content_meta'",
  );
  if (tables.isEmpty) return 0;
  final rows = await db.query(
    'content_meta',
    where: 'key = ?',
    whereArgs: ['content_version'],
  );
  if (rows.isEmpty) return 0;
  return int.tryParse(rows.first['value'] as String? ?? '') ?? 0;
}

Future<int> _seedVersion(String seedPath) async {
  final db = await openDatabase(seedPath, readOnly: true);
  try {
    return await _contentVersion(db);
  } finally {
    await db.close();
  }
}

/// Writes the bundled seed to [path], overwriting whatever is there.
Future<void> _writeSeedAsset(String path, String assetKey) async {
  final bytes = await rootBundle.load(assetKey);
  await File(path).writeAsBytes(bytes.buffer.asUint8List(), flush: true);
}

/// Brings [dbPath] up to the bundled seed's content version, keeping player rows.
///
/// [openDb] is injectable so tests can drive this against a plain sqflite ffi
/// database, and [writeSeed] so they can supply a seed file without an asset
/// bundle.
Future<ReseedOutcome> reseedIfNeeded(
  String dbPath, {
  String assetKey = 'assets/seed/vocab.db',
  Future<Database> Function(String path, {bool readOnly})? openDb,
  Future<void> Function(String path)? writeSeed,
}) async {
  final open = openDb ??
      (String path, {bool readOnly = false}) =>
          openDatabase(path, readOnly: readOnly);
  final putSeed = writeSeed ?? ((String path) => _writeSeedAsset(path, assetKey));

  final stagingPath = '$dbPath.reseed';
  await putSeed(stagingPath);

  final current = await open(dbPath, readOnly: true);
  final int installed;
  try {
    installed = await _contentVersion(current);
  } finally {
    await current.close();
  }

  final staging = await open(stagingPath, readOnly: true);
  final int incoming;
  try {
    incoming = await _contentVersion(staging);
  } finally {
    await staging.close();
  }

  if (incoming <= installed) {
    await File(stagingPath).delete();
    return ReseedOutcome(
      reseeded: false,
      fromVersion: installed,
      toVersion: incoming,
    );
  }

  var kept = 0;
  var dropped = 0;
  final target = await open(stagingPath);
  try {
    await target.execute("ATTACH DATABASE ? AS old", [dbPath]);
    try {
      // Content ids are rebuilt on every content build, so the only stable
      // handle on a word is its headword.
      final remap = <int, int>{};
      final oldWords = await target.rawQuery('SELECT id, headword FROM old.words');
      final newWords = await target.rawQuery('SELECT id, headword FROM main.words');
      final newIdByHeadword = {
        for (final r in newWords)
          (r['headword'] as String).toLowerCase(): r['id'] as int,
      };
      for (final r in oldWords) {
        final newId = newIdByHeadword[(r['headword'] as String).toLowerCase()];
        if (newId != null) remap[r['id'] as int] = newId;
      }

      for (final table in kUserTables) {
        final exists = await target.rawQuery(
          "SELECT name FROM old.sqlite_master WHERE type='table' AND name=?",
          [table],
        );
        if (exists.isEmpty) continue;
        await _createLike(target, table);
        final rows = await target.rawQuery('SELECT * FROM old.$table');
        for (final row in rows) {
          final values = Map<String, Object?>.from(row);
          if (kWordScopedTables.contains(table)) {
            final mapped = remap[values['word_id'] as int?];
            if (mapped == null) {
              dropped++;
              continue;
            }
            values['word_id'] = mapped;
          }
          // reviews_log has an autoincrement id; letting SQLite reassign it
          // keeps the copy simple and the log's order comes from `ts` anyway.
          if (table == 'reviews_log') values.remove('id');
          await target.insert(
            table,
            values,
            conflictAlgorithm: ConflictAlgorithm.replace,
          );
          kept++;
        }
      }
    } finally {
      await target.execute('DETACH DATABASE old');
    }
  } finally {
    await target.close();
  }

  await File(dbPath).delete();
  await File(stagingPath).rename(dbPath);
  return ReseedOutcome(
    reseeded: true,
    fromVersion: installed,
    toVersion: incoming,
    rowsKept: kept,
    rowsDropped: dropped,
  );
}

/// Recreates one of the player's tables in the staging database using the DDL
/// the old database recorded, so a schema added by a later migration survives.
Future<void> _createLike(Database db, String table) async {
  final ddl = await db.rawQuery(
    "SELECT sql FROM old.sqlite_master WHERE type='table' AND name=?",
    [table],
  );
  if (ddl.isEmpty) return;
  final statement = (ddl.first['sql'] as String).replaceFirst(
    RegExp(r'CREATE TABLE\s+', caseSensitive: false),
    'CREATE TABLE IF NOT EXISTS ',
  );
  await db.execute(statement);
}

/// Convenience for the store: install the seed on first launch, otherwise
/// reseed when the bundled content is newer.
Future<ReseedOutcome> installOrReseed(
  String dbPath, {
  String assetKey = 'assets/seed/vocab.db',
}) async {
  if (!await File(dbPath).exists()) {
    await _writeSeedAsset(dbPath, assetKey);
    final version = await _seedVersion(dbPath);
    return ReseedOutcome(reseeded: true, fromVersion: 0, toVersion: version);
  }
  return reseedIfNeeded(dbPath, assetKey: assetKey);
}
