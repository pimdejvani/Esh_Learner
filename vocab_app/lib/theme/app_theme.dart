/// Simple Material theme for Phase 1-2 (SPEC.md section 13: "ระหว่าง Phase
/// 1-2 ใช้ UI เรียบง่ายไปก่อน" — default Material + correct layout, no
/// design-language pass until Phase 3 when the meeting-iq/shadcn reference
/// gets ported properly).
library;

import 'package:flutter/material.dart';

class AppTheme {
  static ThemeData light() => ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF3B82F6)),
    brightness: Brightness.light,
  );

  static ThemeData dark() => ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: const Color(0xFF3B82F6),
      brightness: Brightness.dark,
    ),
    brightness: Brightness.dark,
  );
}
