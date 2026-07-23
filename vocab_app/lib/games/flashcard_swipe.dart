/// Flashcard swipe (SPEC.md section 8 game 1). Dual-coding card (word +
/// TTS + [image if has_photo]); reveal answer, then swipe/tap left=Again,
/// right=Good (buttons for Hard/Easy per 6.1 mapping table).
///
/// 2026-07-23 revision: this game also replaces the old separate intro
/// card for brand-new words ([isNewWord]) — the front shows just the
/// word, the reveal shows the full back (meaning/reading/sentence), and
/// the swipe labels become รู้จัก (right = Good) / ไม่รู้จัก (left =
/// Again) with only those two buttons; that first swipe doubles as the
/// word's first FSRS review.
///
/// Real drag-follow-the-finger physics (NOTES.md's UI design pass): once
/// revealed, the result card translates and rotates live under the
/// finger via `onPanUpdate` (not a fixed-direction dismiss animation with
/// no feedback), snaps back with an `elasticOut` spring if released below
/// the distance/velocity threshold, and flies off-screen in the drag
/// direction if released past it — same interaction language as
/// Tinder/Hinge-style card swiping.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/theme/app_theme.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class FlashcardSwipeGame extends StatefulWidget {
  const FlashcardSwipeGame({
    super.key,
    required this.bundle,
    required this.direction,
    required this.tts,
    required this.onRated,
    this.isNewWord = false,
  });

  final WordBundle bundle;
  final Direction direction;
  final TtsService tts;
  final ValueChanged<Rating> onRated;

  /// First-ever encounter of this word (no SRS history yet): swipe labels
  /// become รู้จัก/ไม่รู้จัก and the Hard/Easy buttons are hidden.
  final bool isNewWord;

  @override
  State<FlashcardSwipeGame> createState() => _FlashcardSwipeGameState();
}

class _FlashcardSwipeGameState extends State<FlashcardSwipeGame>
    with SingleTickerProviderStateMixin {
  static const _distanceThreshold = 110.0;
  static const _velocityThreshold = 650.0;

  bool _revealed = false;
  bool _resolved = false; // guards double-fire once a fly-off is committed
  Offset _dragOffset = Offset.zero;

  late final AnimationController _releaseController;
  Animation<Offset>? _releaseAnimation;

  String get _promptText => widget.direction == Direction.enTh
      ? widget.bundle.word.headword
      : widget.bundle.coreSense.meaningTh;

  @override
  void initState() {
    super.initState();
    _releaseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 320),
    )..addListener(() {
      final anim = _releaseAnimation;
      if (anim != null) setState(() => _dragOffset = anim.value);
    });
    // First-ever encounter: auto-pronounce, same dual-coding behaviour the
    // old intro card had (word + sound together on first sight).
    if (widget.isNewWord) widget.tts.speak(widget.bundle.word.headword);
  }

  @override
  void dispose() {
    _releaseController.dispose();
    super.dispose();
  }

  void _onPanUpdate(DragUpdateDetails details) {
    if (_resolved) return;
    setState(() => _dragOffset += details.delta);
  }

  void _onPanEnd(DragEndDetails details) {
    if (_resolved) return;
    final dx = _dragOffset.dx;
    final vx = details.velocity.pixelsPerSecond.dx;
    if (dx > _distanceThreshold || vx > _velocityThreshold) {
      _flyOffAndRate(toRight: true, rating: Rating.good);
    } else if (dx < -_distanceThreshold || vx < -_velocityThreshold) {
      _flyOffAndRate(toRight: false, rating: Rating.again);
    } else {
      _snapBack();
    }
  }

  void _snapBack() {
    _releaseAnimation = Tween<Offset>(begin: _dragOffset, end: Offset.zero).animate(
      CurvedAnimation(parent: _releaseController, curve: Curves.elasticOut),
    );
    _releaseController.forward(from: 0);
  }

  void _flyOffAndRate({required bool toRight, required Rating rating}) {
    setState(() => _resolved = true);
    final width = MediaQuery.of(context).size.width;
    final target = Offset((toRight ? 1 : -1) * width * 1.4, _dragOffset.dy);
    _releaseAnimation = Tween<Offset>(begin: _dragOffset, end: target).animate(
      CurvedAnimation(parent: _releaseController, curve: Curves.easeIn),
    );
    _releaseController.forward(from: 0).whenComplete(() => widget.onRated(rating));
  }

  /// Buttons drive the same fly-off animation so tapping "จำได้"/"ลืม" looks
  /// consistent with swiping, instead of an instant cut.
  void _rateViaButton(Rating rating) {
    if (_resolved) return;
    switch (rating) {
      case Rating.good:
        _flyOffAndRate(toRight: true, rating: Rating.good);
      case Rating.again:
        _flyOffAndRate(toRight: false, rating: Rating.again);
      case Rating.hard:
      case Rating.easy:
        setState(() => _resolved = true);
        widget.onRated(rating);
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final rotation = (_dragOffset.dx / 900).clamp(-0.35, 0.35);
    final swipeProgress = (_dragOffset.dx.abs() / _distanceThreshold).clamp(0.0, 1.0);
    final rightLabel = widget.isNewWord ? 'รู้จัก' : 'จำได้';
    final leftLabel = widget.isNewWord ? 'ไม่รู้จัก' : 'ลืม';

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 260),
          transitionBuilder: (child, anim) => FadeTransition(
            opacity: anim,
            child: ScaleTransition(scale: Tween(begin: 0.96, end: 1.0).animate(anim), child: child),
          ),
          child: !_revealed
              ? Card(
                  key: const ValueKey('prompt'),
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(_promptText, style: Theme.of(context).textTheme.headlineMedium),
                        if (widget.direction == Direction.enTh)
                          IconButton(
                            icon: const Icon(Icons.volume_up),
                            onPressed: () => widget.tts.speak(widget.bundle.word.headword),
                          ),
                      ],
                    ),
                  ),
                )
              : GestureDetector(
                  key: const ValueKey('result'),
                  onPanUpdate: _onPanUpdate,
                  onPanEnd: _onPanEnd,
                  child: Transform.translate(
                    offset: _dragOffset,
                    child: Transform.rotate(
                      angle: rotation,
                      child: Stack(
                        clipBehavior: Clip.none,
                        children: [
                          WordResultCard(
                            bundle: widget.bundle,
                            tts: widget.tts,
                            onOpenDetail: () => Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) =>
                                    WordDetailPage(bundle: widget.bundle, tts: widget.tts),
                              ),
                            ),
                          ),
                          if (_dragOffset.dx > 4)
                            Positioned(
                              top: 12,
                              left: 16,
                              child: _SwipeStamp(
                                label: rightLabel,
                                color: colors.success,
                                opacity: swipeProgress,
                              ),
                            ),
                          if (_dragOffset.dx < -4)
                            Positioned(
                              top: 12,
                              right: 16,
                              child: _SwipeStamp(
                                label: leftLabel,
                                color: colors.danger,
                                opacity: swipeProgress,
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
        ),
        const SizedBox(height: 16),
        if (!_revealed)
          FilledButton(
            onPressed: () => setState(() => _revealed = true),
            child: const Text('เผยคำตอบ'),
          )
        else ...[
          Text(
            'ปัดขวา = $rightLabel · ปัดซ้าย = $leftLabel',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _RateButton(
                label: leftLabel,
                icon: Icons.close,
                color: colors.danger,
                onTap: () => _rateViaButton(Rating.again),
              ),
              if (!widget.isNewWord)
                _RateButton(
                  label: 'Hard',
                  icon: Icons.trending_flat,
                  color: colors.warning,
                  onTap: () => _rateViaButton(Rating.hard),
                ),
              _RateButton(
                label: rightLabel,
                icon: Icons.check,
                color: colors.success,
                onTap: () => _rateViaButton(Rating.good),
              ),
              if (!widget.isNewWord)
                _RateButton(
                  label: 'ง่ายมาก',
                  icon: Icons.star,
                  color: Theme.of(context).colorScheme.primary,
                  onTap: () => _rateViaButton(Rating.easy),
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _SwipeStamp extends StatelessWidget {
  const _SwipeStamp({required this.label, required this.color, required this.opacity});

  final String label;
  final Color color;
  final double opacity;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: opacity,
      child: Transform.rotate(
        angle: -0.2,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            border: Border.all(color: color, width: 2),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            label,
            style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 16),
          ),
        ),
      ),
    );
  }
}

class _RateButton extends StatelessWidget {
  const _RateButton({
    required this.label,
    required this.icon,
    required this.color,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        IconButton.filled(
          style: IconButton.styleFrom(backgroundColor: color, foregroundColor: Colors.white),
          icon: Icon(icon),
          onPressed: onTap,
        ),
        Text(label, style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}
