/// Dictation (SPEC.md section 8 game 7, Phase 2). TTS speaks the headword;
/// the user types the spelling — listening + spelling + production,
/// mature-state words per SPEC.md section 7's ladder.
///
/// Implements the family-B spelling hint (SPEC.md 8b): unlike family A,
/// related words don't help here ("รู้อยู่แล้วว่าคำไหน ความยากอยู่ที่สะกดถูก
/// ไหม"), so the hint is generated at runtime from the headword itself, no
/// pre-stored data needed. Progressive reveal, opened one step at a time
/// (section 12 "เปิดทีละขั้น"): syllable-split skeleton first, then letters
/// revealed left-to-right one at a time, then (once every letter is
/// already visible) a bare letter-count as the final fallback stage.
/// Same as every hint family, using it caps the eventual rating at Hard via
/// `answer_checker.capForHint`, even on a correct answer.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/widgets/result_banner.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

/// Pure spelling-hint logic for Dictation, kept as static helpers so it's
/// directly unit-testable without spinning up the widget.
class DictationHint {
  const DictationHint._();

  /// English has no dedicated syllable-boundary field in the schema, so
  /// this approximates syllable count from `thai_reading`'s hyphen-split
  /// count (e.g. "แอน-เซอร์" -> 2) and naively divides the headword into
  /// that many roughly-equal chunks. Falls back to treating the whole word
  /// as one chunk when [thaiReading] has no hyphens (or is empty).
  static List<String> syllableSkeleton(String headword, String thaiReading) {
    final count = thaiReading.contains('-')
        ? thaiReading.split('-').where((s) => s.isNotEmpty).length
        : 1;
    return _splitInto(headword, count.clamp(1, headword.isEmpty ? 1 : headword.length));
  }

  static List<String> _splitInto(String word, int parts) {
    if (parts <= 1 || word.isEmpty) return [word];
    final base = word.length ~/ parts;
    final extra = word.length % parts;
    final chunks = <String>[];
    var idx = 0;
    for (var i = 0; i < parts; i++) {
      final len = base + (i < extra ? 1 : 0);
      chunks.add(word.substring(idx, idx + len));
      idx += len;
    }
    return chunks;
  }

  /// Total number of distinct hint stages available for [headword]: one
  /// syllable-skeleton stage, one stage per letter revealed, plus one final
  /// letter-count stage.
  static int maxStage(String headword) => headword.isEmpty ? 1 : headword.length + 2;

  /// The hint text to show at [stage] (1-indexed; stage 0 / below means "no
  /// hint yet", handled by the caller not calling this).
  /// - stage 1: syllable skeleton, e.g. "___-____" (letters hidden, hyphens
  ///   mark syllable boundaries).
  /// - stage 2..N: letters revealed left-to-right, one more per stage.
  /// - final stage (once every letter is already revealed by the stage
  ///   above): bare letter count, e.g. "6 ตัวอักษร" — SPEC.md 8b lists this
  ///   as one of the three hint contents; by the time every letter is
  ///   already shown it adds little, but it's kept as the natural last
  ///   step of the progression rather than silently dropped (documented in
  ///   NOTES.md).
  static String stageText(String headword, String thaiReading, int stage) {
    if (stage <= 0 || headword.isEmpty) return '';
    if (stage == 1) {
      final syllables = syllableSkeleton(headword, thaiReading);
      return syllables.map((s) => '_' * s.length).join('-');
    }
    final revealCount = stage - 1;
    if (revealCount >= headword.length) {
      return '${headword.length} ตัวอักษร';
    }
    final revealed = headword.substring(0, revealCount);
    final hidden = '_' * (headword.length - revealCount);
    return '$revealed$hidden';
  }
}

class DictationGame extends StatefulWidget {
  const DictationGame({
    super.key,
    required this.bundle,
    required this.tts,
    required this.onRated,
    this.checker = const AnswerChecker(),
  });

  final WordBundle bundle;
  final TtsService tts;
  final ValueChanged<Rating> onRated;
  final AnswerChecker checker;

  @override
  State<DictationGame> createState() => _DictationGameState();
}

class _DictationGameState extends State<DictationGame> {
  final _controller = TextEditingController();
  final _stopwatch = Stopwatch()..start();
  bool _submitted = false;
  int _hintStage = 0;
  AnswerCheckResult? _result;

  @override
  void initState() {
    super.initState();
    widget.tts.speak(widget.bundle.word.headword);
  }

  void _revealNextHint() {
    final max = DictationHint.maxStage(widget.bundle.word.headword);
    setState(() => _hintStage = (_hintStage + 1).clamp(0, max));
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
      usedHint: _hintStage > 0,
    );
    widget.onRated(capped);
  }

  @override
  Widget build(BuildContext context) {
    final word = widget.bundle.word;
    final sense = widget.bundle.coreSense;
    final maxStage = DictationHint.maxStage(word.headword);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                IconButton.filled(
                  icon: const Icon(Icons.volume_up),
                  onPressed: () => widget.tts.speak(word.headword),
                ),
                Text('ฟังแล้วพิมพ์สะกดคำ', style: Theme.of(context).textTheme.bodyMedium),
                const SizedBox(height: 8),
                Text(sense.meaningTh, style: Theme.of(context).textTheme.titleMedium),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 220),
                  transitionBuilder: (child, anim) => FadeTransition(
                    opacity: anim,
                    child: SizeTransition(sizeFactor: anim, child: child),
                  ),
                  child: _hintStage > 0
                      ? Padding(
                          key: ValueKey(_hintStage),
                          padding: const EdgeInsets.only(top: 8),
                          child: Text(
                            DictationHint.stageText(word.headword, word.thaiReading, _hintStage),
                            style: Theme.of(
                              context,
                            ).textTheme.titleLarge?.copyWith(letterSpacing: 2),
                          ),
                        )
                      : const SizedBox.shrink(),
                ),
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
                      decoration: const InputDecoration(labelText: 'พิมพ์คำที่ได้ยิน'),
                      onSubmitted: (_) => _submit(),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        TextButton.icon(
                          onPressed: _hintStage < maxStage ? _revealNextHint : null,
                          icon: const Icon(Icons.lightbulb_outline),
                          label: const Text('ใบ้'),
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
                    ResultBanner(result: _result!, correctText: word.headword),
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
