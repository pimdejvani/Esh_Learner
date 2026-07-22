/// Credits/Licenses page (SPEC.md section 5's copyright note: "ต้องมีหน้า
/// 'Credits/Licenses' ในแอปแสดงที่มาของคำแปล, related words และภาพ").
/// Translation and image attribution are read from the distinct
/// `words.translation_source/translation_license` and
/// `words.image_license/image_author` values actually present in the DB
/// (via [VocabStore.load]'s already-loaded word list), not hardcoded, so
/// this stays accurate as the content pipeline's data changes. The
/// related-words (SWOW/WordNet) attribution is static text — `related_words`
/// has no per-row source/license column in the schema (SPEC.md section 4),
/// only a dataset-level source documented in SPEC.md section 5/13 and
/// NOTES.md, so there's nothing per-word to query for that section.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/vocab_store.dart';
import 'package:vocab_app/models/word.dart';

class CreditsPage extends StatefulWidget {
  const CreditsPage({super.key, required this.store});

  final VocabStore store;

  @override
  State<CreditsPage> createState() => _CreditsPageState();
}

class _CreditsPageState extends State<CreditsPage> {
  List<Word> _words = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final state = await widget.store.load();
    setState(() {
      _words = state.words;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Credits / Licenses')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    final translationSources = <String>{
      for (final w in _words)
        if (w.translationSource.isNotEmpty)
          '${w.translationSource} — ${w.translationLicense}',
    }..removeWhere((s) => s.trim() == '—');

    final imageSources = <String>{
      for (final w in _words)
        if ((w.imageLicense ?? '').isNotEmpty || (w.imageAuthor ?? '').isNotEmpty)
          '${w.imageAuthor ?? 'ไม่ทราบผู้สร้าง'} — ${w.imageLicense ?? ''}',
    };

    return Scaffold(
      appBar: AppBar(title: const Text('Credits / Licenses')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _Section(
            title: 'คำแปล (Translations)',
            items: translationSources.isEmpty
                ? const ['ไม่มีข้อมูลแหล่งที่มาในฐานข้อมูลนี้']
                : translationSources.toList()..sort(),
          ),
          const SizedBox(height: 16),
          const _Section(
            title: 'คำที่เกี่ยวข้อง (Related words)',
            items: [
              'SWOW (Small World of Words, smallworldofwords.org) — CC BY-NC — '
                  'ข้อมูล free-association จากมนุษย์จริง ใช้ได้เพราะแอปนี้ non-commercial',
              'Princeton WordNet — ใช้กรอง synonym/antonym (is_giveaway) และหมวดคำ '
                  '(hypernym/category) สำหรับเกม Odd One Out',
            ],
          ),
          const SizedBox(height: 16),
          _Section(
            title: 'รูปภาพ (Images)',
            items: imageSources.isEmpty
                ? const ['ยังไม่มีรูปภาพในฐานข้อมูลนี้ (Openverse/Wikimedia, CC BY variants)']
                : imageSources.toList()..sort(),
          ),
          const SizedBox(height: 16),
          const _Section(
            title: 'ประโยคตัวอย่าง (Example sentences)',
            items: [
              'สร้างโดย LLM (ดู NOTES.md) — ไม่ได้คัดลอกจาก Oxford/dictionary ใด ๆ',
            ],
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.items});

  final String title;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            for (final item in items)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text('• $item'),
              ),
          ],
        ),
      ),
    );
  }
}
