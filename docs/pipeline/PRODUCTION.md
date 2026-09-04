# PRODUCTION.md — สถานะการนำคำเข้า production

อัปเดตล่าสุด: 2026-08-27

เอกสารนี้ตอบ 3 คำถาม: **ตอนนี้อยู่ตรงไหน**, **เหลืออะไร**, และ **ถ้าจะทำต่อต้องรันอะไร แก้ไฟล์ไหน ตั้งค่าอะไร**

---

## 0. ภาพรวม: pipeline จริงคืออะไร

จุดเข้าเดียวคือ `tools/run_production_after_review.py` มันเป็น **autorun** — ตรวจ gate ก่อน ถ้าไม่ผ่านจะพิมพ์ `gate=not_ready action=noop` แล้วออก ถ้าผ่านจะรัน 7 stage ติดกันจนได้ DB จริง

Gate (`tools/run_production_after_review.py:66`):

```python
return reviewed == total and errors == 0 and result.returncode == 0, output
```

โดย `reviewed/total/errors` มาจาก `tools/sol_review_progress.py` และ gate จะถูกตรวจ **ซ้ำอีกรอบ** ใต้ lock แบบ `O_EXCL` ที่ `staging/production_pipeline/production.lock` (`:123-125`) กัน run ซ้อน

7 stage ตามลำดับ (`:148-159`):

| # | Stage | ทำอะไร |
|---|-------|--------|
| 1 | `build_vocab_library.py validate` | ตรวจ library ต้นทาง |
| 2 | `build_reviewed_english_drafts.py --output-dir` | รวม canonical + overlay → ประโยคอังกฤษชุดสุดท้าย |
| 3 | `translate_vocab_content.py --dry-run` | ซ้อมแปล ไม่ยิง API |
| 4 | `translate_vocab_content.py --providers azure,deepl` | **ยิง API จริง เสียเงินจริง** |
| 5 | `build_content_db.py --draft-dir --out` | สร้าง content DB |
| 6 | `validate_content_db.py --db` | ตรวจ DB |
| 7 | `export_app_seed.py --content-db --out` | export seed ให้แอป |

จบแล้วเขียน `manifest.json` (มี sha256) และ promote แบบ atomic ไปที่ `data/content_v2.db` + `vocab_app/assets/seed/vocab.db`

### ⚠️ คำเตือนสำคัญ

**ห้ามรัน `tools/run_production_after_review.py` เล่นๆ ตอนนี้** — ด่าน 1 ปิดแล้ว gate เป็น `errors=0` แปลว่าถ้ารัน มันจะวิ่งทะลุไป stage 4 และ **แปลจริง 14,835 ประโยค** ผ่าน Azure/DeepL ทันที เสีย quota จริง ให้รันเฉพาะตอนที่ตั้งใจจะ ship เท่านั้น

ถ้าจะทดสอบ ให้รันทีละ stage เองด้วยมือ หรือหยุดที่ stage 3 (`--dry-run`)

---

## 1. ด่าน 1 — Sol semantic review ✅ ปิดแล้ว

สถานะปัจจุบัน (รัน `python tools/sol_review_progress.py`):

```
reviewed=2967/2967 repaired=2606 failed_priority_reviewed=725/725 errors=0
```

ครบทั้ง 2,967 คำ ไม่มี error เหลือ

### กติกาที่ใช้ (ถ้าต้อง review เพิ่มในอนาคต)

- **รูปแบบ overlay** `data/sol_review_drafts/sol_repair_XXXX_YYYY.txt`

  ```
  @ headword
  rank<TAB>sense_id<TAB>pos<TAB>target<TAB>memorable<TAB>sentence
  ```

  5 แถวต่อคำ, มีแต่ rank 1 ที่ `memorable=1`
- **รูปแบบ report** `data/sol_review_reports/sol_review_XXXX_YYYY.tsv` — 3 ฟิลด์ TAB, status เป็น `pass` หรือ `repaired`, ลำดับต้องตรงกับ manifest
- **bijection**: เซ็ตของ headword ที่มี overlay ต้องเท่ากับเซ็ตของแถวที่ report ว่า `repaired` เป๊ะๆ ไม่งั้น gate ขึ้น `overlay not reported repaired`
- **LENIENT CALIBRATION**: ซ่อมเฉพาะ hard defect เท่านั้น — POS ผิดในบริบท, subject–verb ไม่ตรง, target ไม่ปรากฏ, ซ้ำ, collocation ผิดธรรมชาติชัดเจน, มีภาษาอื่นปน, หรือ sense ที่คำนั้นไม่มีจริง
- **seq ≠ word_id** — manifest seq คือลำดับ review (seq 1 = `enjoy`) ต้องหา `word_id` ผ่าน `source_senses.word_id` จาก `sense_id` ของแถวเสมอ

### ข้อห้ามถาวร

> ห้ามแก้ canonical, manifest, evidence DB, staging SQLite และห้าม start Qwen

การ remap sense ของคำ (เช่นที่ทำกับ `found` / `gang` / `elect`) ทำได้โดย **แก้ `sense_id`/`pos`/ประโยคใน overlay อย่างเดียว** ไม่ต้องแตะ evidence DB เพราะ `build_content_db.py` แค่ตรวจว่า sense มีอยู่จริงใน `source_senses` และมี `meaning_th` ตรงกันใน `data/content_th/senses_th.txt`

---

## 2. ด่าน 2 — Blocker ในโค้ด ❌ ยังไม่แก้

มี blocker ที่ทำให้ build ทั้ง 2,967 คำไม่ได้ ยืนยันจากการอ่านโค้ดตรงๆ

### Blocker A — `build_content_db.py` hard-code ชุดคำไว้แค่ pilot

`tools/build_content_db.py:188-194`

```python
def content_words() -> list[dict]:
    """The pilot subset, plus the hard test set flagged as test-only."""
    words = [dict(word, is_test_only=0) for word in json.loads(PILOT_JSON.read_text(...))["words"]]
    if HARD_TEST_JSON.exists():
        words += [dict(word, is_test_only=1) for word in json.loads(HARD_TEST_JSON.read_text(...))["words"]]
    return words
```

อ่านจาก `data/pilot_100.json` + `data/hard_test_30.json` เท่านั้น และ CLI มีแค่ `--out` กับ `--draft-dir` (`:480-481`) — **ไม่มี flag ให้ขยายชุดคำ**

**สิ่งที่ต้องทำ**: เพิ่ม CLI flag (เช่น `--word-set <json>` หรือ `--all`) ให้ `content_words()` รับชุดคำที่กำหนดได้ โดยยังคงพฤติกรรม `is_test_only` ไว้เหมือนเดิม

### Blocker B — คำอธิบายภาษาไทยไม่มีใครเขียนใส่

- `tools/translate_vocab_content.py:383` เขียน `thai_explanation = ""` โดยตั้งใจ (ตัวแปลส่งแค่ `row.en_text` ให้ Azure/DeepL — API แปลประโยค ไม่ได้เขียนคำอธิบายไวยากรณ์)
- `tools/validate_content_db.py:26,92-96` — `EXPLANATION_MIN_CHARS = 12` และ check `explanation-too-thin` จะ fail ทุกแถวที่ `length(explanation_th) < 12`

แปลว่า stage 6 จะพังทันทีถ้า explanation ว่าง → **explanation ต้องเขียนโดย LLM ไม่ใช่ API แปล** (นี่คือด่าน 3)

### Blocker B2 — ช่องว่างในการต่อสาย (wiring gap)

`build_content_db.py:311` อ่านคำอธิบายจาก **field 8 ของ draft** (`sentence["explanation_th"]`) แต่ไฟล์ที่เราเขียนอยู่ที่ `data/sol_review_explanations/*.tsv`

**ยังไม่มีเครื่องมือ merge ระหว่างสองที่นี้** มีแค่สคริปต์ครั้งเดียว `tools/_gen_2076_2100.py` ที่อ้างถึง directory นั้น

**สิ่งที่ต้องทำ**: เขียน tool ใหม่ (เช่น `tools/merge_explanations.py`) ที่อ่าน `data/sol_review_explanations/*.tsv` แล้วเติมลง field 8 ของ compact-format-v2 draft ก่อนเข้า stage 5

### Blocker C — Thai gloss ยังเป็นสเกล pilot

`data/content_th/` ตอนนี้มีแค่:

| ไฟล์ | บรรทัด (ไม่นับ comment) |
|------|------|
| `senses_th.txt` | 387 |
| `words_th.txt` | 131 |
| `forms_th.txt` | 142 |
| `groups_th.txt` | 84 |
| `relations_th.txt` | 70 |

รูปแบบ: `source_sense_id|headword|pos|meaning_th|meaning_source`

นี่พอสำหรับ 100–130 คำเท่านั้น **การ build ครบ 2,967 คำต้องใช้ Thai gloss อีกหลายพันบรรทัดที่ยังไม่มี** — เป็นงานก้อนใหญ่ที่ยังไม่ได้เริ่ม (`data/content_th/_senses_todo.tsv` มี 258 บรรทัดค้างอยู่)

### ข้อยืนยัน: production ไม่เอากลุ่มคำ test

`tools/run_production_after_review.py` เรียก `export_app_seed.py` **โดยไม่ส่ง `--include-test-words`** และ `tools/export_app_seed.py:40-49` จะ

```python
if not include_test_words:
    db.execute("DELETE FROM words WHERE is_test_only=1")
```

พร้อมทิ้ง relation group ที่เหลือสมาชิกไม่พอ และ stamp `content_meta.includes_test_words = 0` → **ยืนยันว่า seed ที่ส่งเข้าแอปไม่มีคำกลุ่ม test**

---

## 3. ด่าน 3 — เขียนคำอธิบายไทยรายประโยค 🔄 กำลังทำ

### ความคืบหน้าปัจจุบัน

ผล audit ล่าสุด 2026-08-28: 63 ไฟล์ / 7,060 แถวที่มี rank 1–5 ครอบคลุม
1,412 คำ (มี `rank=0 placeholder` อีก 2 แถวซึ่งไม่นับ) รายละเอียดการสร้างต่อ,
A/B Qwen–Glimmer และ quality gate อยู่ใน `GRAMMAR_EXPLANATION_LLM_SPEC.md`.

coverage เดิมที่เอกสารเคยบันทึกไว้:

```
566-1325, 1351-1600, 1626-1750, 1776-1850, 1876-1950, 2001-2050, 2076-2100, 2126-2150
```

ปัจจุบันยังขาด 1,555 คำ = 7,775 คำอธิบาย; รายการช่วงที่ขาดให้สร้างใหม่จาก
manifest ด้วย `tools/grammar_explanation_pipeline.py prepare --only-missing`
แทนการคัดลอกช่วงเก่าด้วยมือ.

ช่วงที่เอกสารเดิมเคยบันทึกว่าขาด:

```
1-565, 1326-1350, 1601-1625, 1751-1775, 1851-1875, 1951-2000, 2051-2075, 2101-2125, 2151-2967
```

**เป้าหมายปัจจุบัน:** เติมทุกคำที่ยังขาด 1,555 คำ = 7,775 คำอธิบายภายใน
10 ชั่วโมง โดยเลือก Qwen หรือ Glimmer จาก A/B gate ใน
`GRAMMAR_EXPLANATION_LLM_SPEC.md` ก่อนเริ่ม full run.

### วิธีทำงาน

1. สร้าง snapshot ประโยคอังกฤษก่อน (ทำครั้งเดียว ใช้ซ้ำได้):

   ```
   python tools/build_reviewed_english_drafts.py --output-dir <scratchpad>/english_reviewed
   ```

   ผลที่ควรได้: `overlays=2606 canonical_unchanged=true`, 53 ไฟล์

2. สร้าง worksheet ต่อ batch ด้วย `<scratchpad>/expl_sheet.py`:

   ```
   python expl_sheet.py START END <snapshot_dir>
   ```

   มันพิมพ์ headword, รูปผันที่ attested, sense id + gloss, และ 5 ประโยคพร้อม target

   > bug ที่เคยเจอ: ต้อง resolve `word_id` จาก `source_senses` ด้วย `sense_id` ของแถว **ห้ามใช้ manifest seq เป็น word_id** (seq 1 คือ `enjoy` แต่ word_id 1 คือ `about`)

3. ปล่อย subagent **opus** batch ละ 25 คำ (= 125 คำอธิบาย) ขนานกันรอบละ ~5 agent
   งานนี้ต้อง reasoning จริง (วิเคราะห์หน้าที่ของคำในแต่ละประโยค) จึงใช้ opus ไม่ใช่ haiku
   ส่วนงานที่เป็นคำสั่งซ้ำๆ เชิงกล (เช่น รัน driver เขียน overlay) ใช้ haiku

4. แต่ละ agent เขียน `data/sol_review_explanations/expl_XXXX_YYYY.tsv`
   UTF-8, LF, 3 ฟิลด์ TAB: `headword<TAB>rank<TAB>explanation_th`

### กติกาของคำอธิบาย

- อธิบาย **ประโยคนั้น** ไม่ใช่อธิบายคำลอยๆ — 5 คำอธิบายของคำเดียวกันต้องต่างกันจริง
- บอกว่าทำไมใช้ **รูปนั้น** (ทำไม `enjoys` ไม่ใช่ `enjoy`) ผูกกับประธาน/tense/พจน์ในประโยคนั้น
- ระบุหน้าที่ทางไวยากรณ์ และบอกว่าขยายหรือกำกับอะไร
- **ต้องอ่านเดี่ยวๆ รู้เรื่อง** ห้ามอ้างประโยคอื่น (regex ปฏิเสธ `ประโยคก่อนหน้า|ตัวอย่างที่\s*\d|ประโยคที่\s*\d|ข้อที่\s*\d|ข้างต้น`)
- อย่างน้อย 12 ตัวอักษร เล็งไว้ ~60–150 ตัวอักษรไทย ให้พอดีการ์ด
- ห้ามแต่งข้อมูลภาษาศาสตร์ขึ้นเอง ใช้เฉพาะ gloss/forms ที่ worksheet ให้มา

ตัวอย่างสไตล์ที่ยอมรับแล้ว:

```
worse r1: worse เป็นคำคุณศัพท์ขั้นกว่าของ bad แปลว่า แย่กว่า ในประโยคนี้ใช้บรรยายผลสแกนว่าแย่กว่าที่คาดไว้
worse r2: worse ในที่นี้เป็นกริยาวิเศษณ์ขยาย plays แปลว่า เล่นได้แย่ลง (ไม่เก่งเท่าเดิม) ไม่ใช่คำคุณศัพท์เพราะขยายคำกริยา
worse r4: worse ในสำนวน for better or worse ทำหน้าที่เป็นคำนาม หมายถึงสิ่งที่แย่กว่า/สถานการณ์เลวร้าย ไม่ได้ขยายคำนามใด
```

### self-check ที่ทุก batch ต้องผ่าน

125 แถว, ทุกแถว ≥12 ตัวอักษร, ไม่มี cross-reference, มีอักษรไทย, 5 แถวต่อคำ, ไม่มีคำอธิบายซ้ำภายในคำเดียวกัน

---

## 4. ของที่มีอยู่แล้ว (อย่าสร้างซ้ำ)

| ไฟล์ | เนื้อหา |
|------|---------|
| `data/content_v2.db` | 130 คำ / 650 ตัวอย่าง — explanation ครบทั้ง 650 |
| `data/content_final_v2.db` | 100 คำ / 500 ตัวอย่าง |
| `data/sol_review_explanations/` | 63 ไฟล์ / 7,060 valid explanations + 2 invalid placeholders |
| `data/sol_review_drafts/` | overlay 2,606 คำ |
| `data/sol_review_reports/` | report ครบ 2,967 คำ |

---

## 5. การตั้งค่า / env ที่ต้องมี

ไฟล์ `.env` ที่ root ต้องมี key เหล่านี้ (ค่าอยู่ในไฟล์แล้ว — **ห้าม echo ค่าออกมาหรือส่งไปที่ไหน**):

```
API_KEY
DEEPL_AUTH_KEY
AZURE_TRANSLATOR_KEY
AZURE_TRANSLATOR_REGION
AZURE_TRANSLATOR_ENDPOINT
```

จำเป็นเฉพาะ stage 3–4 (`translate_vocab_content.py`) เท่านั้น ด่าน 1 และ 3 ไม่ต้องใช้ API เลย

หมายเหตุ shell: บน Windows ให้ `export LC_ALL=C.UTF-8` ก่อนใช้ `grep -P` กับไฟล์ไทย ไม่งั้นได้ error `grep: -P supports only unibyte and UTF-8 locales`

---

## 6. ทำต่อจากตรงนี้ยังไง — checklist

### ถ้าจะทำด่าน 3 ต่อ (งานที่ค้างอยู่ตอนนี้)

```bash
ls data/sol_review_explanations/*.tsv | sed 's/.*expl_//;s/\.tsv//' | sort
```

```bash
python tools/build_reviewed_english_drafts.py --output-dir <scratchpad>/english_reviewed
```

จากนั้นปล่อย opus subagent batch ละ 25 seq ตามช่องที่ขาด

### ถ้าจะแก้ด่าน 2

1. `tools/build_content_db.py` — เพิ่ม CLI flag เลือกชุดคำ แทน hard-code pilot+hard_test ที่ `:188-194`
2. เขียน `tools/merge_explanations.py` — merge `data/sol_review_explanations/*.tsv` เข้า field 8 ของ draft
3. เติม `data/content_th/*` ให้ครบสเกล 2,967 คำ (งานใหญ่ ยังไม่เริ่ม)
4. เสียบ merge step เข้า `run_production_after_review.py` ระหว่าง stage 4 กับ 5

### ถ้าจะ ship จริง

1. ยืนยันว่า `python tools/sol_review_progress.py` ให้ `errors=0`
2. ยืนยันว่า blocker A/B/B2/C แก้ครบแล้ว
3. รัน dry-run ก่อนเสมอ: `python tools/translate_vocab_content.py --dry-run`
4. ค่อยรัน `python tools/run_production_after_review.py` — **ขั้นนี้เสียเงินจริง**
5. ตรวจ `manifest.json` sha256 และเช็คว่า `content_meta.includes_test_words = 0`

---

## 7. สรุปสถานะ

| ด่าน | สถานะ | เหลืออะไร |
|------|-------|-----------|
| 1 — semantic review | ✅ ปิด | ไม่มี (`errors=0`) |
| 2 — blocker ในโค้ด | ❌ ยังไม่เริ่ม | word-set flag, merge tool, Thai gloss สเกลเต็ม |
| 3 — คำอธิบายไทย | 🔄 A/B ก่อน full run | ขาด 1,555 คำ / 7,775 คำอธิบาย |
| 4 — build/ship | ⛔ ล็อกอยู่ | รอด่าน 2 |
