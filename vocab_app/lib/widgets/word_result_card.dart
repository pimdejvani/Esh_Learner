/// Shared "after answer" mini dictionary-entry widget — SPEC.md 9b layer 1
/// (headword + Thai reading with bold stress syllable + CEFR/POS badges +
/// core sense + one example sentence + TTS button). Shown after every game
/// reveals its answer. If the shown sentence uses an irregular word form
/// (`word_forms.is_irregular`), a small "ผิดปกติ" badge is flagged next to
/// it per SPEC.md 9.2 ("irregular forms ถูก flag และมีโน้ตเน้นเป็นพิเศษ") —
/// tapping it shows the full grammar note. Tap-through to the full entry
/// (word_detail_page, Phase 2) is available via [onOpenDetail].
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
    this.onOpenDetail,
  });

  final WordBundle bundle;
  final TtsService tts;
  final int sentenceIndex;

  /// Optional tap-through to the full entry (word_detail_page, SPEC.md 9b
  /// "แตะการ์ดเพื่อเปิด entry เต็ม — ไม่บังคับ"). Null hides the tap
  /// affordance entirely (e.g. contexts with no navigator to push to).
  final VoidCallback? onOpenDetail;

  @override
  Widget build(BuildContext context) {
    final word = bundle.word;
    final sense = bundle.coreSense;
    final sentence = bundle.sentences.isNotEmpty
        ? bundle.sentences[sentenceIndex.clamp(0, bundle.sentences.length - 1)]
        : null;
    WordForm? usedForm;
    if (sentence?.formId != null) {
      for (final f in bundle.forms) {
        if (f.id == sentence!.formId) {
          usedForm = f;
          break;
        }
      }
    }

    final card = Card(
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
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: Text(sentence.enText)),
                  if (usedForm != null && usedForm.isIrregular)
                    IrregularBadge(form: usedForm),
                ],
              ),
              Text(
                sentence.thText,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ],
        ),
      ),
    );

    if (onOpenDetail == null) return card;
    return InkWell(onTap: onOpenDetail, child: card);
  }
}

/// SPEC.md 9.2's "irregular forms ถูก flag และมีโน้ตเน้นเป็นพิเศษ" — a small
/// visually-distinct chip for any [WordForm] with `is_irregular = 1`, tap
/// to see the full (reasoned, not just labelled) grammar note. Shared by
/// the layer-1 mini card and the full word_detail_page entry so the same
/// highlight treatment appears everywhere an irregular form is shown.
class IrregularBadge extends StatelessWidget {
  const IrregularBadge({super.key, required this.form});

  final WordForm form;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Tooltip(
      message: form.grammarNoteTh,
      child: InkWell(
        onTap: () => showDialog<void>(
          context: context,
          builder: (_) => AlertDialog(
            title: Text('${form.formText} (ผิดปกติ)'),
            content: Text(form.grammarNoteTh),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('ปิด'),
              ),
            ],
          ),
        ),
        child: Container(
          margin: const EdgeInsets.only(left: 6),
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: scheme.errorContainer,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Text(
            'ผิดปกติ',
            style: TextStyle(
              color: scheme.onErrorContainer,
              fontSize: 11,
              fontWeight: FontWeight.bold,
            ),
          ),
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
