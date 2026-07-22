/// Numbered migrations, run in order against the writable app database.
/// The .sql files alongside this runner are the source of truth for
/// review/documentation; their content is embedded here as literal strings
/// because Flutter can't read arbitrary `lib/` files at runtime (only
/// `assets/`) and hand-copying keeps a single migration step from drifting
/// out of sync silently — each migration is small enough this is safe.
library;

import 'package:sqflite/sqflite.dart';

class Migration {
  const Migration(this.version, this.name, this.sql);
  final int version;
  final String name;
  final String sql;
}

final List<Migration> kMigrations = [
  const Migration(1, '0001_init', '''
CREATE TABLE IF NOT EXISTS srs_state (
  word_id INTEGER PRIMARY KEY REFERENCES words(id),
  state TEXT NOT NULL DEFAULT 'new',
  stability REAL NOT NULL DEFAULT 0,
  difficulty REAL NOT NULL DEFAULT 0,
  due_at INTEGER NOT NULL,
  last_review INTEGER,
  reps INTEGER NOT NULL DEFAULT 0,
  lapses INTEGER NOT NULL DEFAULT 0,
  last_direction TEXT
);

CREATE TABLE IF NOT EXISTS reviews_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  word_id INTEGER NOT NULL REFERENCES words(id),
  ts INTEGER NOT NULL,
  rating TEXT NOT NULL,
  game_type TEXT NOT NULL,
  direction TEXT NOT NULL,
  elapsed_ms INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_reviews_log_ts ON reviews_log(ts);
CREATE INDEX IF NOT EXISTS idx_reviews_log_word ON reviews_log(word_id);

CREATE TABLE IF NOT EXISTS daily_stats (
  date TEXT PRIMARY KEY,
  new_introduced INTEGER NOT NULL DEFAULT 0,
  reviews_done INTEGER NOT NULL DEFAULT 0,
  streak_kept INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
'''),
];

Future<void> runMigrations(Database db) async {
  await db.execute('''
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version INTEGER PRIMARY KEY,
      name TEXT NOT NULL,
      applied_at INTEGER NOT NULL
    )
  ''');
  final applied = (await db.query(
    'schema_migrations',
  )).map((r) => r['version'] as int).toSet();

  for (final m in kMigrations) {
    if (applied.contains(m.version)) continue;
    await db.transaction((txn) async {
      final statements = m.sql
          .split(';')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty);
      for (final stmt in statements) {
        await txn.execute(stmt);
      }
      await txn.insert('schema_migrations', {
        'version': m.version,
        'name': m.name,
        'applied_at': DateTime.now().millisecondsSinceEpoch,
      });
    });
  }
}
