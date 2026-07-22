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
      pool.where((w) => w.id != correct.id && !excludeIds.contains(w.id)).toList()
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
    final capped = widget.checker.capForHint(base, usedHint: _hintsRevealed > 0);
    widget.onRated(capped);
  }

  @override
  Widget build(BuildContext context) {
    final word = widget.bundle.word;
    return Column(
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
                    Text(word.headword, style: Theme.of(context).textTheme.headlineSmall),
                    IconButton(
                      icon: const Icon(Icons.volume_up),
                      onPressed: () => widget.tts.speak(word.headword),
                    ),
                  ],
                ),
                Text(
                  'คำไหนที่คนส่วนใหญ่นึกถึงเมื่อเห็นคำนี้?',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          alignment: WrapAlignment.center,
          children: widget.options.map(_optionChip).toList(),
        ),
        const SizedBox(height: 8),
        if (!_submitted && widget.hintWords.isNotEmpty)
          TextButton.icon(
            onPressed: _hintsRevealed < widget.hintWords.length ? _revealNextHint : null,
            icon: const Icon(Icons.lightbulb_outline),
            label: Text(
              _hintsRevealed == 0
                  ? 'ใบ้'
                  : widget.hintWords.take(_hintsRevealed).join(', '),
            ),
          ),
        if (_submitted) ...[
          const SizedBox(height: 8),
          WordResultCard(
            bundle: widget.bundle,
            tts: widget.tts,
            onOpenDetail: () => Navigator.of(context).push(
              MaterialPageRoute(
                builder: (_) => WordDetailPage(bundle: widget.bundle, tts: widget.tts),
              ),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _rate, child: const Text('ถัดไป')),
        ],
      ],
    );
  }

  Widget _optionChip(Word w) {
    final selected = _selectedId == w.id;
    final isCorrect = w.id == widget.correctWordId;
    Color? color;
    if (_submitted && selected) {
      color = isCorrect ? Colors.green.withValues(alpha: 0.4) : Colors.red.withValues(alpha: 0.4);
    } else if (_submitted && isCorrect) {
      color = Colors.green.withValues(alpha: 0.2);
    }
    return ChoiceChip(
      label: Text(w.headword),
      selected: selected,
      selectedColor: color,
      backgroundColor: color,
      onSelected: _submitted ? null : (_) => _select(w.id),
    );
  }
}
