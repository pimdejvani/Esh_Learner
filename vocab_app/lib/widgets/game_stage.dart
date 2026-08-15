import 'package:flutter/material.dart';

/// Keeps game content scrollable while pinning the current primary action
/// above the app's persistent bottom navigation.
class GameStage extends StatelessWidget {
  const GameStage({
    super.key,
    required this.child,
    this.bottomAction,
    this.onTapToContinue,
  });

  final Widget child;
  final Widget? bottomAction;
  final VoidCallback? onTapToContinue;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: GestureDetector(
            behavior: HitTestBehavior.translucent,
            onTap: onTapToContinue,
            child: LayoutBuilder(
              builder: (context, constraints) => SingleChildScrollView(
                padding: const EdgeInsets.only(bottom: 12),
                child: ConstrainedBox(
                  constraints: BoxConstraints(minHeight: constraints.maxHeight),
                  child: Center(child: child),
                ),
              ),
            ),
          ),
        ),
        if (bottomAction != null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.only(top: 10),
            decoration: BoxDecoration(
              color: Theme.of(context).scaffoldBackgroundColor,
              border: Border(
                top: BorderSide(color: Theme.of(context).dividerColor),
              ),
            ),
            child: bottomAction,
          ),
      ],
    );
  }
}
