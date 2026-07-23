/// Full-screen "You Pass" celebration (product decision 2026-07-23):
/// shown exactly once, the first time every word has been answered
/// correctly at least once in every game type (domain/mastery.dart).
/// Pushed by play_screen right after the review that completes the grid.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/domain/mastery.dart';
import 'package:vocab_app/theme/app_theme.dart';
import 'package:vocab_app/widgets/staggered_entrance.dart';

class YouPassPage extends StatelessWidget {
  const YouPassPage({super.key, required this.wordCount});

  final int wordCount;

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final textTheme = Theme.of(context).textTheme;
    final gameCount = kMasteryGames.length;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                StaggeredEntrance(
                  index: 0,
                  child: Container(
                    width: 96,
                    height: 96,
                    decoration: BoxDecoration(
                      color: colors.highlightLavender,
                      borderRadius: BorderRadius.circular(28),
                    ),
                    child: Icon(
                      Icons.emoji_events,
                      size: 52,
                      color: colors.badgeBackground,
                    ),
                  ),
                ),
                const SizedBox(height: 28),
                StaggeredEntrance(
                  index: 1,
                  child: Text(
                    'You Pass',
                    textAlign: TextAlign.center,
                    style: textTheme.displaySmall?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                StaggeredEntrance(
                  index: 2,
                  child: Text(
                    'ผ่านครบทุกคำในทุกเกมหลักแล้ว\n$wordCount คำ × $gameCount เกม 🎉',
                    textAlign: TextAlign.center,
                    style: textTheme.titleMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
                const SizedBox(height: 36),
                StaggeredEntrance(
                  index: 3,
                  child: FilledButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 24, vertical: 4),
                      child: Text('เล่นต่อ'),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
