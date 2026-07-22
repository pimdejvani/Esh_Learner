/// Shared "after answer" mini dictionary-entry widget — SPEC.md 9b layer 1
/// (headword + Thai reading with bold stress syllable + CEFR/POS badges +
/// core sense + one example sentence + TTS button). Shown after every game
/// reveals its answer, tap-through to full entry deferred to Phase 2 per
/// spec ("แตะการ์ดเพื่อเปิด entry เต็ม — ไม่บังคับ").
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/word.dart';

class WordResultCard extends StatelessWidget {
  const WordResultCard({
    super.key,
    required this.bundle,
    required this.tts,
    this.sentenceIndex = 0,
  });

  final WordBundle bundle;
  final TtsService tts;
  final int sentenceIndex;

  @override
  Widget build(BuildContext context) {
    final word = bundle.word;
    final sense = bundle.coreSense;
    final sentence = bundle.sentences.isNotEmpty
        ? bundle.sentences[sentenceIndex.clamp(0, bundle.sentences.length - 1)]
        : null;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Text(
                  word.headword,
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.volume_up),
                  onPressed: () => tts.speak(word.headword),
                ),
              ],
            ),
            _StressedReading(reading: word.thaiReading, stress: word.stressIndex),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              children: [
                Chip(label: Text(word.cefr)),
                Chip(label: Text(sense.pos.toUpperCase())),
                if (sense.countable == 1) const Chip(label: Text('นับได้')),
                if (sense.countable == 0) const Chip(label: Text('นับไม่ได้')),
              ],
            ),
            const SizedBox(height: 8),
            Text(sense.meaningTh, style: Theme.of(context).textTheme.titleMedium),
            if (sentence != null) ...[
              const SizedBox(height: 12),
              Text(sentence.enText),
              Text(
                sentence.thText,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _StressedReading extends StatelessWidget {
  const _StressedReading({required this.reading, required this.stress});

  final String reading;
  final int stress;

  @override
  Widget build(BuildContext context) {
    final syllables = reading.split('-');
    final spans = <InlineSpan>[];
    for (var i = 0; i < syllables.length; i++) {
      final isStressed = i + 1 == stress;
      spans.add(
        TextSpan(
          text: syllables[i],
          style: TextStyle(
            fontWeight: isStressed ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      );
      if (i != syllables.length - 1) spans.add(const TextSpan(text: '-'));
    }
    return RichText(text: TextSpan(style: DefaultTextStyle.of(context).style, children: spans));
  }
}
