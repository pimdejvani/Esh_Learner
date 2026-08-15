# Done Vocab — คำศัพท์ที่อยู่ในระบบ และวิธีที่สร้างมา

สถานะ ณ 2026-08-13 · content_version = 2 · ฐานข้อมูล `data/content_v2.db` → seed ของแอป `vocab_app/assets/seed/vocab.db`

## 1. ตัวเลขรวม

| ตาราง | จำนวน |
|---|---|
| words | 130 (ใช้จริง 100 + ชุดทดสอบ 30) |
| senses | 386 |
| word_forms | 649 (inflection 508 + derived 141) |
| example_sentences | 650 (5 ประโยคต่อคำ) |
| related_words | 526 |
| relation_groups | 83 |
| คำที่มีตั้งแต่ 2 POS ขึ้นไป | 72 |

ทุกแถวผ่าน `tools/validate_content_db.py` แล้ว: `checks failed: 0  problems: 0`

## 2. วิธีที่ทำ (pipeline ตามลำดับจริง)

### 2.1 เลือกคำ — `tools/select_pilot_100.py` → `data/pilot_100.json`

- ดึงคำจาก `data/vocabulary_source.db` (Oxford list 2,967 คำ harvest จาก kaikki/Wiktextract)
- เรียงตาม **SWOW-EN18 response frequency** = คำที่คนนึกถึงบ่อยที่สุดก่อน
- โควตา band **40 A1 / 35 A2 / 15 B1 / 10 B2**
- **เงื่อนไขสำคัญ**: เลือกแบบ greedy โดยให้คำที่เชื่อมกับคำที่เลือกไปแล้ว (SWOW closeness ≥ 0.036 ซึ่งเป็นเกณฑ์ Odd One Out ใน SPEC) ได้ก่อน → คำจึงเกาะกันเป็นกลุ่มความหมายจริง ไม่กระจัดกระจาย ทำให้เกม Matching / Odd One Out / Word Association เล่นได้
- สคริปต์จะ exit 1 ถ้าโควตาไม่ครบ, กลุ่มความหมายน้อยกว่า 3 กลุ่ม, หรือคำหลาย POS น้อยกว่า 10 คำ

กลุ่มความหมายที่ได้: งาน/เงิน · น้ำ/ทะเล · อาหาร/การกิน · เครื่องดื่ม · แสง-เงา/เวลา

### 2.2 สร้างประโยค — compact draft format v2

- รูปแบบล็อกไว้ใน `terra_compact_format.md`: `@ headword` แล้วตามด้วย 5 บรรทัด tab-separated
- แต่ละบรรทัดอ้าง `source_senses.id` จริง จึงตรวจย้อนได้ว่า POS/ความหมายมาจาก source ไม่ได้แต่งขึ้น
- rank 1 เป็นประโยคที่มีอารมณ์ (emotional) เสมอ
- เขียน draft เป็นไฟล์ pipe-separated ก่อน แล้วแปลงด้วย `tools/pipe_to_compact.py` — ทำแบบนี้เพราะ tab ในไฟล์ที่แก้ด้วยมือพังง่ายและพังแบบเงียบ ๆ
- ไฟล์ที่เกี่ยวข้อง: `batch_pilot_100.txt` (B1/B2 ที่ยังไม่มี), `batch_pilot_100_repair.txt`, `batch_pilot_100_relegacy.txt`, `batch_hard30_test.txt`

### 2.3 ทิ้งของเก่าแล้วเขียนใหม่

`batch_000_legacy_001_255.txt` (255 คำแรก) ถูกปลดออกจาก active pipeline แล้ว
ต่อมารวม headword ที่ยังไม่ซ้ำเข้า canonical English TXT และลบ legacy directory
ถาวรเมื่อ 2026-08-13

เหตุผล: มี `sense_id=0` และประโยคที่ผ่าน validator เดิมได้แต่ใช้สอนไม่ได้ เช่น
- "We stayed inside during the heavy drink of rain."
- "They were coffeeing after lunch."
- "We are dinnering with our neighbours tonight."
- "We met by the river afternoon."

12 คำใน pilot ที่พึ่งไฟล์นี้ถูกเขียนใหม่ทั้งหมด · อีก 241 คำขึ้นบัญชีรอ regenerate ใน `data/regenerate_manifest.json`

### 2.4 เขียนเนื้อหาไทย — `data/content_th/*.txt` (คั่นด้วย `|`)

| ไฟล์ | เนื้อหา |
|---|---|
| `words_th.txt` | คำอ่านไทย + ตำแหน่งพยางค์ที่เน้น (29 คำยกมาจาก seed เดิม, ที่เหลือเขียนใหม่) |
| `senses_th.txt` | ความหมายไทยต่อ sense (386 แถว) สั้นพอสำหรับหนึ่งบรรทัดบนการ์ด |
| `relations_th.txt` | ความสัมพันธ์แบบมีชนิดจริง 68 คู่ (opposite / used_for / part_of / produces / causes / kind_of / pays) |
| `groups_th.txt` | หมวดและเหตุผลของแต่ละกลุ่ม สำหรับ Odd One Out (83 กลุ่ม) |
| `forms_th.txt` | ความหมายไทย + POS จริง ของคำในตระกูลเดียวกัน 141 คำ |

`forms_th.txt` ทำหน้าที่เป็น **whitelist** ด้วย: derived candidate ที่ไม่อยู่ในไฟล์นี้จะไม่ถูกสร้างเข้า DB
เพราะรายการ derived ของ kaikki กว้างเกินไปและมีคำที่แค่ *ดูเหมือน* ญาติ เช่น `aft` ใต้ afternoon,
`window` ใต้ wind (มาจาก "wind eye" ซึ่งไม่ช่วยผู้เรียนเลย), `barrister` ใต้ bar, `watergate` ใต้ water
· POS ก็เขียนเองเพราะ POS ที่ source ให้มาเป็นของ *หัวข้อ* ที่คำนั้นถูกลิสต์ไว้ ไม่ใช่ของคำนั้นจริง

คู่ที่ไม่ได้เขียนเอง จะได้คำอธิบายตอน build จากหมวดของกลุ่มที่คู่นั้นอยู่ — **ไม่มีการ generate ตอนเล่น**

### 2.5 ประกอบเป็นฐานข้อมูล — `tools/build_content_db.py`

- senses = เฉพาะ sense ที่ประโยคจริงใช้ → ทุกความหมายที่แสดง มีตัวอย่างรองรับเสมอ
- forms แยกเป็น `inflection` (drank · past) กับ `derived` (worker, workplace)
  - inflection: กรอง tag `alternative/obsolete/archaic/misspelling/...` ออก และเลือกรูปที่คนใช้จริงด้วยความถี่ SWOW (จึงได้ `drank` ไม่ใช่ `dranken`) รูปที่ตัวอย่างสอนจะได้ที่ของตัวเองเสมอ (`sprang` และ `sprung` อยู่ด้วยกันได้)
  - derived: ต้องร่วมรากคำ และต้องอยู่ใน Oxford list หรือมีความถี่ SWOW ≥ 20 (ตัด `Waterloo`, `work-brittle`, `pay-per-click` ทิ้ง — จาก 3,751 เหลือ 119)
- related_words ผูกกับ **sense** ไม่ใช่คำ, มี relation_type / closeness / confidence / คำอธิบาย ครบทุกแถว
- relation_groups เก็บ hub + หมวด + เหตุผล ไว้ให้ Odd One Out อธิบายตัวเองได้จากข้อมูลที่ใช้สร้างรอบนั้นจริง

### 2.6 ตรวจ — `tools/validate_content_db.py` (17 ด่าน)

ตกทันทีเมื่อเจอ: family ที่ไม่มีใน source · รูปผันที่ไม่ตรง POS ของ sense · ความหมายไทยยาวเกินการ์ด · ความหมายซ้ำ · derived ที่ไม่ร่วมราก · explanation ที่อ้างประโยคอื่น ("ประโยคที่ 1", "ข้างต้น") · explanation ที่ไม่ได้พูดถึงคู่คำจริง · cloze span ไม่ตรง target · ไม่มี provenance · คำที่ไม่มีคำอ่านไทย ฯลฯ

ตัวอย่างที่มันจับได้จริง: `sail → wind` คำอธิบายไม่ได้พูดถึง sail เลย · `spring rank 2` ใช้ `sprang` ที่ตอนนั้นยังไม่มีในตาราง forms

### 2.7 ส่งเข้าแอป — `tools/export_app_seed.py`

- ตรวจว่าไม่มีตารางของผู้เล่นหลุดเข้าไปใน seed
- ค่าเริ่มต้น **ตัดคำชุดทดสอบ 30 คำออก** ต้องใส่ `--include-test-words` เองถ้าจะเอาไปใช้ตอนพัฒนา

คำสั่งครบชุด:

```bash
python tools/select_pilot_100.py && python tools/build_content_db.py && python tools/validate_content_db.py && python tools/export_app_seed.py
```

ทั้งชุดใช้เวลา **~14 วินาที** (เดิม ~90 วินาที) หลังจากย้าย SWOW ไปใช้ cache กลาง
`tools/swow_cache.py` → `data/swow_cache.json` ซึ่งทั้ง selector และ builder ใช้ร่วมกัน
(เดิมโค้ด parse ไฟล์ 53 MB ซ้ำอยู่สองที่)

## 3. ⚠️ ชุดทดสอบ 30 คำ — ต้องตัดออกก่อนปล่อยแอปจริง

บันทึกตามที่สั่งไว้ (after_revocab ข้อ 7):

- คำ 30 คำในหมวด "ชุดทดสอบยาก" ข้างล่างมี `is_test_only = 1` ในฐานข้อมูล
- กฎ "ทุกการเล่นต้องมีคำหลาย POS โผล่ใน flashcard อย่างน้อย 1 คำ" อยู่ที่ `vocab_app/lib/domain/test_hooks.dart` ตัวแปรเดียวคือ `kForceMultiPosFlashcard` (debug build เท่านั้น)
- **ก่อนทำเป็นแอปจริงต้องลบ**: ไฟล์ `test_hooks.dart` + จุดที่เรียกใช้ใน `play_screen.dart` + `data/hard_test_30.json` + `batch_hard30_test.txt` และ export seed โดยไม่ใส่ `--include-test-words`
- เหตุผลที่ต้องลบ: การยัดคำเข้าคิวทำให้ลำดับ FSRS และ new-card governor เพี้ยน ถ้าปล่อยไว้ผู้เรียนจะได้ลำดับคำที่ไม่ตรงกับที่ระบบคำนวณ

## 4. รายการคำศัพท์ทั้งหมด

(ตัวเลขในวงเล็บ = จำนวน part of speech ที่มีในระบบ)

### A1 — 40 คำ

money (2 POS) · water · time · music (2 POS) · food · work · fish (2 POS) · job (2 POS) · career (3 POS) · pay (2 POS) · business (2 POS) · day · week · month · year · night (2 POS) · age (2 POS) · morning · sun (3 POS) · afternoon · lunch (2 POS) · breakfast (2 POS) · dinner · meal · eat (2 POS) · evening · light (2 POS) · dark (2 POS) · black (3 POS) · tonight · midnight (2 POS) · sleep (2 POS) · white · drink (2 POS) · coffee (2 POS) · tea (2 POS) · hot (2 POS) · cup (2 POS) · glass (2 POS) · wine

### A2 — 35 คำ

salary · earn · employ · boss · employee · employer · moon (3 POS) · bright · sky · clear · oil · heat · boil · bar (2 POS) · wet · gas · deep · ocean · ship · sail · sailing · wind · hole · ground · wave · storm · cloud · lake · spoon · fork · plate · bowl · knife · task (2 POS) · fishing (2 POS)

### B1 — 15 คำ

employment · profession · hire (2 POS) · unemployment · contrast (2 POS) · consume · alcohol · shine (2 POS) · drunk (3 POS) · fry (2 POS) · liquid (2 POS) · pour (2 POS) · assignment · spicy · net (4 POS)

### B2 — 10 คำ

wage (2 POS) · shadow (2 POS) · depth · pure · flame (3 POS) · shade (2 POS) · flash (3 POS) · income · melt (2 POS) · tunnel (2 POS)

### ชุดทดสอบยาก (test-only) — 30 คำ

round (4 POS) · right (4 POS) · well (4 POS) · back (4 POS) · close (4 POS) · last (4 POS) · run (2 POS) · go (2 POS) · stick (2 POS) · set (3 POS) · head (3 POS) · mean (3 POS) · fire (3 POS) · check (2 POS) · present (3 POS) · record (3 POS) · hold (2 POS) · type (2 POS) · bank (2 POS) · match (2 POS) · spring (2 POS) · take (2 POS) · break (2 POS) · turn (2 POS) · look (2 POS) · decision · practice (2 POS) · colour (3 POS) · fall (2 POS) · leaf (2 POS)
