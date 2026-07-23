/// Matching (SPEC.md section 8 game 3). EN-TH pairs, 6-12 pairs depending
/// on how many due words are available in the batch.
///
/// 2026-07-23 v2 (user feedback): connect-the-words with visible LINES —
/// * Link a pair by dragging a line from a left (EN) chip to a right (TH)
///   chip, or by tapping left then tapping right.
/// * Links are tentative and fully editable until checked: re-linking a
///   word replaces its old line, so a pair you second-guess CAN be fixed.
/// * A "ตรวจคำตอบ" button grades all links at once — correct pairs lock
///   green, wrong pairs turn red and stay editable for another try.
/// * Ratings (emitted once every pair is locked): Good if the pair was
///   never wrong at a check, Hard if it took a retry — matching never
///   emits Again, same as v1.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/theme/app_theme.dart';

class MatchingGame extends StatefulWidget {
  const MatchingGame({
    super.key,
    required this.bundles,
    required this.onAllRated,
  });

  final List<WordBundle> bundles;

  /// Called once, after every pair is matched, with a rating per word id.
  final ValueChanged<Map<int, Rating>> onAllRated;

  @override
  State<MatchingGame> createState() => _MatchingGameState();
}

class _MatchingTile {
  _MatchingTile(this.wordId, this.text);
  final int wordId;
  final String text;
}

class _MatchingGameState extends State<MatchingGame> {
  late List<_MatchingTile> _left; // EN headwords
  late List<_MatchingTile> _right; // TH meanings

  /// Tentative links: left wordId -> right wordId (editable until locked).
  final Map<int, int> _links = {};

  /// Left wordIds whose link was graded correct — locked, no longer editable.
  final Set<int> _locked = {};

  /// Left wordIds whose link was wrong at the LAST check (drawn red until
  /// the player edits them).
  final Set<int> _wrongNow = {};

  final Map<int, int> _wrongAttempts = {};
  int? _selectedLeft;
  bool _finished = false;

  // Live drag-a-line state.
  int? _dragFromLeft;
  Offset? _dragPos; // in the paint area's local coordinates

  final GlobalKey _paintKey = GlobalKey();
  final Map<int, GlobalKey> _leftKeys = {};
  final Map<int, GlobalKey> _rightKeys = {};

  /// Each pair gets its own line color (user request) so crossing lines
  /// stay readable. Keyed by the LEFT word id, assigned from the shuffled
  /// left column's order.
  final Map<int, Color> _pairColor = {};

  static const List<Color> _palette = [
    Color(0xFF1E88E5), // blue
    Color(0xFFF4511E), // deep orange
    Color(0xFF8E24AA), // purple
    Color(0xFF00897B), // teal
    Color(0xFFD81B60), // pink
    Color(0xFF3949AB), // indigo
    Color(0xFF6D4C41), // brown
    Color(0xFF00ACC1), // cyan
    Color(0xFF7CB342), // light green
    Color(0xFFFFB300), // amber
    Color(0xFF5E35B1), // deep purple
    Color(0xFFC0CA33), // lime
  ];

  @override
  void initState() {
    super.initState();
    _left = widget.bundles
        .map((b) => _MatchingTile(b.word.id, b.word.headword))
        .toList()
      ..shuffle();
    _right = widget.bundles
        .map((b) => _MatchingTile(b.word.id, b.coreSense.meaningTh))
        .toList()
      ..shuffle();
    for (final (i, t) in _left.indexed) {
      _leftKeys[t.wordId] = GlobalKey();
      _pairColor[t.wordId] = _palette[i % _palette.length];
    }
    for (final t in _right) {
      _rightKeys[t.wordId] = GlobalKey();
    }
  }

  bool get _allLinked =>
      _left.every((t) => _locked.contains(t.wordId) || _links.containsKey(t.wordId));

  /// Link left->right (one-to-one: steals the right chip from any other
  /// left word, replaces the left word's previous link). Editing clears
  /// the red "wrong" mark so the new attempt is drawn neutral again.
  void _link(int leftId, int rightId) {
    if (_locked.contains(leftId) || _finished) return;
    setState(() {
      _links.removeWhere((l, r) => r == rightId && !_locked.contains(l));
      _links[leftId] = rightId;
      _wrongNow.remove(leftId);
      _selectedLeft = null;
    });
  }

  void _unlink(int leftId) {
    if (_locked.contains(leftId) || _finished) return;
    setState(() {
      _links.remove(leftId);
      _wrongNow.remove(leftId);
      _selectedLeft = null;
    });
  }

  /// Tap on a LEFT chip. If it already has a (unlocked) link, a single tap
  /// removes it AND selects the chip — one tap = "undo, ready to redo",
  /// the fix-a-pair gesture users kept reaching for. Otherwise it just
  /// toggles selection.
  void _tapLeft(int wordId) {
    if (_locked.contains(wordId) || _finished) return;
    setState(() {
      if (_links.containsKey(wordId)) {
        _links.remove(wordId);
        _wrongNow.remove(wordId);
        _selectedLeft = wordId;
      } else {
        _selectedLeft = _selectedLeft == wordId ? null : wordId;
      }
    });
  }

  /// Tap on a RIGHT chip. With a left chip selected it links; with nothing
  /// selected, tapping a linked right chip breaks that pair (so a mistake
  /// can be fixed from either end).
  void _tapRight(int wordId) {
    if (_finished) return;
    final sel = _selectedLeft;
    if (sel != null) {
      _link(sel, wordId);
      return;
    }
    final linkedLeft = _links.entries
        .where((e) => e.value == wordId && !_locked.contains(e.key))
        .map((e) => e.key)
        .firstOrNull;
    if (linkedLeft != null) _unlink(linkedLeft);
  }

  void _check() {
    if (_finished) return;
    setState(() {
      _wrongNow.clear();
      _links.forEach((l, r) {
        if (_locked.contains(l)) return;
        if (l == r) {
          _locked.add(l);
        } else {
          _wrongNow.add(l);
          _wrongAttempts[l] = (_wrongAttempts[l] ?? 0) + 1;
        }
      });
    });
    if (_locked.length == widget.bundles.length) {
      _finished = true;
      widget.onAllRated({
        for (final b in widget.bundles)
          b.word.id: (_wrongAttempts[b.word.id] ?? 0) == 0
              ? Rating.good
              : Rating.hard,
      });
    }
  }

  // ---- drag-a-line gestures (start on a left chip, release on a right chip)

  Offset? _toLocal(Offset global) {
    final box = _paintKey.currentContext?.findRenderObject() as RenderBox?;
    return box?.globalToLocal(global);
  }

  void _onPanStart(int leftId, DragStartDetails d) {
    if (_locked.contains(leftId) || _finished) return;
    setState(() {
      _dragFromLeft = leftId;
      _dragPos = _toLocal(d.globalPosition);
    });
  }

  void _onPanUpdate(DragUpdateDetails d) {
    if (_dragFromLeft == null) return;
    setState(() => _dragPos = _toLocal(d.globalPosition));
  }

  void _onPanEnd(DragEndDetails d) {
    final from = _dragFromLeft;
    final pos = _dragPos;
    if (from != null && pos != null) {
      final target = _hitRightChip(pos);
      if (target != null) _link(from, target);
    }
    setState(() {
      _dragFromLeft = null;
      _dragPos = null;
    });
  }

  /// Which right chip (if any) contains [local] (paint-area coordinates)?
  int? _hitRightChip(Offset local) {
    final stackBox = _paintKey.currentContext?.findRenderObject() as RenderBox?;
    if (stackBox == null) return null;
    for (final t in _right) {
      final box = _rightKeys[t.wordId]?.currentContext?.findRenderObject()
          as RenderBox?;
      if (box == null || !box.hasSize) continue;
      final topLeft = box.localToGlobal(Offset.zero, ancestor: stackBox);
      if ((topLeft & box.size).inflate(6).contains(local)) return t.wordId;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.appColors;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'ลากเส้นจับคู่ (หรือแตะซ้ายแล้วแตะขวา) · แตะคำที่โยงแล้วเพื่อแก้คู่',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 8),
        CustomPaint(
          key: _paintKey,
          foregroundPainter: _LinkLinePainter(
            paintKey: _paintKey,
            leftKeys: _leftKeys,
            rightKeys: _rightKeys,
            links: Map.of(_links),
            locked: Set.of(_locked),
            wrong: Set.of(_wrongNow),
            dragFromLeft: _dragFromLeft,
            dragPos: _dragPos,
            pairColors: _pairColor,
            wrongColor: colors.danger,
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: Column(children: _left.map(_leftChip).toList())),
              const SizedBox(width: 40), // room for the lines to breathe
              Expanded(child: Column(children: _right.map(_rightChip).toList())),
            ],
          ),
        ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: _allLinked && !_finished ? _check : null,
          child: const Text('ตรวจคำตอบ'),
        ),
      ],
    );
  }

  Widget _leftChip(_MatchingTile t) {
    final locked = _locked.contains(t.wordId);
    final wrong = _wrongNow.contains(t.wordId);
    final selected = _selectedLeft == t.wordId;
    final linked = _links.containsKey(t.wordId);
    final colors = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: GestureDetector(
        onPanStart: (d) => _onPanStart(t.wordId, d),
        onPanUpdate: _onPanUpdate,
        onPanEnd: _onPanEnd,
        onDoubleTap: () => _unlink(t.wordId),
        child: Container(
          key: _leftKeys[t.wordId],
          child: ChoiceChip(
            label: Text(t.text),
            selected: selected,
            backgroundColor: locked
                ? colors.success.withValues(alpha: 0.3)
                : wrong
                    ? colors.danger.withValues(alpha: 0.2)
                    : null,
            side: linked && !locked && !wrong
                ? BorderSide(color: _pairColor[t.wordId]!, width: 2)
                : null,
            onSelected: locked ? null : (_) => _tapLeft(t.wordId),
          ),
        ),
      ),
    );
  }

  Widget _rightChip(_MatchingTile t) {
    final lockedTo = _locked.any((l) => _links[l] == t.wordId);
    // Which (unlocked) left word points at this right chip — used to tint
    // the border with that pair's line color.
    final linkedLeft = _links.entries
        .where((e) => e.value == t.wordId)
        .map((e) => e.key)
        .firstOrNull;
    final colors = context.appColors;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Container(
        key: _rightKeys[t.wordId],
        child: ActionChip(
          label: Text(t.text),
          backgroundColor:
              lockedTo ? colors.success.withValues(alpha: 0.3) : null,
          side: linkedLeft != null && !lockedTo
              ? BorderSide(
                  color: _wrongNow.contains(linkedLeft)
                      ? colors.danger
                      : _pairColor[linkedLeft]!,
                  width: 2,
                )
              : null,
          onPressed: lockedTo ? null : () => _tapRight(t.wordId),
        ),
      ),
    );
  }
}

/// Draws the link lines on top of the two chip columns. Endpoints are read
/// straight from each chip's RenderBox at paint time (paint runs after
/// layout within the frame, so positions are always current — no
/// post-frame-callback bookkeeping needed).
class _LinkLinePainter extends CustomPainter {
  _LinkLinePainter({
    required this.paintKey,
    required this.leftKeys,
    required this.rightKeys,
    required this.links,
    required this.locked,
    required this.wrong,
    required this.dragFromLeft,
    required this.dragPos,
    required this.pairColors,
    required this.wrongColor,
  });

  final GlobalKey paintKey;
  final Map<int, GlobalKey> leftKeys;
  final Map<int, GlobalKey> rightKeys;
  final Map<int, int> links;
  final Set<int> locked;
  final Set<int> wrong;
  final int? dragFromLeft;
  final Offset? dragPos;

  /// Per-pair line color, keyed by left word id.
  final Map<int, Color> pairColors;
  final Color wrongColor;

  Offset? _anchor(GlobalKey key, {required bool rightEdge}) {
    final stackBox = paintKey.currentContext?.findRenderObject() as RenderBox?;
    final box = key.currentContext?.findRenderObject() as RenderBox?;
    if (stackBox == null || box == null || !box.hasSize) return null;
    final topLeft = box.localToGlobal(Offset.zero, ancestor: stackBox);
    return topLeft + Offset(rightEdge ? box.size.width : 0, box.size.height / 2);
  }

  void _line(Canvas canvas, Offset a, Offset b, Color color) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    // Gentle S-curve reads better than a straight segment when many lines
    // cross the middle gutter.
    final mid = (a.dx + b.dx) / 2;
    final path = Path()
      ..moveTo(a.dx, a.dy)
      ..cubicTo(mid, a.dy, mid, b.dy, b.dx, b.dy);
    canvas.drawPath(path, paint);
    canvas.drawCircle(a, 3.5, Paint()..color = color);
    canvas.drawCircle(b, 3.5, Paint()..color = color);
  }

  @override
  void paint(Canvas canvas, Size size) {
    links.forEach((leftId, rightId) {
      final a = _anchor(leftKeys[leftId]!, rightEdge: true);
      final rightKey = rightKeys[rightId];
      final b = rightKey == null ? null : _anchor(rightKey, rightEdge: false);
      if (a == null || b == null) return;
      final color = wrong.contains(leftId)
          ? wrongColor
          : pairColors[leftId] ?? wrongColor;
      _line(canvas, a, b, color);
    });
    // Live drag preview.
    final from = dragFromLeft;
    final pos = dragPos;
    if (from != null && pos != null) {
      final a = _anchor(leftKeys[from]!, rightEdge: true);
      if (a != null) {
        final c = pairColors[from] ?? wrongColor;
        _line(canvas, a, pos, c.withValues(alpha: 0.7));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _LinkLinePainter old) =>
      old.links.toString() != links.toString() ||
      old.locked.length != locked.length ||
      old.wrong.length != wrong.length ||
      old.dragFromLeft != dragFromLeft ||
      old.dragPos != dragPos;
}
