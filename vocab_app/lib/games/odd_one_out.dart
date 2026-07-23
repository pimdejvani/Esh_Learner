/// Odd One Out (SPEC.md section 8 game 6, Phase 2). A group of words is
/// shown; one ([oddWord]) doesn't belong with the rest ([groupWords]) —
/// semantic categorization, a recognition-level task per SPEC.md section
/// 7's ladder (learning-state words, alongside flashcard/Matching). No
/// hint system: SPEC.md 8b's two hint families are for retrieval-from-cue
/// (Cloze/flashcard-production/Scramble/Word Association) and spelling
/// (Dictation) respectively — categorization recognition isn't either.
library;

import 'dart:math';

import 'package:flutter/material.dart';

import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/theme/app_theme.dart';
import 'package:vocab_app/widgets/staggered_entrance.dart';

/// Builds an odd-one-out round: finds a "hub" word whose `related_words`
/// rows (any word_id in [relatedByWord]) name at least [groupSize] other
/// words in [pool] that (a) aren't [target] and (b) aren't themselves
/// related to [target] — i.e. a coherent group that [target] genuinely
/// doesn't belong to.
///
/// 2026-07-24 revision (user feedback "กลุ่มคำรู้สึกไม่ค่อยเหมือนกัน"):
/// - **One consistent coherence bar**: a row only counts as "same group"
///   when it's typed category data (`hypernym`/`category`/`part_of`) OR
///   its SWOW `closeness` ≥ [minCloseness]. Default 0.036 — started at
///   0.03 (≈ p75 of the seed's association strengths), raised +20% on
///   user feedback 2026-07-24 ("คำยังไม่เข้ากันเท่าที่ควร ปรับเพิ่มอีก
///   20%").
/// - **Minimum 3 group members**: the old fallback to a 2-word group is
///   gone. Fewer than [groupSize] strong members = no Odd round (caller
///   re-routes to flashcard).
/// - **[strict] early-game mode** (the player's first ~2 new-word blocks,
///   ~8 words): require MORE THAN 2 qualifying groups to choose from —
///   fewer means the data around today's words is too thin to guarantee
///   a clean round, so skip Odd entirely. Beyond that the normal rules
///   above apply.
/// - Any group above the bar is fair game: [random] (when given) picks
///   uniformly among ALL qualifying groups — passing the threshold is
///   the quality gate, no extra ranking needed (user 2026-07-24 "ถ้ามี
///   กลุ่มที่คะแนนเกินเกณฑ์ก็สุ่มกลุ่มได้เลย"). Without [random] the
///   best-scoring group is returned (deterministic for tests).
///
/// Returns null when no hub qualifies — callers should skip/re-route the
/// round rather than force a bad one.
List<Word>? buildOddOneOutGroup({
  required Word target,
  required List<Word> pool,
  required Map<int, List<RelatedWord>> relatedByWord,
  int groupSize = 3,
  double minCloseness = 0.036,
  bool strict = false,
  Random? random,
}) {
  const preferredTypes = {'hypernym', 'category', 'part_of'};
  final poolById = {for (final w in pool) w.id: w};

  final candidates = <(double, List<Word>)>[];
  for (final hub in relatedByWord.entries) {
    if (hub.key == target.id) continue;
    if (hub.value.any((r) => r.relatedWordId == target.id)) {
      continue; // target IS related to this hub -> not a fair "odd one"
    }
    final rows = hub.value.where((r) {
      if (r.isGiveaway) return false;
      return preferredTypes.contains(r.relationType) ||
          r.closeness >= minCloseness;
    }).toList()
      ..sort((a, b) => b.closeness.compareTo(a.closeness));
    final seen = <int>{};
    final members = <RelatedWord>[];
    for (final r in rows) {
      if (r.relatedWordId == target.id) continue;
      if (!poolById.containsKey(r.relatedWordId)) continue;
      if (!seen.add(r.relatedWordId)) continue;
      members.add(r);
    }
    if (members.length < groupSize) continue;
    final top = members.take(groupSize).toList();
    final score = top.fold(0.0, (s, r) => s + r.closeness);
    candidates.add((score, [for (final r in top) poolById[r.relatedWordId]!]));
  }

  if (candidates.isEmpty) return null;
  if (strict && candidates.length <= 2) return null;
  if (random != null) return candidates[random.nextInt(candidates.length)].$2;
  candidates.sort((a, b) => b.$1.compareTo(a.$1));
  return candidates.first.$2;
}

class OddOneOutGame extends StatefulWidget {
  const OddOneOutGame({
    super.key,
    required this.oddWord,
    required this.groupWords,
    required this.onRated,
  });

  /// The word actually being tested (the true "odd one out").
  final Word oddWord;

  /// The words that belong together (distractors).
  final List<Word> groupWords;

  /// Called once with the target's rating and, on a wrong answer, the id
  /// of the group word the player wrongly picked (null when correct) —
  /// user request 2026-07-24: a wrong pick should also cost the PICKED
  /// word's proficiency, not just the target's.
  final void Function(Rating rating, int? wrongPickedWordId) onRated;

  @override
  State<OddOneOutGame> createState() => _OddOneOutGameState();
}

class _OddOneOutGameState extends State<OddOneOutGame> {
  final _stopwatch = Stopwatch()..start();
  late final List<Word> _options;
  int? _selectedId;
  bool _submitted = false;

  @override
  void initState() {
    super.initState();
    _options = [widget.oddWord, ...widget.groupWords]..shuffle();
  }

  void _select(int wordId) {
    if (_submitted) return;
    _stopwatch.stop();
    setState(() {
      _selectedId = wordId;
      _submitted = true;
    });
  }

  void _rate() {
    final correct = _selectedId == widget.oddWord.id;
    final fast = _stopwatch.elapsedMilliseconds <= 3000;
    widget.onRated(
      correct ? (fast ? Rating.easy : Rating.good) : Rating.again,
      correct ? null : _selectedId,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(
          'คำไหนไม่เข้าพวก?',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          alignment: WrapAlignment.center,
          children: [
            for (var i = 0; i < _options.length; i++)
              StaggeredEntrance(index: i, child: _optionChip(_options[i])),
          ],
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
                    const SizedBox(height: 16),
                    Text(
                      _selectedId == widget.oddWord.id
                          ? 'ถูกต้อง! "${widget.oddWord.headword}" ไม่เข้าพวก'
                          : 'คำที่ไม่เข้าพวกคือ "${widget.oddWord.headword}"',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 16),
                    FilledButton(onPressed: _rate, child: const Text('ถัดไป')),
                  ],
                )
              : const SizedBox.shrink(key: ValueKey('empty')),
        ),
      ],
    );
  }

  Widget _optionChip(Word w) {
    final colors = context.appColors;
    final selected = _selectedId == w.id;
    final isOdd = w.id == widget.oddWord.id;
    Color? color;
    Widget? avatar;
    if (_submitted && selected) {
      color = isOdd
          ? colors.success.withValues(alpha: 0.35)
          : colors.danger.withValues(alpha: 0.35);
      // Explicit right/wrong icon on the chip the player chose (user
      // feedback 2026-07-24 — the color alone read as "correct").
      avatar = Icon(
        isOdd ? Icons.check_circle : Icons.cancel,
        size: 18,
        color: isOdd ? colors.success : colors.danger,
      );
    } else if (_submitted && isOdd) {
      color = colors.success.withValues(alpha: 0.18);
      avatar = Icon(Icons.check_circle, size: 18, color: colors.success);
    }
    return ChoiceChip(
      avatar: avatar,
      label: Text(w.headword),
      selected: selected,
      selectedColor: color,
      backgroundColor: color,
      onSelected: _submitted ? null : (_) => _select(w.id),
    );
  }
}
