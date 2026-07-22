-- App-state tables layered on top of the bundled content seed (words,
-- senses, word_forms, example_sentences, related_words, topics,
-- word_topics — all shipped read-only in assets/seed/vocab.db).
-- Numbered migration pattern borrowed from Gymmer_App's data/ layer.

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
