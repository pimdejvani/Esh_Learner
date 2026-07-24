/// Dictionary / word-search tab (user request 2026-07-24: "อยากให้มี
/// feature หาคำศัพย์"). One search box filters the whole word list live —
/// matching the English headword, the Thai reading, any sense's Thai
/// meaning, or any inflected form — and tapping a result opens the full
/// [WordDetailPage] entry. Bundles are loaded once on open (a few hundred
/// words is cheap) so filtering is pure in-memory.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/data/vocab_store.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/screens/word_detail_page.dart';
import 'package:vocab_app/widgets/speak_buttons.dart';

class DictionaryPage extends StatefulWidget {
  const DictionaryPage({super.key, required this.store, required this.tts});

  final VocabStore store;
  final TtsService tts;

  @override
  State<DictionaryPage> createState() => _DictionaryPageState();
}

class _DictionaryPageState extends State<DictionaryPage> {
  List<WordBundle>? _bundles;
  String _query = '';
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final state = await widget.store.load();
      final ids = state.words.map((w) => w.id).toList();
      final bundles = await widget.store.loadWordBundles(ids);
      if (mounted) setState(() => _bundles = bundles);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  /// Opens a word's full entry with its 5 closest words (item 1). Closeness
  /// from `related_words`, resolved to Words we have loaded, top 5 — shown
  /// regardless of whether the player has met them. Tapping a similar word
  /// opens ITS entry the same way (recursively).
  void _openWord(BuildContext context, WordBundle bundle) {
    final byId = {for (final b in _bundles ?? <WordBundle>[]) b.word.id: b};
    final similar = [
      ...bundle.related.where((r) => !r.isGiveaway),
    ]..sort((a, b) => b.closeness.compareTo(a.closeness));
    final seen = <int>{};
    final words = <Word>[];
    for (final r in similar) {
      if (words.length >= 5) break;
      final b = byId[r.relatedWordId];
      if (b == null || !seen.add(b.word.id)) continue;
      words.add(b.word);
    }
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => WordDetailPage(
          bundle: bundle,
          tts: widget.tts,
          similar: words,
          onOpenSimilar: (w) {
            final b = byId[w.id];
            if (b != null) _openWord(context, b);
          },
        ),
      ),
    );
  }

  bool _matches(WordBundle b, String q) {
    if (b.word.headword.toLowerCase().contains(q)) return true;
    if (b.word.thaiReading.contains(q)) return true;
    for (final s in b.senses) {
      if (s.meaningTh.contains(q)) return true;
    }
    for (final f in b.forms) {
      if (f.formText.toLowerCase().contains(q)) return true;
    }
    return false;
  }

  @override
  Widget build(BuildContext context) {
    final error = _error;
    if (error != null) {
      return Center(child: Text('Failed to load words: $error'));
    }
    final bundles = _bundles;
    if (bundles == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final q = _query.trim().toLowerCase();
    final results =
        q.isEmpty ? bundles : bundles.where((b) => _matches(b, q)).toList();

    // Mobile-first: same centered max-480 column as the play screen.
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
              child: TextField(
                autofocus: false,
                decoration: InputDecoration(
                  hintText: 'Search: English / reading / Thai meaning',
                  prefixIcon: const Icon(Icons.search),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                  ),
                  isDense: true,
                ),
                onChanged: (v) => setState(() => _query = v),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Text(
                '${results.length} words',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ),
            Expanded(
              child: results.isEmpty
                  ? const Center(child: Text('No matches'))
                  : ListView.builder(
                      padding: const EdgeInsets.only(bottom: 96),
                      itemCount: results.length,
                      itemBuilder: (context, i) => _WordTile(
                        bundle: results[i],
                        tts: widget.tts,
                        onOpen: () => _openWord(context, results[i]),
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WordTile extends StatelessWidget {
  const _WordTile({required this.bundle, required this.tts, required this.onOpen});

  final WordBundle bundle;
  final TtsService tts;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final word = bundle.word;
    return ListTile(
      title: Text(
        word.headword,
        style: const TextStyle(fontWeight: FontWeight.w600),
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        '${word.thaiReading} · ${bundle.coreSense.meaningTh}',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: SpeakButtons(tts: tts, text: word.headword),
      onTap: onOpen,
    );
  }
}
