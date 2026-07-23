/// New-word intro card (SPEC.md section 9.1). Not a game — just encoding:
/// image (if any) + TTS + headword + Thai reading + core meaning. The
/// rank=1 (emotional) example sentence is hidden behind a reveal button.
/// Swiping through is unforced; the word enters the FSRS queue regardless,
/// due next morning per the sleep-gap.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class WordIntroPage extends StatefulWidget {
  const WordIntroPage({
    super.key,
    required this.bundle,
    required this.tts,
    required this.onContinue,
  });

  final WordBundle bundle;
  final TtsService tts;
  final VoidCallback onContinue;

  @override
  State<WordIntroPage> createState() => _WordIntroPageState();
}

class _WordIntroPageState extends State<WordIntroPage> {
  bool _showExample = false;

  @override
  void initState() {
    super.initState();
    widget.tts.speak(widget.bundle.word.headword);
  }

  @override
  Widget build(BuildContext context) {
    final rank1 = widget.bundle.sentences.isNotEmpty
        ? widget.bundle.sentences.first
        : null;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Chip(label: Text('คำใหม่ · ${widget.bundle.word.cefr}')),
        const SizedBox(height: 12),
        WordResultCard(
          bundle: widget.bundle,
          tts: widget.tts,
          onOpenDetail: () => Navigator.of(context).push(
            MaterialPageRoute(
              builder: (_) => WordDetailPage(bundle: widget.bundle, tts: widget.tts),
            ),
          ),
        ),
        const SizedBox(height: 12),
        if (rank1 != null)
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 260),
            transitionBuilder: (child, anim) => FadeTransition(
              opacity: anim,
              child: SizeTransition(sizeFactor: anim, child: child),
            ),
            child: !_showExample
                ? OutlinedButton(
                    key: const ValueKey('reveal-button'),
                    onPressed: () => setState(() => _showExample = true),
                    child: const Text('ดูตัวอย่างประโยค'),
                  )
                : Card(
                    key: const ValueKey('example'),
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        children: [
                          Text(rank1.enText),
                          Text(rank1.thText, style: Theme.of(context).textTheme.bodySmall),
                        ],
                      ),
                    ),
                  ),
          ),
        const SizedBox(height: 20),
        FilledButton(onPressed: widget.onContinue, child: const Text('ต่อไป')),
      ],
    );
  }
}
