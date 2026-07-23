/// Thin wrapper over flutter_tts (device TTS -> iOS AVSpeechSynthesizer),
/// per SPEC.md decision #4: free, offline, reads both words and sentences.
library;

import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  TtsService() : _tts = FlutterTts() {
    _tts.setLanguage('en-US');
    _tts.setSpeechRate(_normalRate);
  }

  static const _normalRate = 0.45;
  static const _slowRate = 0.22;

  final FlutterTts _tts;

  Future<void> speak(String text) => _speakAt(text, _normalRate);

  /// Slow, exaggerated pronunciation (user request 2026-07-23 for
  /// Dictation) — about half the normal rate so each phoneme is audible.
  Future<void> speakSlow(String text) => _speakAt(text, _slowRate);

  Future<void> _speakAt(String text, double rate) async {
    if (text.trim().isEmpty) return;
    await _tts.stop();
    await _tts.setSpeechRate(rate);
    await _tts.speak(text);
  }

  Future<void> stop() => _tts.stop();
}
