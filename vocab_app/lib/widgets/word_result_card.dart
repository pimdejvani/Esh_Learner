/// The Flashcard back, also reused as the "after answer" card in every game
/// (SPEC.md 9b layer 1, final design confirmed 2026-08-12).
///
/// Order is fixed: headword + TTS + Thai reading, then one line per part of
/// speech, then one EN/TH example per part of speech, then the two dropdowns
/// (word family & forms, related words), then a shortcut into the full
/// Dictionary entry. The dropdowns start closed so the card stays short, and
/// long content scrolls rather than being shrunk to fit. No IPA, no symbols,
/// no CEFR tag here — those live in the Dictionary.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/widgets/speak_buttons.dart';

/// Part-of-speech order on the card: the ones a learner meets first, then
/// anything else alphabetically, so `light` reads noun → verb → adj.
const List<String> kPosOrder = ['noun', 'verb', 'adj', 'adv', 'prep', 'det', 'name'];

int comparePos(String a, String b) {
  final ia = kPosOrder.indexOf(a);
  final ib = kPosOrder.indexOf(b);
  if (ia == -1 && ib == -1) return a.compareTo(b);
  if (ia == -1) return 1;
  if (ib == -1) return -1;
  return ia.compareTo(ib);
}

class WordResultCard extends StatelessWidget {
  const WordResultCard({
    super.key,
    required this.bundle,
    required this.tts,
    this.sentenceIndex = 0,
    this.onOpenDetail,
    this.fillHeight = false,
  });

  final WordBundle bundle;
  final TtsService tts;

  /// Which example to prefer when a part of speech has more than one.
  final int sentenceIndex;
  final bool fillHeight;

  /// Tap-through to the full entry (word_detail_page). Null hides both the
  /// tap affordance and the "เปิด Dictionary เต็ม" button.
  final VoidCallback? onOpenDetail;

  @override
  Widget build(BuildContext context) {
    final word = bundle.word;
    final theme = Theme.of(context);
    final grouped = bundle.sensesByPos;
    final positions = grouped.keys.toList()..sort(comparePos);

    final content = Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: fillHeight ? MainAxisSize.max : MainAxisSize.min,
        children: [
          Row(
            children: [
              Flexible(
                child: Text(word.headword, style: theme.textTheme.headlineSmall),
              ),
              const SizedBox(width: 8),
              SpeakButtons(tts: tts, text: word.headword),
            ],
          ),
          _StressedReading(reading: word.thaiReading, stress: word.stressIndex),
          const SizedBox(height: 12),
          for (final pos in positions)
            _PosBlock(
              pos: pos,
              senses: grouped[pos]!,
              example: _exampleForPos(grouped[pos]!),
              tts: tts,
            ),
          if (bundle.forms.isNotEmpty) ...[
            const SizedBox(height: 4),
            _FormsDropdown(bundle: bundle),
          ],
          if (bundle.related.isNotEmpty) _RelatedDropdown(bundle: bundle),
          if (onOpenDetail != null) ...[
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: onOpenDetail,
                icon: const Icon(Icons.menu_book_outlined, size: 18),
                label: const Text('เปิด Dictionary เต็ม'),
              ),
            ),
          ],
        ],
      ),
    );

    return Card(
      child: fillHeight ? SingleChildScrollView(child: content) : content,
    );
  }

  /// The example filed under one of this POS's senses. [sentenceIndex] picks
  /// among several so games can show a different sentence than the card did.
  ExampleSentence? _exampleForPos(List<Sense> senses) {
    final ids = senses.map((s) => s.id).toSet();
    final matches = bundle.sentences
        .where((s) => ids.contains(s.senseId))
        .toList(growable: false);
    if (matches.isEmpty) return null;
    return matches[sentenceIndex.clamp(0, matches.length - 1)];
  }
}

/// One part of speech: its meanings on a single line, then one example.
class _PosBlock extends StatelessWidget {
  const _PosBlock({
    required this.pos,
    required this.senses,
    required this.example,
    required this.tts,
  });

  final String pos;
  final List<Sense> senses;
  final ExampleSentence? example;
  final TtsService tts;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    // Several senses of one POS read as one comma-separated line, and a sense
    // whose Thai already contains commas keeps them without duplicating.
    final meanings = <String>[];
    for (final sense in senses) {
      for (final part in sense.meaningTh.split(',')) {
        final trimmed = part.trim();
        if (trimmed.isNotEmpty && !meanings.contains(trimmed)) {
          meanings.add(trimmed);
        }
      }
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _PosLabel(pos: pos),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  meanings.join(', '),
                  style: theme.textTheme.titleMedium,
                ),
              ),
            ],
          ),
          if (example != null) ...[
            const SizedBox(height: 6),
            Padding(
              padding: const EdgeInsets.only(left: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          example!.enText,
                          style: theme.textTheme.bodyMedium,
                        ),
                      ),
                      SpeakButtons(tts: tts, text: example!.enText),
                    ],
                  ),
                  Text(
                    example!.thText,
                    style: theme.textTheme.bodySmall,
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _PosLabel extends StatelessWidget {
  const _PosLabel({required this.pos});

  final String pos;

  static const Map<String, String> _short = {
    'noun': 'n.',
    'verb': 'v.',
    'adj': 'adj.',
    'adv': 'adv.',
    'prep': 'prep.',
    'det': 'det.',
    'name': 'name',
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(top: 2),
      child: Text(
        _short[pos] ?? pos,
        style: theme.textTheme.titleMedium?.copyWith(
          fontStyle: FontStyle.italic,
          color: theme.colorScheme.primary,
        ),
      ),
    );
  }
}

/// Inflections and derived family, kept apart because they are different
/// things to a learner: `drank` is the same word, `drinker` is another word.
class _FormsDropdown extends StatelessWidget {
  const _FormsDropdown({required this.bundle});

  final WordBundle bundle;

  @override
  Widget build(BuildContext context) {
    final inflections = bundle.inflections;
    final family = bundle.family;
    return _CardExpansion(
      title: 'Word family & forms',
      children: [
        if (inflections.isNotEmpty) ...[
          const _SubHeading('รูปผันของคำ'),
          for (final form in inflections) _FormRow(form: form),
        ],
        if (family.isNotEmpty) ...[
          if (inflections.isNotEmpty) const SizedBox(height: 8),
          const _SubHeading('คำในตระกูลเดียวกัน'),
          for (final form in family) _FormRow(form: form),
        ],
      ],
    );
  }
}

class _FormRow extends StatelessWidget {
  const _FormRow({required this.form});

  final WordForm form;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(form.formText, style: theme.textTheme.bodyMedium),
          if (form.isIrregular) const IrregularBadge(),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              // A derived word means something of its own, so its Thai carries
              // the row; an inflection is the same word, so the grammar slot does.
              form.isDerived
                  ? '${form.pos} · ${form.meaningTh ?? ''}'
                  : '${form.relation} · ${form.pos}',
              style: theme.textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

class _RelatedDropdown extends StatelessWidget {
  const _RelatedDropdown({required this.bundle});

  final WordBundle bundle;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final related = [...bundle.related]
      ..sort((a, b) => b.closeness.compareTo(a.closeness));
    return _CardExpansion(
      title: 'Related words',
      children: [
        for (final item in related.take(12))
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(item.relatedHeadword, style: theme.textTheme.bodyMedium),
                    const SizedBox(width: 8),
                    Text(
                      item.relationType,
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.primary,
                      ),
                    ),
                  ],
                ),
                if ((item.explanationTh ?? '').isNotEmpty)
                  Text(
                    item.explanationTh!,
                    style: theme.textTheme.bodySmall,
                  ),
              ],
            ),
          ),
      ],
    );
  }
}

/// A dropdown that is closed by default and carries no divider lines, so two
/// of them stacked still read as part of one card.
class _CardExpansion extends StatelessWidget {
  const _CardExpansion({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Theme(
      data: theme.copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        title: Text(title, style: theme.textTheme.titleSmall),
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.only(left: 4, bottom: 8),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }
}

class _SubHeading extends StatelessWidget {
  const _SubHeading(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 2),
    child: Text(
      text,
      style: Theme.of(context).textTheme.labelMedium,
    ),
  );
}

/// SPEC.md 9.2's "irregular forms ถูก flag" — a small chip next to a form
/// whose spelling does not follow the regular pattern.
class IrregularBadge extends StatelessWidget {
  const IrregularBadge({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(left: 6),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        'irregular',
        style: TextStyle(
          color: scheme.onErrorContainer,
          fontSize: 11,
          fontWeight: FontWeight.bold,
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
        style: DefaultTextStyle.of(context).style,
        children: spans,
      ),
    );
  }
}
