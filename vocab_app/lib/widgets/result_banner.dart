/// Shared correct/almost/wrong feedback banner for the typed-answer games
/// (Cloze, Word Scramble, Dictation) — a colored flash (success/warning/
/// danger from [AppColors]) instead of a plain unstyled [Text], animated in
/// so the "reveal" reads as a deliberate beat rather than an instant cut.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/domain/answer_checker.dart';
import 'package:vocab_app/theme/app_theme.dart';

class ResultBanner extends StatelessWidget {
  const ResultBanner({super.key, required this.result, required this.correctText});

  final AnswerCheckResult result;
  final String correctText;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final (color, icon, message) = switch (result.verdict) {
      AnswerVerdict.correct => (colors.success, Icons.check_circle, 'ถูกต้อง!'),
      AnswerVerdict.almostTypo => (
        colors.warning,
        Icons.info,
        'เกือบถูก (สะกดผิดนิดหน่อย)',
      ),
      AnswerVerdict.wrong => (colors.danger, Icons.cancel, 'คำตอบที่ถูกคือ "$correctText"'),
    };

    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOut,
      builder: (context, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 8), child: child),
      ),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.4)),
        ),
        child: Row(
          children: [
            Icon(icon, color: color),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(color: color),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
