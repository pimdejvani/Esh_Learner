/// Full dictionary entry (SPEC.md section 9b, layer 2). Explicitly out of
/// scope for Phase 1 ("word_detail_page.dart is Phase 2 — skip full entry
/// but can stub"). This stub shows the same content as the layer-1 result
/// card so the route exists and doesn't crash if navigated to, but the
/// full multi-sense / inline word-forms / all-5-sentences layout is
/// deferred — see NOTES.md.
library;

import 'package:flutter/material.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/models/word.dart';
import 'package:vocab_app/widgets/word_result_card.dart';

class WordDetailPage extends StatelessWidget {
  const WordDetailPage({super.key, required this.bundle, required this.tts});

  final WordBundle bundle;
  final TtsService tts;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(bundle.word.headword)),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            WordResultCard(bundle: bundle, tts: tts),
            const SizedBox(height: 12),
            const Text(
              '(Entry เต็ม: ทุก sense, รูปผัน inline, ประโยคครบ 5 — Phase 2)',
              style: TextStyle(fontStyle: FontStyle.italic),
            ),
          ],
        ),
      ),
    );
  }
}
