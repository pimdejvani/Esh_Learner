/// Renders the revealed steps of a [buildHintLadder] plus the "Hint"
/// button that reveals the next one, disabled once every step is shown
/// ("จะไม่ใบ้ไปมากกว่านี้"). Shared by Dictation, Cloze, Word Scramble.
library;

import 'package:flutter/material.dart';

class HintLadderView extends StatelessWidget {
  const HintLadderView({
    super.key,
    required this.stages,
    required this.revealed,
    required this.onReveal,
  });

  final List<String> stages;
  final int revealed;
  final VoidCallback onReveal;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < revealed && i < stages.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Text(
              stages[i],
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              ),
            ),
          ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: revealed < stages.length ? onReveal : null,
            icon: const Icon(Icons.lightbulb_outline),
            label: Text(revealed < stages.length ? 'Hint' : 'No more hints'),
          ),
        ),
      ],
    );
  }
}
