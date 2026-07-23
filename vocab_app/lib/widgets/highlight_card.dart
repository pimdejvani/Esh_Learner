/// Colorful "highlight card" — the reference site's second card style
/// (SPEC.md section 13 / NOTES.md's UI design pass): tonal pastel blocks
/// riffing on the `#49ADFF` accent, each with a small black (light mode) /
/// off-white (dark mode) rounded-square icon badge in the corner. Used for
/// at-a-glance summary/feature-highlight sections — e.g. the play screen's
/// current-game-mode indicator and the progress page's "due today" tiles —
/// distinct from the clean white-bordered [Card] style used for denser
/// content (word detail entries, sentence lists, credits).
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/theme/app_theme.dart';

enum HighlightTone { sky, lavender, blue }

class HighlightCard extends StatelessWidget {
  const HighlightCard({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    this.tone = HighlightTone.sky,
    this.dense = false,
  });

  final IconData icon;
  final String title;
  final String? subtitle;
  final HighlightTone tone;

  /// Compact variant: smaller badge/padding, single-line — used for inline
  /// indicators (e.g. play screen's game-mode chip) rather than full tiles.
  final bool dense;

  Color _bg(AppColors c) {
    switch (tone) {
      case HighlightTone.sky:
        return c.highlightSky;
      case HighlightTone.lavender:
        return c.highlightLavender;
      case HighlightTone.blue:
        return c.highlightBlue;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final bg = _bg(colors);
    final badgeSize = dense ? 28.0 : 36.0;

    final badge = Container(
      width: badgeSize,
      height: badgeSize,
      decoration: BoxDecoration(
        color: colors.badgeBackground,
        borderRadius: BorderRadius.circular(dense ? 8 : 10),
      ),
      child: Icon(icon, color: colors.badgeForeground, size: dense ? 16 : 20),
    );

    final textTheme = Theme.of(context).textTheme;
    final titleStyle = (dense ? textTheme.labelLarge : textTheme.titleMedium)
        ?.copyWith(color: colors.onHighlight);
    final subtitleStyle = textTheme.bodySmall?.copyWith(
      color: colors.onHighlight.withValues(alpha: 0.7),
    );

    return Container(
      padding: EdgeInsets.all(dense ? 10 : 16),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
      child: dense
          ? Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                badge,
                const SizedBox(width: 8),
                Text(title, style: titleStyle),
              ],
            )
          : Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                badge,
                const SizedBox(height: 12),
                Text(title, style: titleStyle),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(subtitle!, style: subtitleStyle),
                ],
              ],
            ),
    );
  }
}
