import 'package:flutter/material.dart';

/// An outlined answer field with its caption on its own line above the box.
///
/// Earlier versions floated the caption onto the border with a negative
/// offset; sitting outside the field's own bounds, it kept getting clipped
/// by whatever laid the field out (user feedback 2026-07-24, twice: "ช่อง
/// ตอบตัวอักษรยังโดนตัดครึ่ง"). A plain Column child cannot be clipped by
/// construction, so the caption is always fully readable.
class GameAnswerField extends StatelessWidget {
  const GameAnswerField({
    super.key,
    required this.controller,
    required this.label,
    required this.onSubmitted,
  });

  final TextEditingController controller;
  final String label;
  final ValueChanged<String> onSubmitted;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 6),
          child: Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        TextField(
          controller: controller,
          decoration: const InputDecoration(),
          onSubmitted: onSubmitted,
        ),
      ],
    );
  }
}
