/// Word Scramble (SPEC.md section 8 game 5, Phase 2). The headword's
/// letters are shuffled; the user retypes the word — a pure production
/// task (desirable difficulty), used for mature-state words per SPEC.md
/// section 7's ladder. Uses `answer_checker` for typo-tolerant grading and
/// supports the family-A semantic hint (SPEC.md 8b) with a progressive
/// reveal button, same pattern as Cloze/Word Association.
library;

import 'dart:math';

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/widgets/result_banner.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

/// Shuffles [word]'s letters. Guarantees the result differs from the
/// original whenever that's actually possible (retries up to 20 times);
/// words of length <= 1, or made entirely of one repeated letter, can't
/// produce a different permutation, so those are returned unscrambled
/// rather than looping forever.
String scrambleWord(String word, {Random? random}) {
  if (word.length <= 1) return word;
  final rnd = random ?? Random();
  final chars = word.split('');
  var shuffled = List<String>.from(chars);
  var attempts = 0;
  do {
    shuffled = List<String>.from(chars)..shuffle(rnd);
    attempts++;
  } while (shuffled.join() == word && attempts < 20);
  return shuffled.join();
}

class WordScrambleGame extends StatefulWidget {
  const WordScrambleGame({
    super.key,
    required this.bundle,
    required this.tts,
    required this.onRated,
    this.hintWords = const [],
    this.checker = const AnswerChecker(),
    this.random,
  });

  final WordBundle bundle;
  final TtsService tts;
  final ValueChanged<Rating> onRated;
  final List<String> hintWords;
  final AnswerChecker checker;

  /// Injectable for deterministic tests; null uses a real [Random].
  final Random? random;

  @override
  State<WordScrambleGame> createState() => _WordScrambleGameState();
}

class _WordScrambleGameState extends State<WordScrambleGame> {
  final _controller = TextEditingController();
  final _stopwatch = Stopwatch()..start();
  late final String _scrambled;
  bool _submitted = false;
  int _hintsRevealed = 0;
  AnswerCheckResult? _result;

  @override
  void initState() {
    super.initState();
    _scrambled = scrambleWord(widget.bundle.word.headword, random: widget.random);
  }

  void _revealNextHint() {
    setState(() {
      _hintsRevealed = (_hintsRevealed + 1).clamp(0, widget.hintWords.length);
    });
  }

  void _submit() {
    _stopwatch.stop();
    final result = widget.checker.check(
      userInput: _controller.text,
      expected: widget.bundle.word.headword,
      elapsedMs: _stopwatch.elapsedMilliseconds,
    );
    setState(() {
      _submitted = true;
      _result = result;
    });
  }

  void _rate() {
    final capped = widget.checker.capForHint(
      _result!.rating,
      usedHint: _hintsRevealed > 0,
    );
    widget.onRated(capped);
  }

  @override
  Widget build(BuildContext context) {
    final sense = widget.bundle.coreSense;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                Wrap(
                  alignment: WrapAlignment.center,
                  spacing: 6,
                  children: [
                    for (var i = 0; i < _scrambled.length; i++)
                      _LetterTile(letter: _scrambled[i], index: i),
                  ],
                ),
                const SizedBox(height: 12),
                Text(sense.meaningTh, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 260),
          transitionBuilder: (child, anim) => FadeTransition(
            opacity: anim,
            child: SizeTransition(sizeFactor: anim, child: child),
          ),
          child: !_submitted
              ? Column(
                  key: const ValueKey('input'),
                  children: [
                    TextField(
                      controller: _controller,
                      decoration: const InputDecoration(labelText: 'เรียงตัวอักษรใหม่'),
                      onSubmitted: (_) => _submit(),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        if (widget.hintWords.isNotEmpty)
                          TextButton.icon(
                            onPressed: _hintsRevealed < widget.hintWords.length
                                ? _revealNextHint
                                : null,
                            icon: const Icon(Icons.lightbulb_outline),
                            label: Text(
                              _hintsRevealed == 0
                                  ? 'ใบ้'
                                  : widget.hintWords.take(_hintsRevealed).join(', '),
                            ),
                          ),
                        FilledButton(onPressed: _submit, child: const Text('ตอบ')),
                      ],
                    ),
                  ],
                )
              : Column(
                  key: const ValueKey('result'),
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    ResultBanner(result: _result!, correctText: widget.bundle.word.headword),
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
                ),
        ),
      ],
    );
  }
}

/// A single scrambled letter, staggered fade+scale entrance per tile index
/// so the scrambled word reads as a deliberately shuffled set of tiles
/// rather than a static string.
class _LetterTile extends StatelessWidget {
  const _LetterTile({required this.letter, required this.index});

  final String letter;
  final int index;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 260 + index * 40),
      curve: Curves.easeOutBack,
      builder: (context, t, child) => Opacity(
        opacity: t.clamp(0, 1),
        child: Transform.scale(scale: t.clamp(0, 1.2), child: child),
      ),
      child: Container(
        width: 40,
        height: 44,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: scheme.outline, width: 1),
        ),
        child: Text(
          letter.toUpperCase(),
          style: Theme.of(
            context,
          ).textTheme.titleLarge?.copyWith(letterSpacing: 0),
        ),
      ),
    );
  }
}
