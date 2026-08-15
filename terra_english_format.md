# Terra English draft format

รูปแบบนี้ใช้ให้ agent สร้างเฉพาะประโยคอังกฤษ โดยไม่เสีย token กับคำแปลไทย
และไม่คัดลอก dictionary gloss ลงใน draft

```text
@ headword
rank<TAB>sense_id<TAB>pos<TAB>target<TAB>memorable<TAB>English sentence
```

หนึ่งคำต้องมี 5 บรรทัด โดยมีข้อกำหนดดังนี้:

- `rank` ต้องเป็น 1 ถึง 5 ไม่ซ้ำกัน
- `sense_id` และ `pos` ต้องตรงกับ `data/vocabulary_source.db`
- `target` ต้องเป็น headword หรือ form ที่ source รองรับ และปรากฏตรงตัวในประโยค
- `memorable` เป็น `1` เฉพาะ rank 1 หมายถึงประโยคหลักที่มีบริบทชัด ไม่ได้บังคับให้ดราม่า
- ประโยคอังกฤษทั้ง 5 ต้องไม่ซ้ำกันและต้องไม่เป็น placeholder
- ห้ามใส่คำแปลไทย, field name, JSON หรือ Markdown ใน block

`tools/translate_vocab_content.py` จะเติมคำแปลและคำอธิบายไทย แล้วเขียนเป็น
compact format v2 จำนวน 8 fields ใน directory แยกต่างหาก โดยไม่แก้ draft ต้นฉบับ
และไม่รวมไฟล์ test เว้นแต่สั่ง `--include-test` โดยตรง

