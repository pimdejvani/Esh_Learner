/// Flashcard swipe (SPEC.md section 8 game 1).
///
/// 2026-07-23 v2 (user feedback): zero-friction flow —
/// * The card is swipeable IMMEDIATELY, no "reveal answer" button gate:
///   swipe right = รู้จัก, swipe left = ไม่รู้จัก, and the rating is
///   recorded the moment the swipe commits.
/// * Tapping the card flips it to show the full back (meaning / reading /
///   example sentence) for players who want to check before swiping —
///   optional, never required.
/// * Only two outcomes everywhere: รู้จัก / ไม่รู้จัก. The Hard / ง่ายมาก
///   buttons are gone (FSRS still has 4 ratings internally; the UI maps
///   right→Good, left→Again).
/// * First-ever encounter ([isNewWord]) answered รู้จัก maps to
///   Rating.easy instead of Good — knowing a word on first sight means
///   it's already acquired, so FSRS should schedule it far out.
///
/// Real drag-follow-the-finger physics: the card translates and rotates
/// live under the finger via `onPanUpdate`, snaps back with an
/// `elasticOut` spring if released below the distance/velocity threshold,
/// and flies off-screen in the drag direction if released past it.
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

  /// First-ever encounter of this word (no SRS history yet): auto-TTS on
  /// mount, and a รู้จัก answer upgrades to Rating.easy (already-known
  /// words shouldn't clog the learning queue).
  final bool isNewWord;

  @override
  State<FlashcardSwipeGame> createState() => _FlashcardSwipeGameState();
}

class _FlashcardSwipeGameState extends State<FlashcardSwipeGame>
    with SingleTickerProviderStateMixin {
  static const _distanceThreshold = 110.0;
  static const _velocityThreshold = 650.0;

  /// Fixed card height (user request 2026-07-24 "อยากให้ความสูงของกล่อง
  /// คงที่"): the front (word only) and the revealed back (full result
  /// card) render inside the same box so the layout never jumps when the
  /// card flips or between cards. A too-tall back face scales down to
  /// fit instead of growing the box.
  static const _cardHeight = 380.0;

  bool _revealed = false;
  bool _resolved = false; // guards double-fire once a fly-off is committed
  Offset _dragOffset = Offset.zero;

  late final AnimationController _releaseController;
  Animation<Offset>? _releaseAnimation;

  String get _promptText => widget.direction == Direction.enTh
      ? widget.bundle.word.headword
      : widget.bundle.coreSense.meaningTh;

  /// Right swipe = รู้จัก. On a first-ever encounter that's a stronger
  /// signal than a normal correct recall — the player already knew the
  /// word before we taught it — so it maps to Easy instead of Good.
  Rating get _knownRating => widget.isNewWord ? Rating.easy : Rating.good;

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
    // First-ever encounter: auto-pronounce (dual coding — word + sound
    // together on first sight).
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
      _flyOffAndRate(toRight: true, rating: _knownRating);
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
    _releaseController.forward(from: 0).whenComplete(() {
      if (mounted) widget.onRated(rating);
    });
  }

  /// Buttons drive the same fly-off animation so tapping รู้จัก/ไม่รู้จัก
  /// looks consistent with swiping, instead of an instant cut.
  void _rateViaButton({required bool known}) {
    if (_resolved) return;
    _flyOffAndRate(
      toRight: known,
      rating: known ? _knownRating : Rating.again,
    );
  }

  void _flip() {
    if (_resolved) return;
    setState(() => _revealed = true);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    final rotation = (_dragOffset.dx / 900).clamp(-0.35, 0.35);
    final swipeProgress = (_dragOffset.dx.abs() / _distanceThreshold).clamp(0.0, 1.0);

    // Front (word only, tap to flip) vs back (full word info). Both faces
    // live inside the SAME drag transform so the card is swipeable from
    // the very first frame — no reveal gate.
    final face = !_revealed
        ? SizedBox(
            key: const ValueKey('prompt'),
            height: _cardHeight,
            width: double.infinity,
            child: Card(
              child: Center(
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
                      const SizedBox(height: 8),
                      Text(
                        'แตะการ์ดเพื่อดูคำตอบ',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          )
        : SizedBox(
            key: const ValueKey('result'),
            height: _cardHeight,
            width: double.infinity,
            // scaleDown: an unusually tall back face shrinks to fit the
            // fixed box instead of overflowing; normal content renders
            // at natural size.
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 448),
                child: WordResultCard(
                  bundle: widget.bundle,
                  tts: widget.tts,
                  onOpenDetail: () => Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) =>
                          WordDetailPage(bundle: widget.bundle, tts: widget.tts),
                    ),
                  ),
                ),
              ),
            ),
          );

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        GestureDetector(
          onTap: _flip,
          onPanUpdate: _onPanUpdate,
          onPanEnd: _onPanEnd,
          child: Transform.translate(
            offset: _dragOffset,
            child: Transform.rotate(
              angle: rotation,
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  AnimatedSwitcher(
                    duration: const Duration(milliseconds: 260),
                    transitionBuilder: (child, anim) => FadeTransition(
                      opacity: anim,
                      child: ScaleTransition(
                        scale: Tween(begin: 0.96, end: 1.0).animate(anim),
                        child: child,
                      ),
                    ),
                    child: face,
                  ),
                  if (_dragOffset.dx > 4)
                    Positioned(
                      top: 12,
                      left: 16,
                      child: _SwipeStamp(
                        label: 'รู้จัก',
                        color: colors.success,
                        opacity: swipeProgress,
                      ),
                    ),
                  if (_dragOffset.dx < -4)
                    Positioned(
                      top: 12,
                      right: 16,
                      child: _SwipeStamp(
                        label: 'ไม่รู้จัก',
                        color: colors.danger,
                        opacity: swipeProgress,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text(
          'ปัดขวา = รู้จัก · ปัดซ้าย = ไม่รู้จัก',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 12),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            _RateButton(
              label: 'ไม่รู้จัก',
              icon: Icons.close,
              color: colors.danger,
              onTap: () => _rateViaButton(known: false),
            ),
            _RateButton(
              label: 'รู้จัก',
              icon: Icons.check,
              color: colors.success,
              onTap: () => _rateViaButton(known: true),
            ),
          ],
        ),
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
