# Continue Vocab — prompt เดียวจบ

เอกสารนี้คือคู่มือสำหรับ **เปิด session ใหม่ (cloud / มือถือ / เครื่องอื่น) แล้วทำงาน
vocab ต่อได้ทันที** โดยไม่ต้องมี data lake 377 MB ในเครื่อง

## พิมแค่บรรทัดนี้บนมือถือ

```
อ่าน https://raw.githubusercontent.com/pimdejvani/Esh_Learner/master/CONTINUE_VOCAB_PROMPT.md แล้วทำ Sol review ต่อ 1 batch
```

ไม่ต้องพิมอย่างอื่น ไม่ต้องพก key ทุกอย่างที่ต้องรู้อยู่ในไฟล์นี้แล้ว
(ถ้า session นั้น clone repo อยู่แล้ว พิมสั้นกว่านี้ได้: `อ่าน CONTINUE_VOCAB_PROMPT.md แล้วทำ Sol review ต่อ 1 batch`)

---

## งานที่ต้องทำ

ทำ **Sol corpus review** ของ RE Vocab ให้จบ

```
manifest:  data/sol_review_manifest.txt   (2,967 คำ, seq 1..2967)
ทำแล้ว:    seq 1..565
เหลือ:     seq 566..2967  =  2,402 คำ
  - seq 566..725   (160 คำ)  priority = failed  ← ทำก่อน มี deterministic error ระบุไว้ในคอลัมน์สุดท้าย
  - seq 726..2967  (2,242 คำ) priority = audit  ← semantic audit
```

`data/sol_review_manifest.txt` เป็น **authority เดียว** ของการแบ่งงาน
ห้ามเลือกช่วงคำจาก DB เองหรือจากไฟล์ draft โดยตรง

## Setup (ทำครั้งเดียวตอนเปิด session)

```bash
git clone https://github.com/pimdejvani/Esh_Learner.git && cd Esh_Learner
gh release download vocab-evidence-v1 --pattern 'vocabulary_evidence.db.gz' --dir data
gunzip -f data/vocabulary_evidence.db.gz
export ESH_SOURCE_DB="$PWD/data/vocabulary_evidence.db"
python tools/export_evidence_db.py --check
python tools/sol_review_progress.py
```

บรรทัดสุดท้ายต้องได้ `errors=0` ก่อนเริ่มงาน ถ้าไม่ได้ให้หยุดและรายงาน

`vocabulary_evidence.db` (44 MB) คือ slice ของ `vocabulary_source.db` (377 MB)
ที่ตัด `source_documents`, `source_translations`, `source_related_candidates` ออก
ตารางที่เหลือให้ผลการ validate **ตรงกับ DB เต็มทุกตัวเลข** สำหรับงาน English
ไม่ต้องพยายามหา DB เต็ม — งาน review ไม่ต้องใช้

## ทำงานทีละ batch

หนึ่ง batch = **15 คำ** ช่วง seq ต่อเนื่องกัน ห้ามทับกับ batch อื่น
เริ่มจาก seq ต่ำสุดที่ยังไม่มี report

### input ที่ต้องอ่านสำหรับแต่ละคำ

1. block ของคำนั้นใน `data/terra_english_drafts/` (ชื่อไฟล์อยู่คอลัมน์ `source_file` ของ manifest)
2. หลักฐานจาก DB — ต้องตรงตัว ห้ามเดา:
   ```sql
   SELECT s.id, s.pos, s.gloss FROM source_senses s
     JOIN words w ON w.id = s.word_id WHERE lower(w.headword) = '<headword>';
   SELECT form_text, pos FROM source_forms  WHERE word_id = <id>;
   SELECT pos, sense_gloss, example_text FROM source_examples WHERE word_id = <id>;
   ```
3. คอลัมน์ `deterministic_errors` ใน manifest (ถ้า priority = failed)

### format ของ draft (six-field, English-only)

```text
@ headword
rank<TAB>sense_id<TAB>pos<TAB>target<TAB>memorable<TAB>English sentence
```

ตัวอย่างจริงจาก `terra_en_012.txt`:

```text
@ else
1	32357	adj	else	1	When everyone else left, Noor stayed to help clean the hall.
2	32357	adj	else	0	Who else knows the answer?
3	32357	adj	else	0	I need something else to wear.
4	32357	adj	else	0	Ask someone else for help.
5	32357	adj	else	0	What else can we do?
```

กฎ:
- 5 บรรทัดต่อคำ `rank` 1..5 ไม่ซ้ำ
- `sense_id` และ `pos` ต้องเป็นค่าจริงจาก `source_senses` และต้องสอดคล้องกัน
- `target` ต้องเป็น headword หรือ form ที่ source รองรับ **และปรากฏตรงตัวในประโยค**
- `memorable` = `1` เฉพาะ rank 1 (ประโยคมีบริบทจำง่าย ไม่ต้องดราม่า)
- rank 2 ต้องเป็น cloze ที่เดาคำได้ชัดเจน
- เลือก sense ที่ learner เจอบ่อยก่อน rare / archaic / technical
- ประโยคทั้ง 5 ห้ามซ้ำกัน ห้ามเป็น placeholder
- **ห้ามมีภาษาไทย** ใน draft — ขั้นแปลเป็นงานแยก

### output ต่อ batch

เขียน 2 ไฟล์ ตั้งชื่อด้วย seq ของ batch (4 หลัก zero-pad):

| ไฟล์ | เนื้อหา |
|---|---|
| `data/sol_review_reports/sol_review_0566_0580.tsv` | **ทุกคำใน batch** หนึ่งบรรทัด: `headword<TAB>pass\|repaired<TAB>เหตุผลสั้น ๆ` เรียงตาม seq |
| `data/sol_review_drafts/sol_repair_0566_0580.txt` | **เฉพาะคำที่ repaired** เขียน block ครบ 5 บรรทัด |

ระวังชื่อไฟล์: report ใช้ `sol_review_` แต่ overlay ใช้ `sol_repair_` — คนละ prefix
ดูตัวอย่างของจริงใน 2 directory นั้นก่อนตั้งชื่อ

- คำที่ `pass` ห้ามเขียนลงไฟล์ `.txt`
- คำที่ต้องแก้ ให้แก้เฉพาะ rank ที่ผิด และ **คัดลอก rank ที่ผ่านมาแบบคำต่อคำ**
  แล้วเขียน block ครบ 5 บรรทัด (overlay ต้องสมบูรณ์ในตัวเอง)
- ถ้าไม่มีคำไหนต้องแก้เลย ให้สร้าง `.txt` เป็นไฟล์ว่าง แต่ `.tsv` ต้องครบทุกคำ
- ชื่อ report ต้องตรง regex `sol_review_(\d{4})_(\d{4})\.tsv` ไม่งั้น validator ปฏิเสธ
  และช่วง seq ในชื่อไฟล์ต้องตรงกับแถวที่อยู่ข้างในเป๊ะ ๆ ตามลำดับ manifest

### ตรวจก่อน commit ทุกครั้ง

```bash
ESH_SOURCE_DB="$PWD/data/vocabulary_evidence.db" python tools/sol_review_progress.py
```

ต้องได้ `errors=0` และเลข `reviewed=` ต้องเพิ่มขึ้นเท่าจำนวนคำที่เพิ่งทำ
ถ้ามี error ให้แก้ก่อน **ห้าม commit ทับ**

แล้ว commit + push:

```bash
git add data/sol_review_reports data/sol_review_drafts
git commit -m "Review vocab seq 566-580"
git push
```

CI (`.github/workflows/vocab-check.yml`) จะ re-verify ให้อีกชั้นบน GitHub

## ห้ามทำ

- ห้ามแก้ `data/terra_english_drafts/` (canonical) — การซ่อมทำผ่าน overlay เท่านั้น
- ห้ามแก้ `data/sol_review_manifest.txt` หรือ `data/terra_missing_manifest.txt`
- ห้ามแก้ DB, ไฟล์แปลไทย, `vocab_app/`, หรือ code/docs
- ห้ามแตะ batch ที่ agent อื่นถืออยู่
- ห้ามคิดค่า sense_id / pos / form ขึ้นมาเอง ถ้า source ไม่มี ให้รายงานว่าคำนั้นบล็อก
- ห้ามเพิ่มคำให้ครบ 3,000 — corpus มี 2,967 คำ ตัวเลขนี้ถูกแล้ว

## ขั้นตอนหลังจาก review จบ (ยังไม่ต้องทำตอนนี้)

1. re-validate corpus ทั้งชุด
2. แปลไทย: Azure Translator เป็นตัวหลัก DeepL ซ่อมเคสที่ fail
   (ต้องมี key — ดู "keys" ด้านล่าง; cache อยู่ที่ `data/translation_cache.db`)
3. audit เคสแปลที่ยังไม่ผ่าน
4. รวมเป็น JSON แล้ว import เข้า SQLite ครั้งเดียว
5. export seed ให้ Flutter

## keys

`.env` ที่ repo root ของเครื่องหลัก (Windows) — **ถูก gitignore ไว้ ไม่มีใน repo และไม่มีใน Drive**

```
API_KEY, DEEPL_AUTH_KEY, AZURE_TRANSLATOR_KEY,
AZURE_TRANSLATOR_REGION, AZURE_TRANSLATOR_ENDPOINT
```

**งาน Sol review ไม่ต้องใช้ key เลย** ไม่ต้องขอ ไม่ต้องอ่าน `.env`
ถ้าจะรันขั้นแปลบน CI ต้องใส่เป็น GitHub Secrets ก่อน (ยังไม่ได้ตั้ง)

## เอกสารอ้างอิงใน repo

| ไฟล์ | เนื้อหา |
|---|---|
| `re vocab.md` | นโยบาย source-first ที่ครอบทุกอย่าง |
| `continue_revocab.md` | สถานะ pipeline + ลำดับขั้นที่ล็อกไว้ |
| `sol_subagent.md` | contract ของ Sol (ฉบับย่อของไฟล์นี้) |
| `terra_english_format.md` | format six-field |
| `SPEC.md` / `ALGORITHM.md` | schema และ algorithm ของแอป |
