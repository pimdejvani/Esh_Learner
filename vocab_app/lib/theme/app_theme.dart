/// Real design-language theme (Phase 3 UI pass, SPEC.md section 13).
///
/// UX/logic is now settled (Phase 1 + Phase 2 complete per NOTES.md), so
/// this replaces the Phase 1-2 "default Material, don't polish yet"
/// placeholder with an actual `ThemeData` built from design tokens
/// extracted directly from the reference site named in SPEC.md section 13
/// (`meeting-iq`, https://meetingiq.shadcn.io) via live browser devtools
/// inspection — not re-derived/guessed. See NOTES.md's "UI design pass"
/// section for the full token table and citation.
///
/// Structural language: soft cyan-tinted background, pure-white (or dark
/// elevated) cards with a THIN solid near-black/near-white outline instead
/// of Material's usual drop-shadow elevation, 12px card radius, fully
/// pill-shaped buttons, and Plus Jakarta Sans (Google Fonts — the nearest
/// open equivalent to the reference's commercial "Satoshi") as the
/// typeface. Headings are bold/heavy (700-800) per direct inspection of
/// the reference's actual rendered screenshots — size does NOT carry
/// hierarchy alone here, weight does too.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Colors this app needs that don't have a natural home in Flutter's
/// [ColorScheme] — the rating semantics (again/hard/good/easy) every game
/// uses, and the tonal "highlight card" family (pastel blocks + a black/
/// white rounded-square icon badge) the reference site uses for
/// feature-highlight / at-a-glance summary sections, distinct from the
/// clean white-bordered cards used for dense content (word detail entries,
/// sentence lists, credits).
class AppColors extends ThemeExtension<AppColors> {
  const AppColors({
    required this.success,
    required this.warning,
    required this.danger,
    required this.highlightSky,
    required this.highlightLavender,
    required this.highlightBlue,
    required this.onHighlight,
    required this.badgeBackground,
    required this.badgeForeground,
  });

  /// Correct / "Good" or "Easy" rating, matched pairs, etc.
  final Color success;

  /// "Hard" rating / hint-used / near-miss.
  final Color warning;

  /// "Again" rating / wrong answer.
  final Color danger;

  /// Tonal pastel family riffing on the `#49ADFF` accent, used for
  /// feature-highlight / summary tiles (SPEC.md section 13's colorful-card
  /// pattern) rather than dense content.
  final Color highlightSky;
  final Color highlightLavender;
  final Color highlightBlue;

  /// Text/icon color that reads on any of the three highlight tones above.
  final Color onHighlight;

  /// The small rounded-square icon badge shown in the corner of a
  /// highlight card.
  final Color badgeBackground;
  final Color badgeForeground;

  static const light = AppColors(
    success: Color(0xFF16A34A),
    warning: Color(0xFFF59E0B),
    danger: Color(0xFFEF4444),
    highlightSky: Color(0xFFD6F1FF),
    highlightLavender: Color(0xFFE4E1FF),
    highlightBlue: Color(0xFF8FCBFF),
    onHighlight: Color(0xFF010101),
    badgeBackground: Color(0xFF010101),
    badgeForeground: Color(0xFFFFFFFF),
  );

  static const dark = AppColors(
    success: Color(0xFF34D399),
    warning: Color(0xFFFBBF24),
    danger: Color(0xFFF87171),
    highlightSky: Color(0xFF163247),
    highlightLavender: Color(0xFF241F3D),
    highlightBlue: Color(0xFF1D4E73),
    onHighlight: Color(0xFFF2FBFD),
    badgeBackground: Color(0xFFF2FBFD),
    badgeForeground: Color(0xFF0A1418),
  );

  @override
  AppColors copyWith({
    Color? success,
    Color? warning,
    Color? danger,
    Color? highlightSky,
    Color? highlightLavender,
    Color? highlightBlue,
    Color? onHighlight,
    Color? badgeBackground,
    Color? badgeForeground,
  }) {
    return AppColors(
      success: success ?? this.success,
      warning: warning ?? this.warning,
      danger: danger ?? this.danger,
      highlightSky: highlightSky ?? this.highlightSky,
      highlightLavender: highlightLavender ?? this.highlightLavender,
      highlightBlue: highlightBlue ?? this.highlightBlue,
      onHighlight: onHighlight ?? this.onHighlight,
      badgeBackground: badgeBackground ?? this.badgeBackground,
      badgeForeground: badgeForeground ?? this.badgeForeground,
    );
  }

  @override
  AppColors lerp(ThemeExtension<AppColors>? other, double t) {
    if (other is! AppColors) return this;
    Color l(Color a, Color b) => Color.lerp(a, b, t)!;
    return AppColors(
      success: l(success, other.success),
      warning: l(warning, other.warning),
      danger: l(danger, other.danger),
      highlightSky: l(highlightSky, other.highlightSky),
      highlightLavender: l(highlightLavender, other.highlightLavender),
      highlightBlue: l(highlightBlue, other.highlightBlue),
      onHighlight: l(onHighlight, other.onHighlight),
      badgeBackground: l(badgeBackground, other.badgeBackground),
      badgeForeground: l(badgeForeground, other.badgeForeground),
    );
  }
}

/// Convenience accessor: `context.appColors.success` instead of the more
/// verbose `Theme.of(context).extension<AppColors>()!`.
extension AppColorsX on BuildContext {
  AppColors get appColors => Theme.of(this).extension<AppColors>()!;
}

class AppTheme {
  // ---- Light tokens (extracted from meeting-iq.shadcn.io via devtools) ----
  static const _lightBackground = Color(0xFFE9FBFF);
  static const _lightSurface = Color(0xFFFFFFFF);
  static const _lightBorder = Color(0xFF010101);
  static const _lightPrimary = Color(0xFF49ADFF);
  static const _lightText = Color(0xFF010101);
  static const _lightMutedSurface = Color(0xFFF5F5F5);
  static const _lightMutedText = Color(0xFF737373);

  // ---- Dark tokens (no dark variant exposed on the reference site — see
  // SPEC.md section 13's note; derived to follow the same structural
  // language: thin light borders on dark cards, same sky-blue accent). ----
  static const _darkBackground = Color(0xFF0A1418);
  static const _darkSurface = Color(0xFF101B20);
  static const _darkBorder = Color(0x2BE9FBFF); // ~17% opacity light outline
  static const _darkPrimary = Color(0xFF49ADFF);
  static const _darkText = Color(0xFFF2FBFD);
  static const _darkMutedSurface = Color(0xFF172226);
  static const _darkMutedText = Color(0xFF93A3A8);

  static const double _cardRadius = 12;

  static ThemeData light() => _build(
    brightness: Brightness.light,
    background: _lightBackground,
    surface: _lightSurface,
    border: _lightBorder,
    primary: _lightPrimary,
    text: _lightText,
    mutedSurface: _lightMutedSurface,
    mutedText: _lightMutedText,
    colors: AppColors.light,
  );

  static ThemeData dark() => _build(
    brightness: Brightness.dark,
    background: _darkBackground,
    surface: _darkSurface,
    border: _darkBorder,
    primary: _darkPrimary,
    text: _darkText,
    mutedSurface: _darkMutedSurface,
    mutedText: _darkMutedText,
    colors: AppColors.dark,
  );

  static ThemeData _build({
    required Brightness brightness,
    required Color background,
    required Color surface,
    required Color border,
    required Color primary,
    required Color text,
    required Color mutedSurface,
    required Color mutedText,
    required AppColors colors,
  }) {
    final isDark = brightness == Brightness.dark;
    final onPrimary = Colors.white;

    final colorScheme = ColorScheme(
      brightness: brightness,
      primary: primary,
      onPrimary: onPrimary,
      secondary: mutedText,
      onSecondary: isDark ? Colors.black : Colors.white,
      error: colors.danger,
      onError: Colors.white,
      surface: surface,
      onSurface: text,
      surfaceContainerHighest: mutedSurface,
      onSurfaceVariant: mutedText,
      outline: border,
      outlineVariant: border.withValues(alpha: isDark ? 0.5 : 0.3),
      tertiary: colors.highlightBlue,
      onTertiary: colors.onHighlight,
    );

    final baseTextTheme = isDark
        ? Typography.material2021().white
        : Typography.material2021().black;
    final textTheme = _buildTextTheme(baseTextTheme, text);

    final pillShape = const StadiumBorder();
    final cardShape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(_cardRadius),
      side: BorderSide(color: border, width: 1),
    );

    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: background,
      canvasColor: background,
      fontFamily: GoogleFonts.plusJakartaSans().fontFamily,
      textTheme: textTheme,
      extensions: [colors],

      appBarTheme: AppBarTheme(
        backgroundColor: background,
        foregroundColor: text,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
        titleTextStyle: textTheme.headlineSmall,
        iconTheme: IconThemeData(color: text),
      ),

      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        surfaceTintColor: Colors.transparent,
        shadowColor: Colors.transparent,
        shape: cardShape,
      ),

      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primary,
          shape: pillShape,
          textStyle: textTheme.labelLarge,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        ),
      ),

      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: text,
          side: BorderSide(color: border, width: 1),
          shape: pillShape,
          textStyle: textTheme.labelLarge,
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: onPrimary,
          elevation: 0,
          shadowColor: Colors.transparent,
          shape: pillShape,
          textStyle: textTheme.labelLarge,
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
        ),
      ),

      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: onPrimary,
          shape: pillShape,
          textStyle: textTheme.labelLarge,
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 14),
        ),
      ),

      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(foregroundColor: primary),
      ),

      chipTheme: ChipThemeData(
        backgroundColor: mutedSurface,
        disabledColor: mutedSurface,
        selectedColor: primary.withValues(alpha: isDark ? 0.28 : 0.16),
        labelStyle: textTheme.labelMedium?.copyWith(color: text),
        secondaryLabelStyle: textTheme.labelMedium?.copyWith(color: text),
        side: BorderSide.none,
        shape: pillShape,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: mutedSurface,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(_cardRadius),
          borderSide: BorderSide(color: border, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(_cardRadius),
          borderSide: BorderSide(color: border, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(_cardRadius),
          borderSide: BorderSide(color: primary, width: 1.6),
        ),
        labelStyle: textTheme.bodyMedium?.copyWith(color: mutedText),
        hintStyle: textTheme.bodyMedium?.copyWith(color: mutedText),
      ),

      dividerTheme: DividerThemeData(color: border.withValues(alpha: 0.4), thickness: 1),

      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: surface,
        indicatorColor: primary.withValues(alpha: 0.16),
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        labelTextStyle: WidgetStatePropertyAll(textTheme.labelSmall),
      ),

      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: text,
          borderRadius: BorderRadius.circular(8),
        ),
        textStyle: TextStyle(color: background, fontSize: 12),
      ),

      snackBarTheme: SnackBarThemeData(
        backgroundColor: text,
        contentTextStyle: TextStyle(color: background),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_cardRadius)),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  /// Plus Jakarta Sans across the whole scale, with the reference's actual
  /// weight rhythm: big display/headline text is bold/heavy (700-800 —
  /// confirmed by inspecting the live site's rendered screenshots, not the
  /// originally-guessed "regular carries hierarchy" assumption), while body
  /// text stays regular and only small emphasis labels (buttons, chips) use
  /// semibold (600).
  static TextTheme _buildTextTheme(TextTheme base, Color color) {
    final withFont = GoogleFonts.plusJakartaSansTextTheme(base);
    TextStyle? w(TextStyle? s, FontWeight weight) =>
        s?.copyWith(fontWeight: weight, color: color);

    return withFont.copyWith(
      displayLarge: w(withFont.displayLarge, FontWeight.w800),
      displayMedium: w(withFont.displayMedium, FontWeight.w800),
      displaySmall: w(withFont.displaySmall, FontWeight.w800),
      headlineLarge: w(withFont.headlineLarge, FontWeight.w700),
      headlineMedium: w(withFont.headlineMedium, FontWeight.w700),
      headlineSmall: w(withFont.headlineSmall, FontWeight.w700),
      titleLarge: w(withFont.titleLarge, FontWeight.w700),
      titleMedium: w(withFont.titleMedium, FontWeight.w600),
      titleSmall: w(withFont.titleSmall, FontWeight.w600),
      bodyLarge: w(withFont.bodyLarge, FontWeight.w400),
      bodyMedium: w(withFont.bodyMedium, FontWeight.w400),
      bodySmall: w(withFont.bodySmall, FontWeight.w400),
      labelLarge: w(withFont.labelLarge, FontWeight.w600),
      labelMedium: w(withFont.labelMedium, FontWeight.w600),
      labelSmall: w(withFont.labelSmall, FontWeight.w600),
    );
  }
}
