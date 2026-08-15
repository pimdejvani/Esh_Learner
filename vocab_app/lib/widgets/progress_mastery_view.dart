/// "You Pass" progress — the grid of (word x mastery game) cells the player
/// has to sweep clean in one round.
///
/// The condition was already computed but invisible, so a reset looked like
/// progress vanishing for no reason. This shows the count, the per-game
/// breakdown, what is still missing, and — when it happened — that an Again
/// wiped the round (SPEC.md section 10, action_plan.txt item 16).
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/domain/mastery.dart';
import 'package:vocab_app/domain/session_engine.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/widgets/highlight_card.dart';

/// Everything the view needs, computed from rows the store already loads.
class MasterySnapshot {
  const MasterySnapshot({
    required this.passed,
    required this.total,
    required this.perGamePassed,
    required this.missingByGame,
    this.resetAt,
    this.resetWord,
  });

  final int passed;
  final int total;
  final Map<GameType, int> perGamePassed;

  /// Words still missing a cell, per game, so the player can see why the next
  /// round picked what it picked.
  final Map<GameType, List<String>> missingByGame;

  /// When the current clean round was last wiped by an Again, and on which
  /// word. Null when the round has never been reset.
  final DateTime? resetAt;
  final String? resetWord;

  double get fraction => total == 0 ? 0 : passed / total;
  int get percent => (fraction * 100).round();

  /// Builds the snapshot from the passed-pair set the store returns plus the
  /// review log, which is where the reset is visible.
  factory MasterySnapshot.from({
    required List<Word> words,
    required Set<String> passedPairs,
    required List<ReviewLogEntry> recentReviews,
    required Map<int, String> headwordById,
  }) {
    final perGame = <GameType, int>{};
    final missing = <GameType, List<String>>{};
    for (final game in kMasteryGames) {
      var count = 0;
      final absent = <String>[];
      for (final word in words) {
        if (passedPairs.contains(masteryKey(word.id, game.name))) {
          count++;
        } else {
          absent.add(word.headword);
        }
      }
      perGame[game] = count;
      missing[game] = absent;
    }

    // The reset is the most recent Again in a mastery game: everything before
    // it stopped counting.
    ReviewLogEntry? reset;
    for (final entry in recentReviews) {
      if (entry.rating != Rating.again) continue;
      if (!kMasteryGameNames.contains(entry.gameType)) continue;
      if (reset == null || entry.ts.isAfter(reset.ts)) reset = entry;
    }

    final progress = masteryProgress(words: words, passedPairs: passedPairs);
    return MasterySnapshot(
      passed: progress.$1,
      total: progress.$2,
      perGamePassed: perGame,
      missingByGame: missing,
      resetAt: reset?.ts,
      resetWord: reset == null ? null : headwordById[reset.wordId],
    );
  }
}

class ProgressMasteryView extends StatelessWidget {
  const ProgressMasteryView({super.key, required this.snapshot});

  final MasterySnapshot snapshot;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('You Pass progress', style: theme.textTheme.titleMedium),
        Text(
          'ต้องตอบถูกทุกคำในทุกเกมหลัก โดยไม่ตอบผิดเลยในรอบเดียว',
          style: theme.textTheme.bodySmall,
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: HighlightCard(
                icon: Icons.grid_view,
                title: '${snapshot.passed}/${snapshot.total}',
                subtitle: 'ช่องที่ผ่าน',
                tone: HighlightTone.blue,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: HighlightCard(
                icon: Icons.percent,
                title: '${snapshot.percent}%',
                subtitle: 'ความคืบหน้า',
                tone: HighlightTone.sky,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: LinearProgressIndicator(
            value: snapshot.fraction,
            minHeight: 8,
          ),
        ),
        const SizedBox(height: 16),
        for (final game in kMasteryGames)
          _GameRow(
            game: game,
            passed: snapshot.perGamePassed[game] ?? 0,
            total: snapshot.total ~/ kMasteryGames.length,
            missing: snapshot.missingByGame[game] ?? const [],
          ),
        if (snapshot.resetAt != null) ...[
          const SizedBox(height: 12),
          _ResetNotice(at: snapshot.resetAt!, word: snapshot.resetWord),
        ],
      ],
    );
  }
}

class _GameRow extends StatelessWidget {
  const _GameRow({
    required this.game,
    required this.passed,
    required this.total,
    required this.missing,
  });

  final GameType game;
  final int passed;
  final int total;
  final List<String> missing;

  static const Map<GameType, String> _labels = {
    GameType.flashcard: 'Flashcard',
    GameType.matching: 'Matching',
    GameType.cloze: 'Cloze',
    GameType.dictation: 'Dictation',
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final done = missing.isEmpty;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                done ? Icons.check_circle : Icons.radio_button_unchecked,
                size: 18,
                color: done
                    ? theme.colorScheme.primary
                    : theme.colorScheme.outline,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  _labels[game] ?? game.name,
                  style: theme.textTheme.bodyMedium,
                ),
              ),
              Text('$passed/$total', style: theme.textTheme.bodyMedium),
            ],
          ),
          // Naming the missing words is the point: it explains why the next
          // round keeps serving this game.
          if (missing.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 26, top: 2),
              child: Text(
                missing.length <= 6
                    ? 'ยังขาด: ${missing.join(', ')}'
                    : 'ยังขาด ${missing.length} คำ เช่น ${missing.take(6).join(', ')}',
                style: theme.textTheme.bodySmall,
              ),
            ),
        ],
      ),
    );
  }
}

class _ResetNotice extends StatelessWidget {
  const _ResetNotice({required this.at, this.word});

  final DateTime at;
  final String? word;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final when =
        '${at.day}/${at.month} ${at.hour.toString().padLeft(2, '0')}:'
        '${at.minute.toString().padLeft(2, '0')}';
    return Card(
      color: scheme.errorContainer.withValues(alpha: 0.4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.restart_alt, size: 18, color: scheme.error),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                word == null
                    ? 'รอบสะอาดถูกรีเซ็ตเมื่อ $when เพราะมีคำตอบผิดในเกมหลัก'
                    : 'รอบสะอาดถูกรีเซ็ตเมื่อ $when เพราะตอบผิดที่คำว่า "$word"',
                style: theme.textTheme.bodySmall,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Compact one-line version for the Play screen.
class ProgressMasteryChip extends StatelessWidget {
  const ProgressMasteryChip({super.key, required this.snapshot, this.onTap});

  final MasterySnapshot snapshot;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      avatar: const Icon(Icons.grid_view, size: 16),
      label: Text('${snapshot.passed}/${snapshot.total} · ${snapshot.percent}%'),
      onPressed: onTap,
    );
  }
}
