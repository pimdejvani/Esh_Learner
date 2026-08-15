/// Full dictionary entry (SPEC.md section 9b, layer 2).
///
/// It reads the same rows as the Flashcard back — never a second dataset — and
/// simply shows more of them: every part of speech with every sense (Thai
/// meaning plus the English gloss it was taken from), the examples filed under
/// each sense with that sentence's own explanation, forms split into
/// inflections and word family, related words with their relation type and
/// stored reason, and the source attribution behind all of it.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/theme/app_theme.dart';
import 'package:vocab_app/widgets/speak_buttons.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class WordDetailPage extends StatelessWidget {
  const WordDetailPage({
    super.key,
    required this.bundle,
    required this.tts,
    this.similar = const [],
    this.onOpenSimilar,
  });

  final WordBundle bundle;
  final TtsService tts;

  /// Up to 5 closest words by SWOW closeness (item 1, 2026-07-24), shown as
  /// tappable chips; empty hides the section.
  final List<Word> similar;

  /// Tapping a similar word opens ITS entry (item 1). Null disables the tap.
  final void Function(Word)? onOpenSimilar;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final word = bundle.word;
    final grouped = bundle.sensesByPos;
    final positions = grouped.keys.toList()..sort(comparePos);

    return Scaffold(
      appBar: AppBar(title: Text(word.headword)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _Header(word: word, tts: tts),
          const SizedBox(height: 20),
          for (final pos in positions) ...[
            _SenseGroup(
              pos: pos,
              senses: grouped[pos]!,
              bundle: bundle,
              tts: tts,
            ),
            const SizedBox(height: 16),
          ],
          if (bundle.inflections.isNotEmpty)
            _FormSection(
              title: 'Forms',
              subtitle: 'รูปผันของคำเดียวกัน',
              forms: bundle.inflections,
            ),
          if (bundle.family.isNotEmpty)
            _FormSection(
              title: 'Word family',
              subtitle: 'คำที่สร้างจากรากเดียวกัน',
              forms: bundle.family,
            ),
          if (bundle.related.isNotEmpty) _RelatedSection(related: bundle.related),
          if (similar.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text('Similar words', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final w in similar)
                  ActionChip(
                    label: Text(w.headword),
                    onPressed:
                        onOpenSimilar == null ? null : () => onOpenSimilar!(w),
                  ),
              ],
            ),
          ],
          const SizedBox(height: 20),
          _Attribution(bundle: bundle),
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
        Flexible(
          child:
              Text(word.headword, style: Theme.of(context).textTheme.headlineMedium),
        ),
        const SizedBox(width: 8),
        SpeakButtons(tts: tts, text: word.headword),
        const SizedBox(width: 8),
        Expanded(
          child: _StressedReading(
            reading: word.thaiReading,
            stress: word.stressIndex,
          ),
        ),
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
      spans.add(
        TextSpan(
          text: syllables[i],
          style: TextStyle(
            fontWeight: i + 1 == stress ? FontWeight.bold : FontWeight.normal,
          ),
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

/// One part of speech: each of its senses, with the examples that teach that
/// exact sense underneath it.
class _SenseGroup extends StatelessWidget {
  const _SenseGroup({
    required this.pos,
    required this.senses,
    required this.bundle,
    required this.tts,
  });

  final String pos;
  final List<Sense> senses;
  final WordBundle bundle;
  final TtsService tts;

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
            for (final sense in senses)
              _SenseTile(
                sense: sense,
                examples: bundle.sentences
                    .where((s) => s.senseId == sense.id)
                    .toList(growable: false),
                tts: tts,
              ),
          ],
        ),
      ),
    );
  }
}

class _SenseTile extends StatelessWidget {
  const _SenseTile({
    required this.sense,
    required this.examples,
    required this.tts,
  });

  final Sense sense;
  final List<ExampleSentence> examples;
  final TtsService tts;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (sense.isCore) ...[
                Icon(Icons.star, size: 16, color: context.appColors.warning),
                const SizedBox(width: 4),
              ],
              Expanded(
                child: Text(sense.meaningTh, style: theme.textTheme.bodyLarge),
              ),
            ],
          ),
          // The English gloss the Thai meaning was written from, so a learner
          // (and a reviewer) can see it was not invented.
          if (sense.glossEn.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(
                sense.glossEn,
                style: theme.textTheme.bodySmall
                    ?.copyWith(fontStyle: FontStyle.italic),
              ),
            ),
          for (final example in examples)
            _SentenceTile(sentence: example, tts: tts),
        ],
      ),
    );
  }
}

class _SentenceTile extends StatelessWidget {
  const _SentenceTile({required this.sentence, required this.tts});

  final ExampleSentence sentence;
  final TtsService tts;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 10, left: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: Text(sentence.enText)),
              SpeakButtons(tts: tts, text: sentence.enText),
            ],
          ),
          Text(sentence.thText, style: theme.textTheme.bodySmall),
          if (sentence.explanationTh.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                sentence.explanationTh,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.primary,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _FormSection extends StatelessWidget {
  const _FormSection({
    required this.title,
    required this.subtitle,
    required this.forms,
  });

  final String title;
  final String subtitle;
  final List<WordForm> forms;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: theme.textTheme.titleMedium),
          Text(subtitle, style: theme.textTheme.bodySmall),
          const SizedBox(height: 8),
          for (final form in forms)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(form.formText, style: theme.textTheme.bodyMedium),
                  if (form.isIrregular) const IrregularBadge(),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      form.isDerived
                          ? '${form.pos} · ${form.meaningTh ?? ''}'
                          : '${form.relation} · ${form.pos}',
                      style: theme.textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _RelatedSection extends StatelessWidget {
  const _RelatedSection({required this.related});

  final List<RelatedWord> related;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sorted = [...related]
      ..sort((a, b) => b.closeness.compareTo(a.closeness));
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Related words', style: theme.textTheme.titleMedium),
          Text('คำที่สัมพันธ์กันและเหตุผล', style: theme.textTheme.bodySmall),
          const SizedBox(height: 8),
          for (final item in sorted)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(item.relatedHeadword,
                          style: theme.textTheme.bodyMedium),
                      const SizedBox(width: 8),
                      Text(
                        item.relationType,
                        style: theme.textTheme.labelSmall
                            ?.copyWith(color: theme.colorScheme.primary),
                      ),
                    ],
                  ),
                  if ((item.explanationTh ?? '').isNotEmpty)
                    Text(item.explanationTh!, style: theme.textTheme.bodySmall),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// Where the entry's facts came from. Licences are per source, so they are
/// collected from the rows actually shown rather than hardcoded.
class _Attribution extends StatelessWidget {
  const _Attribution({required this.bundle});

  final WordBundle bundle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final sources = <String>{
      for (final sense in bundle.senses)
        if (sense.meaningSource.isNotEmpty) sense.meaningSource,
      for (final form in bundle.forms)
        if (form.sourceLicense.isNotEmpty)
          '${form.sourceName} — ${form.sourceLicense}',
    }.toList()
      ..sort();
    if (sources.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Sources', style: theme.textTheme.titleSmall),
        const SizedBox(height: 4),
        for (final source in sources)
          Text(source, style: theme.textTheme.bodySmall),
      ],
    );
  }
}
