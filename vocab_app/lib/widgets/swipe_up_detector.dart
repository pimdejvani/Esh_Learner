/// Passive swipe-up detector (item 10, 2026-07-24: "ปัดหน้าจอขึ้น = ไปอัน
/// ต่อไป, ถ้ารอคำตอบอยู่ = ส่งคำตอบ"). Uses a [Listener] on raw pointer
/// events instead of a [GestureDetector] so it fires even inside the play
/// screen's scroll view (a vertical GestureDetector would lose the gesture
/// arena to the scrollable). A quick upward flick — mostly vertical, past a
/// small distance/time threshold — triggers [onSwipeUp]; taps and
/// horizontal swipes are ignored.
library;

import 'package:flutter/widgets.dart';

class SwipeUpDetector extends StatefulWidget {
  const SwipeUpDetector({
    super.key,
    required this.onSwipeUp,
    required this.child,
  });

  final VoidCallback onSwipeUp;
  final Widget child;

  @override
  State<SwipeUpDetector> createState() => _SwipeUpDetectorState();
}

class _SwipeUpDetectorState extends State<SwipeUpDetector> {
  Offset? _start;
  DateTime? _startTime;

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: (e) {
        _start = e.position;
        _startTime = DateTime.now();
      },
      onPointerUp: (e) {
        final start = _start;
        final t0 = _startTime;
        _start = null;
        _startTime = null;
        if (start == null || t0 == null) return;
        final dy = e.position.dy - start.dy;
        final dx = e.position.dx - start.dx;
        final dt = DateTime.now().difference(t0).inMilliseconds;
        // Upward, mostly vertical, quick enough to read as a flick.
        if (dy < -70 && dy.abs() > dx.abs() && dt < 600) {
          widget.onSwipeUp();
        }
      },
      child: widget.child,
    );
  }
}
