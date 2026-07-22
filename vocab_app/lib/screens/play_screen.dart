/// Main play screen — endless queue per SPEC.md section 7. Pulls the next
/// [SessionItem] from [SessionEngine], renders the matching game/intro
/// page, and on rating feeds the result back through FSRS + the sleep-gap
/// + governors, persists it, then advances.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/data/vocab_store.dart';
import 'package:vocab_app/domain/fsrs/fsrs5.dart';
import 'package:vocab_app/domain/fsrs/sleep_gap.dart';
import 'package:vocab_app/domain/new_card_governor.dart';
import 'package:vocab_app/domain/retention_tuner.dart';
import 'package:vocab_app/domain/session_engine.dart';
import 'package:vocab_app/domain/streaks.dart';
import 'package:vocab_app/games/cloze.dart';
import 'package:vocab_app/games/flashcard_swipe.dart';
import 'package:vocab_app/games/matching.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_intro_page.dart';

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
  String? _error;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    try {
      final state = await widget.store.load();
      final today = dateKey(DateTime.now());
      final stats = await widget.store.loadDailyStats(today);
      setState(() {
        _state = state;
        _newIntroducedToday = stats?.newIntroduced ?? 0;
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
    );
    await _loadNext();
  }

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
    } else {
      final bundle = await widget.store.loadWordBundle(item.wordId);
      setState(() {
        _currentBundle = bundle;
        _currentBatch = [];
      });
    }
  }

  List<int> _pickMatchingBatch(int seedWordId) {
    final learningWords = _state!.words.where((w) {
      final s = _state!.srsStates[w.id];
      return s != null && s.state == CardState.learning;
    }).map((w) => w.id).toList();
    if (!learningWords.contains(seedWordId)) learningWords.insert(0, seedWordId);
    return learningWords.take(6).toList();
  }

  Future<void> _handleIntroContinue() async {
    final bundle = _currentBundle!;
    final now = DateTime.now();
    final srs = SrsState.initial(bundle.word.id, now);
    final candidateDue = _scheduler
        .review(
          current: srs,
          rating: Rating.good,
          now: now,
          requestRetention: _requestRetention,
        )
        .dueAt;
    final sleepGapped = applySleepGap(now, candidateDue);
    final updated = srs.copyWith(
      state: CardState.learning,
      dueAt: sleepGapped,
      lastReview: now,
      reps: 1,
    );
    await widget.store.upsertSrsState(updated);
    _state!.srsStates[bundle.word.id] = updated;
    _newIntroducedToday++;
    await _persistDailyStats(newIntroducedDelta: 1);
    await _advance();
  }

  Future<void> _handleRated(int wordId, Rating rating, GameType game) async {
    final now = DateTime.now();
    final current = _state!.srsStates[wordId] ?? SrsState.initial(wordId, now);
    var updated = _scheduler.review(
      current: current,
      rating: rating,
      now: now,
      requestRetention: _requestRetention,
    );
    // Sleep-gap only meaningfully applies to a word's very first
    // post-intro review; subsequent FSRS intervals are already >= 1 day
    // in virtually all cases, so we only special-case reps==1.
    if (current.reps <= 1) {
      updated = updated.copyWith(dueAt: applySleepGap(now, updated.dueAt));
    }
    await widget.store.upsertSrsState(updated);
    _state!.srsStates[wordId] = updated;

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
    await _persistDailyStats(reviewsDelta: 1);
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
    final today = dateKey(DateTime.now());
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
      child: _buildItem(item),
    );
  }

  Widget _buildItem(SessionItem item) {
    switch (item.gameType) {
      case GameType.intro:
        if (_currentBundle == null) return const SizedBox.shrink();
        return WordIntroPage(
          bundle: _currentBundle!,
          tts: widget.tts,
          onContinue: _handleIntroContinue,
        );
      case GameType.flashcard:
        if (_currentBundle == null) return const SizedBox.shrink();
        return FlashcardSwipeGame(
          bundle: _currentBundle!,
          direction: item.direction,
          tts: widget.tts,
          onRated: (r) => _handleRated(item.wordId, r, GameType.flashcard),
        );
      case GameType.cloze:
        if (_currentBundle == null) return const SizedBox.shrink();
        return ClozeGame(
          bundle: _currentBundle!,
          tts: widget.tts,
          onRated: (r) => _handleRated(item.wordId, r, GameType.cloze),
        );
      case GameType.matching:
        if (_currentBatch.isEmpty) return const SizedBox.shrink();
        return MatchingGame(
          bundles: _currentBatch,
          onAllRated: _handleMatchingResult,
        );
    }
  }
}
