# Terra Subagent Contract — Missing Vocabulary First Pass

ใช้ contract นี้เฉพาะช่วงเติมคำที่ยังไม่มี draft ให้ครบ 2,967 คำ ก่อนเริ่ม Sol review

## Assignment

parent ต้องกำหนดตัวแปรสามค่าให้ชัดเจน:

- `SEQ_START`
- `SEQ_END` (ไม่เกิน 25 คำต่อ turn)
- `OUTPUT` เช่น `data/terra_english_drafts/terra_missing_0001_0025.txt`

รายการคำต้องอ่านจาก `data/terra_missing_manifest.txt` เฉพาะแถวที่ `seq` อยู่ในช่วง
ที่ได้รับ ห้ามเลือกจาก source rank เอง ห้ามสลับคำ ห้ามเพิ่มคำ และห้ามทำคำที่มีอยู่
นอกช่วง

## Required reading

1. `terra_english_format.md`
2. แถว assignment ใน `data/terra_missing_manifest.txt`
3. `source_senses`, `source_forms` และเมื่อมี `source_examples` ของคำที่ได้รับจาก
   `data/vocabulary_source.db`

## Output rules

- เขียนเฉพาะ English-only six-field literal-tab TXT
- หนึ่งคำมี `@ headword` และ 5 ประโยค ranks 1–5
- `sense_id` และ POS ต้องตรง source
- target ต้องเป็น headword หรือ source-supported form ของ POS นั้น และอยู่ในประโยค
- rank 1 ใช้ `memorable=1` เพียงบรรทัดเดียว: บริบทชัดและจำง่าย ไม่บังคับดราม่า
- rank 2 ต้องเป็น cloze ที่เดาคำตอบได้ชัดจากบริบท
- ประโยคทั้งห้าต้องเป็นธรรมชาติ ไม่ใช้ template ซ้ำ ไม่ใช้ placeholder
- เลือกความหมายทั่วไปที่ผู้เรียนใช้ได้ก่อน หลีกเลี่ยง rare/archaic/technical sense
  เมื่อยังมี sense ปกติที่เหมาะกว่า
- ห้ามเขียนคำแปลไทย, explanation, JSON, Markdown หรือ dictionary gloss ลง draft
- ห้ามแปล ห้าม import ห้ามแก้ DB/โค้ด/docs และห้ามแตะไฟล์ของ agent อื่น
- ถ้า `OUTPUT` มีอยู่แล้ว ให้หยุดและแจ้ง parent ห้าม overwrite

## Required validation

เมื่อเขียนครบ ให้รัน:

```powershell
python tools/validate_english_draft_batch.py OUTPUT --seq-start SEQ_START --seq-end SEQ_END
```

งานถือว่าเสร็จเมื่อผลเป็น:

- assigned = words = จำนวนแถวในช่วง
- sentences = words × 5
- errors = 0

ถ้า validator ไม่ผ่าน ให้แก้เฉพาะ `OUTPUT` ของตัวเองจนผ่าน แล้วรายงานจำนวนคำ,
จำนวนประโยค และ errors เท่านั้น

## Parent scheduling

- ใช้ Terra Medium พร้อมกันสูงสุด 3 agents (รวม root เป็น 4 slots)
- แจกช่วงต่อเนื่องที่ไม่ทับกัน ครั้งละ 25 คำ
- หลัง agent จบ ให้ parent ตรวจไฟล์อีกครั้ง แล้วรัน
  `tools/build_missing_draft_manifest.py`; สคริปต์จะเก็บเลข seq เดิมและรายงาน remaining
- ห้ามเริ่ม Sol ก่อน manifest เหลือ 0
- เมื่อครบแล้ว Sol Medium รับ failed-review manifest คนละช่วงเพื่อแก้ semantic/legacy issues
