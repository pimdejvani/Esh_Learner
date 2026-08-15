import 'package:flutter_test/flutter_test.dart';
import 'package:vocab_app/domain/gloss_fit.dart';

void main() {
  group('fitGloss', () {
    test('a short gloss is shown in full', () {
      expect(fitGloss('ใบไม้'), 'ใบไม้');
    });

    test('drops trailing senses that do not fit', () {
      final out = fitGloss('หาได้, ได้มาด้วยความพยายาม, ทำเงิน', maxChars: 20);
      expect(out, 'หาได้');
    });

    test('keeps every sense that still fits', () {
      final out = fitGloss('กิ่งไม้, ท่อนไม้, ติด, แปะ', maxChars: 20);
      expect(out, 'กิ่งไม้, ท่อนไม้');
    });

    test('a single over-long sense is kept rather than cut', () {
      const long = 'ได้มาด้วยความพยายามอย่างมากจนสำเร็จ';
      expect(fitGloss(long, maxChars: 10), long);
    });

    test('trims whitespace around senses', () {
      expect(fitGloss('  ใบไม้ ,  ใบ '), 'ใบไม้ ,  ใบ');
    });
  });
}
