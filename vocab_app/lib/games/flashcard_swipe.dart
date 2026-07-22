/// Flashcard swipe (SPEC.md section 8 game 1). Dual-coding card (word +
/// TTS + [image if has_photo]); reveal answer, then swipe/tap left=Again,
/// right=Good (long-press variants for Hard/Easy per 6.1 mapping table).
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class FlashcardSwipeGame extends StatefulWidget {
  const FlashcardSwipeGame({
    super.key,
    required this.bundle,
    required this.direction,
    required this.tts,
    required this.onRated,
  });

  final WordBundle bundle;
  final Direction direction;
  final TtsService tts;
  final ValueChanged<Rating> onRated;

  @override
  State<FlashcardSwipeGame> createState() => _FlashcardSwipeGameState();
}

class _FlashcardSwipeGameState extends State<FlashcardSwipeGame> {
  bool _revealed = false;

  String get _promptText => widget.direction == Direction.enTh
      ? widget.bundle.word.headword
      : widget.bundle.coreSense.meaningTh;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(_promptText, style: Theme.of(context).textTheme.headlineMedium),
                if (widget.direction == Direction.enTh)
                  IconButton(
                    icon: const Icon(Icons.volume_up),
                    onPressed: () => widget.tts.speak(widget.bundle.word.headword),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (!_revealed)
          FilledButton(
            onPressed: () => setState(() => _revealed = true),
            child: const Text('เผยคำตอบ'),
          )
        else ...[
          WordResultCard(bundle: widget.bundle, tts: widget.tts),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _RateButton(
                label: 'ลืม',
                icon: Icons.close,
                color: Colors.red,
                onTap: () => widget.onRated(Rating.again),
              ),
              _RateButton(
                label: 'Hard',
                icon: Icons.trending_flat,
                color: Colors.orange,
                onTap: () => widget.onRated(Rating.hard),
              ),
              _RateButton(
                label: 'จำได้',
                icon: Icons.check,
                color: Colors.green,
                onTap: () => widget.onRated(Rating.good),
              ),
              _RateButton(
                label: 'ง่ายมาก',
                icon: Icons.star,
                color: Colors.blue,
                onTap: () => widget.onRated(Rating.easy),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

class _RateButton extends StatelessWidget {
  const _RateButton({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        IconButton.filled(
          style: IconButton.styleFrom(backgroundColor: color),
          icon: Icon(icon),
          onPressed: onTap,
        ),
        Text(label, style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}
