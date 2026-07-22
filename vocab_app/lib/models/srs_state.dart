/// FSRS-5 per-word scheduling state. Mirrors `srs_state` table.
library;

enum CardState { newState, learning, young, mature }

CardState cardStateFromString(String s) {
  switch (s) {
    case 'new':
      return CardState.newState;
    case 'learning':
      return CardState.learning;
    case 'young':
      return CardState.young;
    case 'mature':
      return CardState.mature;
    default:
      return CardState.newState;
  }
}

String cardStateToString(CardState s) {
  switch (s) {
    case CardState.newState:
      return 'new';
    case CardState.learning:
      return 'learning';
    case CardState.young:
      return 'young';
    case CardState.mature:
      return 'mature';
  }
}

enum Direction { enTh, thEn }

String directionToString(Direction d) => d == Direction.enTh ? 'en_th' : 'th_en';

Direction directionFromString(String? s) =>
    s == 'th_en' ? Direction.thEn : Direction.enTh;

enum Rating { again, hard, good, easy }

String ratingToString(Rating r) {
  switch (r) {
    case Rating.again:
      return 'again';
    case Rating.hard:
      return 'hard';
    case Rating.good:
      return 'good';
    case Rating.easy:
      return 'easy';
  }
}

class SrsState {
  const SrsState({
    required this.wordId,
    required this.state,
    required this.stability,
    required this.difficulty,
    required this.dueAt,
    this.lastReview,
    required this.reps,
    required this.lapses,
    this.lastDirection,
  });

  final int wordId;
  final CardState state;
  final double stability;
  final double difficulty;
  final DateTime dueAt;
  final DateTime? lastReview;
  final int reps;
  final int lapses;
  final Direction? lastDirection;

  SrsState copyWith({
    CardState? state,
    double? stability,
    double? difficulty,
    DateTime? dueAt,
    DateTime? lastReview,
    int? reps,
    int? lapses,
    Direction? lastDirection,
  }) => SrsState(
    wordId: wordId,
    state: state ?? this.state,
    stability: stability ?? this.stability,
    difficulty: difficulty ?? this.difficulty,
    dueAt: dueAt ?? this.dueAt,
    lastReview: lastReview ?? this.lastReview,
    reps: reps ?? this.reps,
    lapses: lapses ?? this.lapses,
    lastDirection: lastDirection ?? this.lastDirection,
  );

  static SrsState initial(int wordId, DateTime now) => SrsState(
    wordId: wordId,
    state: CardState.newState,
    stability: 0,
    difficulty: 0,
    dueAt: now,
    lastReview: null,
    reps: 0,
    lapses: 0,
    lastDirection: null,
  );

  factory SrsState.fromMap(Map<String, Object?> m) => SrsState(
    wordId: m['word_id'] as int,
    state: cardStateFromString(m['state'] as String? ?? 'new'),
    stability: (m['stability'] as num?)?.toDouble() ?? 0,
    difficulty: (m['difficulty'] as num?)?.toDouble() ?? 0,
    dueAt: DateTime.fromMillisecondsSinceEpoch(m['due_at'] as int? ?? 0),
    lastReview: m['last_review'] == null
        ? null
        : DateTime.fromMillisecondsSinceEpoch(m['last_review'] as int),
    reps: m['reps'] as int? ?? 0,
    lapses: m['lapses'] as int? ?? 0,
    lastDirection: directionFromString(m['last_direction'] as String?),
  );

  Map<String, Object?> toMap() => {
    'word_id': wordId,
    'state': cardStateToString(state),
    'stability': stability,
    'difficulty': difficulty,
    'due_at': dueAt.millisecondsSinceEpoch,
    'last_review': lastReview?.millisecondsSinceEpoch,
    'reps': reps,
    'lapses': lapses,
    'last_direction': lastDirection == null
        ? null
        : directionToString(lastDirection!),
  };
}

class ReviewLogEntry {
  const ReviewLogEntry({
    this.id,
    required this.wordId,
    required this.ts,
    required this.rating,
    required this.gameType,
    required this.direction,
    required this.elapsedMs,
  });

  final int? id;
  final int wordId;
  final DateTime ts;
  final Rating rating;
  final String gameType;
  final Direction direction;
  final int elapsedMs;

  Map<String, Object?> toMap() => {
    if (id != null) 'id': id,
    'word_id': wordId,
    'ts': ts.millisecondsSinceEpoch,
    'rating': ratingToString(rating),
    'game_type': gameType,
    'direction': directionToString(direction),
    'elapsed_ms': elapsedMs,
  };

  factory ReviewLogEntry.fromMap(Map<String, Object?> m) => ReviewLogEntry(
    id: m['id'] as int?,
    wordId: m['word_id'] as int,
    ts: DateTime.fromMillisecondsSinceEpoch(m['ts'] as int),
    rating: Rating.values.firstWhere(
      (r) => ratingToString(r) == m['rating'],
      orElse: () => Rating.good,
    ),
    gameType: m['game_type'] as String? ?? '',
    direction: directionFromString(m['direction'] as String?),
    elapsedMs: m['elapsed_ms'] as int? ?? 0,
  );
}

class DailyStats {
  const DailyStats({
    required this.date,
    required this.newIntroduced,
    required this.reviewsDone,
    required this.streakKept,
  });

  final String date; // yyyy-MM-dd
  final int newIntroduced;
  final int reviewsDone;
  final bool streakKept;

  DailyStats copyWith({
    int? newIntroduced,
    int? reviewsDone,
    bool? streakKept,
  }) => DailyStats(
    date: date,
    newIntroduced: newIntroduced ?? this.newIntroduced,
    reviewsDone: reviewsDone ?? this.reviewsDone,
    streakKept: streakKept ?? this.streakKept,
  );

  factory DailyStats.fromMap(Map<String, Object?> m) => DailyStats(
    date: m['date'] as String,
    newIntroduced: m['new_introduced'] as int? ?? 0,
    reviewsDone: m['reviews_done'] as int? ?? 0,
    streakKept: (m['streak_kept'] as int? ?? 0) == 1,
  );

  Map<String, Object?> toMap() => {
    'date': date,
    'new_introduced': newIntroduced,
    'reviews_done': reviewsDone,
    'streak_kept': streakKept ? 1 : 0,
  };
}
