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
      return Center(child: Text('โหลดคำศัพท์ไม่สำเร็จ: $error'));
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
                  hintText: 'ค้นหา: อังกฤษ / คำอ่าน / ความหมายไทย',
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
                'พบ ${results.length} คำ',
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ),
            Expanded(
              child: results.isEmpty
                  ? const Center(child: Text('ไม่พบคำที่ค้นหา'))
                  : ListView.builder(
                      padding: const EdgeInsets.only(bottom: 96),
                      itemCount: results.length,
                      itemBuilder: (context, i) =>
                          _WordTile(bundle: results[i], tts: widget.tts),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WordTile extends StatelessWidget {
  const _WordTile({required this.bundle, required this.tts});

  final WordBundle bundle;
  final TtsService tts;

  @override
  Widget build(BuildContext context) {
    final word = bundle.word;
    return ListTile(
      title: Row(
        children: [
          Flexible(
            child: Text(
              word.headword,
              style: const TextStyle(fontWeight: FontWeight.w600),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 8),
          Chip(
            label: Text(word.cefr, style: const TextStyle(fontSize: 11)),
            visualDensity: VisualDensity.compact,
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            padding: EdgeInsets.zero,
          ),
        ],
      ),
      subtitle: Text(
        '${word.thaiReading} · ${bundle.coreSense.meaningTh}',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: IconButton(
        icon: const Icon(Icons.volume_up),
        tooltip: 'ฟังเสียง',
        onPressed: () => tts.speak(word.headword),
      ),
      onTap: () => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => WordDetailPage(bundle: bundle, tts: tts),
        ),
      ),
    );
  }
}
