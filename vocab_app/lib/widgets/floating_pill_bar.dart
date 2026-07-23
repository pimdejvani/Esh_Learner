/// Floating pill-shaped top/bottom bars (SPEC.md section 13 / NOTES.md's UI
/// design pass): the reference site's persistent nav chrome is itself a
/// rounded-full bar with the same thin-border/white(dark:elevated)-bg
/// treatment as its cards, floating with visible margin from the screen
/// edge rather than a flush full-width Material AppBar/BottomNavigationBar.
/// Used for the app's root shell only (see main.dart) — pushed detail
/// screens keep a plain themed AppBar, since those aren't the persistent
/// nav this pattern is meant for.
library;

import 'package:flutter/material.dart';

class FloatingTopBar extends StatelessWidget {
  const FloatingTopBar({super.key, required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        decoration: BoxDecoration(
          color: theme.cardTheme.color,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: theme.colorScheme.outline, width: 1),
        ),
        child: Text(title, style: theme.textTheme.titleMedium),
      ),
    );
  }
}

class FloatingNavItem {
  const FloatingNavItem({required this.icon, required this.label});
  final IconData icon;
  final String label;
}

class FloatingBottomNav extends StatelessWidget {
  const FloatingBottomNav({
    super.key,
    required this.items,
    required this.selectedIndex,
    required this.onSelected,
  });

  final List<FloatingNavItem> items;
  final int selectedIndex;
  final ValueChanged<int> onSelected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final primary = theme.colorScheme.primary;
    final muted = theme.colorScheme.onSurfaceVariant;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        decoration: BoxDecoration(
          color: theme.cardTheme.color,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: theme.colorScheme.outline, width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < items.length; i++)
              _NavButton(
                item: items[i],
                selected: i == selectedIndex,
                color: i == selectedIndex ? primary : muted,
                onTap: () => onSelected(i),
              ),
          ],
        ),
      ),
    );
  }
}

class _NavButton extends StatelessWidget {
  const _NavButton({
    required this.item,
    required this.selected,
    required this.color,
    required this.onTap,
  });

  final FloatingNavItem item;
  final bool selected;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      borderRadius: BorderRadius.circular(999),
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        decoration: BoxDecoration(
          color: selected ? theme.colorScheme.primary.withValues(alpha: 0.14) : null,
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(item.icon, color: color, size: 22),
            const SizedBox(width: 8),
            Text(
              item.label,
              style: theme.textTheme.labelMedium?.copyWith(color: color),
            ),
          ],
        ),
      ),
    );
  }
}
