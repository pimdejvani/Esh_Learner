/// Small staggered fade+rise entrance for option grids (Word Association,
/// Odd One Out MCQ chips) — each option animates in slightly after the
/// previous one instead of the whole set popping in at once, per NOTES.md's
/// UI design pass "deliberate motion design per interaction" instruction.
library;

import 'package:flutter/material.dart';

class StaggeredEntrance extends StatelessWidget {
  const StaggeredEntrance({super.key, required this.index, required this.child});

  final int index;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 220 + index * 60),
      curve: Curves.easeOutCubic,
      builder: (context, t, child) => Opacity(
        opacity: t,
        child: Transform.translate(offset: Offset(0, (1 - t) * 12), child: child),
      ),
      child: child,
    );
  }
}
