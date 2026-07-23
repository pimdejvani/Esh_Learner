/// Motivation layer (SPEC.md section 10): streak, calendar heatmap, word
/// status counts. Heatmap grid pattern borrowed from Gymmer_App's
/// month_grid/calendar widget, adapted from workout-days to
/// review-counts-per-day. Also hosts two small Phase 2 additions that
/// didn't warrant their own tab: a focus-topic picker (SPEC.md 6.4/8 "ปัก
/// หมวด focus ได้") and a link to the Credits/Licenses page (section 5).
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/vocab_store.dart';
import 'package:vocab_app/domain/streaks.dart';
import 'package:vocab_app/models/srs_state.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/credits_page.dart';
import 'package:vocab_app/widgets/highlight_card.dart';

class ProgressPage extends StatefulWidget {
  const ProgressPage({super.key, required this.store});

  final VocabStore store;

  @override
  State<ProgressPage> createState() => _ProgressPageState();
}

class _ProgressPageState extends State<ProgressPage> {
  Map<String, DailyStats> _stats = {};
  Map<CardState, int> _statusCounts = {};
  List<Topic> _topics = [];
  int? _focusTopicId;
  int _dueCount = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final now = DateTime.now();
    final from = DateTime(now.year, now.month - 2, 1);
    final stats = await widget.store.loadDailyStatsRange(from, now);
    final state = await widget.store.load();
    final topics = await widget.store.loadTopics();
    final counts = <CardState, int>{
      for (final s in CardState.values) s: 0,
    };
    var dueCount = 0;
    for (final w in state.words) {
      final srs = state.srsStates[w.id];
      counts[srs?.state ?? CardState.newState] =
          (counts[srs?.state ?? CardState.newState] ?? 0) + 1;
      if (srs != null && !srs.dueAt.isAfter(now)) dueCount++;
    }
    setState(() {
      _stats = stats;
      _statusCounts = counts;
      _topics = topics;
      _focusTopicId = int.tryParse(state.settings['focus_topic'] ?? '');
      _dueCount = dueCount;
      _loading = false;
    });
  }

  Future<void> _setFocusTopic(int? topicId) async {
    await widget.store.saveSetting('focus_topic', topicId?.toString() ?? '');
    setState(() => _focusTopicId = topicId);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    final keptDates = {
      for (final e in _stats.entries)
        if (e.value.streakKept) e.key,
    };
    final streak = dayStreak(keptDates, now: DateTime.now());
    final heat = monthHeatmap(
      {for (final e in _stats.entries) e.key: e.value.reviewsDone},
      DateTime.now(),
    );

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // "At-a-glance" summary — the reference site's colorful pastel
        // highlight-card pattern (SPEC.md section 13 / NOTES.md's UI design
        // pass), distinct from the clean white-bordered content cards used
        // further down this page.
        Row(
          children: [
            Expanded(
              child: HighlightCard(
                icon: Icons.local_fire_department,
                title: '$streak วัน',
                subtitle: 'Streak',
                tone: HighlightTone.blue,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: HighlightCard(
                icon: Icons.event_available,
                title: '$_dueCount คำ',
                subtitle: 'ค้างทวนวันนี้',
                tone: HighlightTone.sky,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: HighlightCard(
                icon: Icons.auto_awesome,
                title: '${_stats[dateKey(DateTime.now())]?.newIntroduced ?? 0} คำ',
                subtitle: 'คำใหม่วันนี้',
                tone: HighlightTone.lavender,
              ),
            ),
          ],
        ),
        const SizedBox(height: 20),
        Text('สถานะคำ', style: Theme.of(context).textTheme.titleMedium),
        Wrap(
          spacing: 8,
          children: [
            for (final state in CardState.values)
              Chip(label: Text('${_labelFor(state)}: ${_statusCounts[state] ?? 0}')),
          ],
        ),
        const SizedBox(height: 16),
        Text('ปฏิทินการทวน', style: Theme.of(context).textTheme.titleMedium),
        _HeatmapGrid(heat: heat),
        // Focus topic (SPEC.md 6.4/8): hidden entirely when `topics` is
        // still empty (content pipeline hasn't populated it yet) instead
        // of showing a picker with nothing to pick.
        if (_topics.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text('หมวดที่อยากโฟกัส (Focus topic)', style: Theme.of(context).textTheme.titleMedium),
          DropdownButton<int?>(
            value: _focusTopicId,
            hint: const Text('ไม่มี'),
            items: [
              const DropdownMenuItem<int?>(value: null, child: Text('ไม่มี')),
              for (final t in _topics)
                DropdownMenuItem<int?>(value: t.id, child: Text('${t.name} (${t.cefr})')),
            ],
            onChanged: _setFocusTopic,
          ),
        ],
        const SizedBox(height: 16),
        Card(
          child: ListTile(
            leading: const Icon(Icons.info_outline),
            title: const Text('Credits / Licenses'),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => CreditsPage(store: widget.store)),
            ),
          ),
        ),
      ],
    );
  }

  String _labelFor(CardState s) {
    switch (s) {
      case CardState.newState:
        return 'New';
      case CardState.learning:
        return 'Learning';
      case CardState.young:
        return 'Young';
      case CardState.mature:
        return 'Mature';
    }
  }
}

class _HeatmapGrid extends StatelessWidget {
  const _HeatmapGrid({required this.heat});

  final Map<String, int> heat;

  Color _colorFor(int count, BuildContext context) {
    final base = Theme.of(context).colorScheme.primary;
    if (count == 0) return base.withValues(alpha: 0.08);
    if (count < 5) return base.withValues(alpha: 0.35);
    if (count < 15) return base.withValues(alpha: 0.65);
    return base;
  }

  @override
  Widget build(BuildContext context) {
    final entries = heat.entries.toList()..sort((a, b) => a.key.compareTo(b.key));
    return Wrap(
      spacing: 4,
      runSpacing: 4,
      children: [
        for (var i = 0; i < entries.length; i++)
          Tooltip(
            message: '${entries[i].key}: ${entries[i].value} ครั้ง',
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: 1),
              duration: Duration(milliseconds: 200 + (i % 31) * 8),
              curve: Curves.easeOut,
              builder: (context, t, child) => Opacity(opacity: t, child: child),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                width: 16,
                height: 16,
                decoration: BoxDecoration(
                  color: _colorFor(entries[i].value, context),
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
