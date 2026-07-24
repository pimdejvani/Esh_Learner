/// Top bar shared by the games (2026-07-24): an optional keyboard toggle on
/// the left (typed-answer games only, item 13) and the standard "!" info
/// affordance on the right (item 6 pattern). Non-typed games pass
/// [keyboardEnabled] null to hide the keyboard control.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/widgets/info_hint.dart';

class GameTopBar extends StatelessWidget {
  const GameTopBar({
    super.key,
    required this.infoMessage,
    this.keyboardEnabled,
    this.onToggleKeyboard,
  });

  final String infoMessage;

  /// null = no keyboard toggle (non-typed game). Otherwise the current
  /// auto-keyboard state, with [onToggleKeyboard] flipping it.
  final bool? keyboardEnabled;
  final VoidCallback? onToggleKeyboard;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (keyboardEnabled != null)
          IconButton(
            icon: Icon(keyboardEnabled! ? Icons.keyboard : Icons.keyboard_hide),
            tooltip: keyboardEnabled!
                ? 'Auto-keyboard on'
                : 'Auto-keyboard off',
            visualDensity: VisualDensity.compact,
            iconSize: 20,
            onPressed: onToggleKeyboard,
          ),
        const Spacer(),
        InfoHint(message: infoMessage),
      ],
    );
  }
}
