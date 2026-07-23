/// Full dictionary entry (SPEC.md section 9b, layer 2), replacing the
/// Phase 1 stub that just reused the layer-1 result card (see NOTES.md's
/// Phase 1 section). Header matches layer 1 (headword + Thai reading with
/// bold stress syllable + TTS button, no IPA — IPA is internal-only per
/// spec). Below that: every sense grouped by POS and ordered by
/// `sense_rank`, each with a CEFR badge + meaning + collocation (EN = TH),
/// the `is_core` sense starred; for verb entries, the inflected forms
/// inline ("answered · answered · answering" style) with irregular forms
/// flagged (SPEC.md 9.2) and tappable to expand the full grammar note; and
/// finally all 5 example sentences.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/theme/app_theme.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class WordDetailPage extends StatelessWidget {
  const WordDetailPage({super.key, required this.bundle, required this.tts});

  final WordBundle bundle;
  final TtsService tts;

  @override
  Widget build(BuildContext context) {
    final word = bundle.word;
    // Group senses by POS, preserving sense_rank order within each group
    // (bundle.senses is already loaded ordered by sense_rank ASC).
    final byPos = <String, List<Sense>>{};
    for (final s in bundle.senses.isNotEmpty ? bundle.senses : [bundle.coreSense]) {
      byPos.putIfAbsent(s.pos, () => []).add(s);
    }

    return Scaffold(
      appBar: AppBar(title: Text(word.headword)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _Header(word: word, tts: tts),
          const SizedBox(height: 20),
          for (final entry in byPos.entries) ...[
            _SenseGroup(
              pos: entry.key,
              senses: entry.value,
              forms: bundle.forms,
            ),
            const SizedBox(height: 16),
          ],
          if (bundle.sentences.isNotEmpty) ...[
            Text('ประโยคตัวอย่าง', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            for (final s in bundle.sentences) _SentenceTile(sentence: s, forms: bundle.forms),
          ],
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.word, required this.tts});

  final Word word;
  final TtsService tts;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(word.headword, style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(width: 8),
        IconButton(
          icon: const Icon(Icons.volume_up),
          onPressed: () => tts.speak(word.headword),
        ),
        const SizedBox(width: 8),
        Expanded(child: _StressedReading(reading: word.thaiReading, stress: word.stressIndex)),
      ],
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
          style: TextStyle(fontWeight: isStressed ? FontWeight.bold : FontWeight.normal),
        ),
      );
      if (i != syllables.length - 1) spans.add(const TextSpan(text: '-'));
    }
    return RichText(
      text: TextSpan(
        style: DefaultTextStyle.of(context).style.copyWith(fontSize: 18),
        children: spans,
      ),
    );
  }
}

class _SenseGroup extends StatelessWidget {
  const _SenseGroup({required this.pos, required this.senses, required this.forms});

  final String pos;
  final List<Sense> senses;
  final List<WordForm> forms;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Chip(label: Text(pos.toUpperCase())),
            const SizedBox(height: 8),
            for (final s in senses) _SenseTile(sense: s),
            if (pos == 'v' && forms.isNotEmpty) ...[
              const Divider(),
              _InflectionRow(forms: forms),
            ],
          ],
        ),
      ),
    );
  }
}

class _SenseTile extends StatelessWidget {
  const _SenseTile({required this.sense});

  final Sense sense;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (sense.isCore)
                Icon(Icons.star, size: 16, color: context.appColors.warning),
              if (sense.isCore) const SizedBox(width: 4),
              Chip(
                label: Text(sense.cefr, style: const TextStyle(fontSize: 11)),
                visualDensity: VisualDensity.compact,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              const SizedBox(width: 6),
              if (sense.countable == 1)
                const Text('นับได้', style: TextStyle(fontSize: 12)),
              if (sense.countable == 0)
                const Text('นับไม่ได้', style: TextStyle(fontSize: 12)),
            ],
          ),
          const SizedBox(height: 4),
          Text(sense.meaningTh, style: Theme.of(context).textTheme.bodyLarge),
          if ((sense.collocationEn ?? '').isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                '${sense.collocationEn} = ${sense.collocationTh}',
                style: Theme.of(
                  context,
                ).textTheme.bodySmall?.copyWith(fontStyle: FontStyle.italic),
              ),
            ),
        ],
      ),
    );
  }
}

/// Inline word-forms row ("answered · answered · answering" style per
/// SPEC.md 9b), tap to expand the full grammar note for each form.
/// Irregular forms get the shared [IrregularBadge] highlight.
class _InflectionRow extends StatefulWidget {
  const _InflectionRow({required this.forms});

  final List<WordForm> forms;

  @override
  State<_InflectionRow> createState() => _InflectionRowState();
}

class _InflectionRowState extends State<_InflectionRow> {
  bool _expanded = false;

  /// Preferred display order for the inline verb-forms summary.
  static const _order = ['past', 'past_participle', 'ving', '3sg'];

  @override
  Widget build(BuildContext context) {
    final ordered = [
      for (final type in _order)
        ...widget.forms.where((f) => f.formType == type),
    ];
    final rest = widget.forms.where((f) => !_order.contains(f.formType)).toList();
    final display = ordered.isNotEmpty ? ordered : widget.forms;

    return InkWell(
      onTap: () => setState(() => _expanded = !_expanded),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              for (var i = 0; i < display.length; i++) ...[
                if (i != 0) const Text(' · '),
                Text(display[i].formText),
                if (display[i].isIrregular) IrregularBadge(form: display[i]),
              ],
              const SizedBox(width: 6),
              AnimatedRotation(
                turns: _expanded ? 0.5 : 0,
                duration: const Duration(milliseconds: 220),
                child: const Icon(Icons.expand_more, size: 18),
              ),
            ],
          ),
          AnimatedSize(
            duration: const Duration(milliseconds: 220),
            curve: Curves.easeOut,
            alignment: Alignment.topLeft,
            child: !_expanded
                ? const SizedBox(width: double.infinity)
                : Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        for (final f in [...display, ...rest])
                          Padding(
                            padding: const EdgeInsets.only(bottom: 6),
                            child: Text('${f.formText} (${f.formType}): ${f.grammarNoteTh}'),
                          ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }
}

class _SentenceTile extends StatelessWidget {
  const _SentenceTile({required this.sentence, required this.forms});

  final ExampleSentence sentence;
  final List<WordForm> forms;

  @override
  Widget build(BuildContext context) {
    WordForm? usedForm;
    if (sentence.formId != null) {
      for (final f in forms) {
        if (f.id == sentence.formId) {
          usedForm = f;
          break;
        }
      }
    }
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(sentence.enText),
                Text(sentence.thText, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
          if (usedForm != null && usedForm.isIrregular) IrregularBadge(form: usedForm),
        ],
      ),
    );
  }
}
