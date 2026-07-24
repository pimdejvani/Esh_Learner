/// Standard "!" info affordance (user request 2026-07-24): faint on-screen
/// instruction text is removed from game cards and folded behind this small
/// top-right icon instead. Tapping it shows the explanation in a popup.
/// Going forward every screen that needs an instruction uses this pattern.
library;

import 'package:flutter/material.dart';

class InfoHint extends StatelessWidget {
  const InfoHint({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      icon: const Icon(Icons.info_outline),
      tooltip: 'How to play',
      visualDensity: VisualDensity.compact,
      iconSize: 20,
      onPressed: () => showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          content: Text(message),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('OK'),
            ),
          ],
        ),
      ),
    );
  }
}
