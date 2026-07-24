/// Paired normal + slow pronunciation buttons. Shown together everywhere a
/// word or sentence can be heard — user request 2026-07-24: every listen
/// button always has a "speak slowly" companion.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';

class SpeakButtons extends StatelessWidget {
  const SpeakButtons({
    super.key,
    required this.tts,
    required this.text,
    this.filled = false,
    this.size,
  });

  final TtsService tts;
  final String text;

  /// Filled/tonal button styling (used on the prominent game cards);
  /// plain icon buttons elsewhere (headers, list rows).
  final bool filled;
  final double? size;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _btn(
          icon: Icons.volume_up,
          tooltip: 'Listen',
          onPressed: () => tts.speak(text),
          tonal: false,
        ),
        _btn(
          icon: Icons.slow_motion_video,
          tooltip: 'Listen slowly',
          onPressed: () => tts.speakSlow(text),
          tonal: true,
        ),
      ],
    );
  }

  Widget _btn({
    required IconData icon,
    required String tooltip,
    required VoidCallback onPressed,
    required bool tonal,
  }) {
    final child = Icon(icon, size: size);
    if (!filled) {
      return IconButton(icon: child, tooltip: tooltip, onPressed: onPressed);
    }
    return tonal
        ? IconButton.filledTonal(icon: child, tooltip: tooltip, onPressed: onPressed)
        : IconButton.filled(icon: child, tooltip: tooltip, onPressed: onPressed);
  }
}
