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
import 'package:vocab_app/domain/hint_ladder.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/widgets/game_answer_field.dart';
import 'package:vocab_app/widgets/game_stage.dart';
import 'package:vocab_app/widgets/hint_ladder_view.dart';
import 'package:vocab_app/widgets/result_banner.dart';
import 'package:vocab_app/widgets/swipe_up_detector.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class ClozeGame extends StatefulWidget {
  const ClozeGame({
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
  State<ClozeGame> createState() => _ClozeGameState();
}

class _ClozeGameState extends State<ClozeGame> {
  final _controller = TextEditingController();
  final _stopwatch = Stopwatch()..start();
  bool _submitted = false;
  int _hintsRevealed = 0;
  AnswerCheckResult? _result;
  bool _showWrongReason = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onSwipeUp() => !_submitted ? _submit() : _rate();

  ExampleSentence get _sentence {
    final sentences = widget.bundle.sentences;
    // Prefer a non-rank-1 sentence for retrieval variety; fall back to any.
    return sentences.length > 1 ? sentences[1] : sentences.first;
  }

  /// Unified hint ladder for the missing word (item 12). Empty when there's
  /// no sentence to blank.
  List<String> get _ladder => widget.bundle.sentences.isEmpty
      ? const []
      : buildHintLadder(
          target: _sentence.clozeTarget,
          meaningTh: widget.bundle.coreSense.meaningTh,
          similarKnownWord: widget.similarKnownWord,
        );

  /// The `word_forms` row for the blank, when the blank was an inflection
  /// rather than the headword itself. Used only to label the form; the
  /// reasoning itself comes from the sentence's own explanation.
  WordForm? get _grammarForm {
    final target = _sentence.formUsed.toLowerCase();
    if (target.isEmpty ||
        target == widget.bundle.word.headword.toLowerCase()) {
      return null;
    }
    for (final f in widget.bundle.forms) {
      if (f.isInflection && f.formText.toLowerCase() == target) return f;
    }
    return null;
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
      _hintsRevealed = (_hintsRevealed + 1).clamp(0, _ladder.length);
    });
  }

  /// Listen to the sentence (user request 2026-07-23). Before answering,
  /// the blanked word is replaced with "blank" so the audio doesn't give
  /// the answer away; after the reveal it reads the full real sentence.
  void _speakSentence({bool slow = false}) {
    final s = _sentence;
    final text = _submitted
        ? s.enText
        : s.enText.replaceRange(s.clozeStart, s.clozeEnd, 'blank');
    slow ? widget.tts.speakSlow(text) : widget.tts.speak(text);
  }

  void _rate() {
    final base = _result!.rating;
    final capped = widget.checker.capForHint(
      base,
      usedHint: _hintsRevealed > 0,
    );
    widget.onRated(capped);
  }

  @override
  Widget build(BuildContext context) {
    if (widget.bundle.sentences.isEmpty) {
      return const Text('No example sentence for this word');
    }
    final s = _sentence;
    final before = s.enText.substring(0, s.clozeStart);
    final after = s.enText.substring(s.clozeEnd);

    return SwipeUpDetector(
      onSwipeUp: _onSwipeUp,
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
                    RichText(
                      textAlign: TextAlign.center,
                      text: TextSpan(
                        style: DefaultTextStyle.of(
                          context,
                        ).style.copyWith(fontSize: 18),
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
                    Text(
                      s.thText,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    const SizedBox(height: 4),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton.filled(
                          icon: const Icon(Icons.volume_up),
                          tooltip: 'Listen to the sentence',
                          onPressed: () => _speakSentence(),
                        ),
                        const SizedBox(width: 8),
                        IconButton.filledTonal(
                          icon: const Icon(Icons.slow_motion_video),
                          tooltip: 'Listen slowly',
                          onPressed: () => _speakSentence(slow: true),
                        ),
                      ],
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
                        GameAnswerField(
                          controller: _controller,
                          label: 'Type the answer',
                          onSubmitted: (_) => _submit(),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: HintLadderView(
                                stages: _ladder,
                                revealed: _hintsRevealed,
                                onReveal: _revealNextHint,
                              ),
                            ),
                            const SizedBox(width: 8),
                            FilledButton(
                              onPressed: _submit,
                              child: const Text('Submit'),
                            ),
                          ],
                        ),
                      ],
                    )
                  : Column(
                      key: const ValueKey('result'),
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        ResultBanner(
                          result: _result!,
                          correctText: s.clozeTarget,
                          onToggleDetails:
                              _result!.verdict == AnswerVerdict.wrong
                              ? () => setState(
                                  () => _showWrongReason = !_showWrongReason,
                                )
                              : null,
                          detailsExpanded: _showWrongReason,
                        ),
                        if (_result!.verdict != AnswerVerdict.wrong ||
                            _showWrongReason) ...[
                          const SizedBox(height: 8),
                          _SentenceReasonCard(
                            sentence: s,
                            form: _grammarForm,
                            headword: widget.bundle.word.headword,
                            answered: _controller.text.trim(),
                            wasWrong: _result!.verdict == AnswerVerdict.wrong,
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
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

/// The reveal's explanation. The text is the sentence's own `explanation_th`,
/// written when the content was built and stored per sentence — a player may
/// see this sentence and nothing else, so it never refers to another one. When
/// the answer was wrong, the card also names what the player typed instead, so
/// the mistake is concrete rather than just "incorrect".
class _SentenceReasonCard extends StatelessWidget {
  const _SentenceReasonCard({
    required this.sentence,
    required this.form,
    required this.headword,
    required this.answered,
    required this.wasWrong,
  });

  final ExampleSentence sentence;
  final WordForm? form;
  final String headword;
  final String answered;
  final bool wasWrong;

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
                Icon(Icons.menu_book, size: 18, color: scheme.primary),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'ทำไมถึงใช้ "${sentence.clozeTarget}"',
                    style: theme.textTheme.titleSmall,
                  ),
                ),
                if (form?.isIrregular ?? false)
                  Text(
                    'irregular',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: scheme.error,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
              ],
            ),
            if (form != null) ...[
              const SizedBox(height: 6),
              Text('$headword → ${form!.formText} (${form!.relation})'),
            ],
            if (sentence.explanationTh.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(sentence.explanationTh),
            ],
            if (wasWrong && answered.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'คุณตอบ "$answered" ซึ่งไม่ใช่รูปที่ประโยคนี้ต้องการ',
                style: theme.textTheme.bodySmall?.copyWith(color: scheme.error),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
