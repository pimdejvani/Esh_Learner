# After RE Vocab

## สถานะ (2026-08-13)

ทำครบทุกข้อแล้ว รายละเอียดคำศัพท์และวิธีทำอยู่ใน `done_vocab.md`

| ข้อ | งาน | สถานะ |
|---|---|---|
| 2 | โครงสร้าง Sense และ POS ที่สมบูรณ์ | ✅ `senses` ผูก POS + rank + source, 386 sense |
| 3 | ตาราง Word family และ forms | ✅ `word_forms` แยก inflection / derived, 688 แถว |
| 4 | explanation ต่อประโยค | ✅ `example_sentences.explanation_th` 650 ประโยค อ่านเดี่ยวได้ |
| 5 | ข้อมูลอธิบายความสัมพันธ์ | ✅ `related_words` 526 แถว + `relation_groups` 83 กลุ่ม |
| 6 | สร้าง Content Pipeline รุ่นใหม่ | ✅ `tools/select_pilot_100.py` → `build_content_db.py` → `export_app_seed.py` |
| 7 | Validator | ✅ `tools/validate_content_db.py` 17 ด่าน · 0 problems |
| 8 | คำศัพท์ชุดยาก 30 คำ + hook หลาย POS ใน flashcard | ✅ `data/hard_test_30.json` + `lib/domain/test_hooks.dart` — **ต้องลบก่อนทำแอปจริง** |
| 9 | ด้านหลังการ์ด | ✅ `widgets/word_result_card.dart` |
| 10 | Dictionary เต็ม | ✅ `screens/word_detail_page.dart` อ่าน dataset เดียวกับการ์ด |
| 11 | คำอธิบายในเกม | ✅ Cloze / Word Association / Odd One Out ดึงจากตาราง ไม่ generate สด |
| 12 | Motivation และ Progress | ✅ `widgets/progress_mastery_view.dart` |
| 13 | Content-version migration | ✅ `lib/data/content_reseed.dart` + เทสครอบ |

ตรวจแล้ว: `flutter analyze` 0 errors · `flutter test` 127/127 ผ่าน · pipeline ทั้งชุด ~14 วินาที

## ที่ยังเหลือ

- regenerate 241 คำที่ปลดออกจาก legacy batch (`data/regenerate_manifest.json`) ก่อนขยาย corpus
- ขยายจาก 100 คำเป็นชุดเต็ม ตามขั้นใน `action_plan.txt` ระยะที่ 8
- ลบ scaffolding ชุดทดสอบ 30 คำ ก่อน ship (ดู `done_vocab.md` ข้อ 3)
