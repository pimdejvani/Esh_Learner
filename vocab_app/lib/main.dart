import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:vocab_app/data/tts_service.dart';
import 'package:vocab_app/data/vocab_store.dart';
import 'package:vocab_app/data/vocab_store_sqlite.dart';
import 'package:vocab_app/screens/play_screen.dart';
import 'package:vocab_app/screens/progress_page.dart';
import 'package:vocab_app/theme/app_theme.dart';

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
      home: const _RootPage(),
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
      ProgressPage(store: store),
    ];
    return Scaffold(
      appBar: AppBar(title: const Text('Oxford 3000 -> Thai')),
      body: pages[_tab],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.play_arrow), label: 'เล่น'),
          NavigationDestination(icon: Icon(Icons.bar_chart), label: 'ความก้าวหน้า'),
        ],
      ),
    );
  }
}
