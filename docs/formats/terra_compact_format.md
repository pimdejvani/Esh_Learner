# Terra compact draft format v2

ใช้สำหรับสร้างประโยคเท่านั้น โดยไม่ซ้ำข้อมูล dictionary ที่มีอยู่แล้วใน
`data/vocabulary_source.db`

หนึ่งไฟล์มีหลายคำได้ แต่แต่ละคำต้องอยู่ใน block ของตัวเอง:

```text
@ headword
rank<TAB>sense_id<TAB>pos<TAB>target<TAB>emotional<TAB>English sentence<TAB>Thai translation<TAB>Thai explanation
rank<TAB>sense_id<TAB>pos<TAB>target<TAB>emotional<TAB>English sentence<TAB>Thai translation<TAB>Thai explanation
rank<TAB>sense_id<TAB>pos<TAB>target<TAB>emotional<TAB>English sentence<TAB>Thai translation<TAB>Thai explanation
rank<TAB>sense_id<TAB>pos<TAB>target<TAB>emotional<TAB>English sentence<TAB>Thai translation<TAB>Thai explanation
rank<TAB>sense_id<TAB>pos<TAB>target<TAB>emotional<TAB>English sentence<TAB>Thai translation<TAB>Thai explanation
```

ความหมายของแต่ละส่วน:

| ส่วน | ความหมาย |
|---|---|
| `@ headword` | คำหลักของ 5 บรรทัดถัดไป เช่น `@ explain` |
| `rank` | `1` ถึง `5` ไม่ซ้ำกัน |
| `sense_id` | เลข `source_senses.id` ของความหมายที่ใช้ ต้องเป็นของ headword นี้ |
| `pos` | POS ตรงกับ sense_id เช่น `verb`, `noun`, `adj` |
| `target` | headword หรือ form ที่ source รองรับ และต้องปรากฏตรงตัวในประโยคอังกฤษ |
| `emotional` | `1` เฉพาะ rank 1; rank อื่นใช้ `0` |
| English sentence | ประโยคอังกฤษสำหรับ Cloze |
| Thai translation | คำแปลของประโยค |
| Thai explanation | อธิบายบริบทและเหตุผลการใช้คำ/รูปคำ โดยอ่านเดี่ยว ๆ ได้ |

กติกาไฟล์:

- คั่น field ด้วย tab จริง (`\t`) จำนวน 7 จุดต่อบรรทัด
- ห้ามมี tab หรือขึ้นบรรทัดใหม่ในเนื้อหา
- ใช้ UTF-8
- ไม่ต้องใส่ JSON, field names, markdown หรือ source gloss ยาว ๆ
- หนึ่ง headword ต้องมี 5 บรรทัดเท่านั้น
- comment เริ่มด้วย `#` ได้ และ importer จะข้าม

ตัวอย่างเชิงโครงสร้าง (ข้อความเป็น placeholder):

```text
@ explain
1	12345	verb	explain	1	English text.	คำแปลไทย	คำอธิบายไทย
2	12346	noun	explanation	0	English text.	คำแปลไทย	คำอธิบายไทย
3	12345	verb	explained	0	English text.	คำแปลไทย	คำอธิบายไทย
4	12345	verb	explaining	0	English text.	คำแปลไทย	คำอธิบายไทย
5	12345	verb	explains	0	English text.	คำแปลไทย	คำอธิบายไทย
```

Extractor จะใช้ `headword + sense_id` ดึง source gloss จริงจาก SQLite เอง จึงไม่ต้อง
เสีย token ส่ง gloss ซ้ำ และยังตรวจว่า POS/sense/form เป็นข้อมูลจาก source จริงได้.
