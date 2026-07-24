/// Dictation (SPEC.md section 8 game 7, Phase 2). TTS speaks the headword;
/// the user types the spelling — listening + spelling + production,
/// mature-state words per SPEC.md section 7's ladder.
///
/// Uses the unified [buildHintLadder] (item 12, 2026-07-24): letter count →
/// closest known related word → first letter → meaning → first & last
/// letter, and no further. Using any step caps the rating at Hard via
/// `answer_checker.capForHint`.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/domain/hint_ladder.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/widgets/game_top_bar.dart';
import 'package:vocab_app/widgets/hint_ladder_view.dart';
import 'package:vocab_app/widgets/result_banner.dart';
import 'package:vocab_app/widgets/swipe_up_detector.dart';
import 'package:vocab_app/widgets/ui_prefs.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class DictationGame extends StatefulWidget {
  const DictationGame({
    super.key,
    required this.bundle,
    required this.tts,
    required this.onRated,
    this.similarKnownWord,
    this.checker = const AnswerChecker(),
  });

  final WordBundle bundle;
  final TtsService tts;
  final ValueChanged<Rating> onRated;

  /// Step-2 hint (item 12): closest known related word, or null.
  final String? similarKnownWord;
  final AnswerChecker checker;

  @override
  State<DictationGame> createState() => _DictationGameState();
}

class _DictationGameState extends State<DictationGame> {
  final _controller = TextEditingController();
  final _focus = FocusNode();
  final _stopwatch = Stopwatch()..start();
  late final List<String> _ladder;
  bool _submitted = false;
  int _hintStage = 0;
  AnswerCheckResult? _result;

  @override
  void initState() {
    super.initState();
    widget.tts.speak(widget.bundle.word.headword);
    _ladder = buildHintLadder(
      target: widget.bundle.word.headword,
      meaningTh: widget.bundle.coreSense.meaningTh,
      similarKnownWord: widget.similarKnownWord,
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _onSwipeUp() => !_submitted ? _submit() : _rate();

  void _toggleKeyboard() {
    autoKeyboardEnabled.value = !autoKeyboardEnabled.value;
    autoKeyboardEnabled.value ? _focus.requestFocus() : _focus.unfocus();
    setState(() {});
  }

  void _revealNextHint() {
    setState(() => _hintStage = (_hintStage + 1).clamp(0, _ladder.length));
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

    return SwipeUpDetector(
      onSwipeUp: _onSwipeUp,
      child: Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        GameTopBar(
          infoMessage: 'Listen, then type the spelling. Use the hint if '
              'stuck.\nSwipe up to submit, then again to continue.',
          keyboardEnabled: autoKeyboardEnabled.value,
          onToggleKeyboard: _toggleKeyboard,
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    IconButton.filled(
                      icon: const Icon(Icons.volume_up),
                      tooltip: 'Listen again',
                      onPressed: () => widget.tts.speak(word.headword),
                    ),
                    const SizedBox(width: 12),
                    // Slow-speech replay (user request 2026-07-23): same
                    // word at ~half rate so each phoneme is audible.
                    IconButton.filledTonal(
                      icon: const Icon(Icons.slow_motion_video),
                      tooltip: 'Slow',
                      onPressed: () => widget.tts.speakSlow(word.headword),
                    ),
                  ],
                ),
                // Faint instruction caption removed (user 2026-07-24) — the
                // "!" info affordance carries hints elsewhere; the two audio
                // buttons are self-explanatory.
                const SizedBox(height: 8),
                Text(sense.meaningTh, style: Theme.of(context).textTheme.titleMedium),
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
                      focusNode: _focus,
                      autofocus: autoKeyboardEnabled.value,
                      decoration: const InputDecoration(labelText: 'Type what you hear'),
                      onSubmitted: (_) => _submit(),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: HintLadderView(
                            stages: _ladder,
                            revealed: _hintStage,
                            onReveal: _revealNextHint,
                          ),
                        ),
                        const SizedBox(width: 8),
                        FilledButton(onPressed: _submit, child: const Text('Submit')),
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
                    FilledButton(onPressed: _rate, child: const Text('Next')),
                  ],
                ),
        ),
      ],
      ),
    );
  }
}
