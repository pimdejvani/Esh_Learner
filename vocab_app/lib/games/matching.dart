/// Matching (SPEC.md section 8 game 3). EN-TH pairs, 6-12 pairs depending
/// on how many due words are available in the batch. Batch game: emits one
/// rating per word once all pairs are matched (Good if matched without a
/// wrong attempt on that pair, Hard if it took a retry, per the same
/// "testing effect" spirit as the other games).
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';

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
  _MatchingTile(this.wordId, this.text, this.isEnglish);
  final int wordId;
  final String text;
  final bool isEnglish;
}

class _MatchingGameState extends State<MatchingGame> {
  late List<_MatchingTile> _left;
  late List<_MatchingTile> _right;
  final Set<int> _matchedWordIds = {};
  final Map<int, int> _wrongAttempts = {};
  int? _selectedLeftWordId;

  @override
  void initState() {
    super.initState();
    _left = widget.bundles
        .map((b) => _MatchingTile(b.word.id, b.word.headword, true))
        .toList()
      ..shuffle();
    _right = widget.bundles
        .map((b) => _MatchingTile(b.word.id, b.coreSense.meaningTh, false))
        .toList()
      ..shuffle();
  }

  void _tapLeft(int wordId) {
    if (_matchedWordIds.contains(wordId)) return;
    setState(() => _selectedLeftWordId = wordId);
  }

  void _tapRight(int wordId) {
    if (_matchedWordIds.contains(wordId) || _selectedLeftWordId == null) return;
    if (_selectedLeftWordId == wordId) {
      setState(() {
        _matchedWordIds.add(wordId);
        _selectedLeftWordId = null;
      });
      if (_matchedWordIds.length == widget.bundles.length) {
        final ratings = <int, Rating>{
          for (final b in widget.bundles)
            b.word.id: (_wrongAttempts[b.word.id] ?? 0) == 0
                ? Rating.good
                : Rating.hard,
        };
        widget.onAllRated(ratings);
      }
    } else {
      setState(() {
        _wrongAttempts[_selectedLeftWordId!] =
            (_wrongAttempts[_selectedLeftWordId!] ?? 0) + 1;
        _selectedLeftWordId = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Column(children: _left.map(_leftChip).toList())),
        const SizedBox(width: 12),
        Expanded(child: Column(children: _right.map(_rightChip).toList())),
      ],
    );
  }

  Widget _leftChip(_MatchingTile t) {
    final matched = _matchedWordIds.contains(t.wordId);
    final selected = _selectedLeftWordId == t.wordId;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: ChoiceChip(
        label: Text(t.text),
        selected: selected,
        disabledColor: Colors.green.withValues(alpha: 0.3),
        onSelected: matched ? null : (_) => _tapLeft(t.wordId),
      ),
    );
  }

  Widget _rightChip(_MatchingTile t) {
    final matched = _matchedWordIds.contains(t.wordId);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: ActionChip(
        label: Text(t.text),
        backgroundColor: matched ? Colors.green.withValues(alpha: 0.3) : null,
        onPressed: matched ? null : () => _tapRight(t.wordId),
      ),
    );
  }
}
