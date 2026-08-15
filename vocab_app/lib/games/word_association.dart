/// Word Association (SPEC.md section 8 game 4, Phase 2). Links the target
/// word to the related word most people associate with it (per the
/// SWOW-style `related_words` data — see SPEC.md sections 4/5/13), picked
/// from a small multiple-choice set of distractor words. Testing/retrieval
/// game for young-state words (SPEC.md section 7 ladder).
///
/// Supports the family-A semantic hint (SPEC.md 8b) with a progressive
/// "reveal next hint" button — each tap surfaces one more (weaker) related
/// word, and using the hint at all caps the eventual rating at Hard via
/// `answer_checker.capForHint`, same rule as every other family-A game.
library;

import 'dart:math';

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/theme/app_theme.dart';
import 'package:vocab_app/widgets/speak_buttons.dart';
import 'package:vocab_app/widgets/staggered_entrance.dart';
import 'package:vocab_app/widgets/swipe_up_detector.dart';
import 'package:vocab_app/widgets/game_stage.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

/// Picks the related word to test this round: prefers `relation_type ==
/// 'association'` (the SWOW-style human free-association data per SPEC.md
/// 5/13) and always excludes `is_giveaway` rows (those are reserved as
/// "never a fair guess" per SPEC.md 8b). Among the remaining candidates,
/// the strongest (`closeness` highest) association wins, since that's the
/// clearest, least-ambiguous "correct" link for a multiple-choice round.
/// Returns null when there's nothing usable yet (e.g. the word has no
/// related_words rows at all).
RelatedWord? pickAssociationTarget(List<RelatedWord> related) {
  final candidates = related.where((r) => !r.isGiveaway).toList();
  if (candidates.isEmpty) return null;
  final associationOnly = candidates
      .where((r) => r.relationType == 'association')
      .toList();
  final pool = associationOnly.isNotEmpty ? associationOnly : candidates;
  pool.sort((a, b) => b.closeness.compareTo(a.closeness));
  return pool.first;
}

/// Builds the shuffled multiple-choice options for a round: [correct] plus
/// up to [distractorCount] other words drawn from [pool], excluding
/// anything in [excludeIds] (the target itself and its other related words,
/// so no distractor is ambiguously "also kind of right").
List<Word> buildAssociationOptions({
  required Word correct,
  required List<Word> pool,
  required Set<int> excludeIds,
  int distractorCount = 3,
  Random? random,
}) {
  final rnd = random ?? Random();
  final candidates =
      pool
          .where((w) => w.id != correct.id && !excludeIds.contains(w.id))
          .toList()
        ..shuffle(rnd);
  final options = [correct, ...candidates.take(distractorCount)];
  options.shuffle(rnd);
  return options;
}

class WordAssociationGame extends StatefulWidget {
  const WordAssociationGame({
    super.key,
    required this.bundle,
    required this.options,
    required this.correctWordId,
    required this.tts,
    required this.onRated,
    this.hintWords = const [],
    this.checker = const AnswerChecker(),
    this.correctRelation,
  });

  /// Target word being tested.
  final WordBundle bundle;

  /// Multiple-choice options (already shuffled by the caller — see
  /// [buildAssociationOptions]), one of which is [correctWordId].
  final List<Word> options;
  final int correctWordId;
  final TtsService tts;
  final ValueChanged<Rating> onRated;

  /// Family-A semantic hint candidates, ordered strongest-first (see
  /// play_screen.dart for how these are sourced from `related_words`).
  final List<String> hintWords;
  final AnswerChecker checker;

  /// The `related_words` row the round was built from. Its `relationType` and
  /// stored `explanationTh` are what the reveal shows — the reason is content,
  /// written when the pair was built, never composed at answer time.
  final RelatedWord? correctRelation;

  @override
  State<WordAssociationGame> createState() => _WordAssociationGameState();
}

class _WordAssociationGameState extends State<WordAssociationGame> {
  final _stopwatch = Stopwatch()..start();
  int? _selectedId;
  bool _submitted = false;
  int _hintsRevealed = 0;

  void _select(int wordId) {
    if (_submitted) return;
    _stopwatch.stop();
    setState(() {
      _selectedId = wordId;
      _submitted = true;
    });
  }

  void _revealNextHint() {
    setState(() {
      _hintsRevealed = (_hintsRevealed + 1).clamp(0, widget.hintWords.length);
    });
  }

  void _rate() {
    final correct = _selectedId == widget.correctWordId;
    final fast = _stopwatch.elapsedMilliseconds <= 3000;
    final base = correct ? (fast ? Rating.easy : Rating.good) : Rating.again;
    final capped = widget.checker.capForHint(
      base,
      usedHint: _hintsRevealed > 0,
    );
    widget.onRated(capped);
  }

  @override
  Widget build(BuildContext context) {
    final word = widget.bundle.word;
    return SwipeUpDetector(
      onSwipeUp: () {
        if (_submitted) _rate();
      },
      child: GameStage(
        onTapToContinue: _submitted ? _rate : null,
        bottomAction: _submitted
            ? FilledButton(onPressed: _rate, child: const Text('Next'))
            : null,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          word.headword,
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                        SpeakButtons(tts: widget.tts, text: word.headword),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                for (var i = 0; i < widget.options.length; i++)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: StaggeredEntrance(
                      index: i,
                      child: _optionChip(widget.options[i]),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            if (!_submitted && widget.hintWords.isNotEmpty)
              TextButton.icon(
                onPressed: _hintsRevealed < widget.hintWords.length
                    ? _revealNextHint
                    : null,
                icon: const Icon(Icons.lightbulb_outline),
                label: Text(
                  _hintsRevealed == 0
                      ? 'Hint'
                      : widget.hintWords.take(_hintsRevealed).join(', '),
                ),
              ),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 260),
              transitionBuilder: (child, anim) => FadeTransition(
                opacity: anim,
                child: SizeTransition(sizeFactor: anim, child: child),
              ),
              child: _submitted
                  ? Column(
                      key: const ValueKey('result'),
                      children: [
                        if (widget.correctRelation != null) ...[
                          const SizedBox(height: 8),
                          _RelationReveal(
                            headword: widget.bundle.word.headword,
                            relation: widget.correctRelation!,
                          ),
                        ],
                        const SizedBox(height: 8),
                        WordResultCard(
                          bundle: widget.bundle,
                          tts: widget.tts,
                          onOpenDetail: () => Navigator.of(context).push(
                            MaterialPageRoute(
                              builder: (_) => WordDetailPage(
                                bundle: widget.bundle,
                                tts: widget.tts,
                              ),
                            ),
                          ),
                        ),
                      ],
                    )
                  : const SizedBox.shrink(key: ValueKey('empty')),
            ),
          ],
        ),
      ),
    );
  }

  Widget _optionChip(Word w) {
    final colors = context.appColors;
    final selected = _selectedId == w.id;
    final isCorrect = w.id == widget.correctWordId;
    Color? color;
    Widget? avatar;
    if (_submitted && selected) {
      color = isCorrect
          ? colors.success.withValues(alpha: 0.35)
          : colors.danger.withValues(alpha: 0.35);
      // Explicit right/wrong icon on the picked chip (user 2026-07-24:
      // a wrong answer must show a cross, not read as correct).
      avatar = Icon(
        isCorrect ? Icons.check_circle : Icons.cancel,
        size: 18,
        color: isCorrect ? colors.success : colors.danger,
      );
    } else if (_submitted && isCorrect) {
      color = colors.success.withValues(alpha: 0.18);
      avatar = Icon(Icons.check_circle, size: 18, color: colors.success);
    }
    // Full-width, generously padded options (user request 2026-07-24: "ทำให้
    // ปุ่มที่เลือกคำที่เกี่ยวข้องมันใหญ่ขึ้นกว่านี้") — the compact chips
    // were a small tap target sitting in a lot of empty space.
    return AnimatedContainer(
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOut,
      width: double.infinity,
      child: ChoiceChip(
        avatar: avatar,
        labelPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
        label: Text(
          w.headword,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        selected: selected,
        selectedColor: color,
        backgroundColor: color,
        onSelected: _submitted ? null : (_) => _select(w.id),
      ),
    );
  }
}

/// The answer's reason: the correct word, the relation type, and the stored
/// Thai explanation of why the pair belongs together.
class _RelationReveal extends StatelessWidget {
  const _RelationReveal({required this.headword, required this.relation});

  final String headword;
  final RelatedWord relation;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Card(
      color: scheme.secondaryContainer.withValues(alpha: 0.5),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '$headword → ${relation.relatedHeadword}',
                    style: theme.textTheme.titleSmall,
                  ),
                ),
                Text(
                  relation.relationType,
                  style: theme.textTheme.labelSmall
                      ?.copyWith(color: scheme.primary),
                ),
              ],
            ),
            if ((relation.explanationTh ?? '').isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(relation.explanationTh!),
            ],
          ],
        ),
      ),
    );
  }
}
