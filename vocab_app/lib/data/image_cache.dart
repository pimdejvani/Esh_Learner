/// Runtime open-license image fetch + local cache (SPEC.md decision #3 and
/// section 5.5). Words are shipped with `has_photo`/`image_url` resolved at
/// build time (Openverse/Wikimedia Commons); the app fetches+caches the
/// actual bytes lazily the first time a card with a photo is shown.
///
/// Phase 1 note: the 160-word seed ships with has_photo=0 for every word
/// (see NOTES.md) — this class is fully wired up and unit-testable via the
/// injected [HttpGet] function, but has no seed rows to exercise it against
/// yet. That's an explicit, spec-sanctioned scope cut ("it's fine if most
/// of the 150-word seed just has has_photo=0").
library;

import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

typedef HttpGet = Future<http.Response> Function(Uri url);

class ImageCache {
  ImageCache({HttpGet? httpGet}) : _httpGet = httpGet ?? http.get;

  final HttpGet _httpGet;

  Future<String> _cacheDirPath() async {
    final dir = await getApplicationDocumentsDirectory();
    final imgDir = Directory(p.join(dir.path, 'image_cache'));
    if (!await imgDir.exists()) {
      await imgDir.create(recursive: true);
    }
    return imgDir.path;
  }

  String _fileNameFor(String url) {
    final hash = sha1.convert(url.codeUnits).toString();
    final ext = p.extension(Uri.parse(url).path);
    return '$hash${ext.isEmpty ? '.jpg' : ext}';
  }

  /// Returns a local file path for [imageUrl], downloading+caching on first
  /// access. Returns null on network failure (caller should just skip the
  /// image — dual coding is a bonus, not a blocker for offline-first use).
  Future<String?> localPathFor(String imageUrl) async {
    final dirPath = await _cacheDirPath();
    final fileName = _fileNameFor(imageUrl);
    final file = File(p.join(dirPath, fileName));
    if (await file.exists()) return file.path;

    try {
      final resp = await _httpGet(Uri.parse(imageUrl));
      if (resp.statusCode != 200) return null;
      await file.writeAsBytes(resp.bodyBytes, flush: true);
      return file.path;
    } catch (_) {
      return null;
    }
  }
}
