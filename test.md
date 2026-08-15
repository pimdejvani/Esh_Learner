# RE Vocab — Test Data Handoff

อัปเดตล่าสุด: 2026-08-13

## เป้าหมายของ test data

ใช้ฐานข้อมูลทดสอบเพื่อตรวจ schema, การแปลไทย, validator และพฤติกรรมเกมก่อนนำ
เฉพาะข้อมูลที่ผ่านไปสร้างฐานข้อมูล production ห้ามใช้ test DB เป็น final DB โดยตรง
และห้ามนำ fixture หลาย POS จำนวน 30 คำติดไปกับแอปจริง

## ฐานข้อมูลที่ใช้อยู่

| ไฟล์ | หน้าที่ | จำนวนคำ | test-only |
|---|---|---:|---:|
| `data/vocabulary_source.db` | หลักฐานคำศัพท์ต้นทาง 2,967 คำ: senses, POS, forms, IPA, source examples | 2,967 | ไม่มี |
| `data/content_test_v2.db` | ฐานข้อมูลสำหรับทดสอบ UI/เกม/validator | 130 | 30 |
| `data/content_final_v2.db` | production candidate ที่ export จาก test DB แล้วตัด fixture ออก | 100 | 0 |

`data/content_v2.db` เป็นฐาน content เดิมที่ใช้สร้าง test DB รอบนี้ อย่าเขียนผลการทดลอง
ใหม่ลงไฟล์นี้โดยตรง

## โครงสร้าง test corpus

- 100 คำ pilot จริงจาก `data/pilot_100.json`
- 30 คำยาก/หลาย POS จาก `data/hard_test_30.json`
- คำ 30 คำมี `words.is_test_only=1`
- fixture ใช้บังคับให้เกมและ Flashcard เจอกรณีหลาย POS ระหว่างพัฒนาเท่านั้น
- เมื่อ export production ต้องลบคำ `is_test_only=1` และ relation group ที่เหลือสมาชิกต่ำกว่า 3

## ผลทดสอบ translation ล่าสุด

ทดสอบคำ `clear` และ `cloud` รวม 10 ประโยค / 20 ข้อความ
(ประโยคไทย 10 + explanation ไทย 10)

- Azure Translator F0: เรียกสำเร็จครบ 20/20 แต่พบการตกคำและ explanation แข็งในบางบรรทัด
- DeepL API: เรียกสำเร็จครบ 20/20 และผลของชุดนี้รักษาบริบทได้ดีกว่า
- ผลที่บันทึกใน `content_test_v2.db` จึงใช้ DeepL สำหรับ 10 ประโยคนี้
- `content_final_v2.db` รับเฉพาะสองคำ production นี้ต่อไป โดยไม่มี fixture 30 คำ
- ทั้ง test DB และ final DB ผ่าน `tools/validate_content_db.py` ด้วย 0 problems

ไฟล์ผลทดลอง:

- Azure: `data/terra_test_translated/terra_en_002.txt`
- DeepL: `data/terra_test_translated_deepl/terra_en_002.txt`
- cache: `data/translation_cache.db` (ไม่ควร commit และไม่ต้องแปลข้อความเดิมซ้ำ)

ข้อสรุปปัจจุบัน: ใช้ Azure เป็นตัวหลักเพื่อรองรับ corpus ใหญ่ และใช้ DeepL กับรายการ
ที่ถูก audit/flag ว่าคุณภาพไม่ดี ห้ามถือว่า API ตอบเป็นภาษาไทยแล้วแปลว่าคุณภาพผ่าน

## Credentials

`.env` มีค่าที่จำเป็นแล้ว แต่ห้ามพิมพ์หรือคัดลอก secret ลงเอกสาร/แชท/log:

```text
AZURE_TRANSLATOR_KEY
AZURE_TRANSLATOR_REGION
AZURE_TRANSLATOR_ENDPOINT
DEEPL_AUTH_KEY
```

โค้ดโหลดค่าเหล่านี้จาก `.env` และ cache ผลใน SQLite

## Pipeline สำหรับทดสอบการแปล

1. ตรวจ English drafts โดยไม่เรียก API:

```powershell
python tools/translate_vocab_content.py --input-dir data/terra_english_drafts --dry-run
```

2. ทดลองเฉพาะคำที่ระบุ:

```powershell
python tools/translate_vocab_content.py `
  --input-dir data/terra_english_drafts `
  --output-dir data/terra_test_translated `
  --headwords clear,cloud `
  --providers azure
```

เปลี่ยน `--providers deepl` และ output directory เมื่อต้องการเทียบ DeepL

3. นำผลที่เลือกลง test DB เท่านั้น:

```powershell
python tools/apply_translated_drafts.py `
  --db data/content_test_v2.db `
  --draft-dir data/terra_test_translated_deepl `
  --headwords clear,cloud `
  --source-label deepl-test `
  --dry-run

python tools/apply_translated_drafts.py `
  --db data/content_test_v2.db `
  --draft-dir data/terra_test_translated_deepl `
  --headwords clear,cloud `
  --source-label deepl-test
```

4. ตรวจ test DB:

```powershell
python tools/validate_content_db.py --db data/content_test_v2.db
```

5. เมื่อผ่านแล้วจึง export production candidate โดยไม่ใส่ `--include-test-words`:

```powershell
python tools/export_app_seed.py `
  --content-db data/content_test_v2.db `
  --out data/content_final_v2.db

python tools/validate_content_db.py --db data/content_final_v2.db
```

## กฎสำหรับแชทที่รับช่วงต่อ

1. อ่าน `re vocab.md`, `continue_revocab.md`, `terra_english_format.md` และไฟล์นี้ก่อนแก้ pipeline
2. Terra สร้างเฉพาะ English-only drafts หกฟิลด์ ห้าม generate Thai
3. ใช้ source sense ID/POS/forms จาก `vocabulary_source.db` เท่านั้น
4. อย่านำ draft เข้า DB ระหว่าง first-pass generation ของทั้ง corpus
5. การทดลอง translation ต้องเริ่มจากคำจำนวนน้อยและลง `content_test_v2.db` ก่อน
6. ต้องตรวจความหมายในบริบท ไม่ใช่ตรวจแค่ว่ามีอักษรไทย
7. สิ่งที่ผ่านจึง export ไป `content_final_v2.db`; ห้าม copy test DB เป็น final ตรง ๆ
8. final DB ต้องมี `is_test_only=0` ทุกคำ และ validator ต้องรายงาน 0 problems
9. ห้ามแก้/เปิดเผย `.env`, API key หรือข้อมูลบัญชี
10. อย่าแก้ Flutter app ระหว่างงาน generate corpus รอบนี้

## งานที่กำลังทำต่อ

- canonical draft มีเฉพาะ `data/terra_english_drafts/*.txt`: 2,967 คำ ไม่ซ้ำกัน
- JSON/compact/retired legacy ถูก consolidate แล้วลบออก
- Terra เติมคำที่เคยขาดครบ 969/969 แล้ว
- Terra Medium รับครั้งละไม่เกิน 25 คำตาม `seq` ที่ระบุ ห้ามเลือก source rank เอง
- ตรวจแต่ละไฟล์ด้วย `tools/validate_english_draft_batch.py`
- Sol Medium review/repair ตาม `data/sol_review_manifest.txt`; ยังห้ามแปลหรือนำเข้า DB จน review ครบ
