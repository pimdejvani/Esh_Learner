/// Cloze (SPEC.md section 8 game 2). Real example sentence with the target
/// word blanked out; user types the answer. Uses answer_checker for
/// typo-tolerant grading and supports the family-A hint (related word) per
/// section 8b: a progressive "reveal next hint" button (tappable multiple
/// times, section 12 "เปิดทีละขั้น") that surfaces one more `hintWords`
/// entry per tap, capping the rating at Hard if any hint was used.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/widgets/result_banner.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class ClozeGame extends StatefulWidget {
  const ClozeGame({
    super.key,
    required this.bundle,
    required this.tts,
    required this.onRated,
    this.hintWords = const [],
    this.checker = const AnswerChecker(),
  });

  final WordBundle bundle;
  final TtsService tts;
  final ValueChanged<Rating> onRated;
  final List<String> hintWords;
  final AnswerChecker checker;

  @override
  State<ClozeGame> createState() => _ClozeGameState();
}

class _ClozeGameState extends State<ClozeGame> {
  final _controller = TextEditingController();
  final _stopwatch = Stopwatch()..start();
  bool _submitted = false;
  int _hintsRevealed = 0;
  AnswerCheckResult? _result;

  ExampleSentence get _sentence {
    final sentences = widget.bundle.sentences;
    // Prefer a non-rank-1 sentence for retrieval variety; fall back to any.
    return sentences.length > 1 ? sentences[1] : sentences.first;
  }

  void _submit() {
    if (widget.bundle.sentences.isEmpty) return;
    _stopwatch.stop();
    final expected = _sentence.clozeTarget;
    final result = widget.checker.check(
      userInput: _controller.text,
      expected: expected,
      elapsedMs: _stopwatch.elapsedMilliseconds,
    );
    setState(() {
      _submitted = true;
      _result = result;
    });
  }

  void _revealNextHint() {
    setState(() {
      _hintsRevealed = (_hintsRevealed + 1).clamp(0, widget.hintWords.length);
    });
  }

  void _rate() {
    final base = _result!.rating;
    final capped = widget.checker.capForHint(base, usedHint: _hintsRevealed > 0);
    widget.onRated(capped);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.bundle.sentences.isEmpty) {
      return const Text('ไม่มีประโยคตัวอย่างสำหรับคำนี้');
    }
    final s = _sentence;
    final before = s.enText.substring(0, s.clozeStart);
    final after = s.enText.substring(s.clozeEnd);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                RichText(
                  text: TextSpan(
                    style: DefaultTextStyle.of(context).style.copyWith(fontSize: 18),
                    children: [
                      TextSpan(text: before),
                      const TextSpan(
                        text: ' _____ ',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      TextSpan(text: after),
                    ],
                  ),
                ),
                const SizedBox(height: 8),
                Text(s.thText, style: Theme.of(context).textTheme.bodySmall),
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
                      decoration: const InputDecoration(labelText: 'พิมพ์คำตอบ'),
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
                            label: AnimatedSwitcher(
                              duration: const Duration(milliseconds: 200),
                              child: Text(
                                _hintsRevealed == 0
                                    ? 'ใบ้'
                                    : widget.hintWords.take(_hintsRevealed).join(', '),
                                key: ValueKey(_hintsRevealed),
                              ),
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
                    ResultBanner(result: _result!, correctText: s.clozeTarget),
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
