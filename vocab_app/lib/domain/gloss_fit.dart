/// Fitting a Thai gloss into a small chip without cutting words in half
/// (user request 2026-07-24: "วางแผนให้ทำการแสดงผลทั้งหมดได้อยู่ หรือหากมี
/// หลายคำแล้วพยายามเลือก 1-หลาย คำที่ไม่เกิน 1-2 บรรทัด").
///
/// Glosses in the seed data are comma-separated senses ("หาได้, ได้มาด้วย
/// ความพยายาม"). A chip that renders the whole string clips it mid-word,
/// which reads like a data bug. The rule instead: show the WHOLE gloss when
/// it fits the space, otherwise drop whole senses from the end until what
/// remains does — never a partial sense.
library;

/// The senses of [gloss] that fit in [maxChars] characters, joined back
/// with ", ".
///
/// Returns the full gloss when it already fits. Otherwise keeps as many
/// leading comma-separated senses as fit; the first sense is always kept
/// even when it alone is longer than [maxChars] (there is nothing shorter
/// to fall back to — the widget's own maxLines/ellipsis handles that rare
/// case).
///
/// [maxChars] defaults to 34 ≈ two lines of Thai at body size in a chip
/// spanning half the phone's width.
String fitGloss(String gloss, {int maxChars = 34}) {
  final text = gloss.trim();
  if (text.length <= maxChars) return text;

  final senses = [
    for (final s in text.split(',')) s.trim(),
  ].where((s) => s.isNotEmpty).toList();
  if (senses.length <= 1) return text;

  final kept = <String>[senses.first];
  var length = senses.first.length;
  for (final sense in senses.skip(1)) {
    final next = length + 2 + sense.length; // ", " + sense
    if (next > maxChars) break;
    kept.add(sense);
    length = next;
  }
  return kept.join(', ');
}
