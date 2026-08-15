# Sol Subagent Contract — Corpus Review and Repair

Sol เริ่มงานได้เมื่อ Terra corpus ครบ 2,967 คำแล้วเท่านั้น

## Assignment

parent กำหนด `SEQ_START`, `SEQ_END` (สูงสุด 15 คำต่อ turn), `OUTPUT` และ `REPORT`
จาก `data/sol_review_manifest.txt` ช่วง seq ต้องไม่ทับกับ agent อื่น

## Review inputs

- canonical block ของคำจาก `data/terra_english_drafts/`
- exact `source_senses`, `source_forms`, `source_examples` จาก `data/vocabulary_source.db`
- deterministic errors ใน manifest
- `terra_english_format.md` และกฎ source-first ใน `re vocab.md`

## What to review

- POS/sense ID/target form ถูกต้องตาม source
- ประโยคเป็น English ธรรมชาติ ใช้ความหมายของ sense นั้นจริง
- เลือก common learner sense ก่อน rare/archaic/technical sense
- rank 1 มีบริบทจำง่าย ไม่บังคับดราม่า
- rank 2 เป็น cloze ที่เดาคำได้ชัด
- ไม่มี placeholder, malformed sentence, semantic mismatch หรือประโยคซ้ำ

## Output

- เขียน `REPORT` หนึ่งบรรทัดต่อคำ: `headword<TAB>pass|repaired<TAB>short reason`
- ถ้าคำใดต้องแก้ ให้แก้เฉพาะ rank ที่ผิด และคัดลอก rank ที่ผ่านจาก canonical
  แบบคำต่อคำ จากนั้นเขียน replacement block ครบ 5 บรรทัดลง `OUTPUT` เพื่อ merge
  อย่างปลอดภัย ห้าม rewrite บรรทัดที่ไม่ได้มีปัญหา
- คำที่ pass ไม่ต้องเขียนลง `OUTPUT`
- replacement ใช้ six-field English-only format และต้องผ่าน deterministic validator
- ห้ามแก้ canonical, DB, translation, code, docs หรือไฟล์ agent อื่น

หากไม่มี repair ให้สร้าง `OUTPUT` เป็นไฟล์ว่างและยังต้องมี REPORT ครบทุกคำ
