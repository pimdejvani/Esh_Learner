/// Odd One Out (SPEC.md section 8 game 6, Phase 2). A group of words is
/// shown; one ([oddWord]) doesn't belong with the rest ([groupWords]) —
/// semantic categorization, a recognition-level task per SPEC.md section
/// 7's ladder (learning-state words, alongside flashcard/Matching). No
/// hint system: SPEC.md 8b's two hint families are for retrieval-from-cue
/// (Cloze/flashcard-production/Scramble/Word Association) and spelling
/// (Dictation) respectively — categorization recognition isn't either.
library;

import 'dart:math';

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/theme/app_theme.dart';
import 'package:vocab_app/widgets/staggered_entrance.dart';
import 'package:vocab_app/widgets/swipe_up_detector.dart';
import 'package:vocab_app/widgets/game_stage.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

/// Builds an odd-one-out round: finds a "hub" word whose `related_words`
/// rows (any word_id in [relatedByWord]) name at least [groupSize] other
/// words in [pool] that (a) aren't [target] and (b) aren't themselves
/// related to [target] — i.e. a coherent group that [target] genuinely
/// doesn't belong to.
///
/// 2026-07-24 revision (user feedback "กลุ่มคำรู้สึกไม่ค่อยเหมือนกัน"):
/// - **One consistent coherence bar**: a row only counts as "same group"
///   when it's typed category data (`hypernym`/`category`/`part_of`) OR
///   its SWOW `closeness` ≥ [minCloseness]. Default 0.036 — started at
///   0.03 (≈ p75 of the seed's association strengths), raised +20% on
///   user feedback 2026-07-24 ("คำยังไม่เข้ากันเท่าที่ควร ปรับเพิ่มอีก
///   20%").
/// - **Minimum 3 group members**: the old fallback to a 2-word group is
///   gone. Fewer than [groupSize] strong members = no Odd round (caller
///   re-routes to flashcard).
/// - **[strict] early-game mode** (the player's first ~2 new-word blocks,
///   ~8 words): require MORE THAN 2 qualifying groups to choose from —
///   fewer means the data around today's words is too thin to guarantee
///   a clean round, so skip Odd entirely. Beyond that the normal rules
///   above apply.
/// - Any group above the bar is fair game: [random] (when given) picks
///   uniformly among ALL qualifying groups — passing the threshold is
///   the quality gate, no extra ranking needed (user 2026-07-24 "ถ้ามี
///   กลุ่มที่คะแนนเกินเกณฑ์ก็สุ่มกลุ่มได้เลย"). Without [random] the
///   best-scoring group is returned (deterministic for tests).
///
/// Returns null when no hub qualifies — callers should skip/re-route the
/// round rather than force a bad one.
class OddOneOutRound {
  const OddOneOutRound({
    required this.hubWordId,
    required this.groupWords,
    required this.memberRelations,
    this.category = '',
    this.explanationTh = '',
  });

  final int hubWordId;
  final List<Word> groupWords;
  final List<RelatedWord> memberRelations;

  /// The category the group shares and the reason it holds, both written when
  /// the content was built (`relation_groups`). The reveal shows these instead
  /// of reconstructing a reason after the answer.
  final String category;
  final String explanationTh;
}

OddOneOutRound? buildOddOneOutRound({
  required Word target,
  required List<Word> pool,
  required Map<int, List<RelatedWord>> relatedByWord,
  Map<int, RelationGroup> groupsByHub = const {},
  int groupSize = 3,
  double minCloseness = 0.036,
  bool strict = false,
  Random? random,
}) {
  const preferredTypes = {'hypernym', 'category', 'part_of'};
  final poolById = {for (final w in pool) w.id: w};

  final candidates = <(double, OddOneOutRound)>[];
  for (final hub in relatedByWord.entries) {
    if (hub.key == target.id) continue;
    if (hub.value.any((r) => r.relatedWordId == target.id)) {
      continue; // target IS related to this hub -> not a fair "odd one"
    }
    final rows = hub.value.where((r) {
      if (r.isGiveaway) return false;
      return preferredTypes.contains(r.relationType) ||
          r.closeness >= minCloseness;
    }).toList()..sort((a, b) => b.closeness.compareTo(a.closeness));
    final seen = <int>{};
    final members = <RelatedWord>[];
    for (final r in rows) {
      if (r.relatedWordId == target.id) continue;
      if (!poolById.containsKey(r.relatedWordId)) continue;
      if (!seen.add(r.relatedWordId)) continue;
      members.add(r);
    }
    if (members.length < groupSize) continue;
    final top = members.take(groupSize).toList();
    final score = top.fold(0.0, (s, r) => s + r.closeness);
    final group = groupsByHub[hub.key];
    candidates.add((
      score,
      OddOneOutRound(
        hubWordId: hub.key,
        groupWords: [for (final r in top) poolById[r.relatedWordId]!],
        memberRelations: top,
        category: group?.category ?? '',
        explanationTh: group?.explanationTh ?? '',
      ),
    ));
  }

  if (candidates.isEmpty) return null;
  if (strict && candidates.length <= 2) return null;
  if (random != null) return candidates[random.nextInt(candidates.length)].$2;
  candidates.sort((a, b) => b.$1.compareTo(a.$1));
  return candidates.first.$2;
}

/// Backward-compatible group-only API used by existing callers/tests.
List<Word>? buildOddOneOutGroup({
  required Word target,
  required List<Word> pool,
  required Map<int, List<RelatedWord>> relatedByWord,
  Map<int, RelationGroup> groupsByHub = const {},
  int groupSize = 3,
  double minCloseness = 0.036,
  bool strict = false,
  Random? random,
}) => buildOddOneOutRound(
  target: target,
  pool: pool,
  relatedByWord: relatedByWord,
  groupsByHub: groupsByHub,
  groupSize: groupSize,
  minCloseness: minCloseness,
  strict: strict,
  random: random,
)?.groupWords;

/// One line explaining why a member belongs. The stored `explanation_th` is
/// the real answer; the typed fallbacks only cover rows written before the
/// content build started storing one.
String oddOneOutRelationText({
  required Word hub,
  required Word member,
  required String relationType,
  String? explanationTh,
}) {
  if ((explanationTh ?? '').isNotEmpty) return explanationTh!;
  return switch (relationType) {
    'hypernym' || 'kind_of' => '${member.headword} เป็นประเภทหนึ่งของ ${hub.headword}',
    'part_of' => '${member.headword} เป็นส่วนหนึ่งของ ${hub.headword}',
    'produces' => '${hub.headword} ทำให้เกิด ${member.headword}',
    'used_for' => '${member.headword} ใช้คู่กับ ${hub.headword}',
    'opposite' => '${member.headword} ตรงข้ามกับ ${hub.headword}',
    _ => '${hub.headword} กับ ${member.headword} มักถูกนึกถึงคู่กัน',
  };
}

/// The reveal's reason lines, with members that share a reason collapsed
/// into ONE line (user request 2026-07-24: "หากแต่ละคำมีการอธิบายเหมือนกัน
/// ให้อธิบายแค่รอบเดียว").
///
/// Group rows usually differ only in which member they name — three lines
/// of "career กับ X เป็นคำที่คนมักนึกถึงคู่กัน…" is the same sentence read
/// three times. Two lines are treated as the same reason when they match
/// after blanking out the member's headword; the collapsed line then names
/// every member of that reason at once ("career กับ job, work, money …").
/// Genuinely different reasons stay on their own lines, in member order.
List<String> oddOneOutReasonLines({
  required Word hub,
  required List<Word> members,
  required List<RelatedWord> relations,
}) {
  const slot = '{member}'; // sentinel: never appears in content text
  final order = <String>[];
  final names = <String, List<String>>{};
  final shapes = <String, String>{};

  for (final relation in relations) {
    final member = members
        .where((w) => w.id == relation.relatedWordId)
        .firstOrNull;
    if (member == null) continue;
    final text = oddOneOutRelationText(
      hub: hub,
      member: member,
      relationType: relation.relationType,
      explanationTh: relation.explanationTh,
    );
    final shape = text.replaceAll(member.headword, slot);
    if (!names.containsKey(shape)) {
      order.add(shape);
      shapes[shape] = text;
    }
    names.putIfAbsent(shape, () => []).add(member.headword);
  }

  return [
    for (final shape in order)
      // No slot in the shape means the line never named its member, so the
      // members' texts were identical outright — show it once, as written.
      shape.contains(slot)
          ? shape.replaceAll(slot, names[shape]!.join(', '))
          : shapes[shape]!,
  ];
}

class OddOneOutGame extends StatefulWidget {
  const OddOneOutGame({
    super.key,
    required this.oddWord,
    required this.groupWords,
    required this.hubWord,
    required this.memberRelations,
    required this.onRated,
    this.category = '',
    this.groupExplanationTh = '',
    this.oddBundle,
    this.tts,
  });

  /// The word actually being tested (the true "odd one out").
  final Word oddWord;

  /// The words that belong together (distractors).
  final List<Word> groupWords;

  /// Stored relation data used to explain the round without generated text.
  final Word hubWord;

  /// The group's shared category and the stored reason it holds — written when
  /// the content was built, not composed here after the answer.
  final String category;
  final String groupExplanationTh;
  final List<RelatedWord> memberRelations;

  /// Called once with the target's rating and, on a wrong answer, the id
  /// of the group word the player wrongly picked (null when correct) —
  /// user request 2026-07-24: a wrong pick should also cost the PICKED
  /// word's proficiency, not just the target's.
  final void Function(Rating rating, int? wrongPickedWordId) onRated;

  /// The odd word's own entry, shown on the reveal (user request
  /// 2026-07-24: "ตอนที่เฉลยให้มีการใช้อธิบายคำศัพท์ของคำนั้นด้วย") — being
  /// told a word doesn't belong teaches nothing unless you also learn what
  /// it means. Null (with [tts] null) simply omits the card, so the game
  /// still renders for callers/tests that have no bundle loaded.
  final WordBundle? oddBundle;
  final TtsService? tts;

  @override
  State<OddOneOutGame> createState() => _OddOneOutGameState();
}

class _OddOneOutGameState extends State<OddOneOutGame> {
  final _stopwatch = Stopwatch()..start();
  late final List<Word> _options;
  int? _selectedId;
  bool _submitted = false;

  @override
  void initState() {
    super.initState();
    _options = [widget.oddWord, ...widget.groupWords]..shuffle();
  }

  void _select(int wordId) {
    if (_submitted) return;
    _stopwatch.stop();
    setState(() {
      _selectedId = wordId;
      _submitted = true;
    });
  }

  void _rate() {
    final correct = _selectedId == widget.oddWord.id;
    final fast = _stopwatch.elapsedMilliseconds <= 3000;
    widget.onRated(
      correct ? (fast ? Rating.easy : Rating.good) : Rating.again,
      correct ? null : _selectedId,
    );
  }

  @override
  Widget build(BuildContext context) {
    return SwipeUpDetector(
      // Swipe up advances once answered (item 10); before that a pick is
      // still required, so it's a no-op.
      onSwipeUp: () {
        if (_submitted) _rate();
      },
      child: GameStage(
        onTapToContinue: _submitted ? _rate : null,
        bottomAction: _submitted
            ? FilledButton(onPressed: _rate, child: const Text('Next'))
            : null,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(
              'Which word doesn\'t belong?',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            // One option per row (user request 2026-07-24: "อยากให้ทั้งสี่คำ
            // เป็นแนวตั้ง") — a wrapped row put two words on one line and
            // two on the next, which reads as two pairs rather than four
            // equal choices.
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (var i = 0; i < _options.length; i++)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: StaggeredEntrance(
                      index: i,
                      child: _optionChip(_options[i]),
                    ),
                  ),
              ],
            ),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 260),
              transitionBuilder: (child, anim) => FadeTransition(
                opacity: anim,
                child: SizeTransition(sizeFactor: anim, child: child),
              ),
              child: _submitted
                  ? Column(
                      key: const ValueKey('result'),
                      children: [
                        const SizedBox(height: 16),
                        Text(
                          _selectedId == widget.oddWord.id
                              ? 'Correct! "${widget.oddWord.headword}" doesn\'t belong'
                              : 'The odd one out is "${widget.oddWord.headword}"',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.bodyLarge,
                        ),
                        const SizedBox(height: 10),
                        Text(
                          widget.category.isNotEmpty
                              ? 'กลุ่มนี้คือ ${widget.category} (${widget.hubWord.headword})'
                              : 'Common link: ${widget.hubWord.headword}',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        if (widget.groupExplanationTh.isNotEmpty) ...[
                          const SizedBox(height: 4),
                          Text(
                            widget.groupExplanationTh,
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                        const SizedBox(height: 4),
                        for (final line in oddOneOutReasonLines(
                          hub: widget.hubWord,
                          members: widget.groupWords,
                          relations: widget.memberRelations,
                        ))
                          Padding(
                            padding: const EdgeInsets.only(bottom: 2),
                            child: Text(
                              line,
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.bodySmall,
                            ),
                          ),
                        const SizedBox(height: 6),
                        // Why the target is out: it is the one word with no
                        // qualifying link to the hub, which is exactly how the
                        // round was built.
                        Text(
                          '"${widget.oddWord.headword}" ไม่มีความเชื่อมโยงกับ'
                          '${widget.category.isNotEmpty ? widget.category : widget.hubWord.headword}'
                          ' จึงไม่เข้าพวก',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        // …and what that word actually means, same card the
                        // other games show after an answer.
                        if (widget.oddBundle != null && widget.tts != null) ...[
                          const SizedBox(height: 12),
                          WordResultCard(
                            bundle: widget.oddBundle!,
                            tts: widget.tts!,
                            onOpenDetail: () => Navigator.of(context).push(
                              MaterialPageRoute(
                                builder: (_) => WordDetailPage(
                                  bundle: widget.oddBundle!,
                                  tts: widget.tts!,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ],
                    )
                  : const SizedBox.shrink(key: ValueKey('empty')),
            ),
          ],
        ),
      ),
    );
  }

  Widget _optionChip(Word w) {
    final colors = context.appColors;
    final selected = _selectedId == w.id;
    final isOdd = w.id == widget.oddWord.id;
    Color? color;
    Widget? avatar;
    if (_submitted && selected) {
      color = isOdd
          ? colors.success.withValues(alpha: 0.35)
          : colors.danger.withValues(alpha: 0.35);
      // Explicit right/wrong icon on the chip the player chose (user
      // feedback 2026-07-24 — the color alone read as "correct").
      avatar = Icon(
        isOdd ? Icons.check_circle : Icons.cancel,
        size: 18,
        color: isOdd ? colors.success : colors.danger,
      );
    } else if (_submitted && isOdd) {
      color = colors.success.withValues(alpha: 0.18);
      avatar = Icon(Icons.check_circle, size: 18, color: colors.success);
    }
    // Same full-width option button as Word Association, so a stacked list
    // of four reads as four equal choices with comfortable tap targets.
    return SizedBox(
      width: double.infinity,
      child: ChoiceChip(
        avatar: avatar,
        labelPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
        label: Text(
          w.headword,
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        selected: selected,
        selectedColor: color,
        backgroundColor: color,
        onSelected: _submitted ? null : (_) => _select(w.id),
      ),
    );
  }
}
