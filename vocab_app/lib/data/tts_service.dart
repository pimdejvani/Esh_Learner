/// Thin wrapper over flutter_tts (device TTS -> iOS AVSpeechSynthesizer),
/// per SPEC.md decision #4: free, offline, reads both words and sentences.
library;

import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  TtsService() : _tts = FlutterTts() {
    _tts.setLanguage('en-US');
    _tts.setSpeechRate(0.45);
  }

  final FlutterTts _tts;

  Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;
    await _tts.stop();
    await _tts.speak(text);
  }

  Future<void> stop() => _tts.stop();
}
