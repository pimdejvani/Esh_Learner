import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/data/vocab_store.dart';
import 'package:vocab_app/data/vocab_store_sqlite.dart';
import 'package:vocab_app/screens/dictionary_page.dart';
import 'package:vocab_app/screens/play_screen.dart';
import 'package:vocab_app/screens/progress_page.dart';
import 'package:vocab_app/theme/app_theme.dart';
import 'package:vocab_app/widgets/floating_pill_bar.dart';

void main() {
  // iOS/Android use the platform sqflite plugin directly. Desktop targets
  // (Windows/Linux/macOS) need the FFI-backed factory instead — this only
  // matters for the `flutter run -d windows` sanity check during dev; the
  // shipping target per SPEC.md is iOS.
  if (!kIsWeb && (Platform.isWindows || Platform.isLinux || Platform.isMacOS)) {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  }
  runApp(const VocabApp());
}

class VocabApp extends StatelessWidget {
  const VocabApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Oxford 3000 -> Thai',
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      // Dev preview: on web / desktop the app runs inside an iPhone 12 Pro
      // -sized frame (390x844) so what you see matches the real phone
      // target instead of smearing across a wide browser window. On an
      // actual phone it's a no-op (uses the real screen).
      builder: (context, child) => _PhoneFrame(child: child!),
      home: const _RootPage(),
    );
  }
}

/// Wraps [child] in a fixed iPhone 12 Pro viewport (390x844 logical px,
/// the shipping target's reference device) when running on web or a
/// desktop OS — a dev-time convenience so the mobile-first layout is seen
/// at true phone proportions. On Android/iOS it returns the child
/// untouched so the app fills the real device screen.
class _PhoneFrame extends StatelessWidget {
  const _PhoneFrame({required this.child});

  final Widget child;

  // iPhone 12 Pro logical resolution.
  static const _size = Size(390, 844);

  bool get _framed {
    if (kIsWeb) return true;
    return Platform.isWindows || Platform.isLinux || Platform.isMacOS;
  }

  @override
  Widget build(BuildContext context) {
    if (!_framed) return child;
    // Override MediaQuery so the app's own layout (SafeArea, max-width
    // clamps, responsive breakpoints) sees the phone size, not the window.
    final framed = MediaQuery(
      data: MediaQuery.of(context).copyWith(
        size: _size,
        padding: EdgeInsets.zero,
        viewInsets: EdgeInsets.zero,
        viewPadding: EdgeInsets.zero,
      ),
      child: SizedBox.fromSize(size: _size, child: child),
    );
    return ColoredBox(
      color: const Color(0xFF1C1C1E),
      child: Center(
        child: ClipRRect(
          borderRadius: BorderRadius.circular(40),
          child: SizedBox.fromSize(size: _size, child: framed),
        ),
      ),
    );
  }
}

class _RootPage extends StatefulWidget {
  const _RootPage();

  @override
  State<_RootPage> createState() => _RootPageState();
}

class _RootPageState extends State<_RootPage> {
  VocabStore? _store;
  final _tts = TtsService();
  int _tab = 0;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    final store = await VocabStoreSqlite.open();
    setState(() => _store = store);
  }

  @override
  Widget build(BuildContext context) {
    final store = _store;
    if (store == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final pages = [
      PlayScreen(store: store, tts: _tts),
      DictionaryPage(store: store, tts: _tts),
      ProgressPage(store: store),
    ];
    // Floating pill top/bottom chrome (SPEC.md section 13 / NOTES.md's UI
    // design pass) instead of a flush Material AppBar/NavigationBar — the
    // reference site's own persistent nav is a rounded-full bar with
    // visible margin from the screen edge.
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            const FloatingTopBar(title: 'Oxford 3000 -> Thai'),
            Expanded(child: pages[_tab]),
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: FloatingBottomNav(
          selectedIndex: _tab,
          onSelected: (i) => setState(() => _tab = i),
          items: const [
            FloatingNavItem(icon: Icons.play_arrow, label: 'Play'),
            FloatingNavItem(icon: Icons.search, label: 'Search'),
            FloatingNavItem(icon: Icons.bar_chart, label: 'Progress'),
          ],
        ),
      ),
    );
  }
}
