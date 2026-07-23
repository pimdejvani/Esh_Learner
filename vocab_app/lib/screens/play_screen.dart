/// Main play screen — endless queue per SPEC.md section 7. Pulls the next
/// [SessionItem] from [SessionEngine], renders the matching game/intro
/// page, and on rating feeds the result back through FSRS + the sleep-gap
/// + governors, persists it, then advances.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/data/vocab_store.dart';
import 'package:vocab_app/domain/fsrs/fsrs5.dart';
import 'package:vocab_app/domain/new_card_governor.dart';
import 'package:vocab_app/domain/retention_tuner.dart';
import 'package:vocab_app/domain/session_engine.dart';
import 'package:vocab_app/domain/streaks.dart';
import 'package:vocab_app/games/cloze.dart';
import 'package:vocab_app/games/dictation.dart';
import 'package:vocab_app/games/flashcard_swipe.dart';
import 'package:vocab_app/games/matching.dart';
import 'package:vocab_app/games/odd_one_out.dart';
import 'package:vocab_app/games/word_association.dart';
import 'package:vocab_app/games/word_scramble.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/widgets/highlight_card.dart';

class PlayScreen extends StatefulWidget {
  const PlayScreen({super.key, required this.store, required this.tts});

  final VocabStore store;
  final TtsService tts;

  @override
  State<PlayScreen> createState() => _PlayScreenState();
}

class _PlayScreenState extends State<PlayScreen> {
  final _sessionEngine = SessionEngine();
  final _scheduler = const FsrsScheduler();
  final _tuner = const RetentionTuner();
  final _governor = const NewCardGovernor();

  VocabStoreState? _state;
  List<SessionItem> _queue = [];
  WordBundle? _currentBundle;
  List<WordBundle> _currentBatch = [];
  bool _loading = true;
  int _newIntroducedToday = 0;
  // True until the first queue of a new logical day (3am boundary) has
  // been built — that queue always opens with a flashcard round.
  bool _firstSessionOfDay = false;
  String? _error;

  Map<int, Word> _wordById = {};
  Map<int, List<RelatedWord>> _relatedByWord = {};
  Set<int> _focusTopicWordIds = {};

  // Cached payload for the batch/multi-choice games so the option/group
  // ordering doesn't reshuffle on every rebuild (only when the queue
  // actually advances to a new item).
  List<Word>? _wordAssocOptions;
  int? _wordAssocCorrectId;
  Word? _oddOneOutTarget;
  List<Word> _oddOneOutGroup = [];

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    try {
      final state = await widget.store.load();
      final today = logicalDateKey(DateTime.now());
      final stats = await widget.store.loadDailyStats(today);
      final relatedByWord = await widget.store.loadAllRelatedWords();
      final focusTopicId = int.tryParse(state.settings['focus_topic'] ?? '');
      final focusTopicWordIds = focusTopicId == null
          ? <int>{}
          : await widget.store.loadWordIdsForTopic(focusTopicId);
      setState(() {
        _state = state;
        _newIntroducedToday = stats?.newIntroduced ?? 0;
        // No daily_stats row yet for today's logical date = nothing has
        // been played since the 3am boundary -> open the day with a
        // flashcard round.
        _firstSessionOfDay = stats == null;
        _wordById = {for (final w in state.words) w.id: w};
        _relatedByWord = relatedByWord;
        _focusTopicWordIds = focusTopicWordIds;
      });
      await _refillQueue();
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      setState(() => _loading = false);
    }
  }

  int get _newCardCap =>
      int.tryParse(_state?.settings['new_card_cap'] ?? '') ?? 8;

  double get _requestRetention =>
      double.tryParse(_state?.settings['request_retention'] ?? '') ?? 0.88;

  Future<void> _refillQueue() async {
    final state = _state!;
    _queue = _sessionEngine.buildQueue(
      words: state.words,
      srsStates: state.srsStates,
      now: DateTime.now(),
      newCardCap: _newCardCap,
      newIntroducedToday: _newIntroducedToday,
      focusTopicWordIds: _focusTopicWordIds,
      firstSessionOfDay: _firstSessionOfDay,
    );
    _firstSessionOfDay = false; // consumed — only the day's opening queue
    await _loadNext();
  }

  /// Family-A semantic hint (SPEC.md 8b): related words for [bundle],
  /// excluding `is_giveaway` rows, ordered strongest-association-first
  /// (`closeness` descending) so the earliest taps of the progressive
  /// hint button surface the most useful-but-not-a-giveaway clue.
  /// [excludeWordId] additionally drops one candidate — used by Word
  /// Association so the hint list never includes the very word that's the
  /// MCQ's correct answer (that would trivialize the round entirely).
  List<String> _semanticHints(
    WordBundle bundle, {
    int maxHints = 3,
    int? excludeWordId,
  }) {
    final candidates = bundle.related
        .where((r) => !r.isGiveaway && r.relatedWordId != excludeWordId)
        .toList()
      ..sort((a, b) => b.closeness.compareTo(a.closeness));
    return candidates
        .map((r) => _wordById[r.relatedWordId]?.headword)
        .whereType<String>()
        .take(maxHints)
        .toList();
  }

  /// Falls back to Flashcard (always buildable from just a WordBundle) when
  /// a batch/multi-choice game can't be assembled for the current word —
  /// e.g. Odd One Out/Word Association need `related_words` rows that many
  /// words don't have yet given how sparse the current fallback dataset is
  /// (see NOTES.md). Keeps the endless queue from ever stalling.
  SessionItem _fallbackToFlashcard(SessionItem original) => SessionItem(
    wordId: original.wordId,
    gameType: GameType.flashcard,
    direction: original.direction,
    source: original.source,
  );

  Future<void> _loadNext() async {
    if (_queue.isEmpty) {
      setState(() {
        _currentBundle = null;
        _currentBatch = [];
      });
      return;
    }
    final item = _queue.first;

    if (item.gameType == GameType.matching) {
      // Pull a small batch of due/learning words for matching.
      final batchIds = _pickMatchingBatch(item.wordId);
      final bundles = await widget.store.loadWordBundles(batchIds);
      setState(() {
        _currentBatch = bundles;
        _currentBundle = null;
      });
      return;
    }

    if (item.gameType == GameType.oddOneOut) {
      final target = _wordById[item.wordId];
      final group = target == null
          ? null
          : buildOddOneOutGroup(
              target: target,
              pool: _state!.words,
              relatedByWord: _relatedByWord,
            );
      if (target == null || group == null) {
        _queue[0] = _fallbackToFlashcard(item);
        return _loadNext();
      }
      setState(() {
        _oddOneOutTarget = target;
        _oddOneOutGroup = group;
        _currentBundle = null;
        _currentBatch = [];
      });
      return;
    }

    if (item.gameType == GameType.wordAssociation) {
      final bundle = await widget.store.loadWordBundle(item.wordId);
      final pick = pickAssociationTarget(bundle.related);
      final correctWord = pick == null ? null : _wordById[pick.relatedWordId];
      if (pick == null || correctWord == null) {
        _queue[0] = _fallbackToFlashcard(item);
        return _loadNext();
      }
      final excludeIds = {
        bundle.word.id,
        for (final r in bundle.related) r.relatedWordId,
      };
      final options = buildAssociationOptions(
        correct: correctWord,
        pool: _state!.words,
        excludeIds: excludeIds,
      );
      setState(() {
        _currentBundle = bundle;
        _currentBatch = [];
        _wordAssocOptions = options;
        _wordAssocCorrectId = correctWord.id;
      });
      return;
    }

    // Everything else (intro / flashcard / cloze / word scramble /
    // dictation) just needs one WordBundle.
    final bundle = await widget.store.loadWordBundle(item.wordId);
    setState(() {
      _currentBundle = bundle;
      _currentBatch = [];
    });
  }

  List<int> _pickMatchingBatch(int seedWordId) {
    final learningWords = _state!.words.where((w) {
      final s = _state!.srsStates[w.id];
      return s != null && s.state == CardState.learning;
    }).map((w) => w.id).toList();
    if (!learningWords.contains(seedWordId)) learningWords.insert(0, seedWordId);
    return learningWords.take(6).toList();
  }

  Future<void> _handleRated(int wordId, Rating rating, GameType game) async {
    final now = DateTime.now();
    // A word with no SRS row yet is a brand-new word whose first flashcard
    // swipe (รู้จัก/ไม่รู้จัก) doubles as both its introduction AND its
    // first FSRS review (2026-07-23 revision — no separate intro step).
    final isFirstEncounter = _state!.srsStates[wordId] == null;
    final current = _state!.srsStates[wordId] ?? SrsState.initial(wordId, now);
    final updated = _scheduler.review(
      current: current,
      rating: rating,
      now: now,
      requestRetention: _requestRetention,
    );
    await widget.store.upsertSrsState(updated);
    _state!.srsStates[wordId] = updated;
    if (isFirstEncounter) _newIntroducedToday++;

    final direction = current.lastDirection == Direction.enTh
        ? Direction.thEn
        : Direction.enTh;
    await widget.store.logReview(
      ReviewLogEntry(
        wordId: wordId,
        ts: now,
        rating: rating,
        gameType: game.name,
        direction: direction,
        elapsedMs: 0,
      ),
    );
    await _persistDailyStats(
      reviewsDelta: 1,
      newIntroducedDelta: isFirstEncounter ? 1 : 0,
    );
    await _maybeRetune();
    await _advance();
  }

  Future<void> _handleMatchingResult(Map<int, Rating> ratings) async {
    for (final entry in ratings.entries) {
      await _handleRated(entry.key, entry.value, GameType.matching);
    }
  }

  Future<void> _maybeRetune() async {
    final since = DateTime.now().subtract(const Duration(days: 7));
    final reviews = await widget.store.loadRecentReviews(since: since);
    final nextRetention = _tuner.nextRetention(
      current: _requestRetention,
      reviews: reviews,
      now: DateTime.now(),
    );
    await widget.store.saveSetting(
      'request_retention',
      nextRetention.toStringAsFixed(4),
    );
    _state!.settings['request_retention'] = nextRetention.toStringAsFixed(4);

    final backlogCount = _state!.words.where((w) {
      final s = _state!.srsStates[w.id];
      return s != null && !s.dueAt.isAfter(DateTime.now());
    }).length;
    final nextCap = _governor.nextCap(
      currentCap: _newCardCap,
      backlogCount: backlogCount,
      reviews: reviews,
      now: DateTime.now(),
    );
    await widget.store.saveSetting('new_card_cap', nextCap.toString());
    _state!.settings['new_card_cap'] = nextCap.toString();
  }

  Future<void> _persistDailyStats({
    int newIntroducedDelta = 0,
    int reviewsDelta = 0,
  }) async {
    final today = logicalDateKey(DateTime.now());
    final existing =
        await widget.store.loadDailyStats(today) ??
        const DailyStats(
          date: '',
          newIntroduced: 0,
          reviewsDone: 0,
          streakKept: false,
        );
    final noDueLeft = !_state!.words.any((w) {
      final s = _state!.srsStates[w.id];
      return s != null && !s.dueAt.isAfter(DateTime.now());
    });
    final updated = DailyStats(
      date: today,
      newIntroduced: existing.newIntroduced + newIntroducedDelta,
      reviewsDone: existing.reviewsDone + reviewsDelta,
      streakKept: noDueLeft,
    );
    await widget.store.upsertDailyStats(updated);
  }

  Future<void> _advance() async {
    _queue.removeAt(0);
    if (_queue.isEmpty) {
      await _refillQueue();
    } else {
      await _loadNext();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return Center(child: Text('Error: $_error'));
    if (_queue.isEmpty) {
      return const Center(child: Text('เคลียร์หมดแล้ว เก่งมาก! กลับมาใหม่พรุ่งนี้'));
    }

    final item = _queue.first;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 220),
            child: _GameModeIndicator(
              key: ValueKey(
                (item.gameType, _state!.srsStates[item.wordId] == null),
              ),
              gameType: item.gameType,
              isNewWord: _state!.srsStates[item.wordId] == null,
            ),
          ),
          const SizedBox(height: 12),
          _buildItem(item),
        ],
      ),
    );
  }

  Widget _buildItem(SessionItem item) {
    switch (item.gameType) {
      case GameType.flashcard:
        if (_currentBundle == null) return const SizedBox.shrink();
        return FlashcardSwipeGame(
          bundle: _currentBundle!,
          direction: item.direction,
          tts: widget.tts,
          isNewWord: _state!.srsStates[item.wordId] == null,
          onRated: (r) => _handleRated(item.wordId, r, GameType.flashcard),
        );
      case GameType.cloze:
        if (_currentBundle == null) return const SizedBox.shrink();
        return ClozeGame(
          bundle: _currentBundle!,
          tts: widget.tts,
          hintWords: _semanticHints(_currentBundle!),
          onRated: (r) => _handleRated(item.wordId, r, GameType.cloze),
        );
      case GameType.matching:
        if (_currentBatch.isEmpty) return const SizedBox.shrink();
        return MatchingGame(
          bundles: _currentBatch,
          onAllRated: _handleMatchingResult,
        );
      case GameType.wordAssociation:
        if (_currentBundle == null ||
            _wordAssocOptions == null ||
            _wordAssocCorrectId == null) {
          return const SizedBox.shrink();
        }
        return WordAssociationGame(
          bundle: _currentBundle!,
          options: _wordAssocOptions!,
          correctWordId: _wordAssocCorrectId!,
          tts: widget.tts,
          hintWords: _semanticHints(
            _currentBundle!,
            excludeWordId: _wordAssocCorrectId,
          ),
          onRated: (r) => _handleRated(item.wordId, r, GameType.wordAssociation),
        );
      case GameType.wordScramble:
        if (_currentBundle == null) return const SizedBox.shrink();
        return WordScrambleGame(
          bundle: _currentBundle!,
          tts: widget.tts,
          hintWords: _semanticHints(_currentBundle!),
          onRated: (r) => _handleRated(item.wordId, r, GameType.wordScramble),
        );
      case GameType.dictation:
        if (_currentBundle == null) return const SizedBox.shrink();
        return DictationGame(
          bundle: _currentBundle!,
          tts: widget.tts,
          onRated: (r) => _handleRated(item.wordId, r, GameType.dictation),
        );
      case GameType.oddOneOut:
        if (_oddOneOutTarget == null) return const SizedBox.shrink();
        return OddOneOutGame(
          oddWord: _oddOneOutTarget!,
          groupWords: _oddOneOutGroup,
          onRated: (r) => _handleRated(item.wordId, r, GameType.oddOneOut),
        );
    }
  }
}

/// Small "what game am I playing right now" indicator (NOTES.md's UI design
/// pass: a colorful highlight-card use case explicitly called out for the
/// play screen) — tone cycles across the three pastel tones by desirable-
/// difficulty tier (recognition/retrieval/production, SPEC.md section 7's
/// ladder) so the player gets a quick at-a-glance read of what kind of
/// round they're in.
class _GameModeIndicator extends StatelessWidget {
  const _GameModeIndicator({
    super.key,
    required this.gameType,
    this.isNewWord = false,
  });

  final GameType gameType;

  /// First-ever encounter (flashcard round doubling as the word's
  /// introduction) — labelled "คำใหม่" so the player knows this card has
  /// no history yet.
  final bool isNewWord;

  @override
  Widget build(BuildContext context) {
    final (icon, label, tone) = switch (gameType) {
      GameType.flashcard when isNewWord =>
        (Icons.auto_awesome, 'คำใหม่', HighlightTone.lavender),
      GameType.flashcard => (Icons.style, 'Flashcard', HighlightTone.sky),
      GameType.matching => (Icons.grid_view, 'Matching', HighlightTone.sky),
      GameType.oddOneOut => (Icons.category, 'Odd One Out', HighlightTone.sky),
      GameType.cloze => (Icons.edit_note, 'Cloze', HighlightTone.lavender),
      GameType.wordAssociation => (Icons.hub, 'Word Association', HighlightTone.lavender),
      GameType.wordScramble => (Icons.shuffle, 'Word Scramble', HighlightTone.blue),
      GameType.dictation => (Icons.hearing, 'Dictation', HighlightTone.blue),
    };
    return HighlightCard(icon: icon, title: label, tone: tone, dense: true);
  }
}
