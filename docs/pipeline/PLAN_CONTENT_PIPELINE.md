# แผน: สร้างประโยค → แปล → เขียนคำอธิบาย grammar (ด้วย subagent)

## สรุปสั้น

งานนี้ไม่ใช่งานเดียว แต่เป็น **3 งานที่ต้องใช้คนละกำลัง** และตอนนี้มีงานหนึ่ง
ทำผิดวิธีอยู่

| งาน | ใครควรทำ | สถานะจริงตอนนี้ |
|---|---|---|
| 1. ประโยคอังกฤษ | LLM (ต้องคิด) | ครบ 2,967 คำ แต่ ~1,654 คำรอแก้ |
| 2. แปลไทย | เครื่องแปล (Azure/DeepL) | ยังไม่ได้ทำ นอกจาก pilot |
| 3. คำอธิบาย grammar | **LLM (ต้องคิด)** | **ทำผิดวิธี — ใช้ template แล้วส่งเครื่องแปล** |

## ปัญหาที่เจอ: คำอธิบายถูกสร้างด้วย template

`tools/translate_vocab_content.py:359` สร้างคำอธิบายแบบนี้:

```python
def explanation_en(headword, row, gloss):
    return (f'In this sentence, "{row.target}" is used as {row.pos} for the '
            f'headword "{headword}" and expresses this dictionary sense: {gloss}')
```

แล้วส่งข้อความนี้ไปให้ Azure แปลเป็นไทย ผลคือทั้ง 5 ประโยคของคำเดียวกัน
ได้คำอธิบาย **เกือบเหมือนกันหมด** ต่างแค่ target/pos/gloss และ**ไม่พูดถึงบริบท
ของประโยคนั้นเลย**

ซึ่งขัดกับข้อกำหนดตรง ๆ:

- `re vocab.md:203` — "Explanation ต้องบอกบริบท เหตุผลที่ต้องใช้คำนั้น/รูปนั้น และ grammar ที่จำเป็น"
- `SPEC.md:423` — "ไม่เก็บ grammar note รวมหนึ่งย่อหน้าต่อคำ **หรือคัดลอก note เดียวใช้กับทั้ง 5 ประโยค**"

และ `tools/validate_content_db.py` จับไม่ได้ เพราะมันเช็คแค่ความยาว >= 12 ตัวอักษร
กับการอ้างประโยคอื่น — template ผ่านทั้งคู่สบาย

### เทียบกับของที่ ship ไปแล้ว (pilot 100 คำ)

pilot ใช้ LLM เขียน (`explanation_source = terra-source-cloze-v1`) ได้แบบนี้:

```
age r4 [ages]  Everyone ages, but some people stay young inside.
  TH   ทุกคนแก่ตัวลง แต่บางคนยังเยาว์วัยอยู่ข้างใน
  EXPL age เป็นกริยาแปลว่าแก่ตัวลง ประธาน everyone ถือเป็นเอกพจน์จึงเติม s

afternoon r2 [afternoons]  We play football on Saturday afternoons.
  EXPL เมื่อพูดถึงบ่ายหลาย ๆ ครั้งที่เกิดซ้ำ ๆ ใช้รูปพหูพจน์ afternoons คู่กับ on
```

นี่คือมาตรฐานที่ต้องได้ — อธิบาย **ประโยคนั้น** ไม่ใช่อธิบายคำ

## ข้อสรุปสำคัญที่สุด: ยังไม่ถึงเวลาทำคำอธิบาย

ลำดับที่ล็อกไว้ใน `continue_revocab.md:78-95` ให้แปล (ขั้น 5) **หลัง** corpus
อังกฤษนิ่งแล้ว (ขั้น 4) และตอนนี้ยังไม่นิ่ง:

```
2,967 คำ ทั้งหมด
  160 คำ  seq 566-725   รอซ่อม (87 คำต้องเขียนประโยคใหม่ทั้ง 5)
1,494 คำ  audit bucket  ละเมิด POS coverage / 3-form
--------
1,654 คำ (56%) ประโยคจะเปลี่ยน
```

**ถ้าเขียนคำอธิบายตอนนี้ 56% จะถูกทิ้ง** เพราะคำอธิบายผูกกับประโยคทีละประโยค
พอประโยคเปลี่ยน คำอธิบายใช้ไม่ได้ทันที

คิดเป็นงานที่เสียเปล่า: 1,654 x 5 = **8,270 คำอธิบาย**

## แผนที่ควรทำ เรียงตามลำดับ

### ขั้น A — ปิดงานอังกฤษให้จบก่อน (ต้องทำก่อนเสมอ)

1. เขียน `tools/check_cloze_coverage.py` (แผนที่อนุมัติไว้แล้วใน
   `~/.claude/plans/claude-recursive-newt.md`) — ได้ defect list ที่เครื่องชี้เอง
2. ซ่อม seq 566-725 (160 คำ, 11 batch)
3. ซ่อม audit bucket ตาม defect list

subagent: `general-purpose`, model `opus`, batch 15 คำ, ขนาน 3 ตัว

### ขั้น B — แปลประโยคด้วยเครื่อง (ถูกและเร็ว ไม่ต้องใช้ subagent)

```bash
python tools/translate_vocab_content.py --input-dir data/terra_english_drafts
```

- Azure Translator F0 ฟรี 2M ตัวอักษร/เดือน
- 2,967 x 5 = 14,835 ประโยค x ~55 ตัวอักษร = **~816K ตัวอักษร** พอดีโควตาฟรี
- cache อยู่ที่ `data/translation_cache.db` แปลซ้ำไม่เสียโควตา
- DeepL ใช้ซ่อมเฉพาะเคสที่ Azure พัง

**ต้องแก้ก่อนรัน:** ตัด `explanation_en()` ออกจาก `translation_items()` ไม่ให้
ส่ง template ไปแปล เหลือแปลแค่ประโยค — ลดโควตาลงครึ่งหนึ่งด้วย

### ขั้น C — เขียนคำอธิบาย grammar ด้วย subagent (ของจริงอยู่ตรงนี้)

นี่คือส่วนเดียวที่ต้องใช้ LLM จริง ๆ และเป็นส่วนที่แพงที่สุด

**ปริมาณ:** 2,967 คำ x 5 = **14,835 คำอธิบาย**

**สิ่งที่ subagent ได้รับต่อ 1 คำ:**

| input | จาก |
|---|---|
| headword | manifest |
| 5 ประโยคอังกฤษ + rank + target + pos | `data/terra_english_drafts/` (หลังซ่อมแล้ว) |
| คำแปลไทยของแต่ละประโยค | ผลขั้น B |
| `source_senses.gloss` ของ sense ที่ใช้ | evidence DB |
| `source_forms` ของคำนั้น | evidence DB |

**กติกาที่ต้องบอก subagent:**

- อธิบาย **ประโยคนั้น** ไม่ใช่อธิบายคำ — คำอธิบาย 5 อันของคำเดียวกันต้องต่างกันจริง
- บอกว่าทำไมต้องใช้ **รูปนั้น** (ทำไม `ages` ไม่ใช่ `age`)
- ใส่ grammar เฉพาะที่จำเป็นต่อประโยคนั้น
- อ่านเดี่ยว ๆ รู้เรื่อง ห้ามอ้าง "ประโยคก่อนหน้า" / "ตัวอย่างที่ 2"
  (`validate_content_db.py` มี regex จับอยู่)
- ยาวไม่เกินการ์ด — ดูเกณฑ์ `MEANING_MAX_CHARS = 42` เป็นแนว, explanation
  ขั้นต่ำ 12 ตัวอักษร
- ห้ามแต่งข้อเท็จจริงทางภาษา ใช้ gloss/form จาก source เท่านั้น

**ขนาด batch และ wave:**

| batch | คำ/batch | คำอธิบาย/batch | จำนวน batch | wave (ขนาน 3) |
|---|---|---|---|---|
| 15 คำ | 15 | 75 | 198 | 66 |
| 25 คำ | 25 | 125 | 119 | 40 |

model: `sonnet` พอ (เขียนตามกฎ มี input ครบ ไม่ต้องตัดสินใจเชิงรสนิยมมาก)
เก็บ `opus` ไว้ให้ขั้น A ที่ต้องแต่งประโยคเอง

**output:** compact format v2 8 fields ตาม `terra_compact_format.md`
เขียนลง directory แยก ไม่แตะ canonical

**validator ที่ต้องเพิ่ม:** ตอนนี้ยังไม่มีอะไรจับ "คำอธิบาย 5 อันเหมือนกัน"
ต้องเพิ่มเช็ค — ถ้าคำอธิบายของคำเดียวกันซ้ำกันเกิน threshold ให้ fail
(ใช้ตรรกะเดียวกับ uniqueness ของประโยคที่ `translate_vocab_content.py:132`)

### ขั้น D — import + export

```bash
python tools/import_terra_compact.py
python tools/validate_content_db.py
python tools/export_app_seed.py        # ไม่ใส่ --include-test-words
```

## ความจริงเรื่องต้นทุน

ขั้น C คือ 40-66 wave ของ subagent ซึ่งใหญ่มาก และตอนนี้ **โควตาเดือนนี้เต็มแล้ว**
(Plan agent ตัวล่าสุดตายด้วย `hit your monthly spend limit`)

ทางลดต้นทุนที่ทำได้จริง:

1. **อย่าเพิ่งทำขั้น C** จนกว่าขั้น A จะจบ — ประหยัดทันที 8,270 คำอธิบายที่จะถูกทิ้ง
2. ทำขั้น B ก่อน (เครื่องแปล ไม่กินโควตา LLM เลย)
3. ขั้น C ใช้ `sonnet` ไม่ใช่ `opus`
4. batch 25 แทน 15 ลด wave จาก 66 เหลือ 40 (ต้องแก้สัญญาใน `sol_subagent.md`)
5. ทำเป็นชุดตาม CEFR — A1 892 คำก่อน (seq 1-892) ได้ของใช้จริงเร็วที่สุด
   แล้วค่อย A2/B1/B2

## ลำดับที่แนะนำให้ลงมือ

```
1. tools/check_cloze_coverage.py         ← ไม่ใช้ subagent เลย ทำได้เดี๋ยวนี้
2. ตัด explanation_en() ออกจาก translate  ← แก้ 3 บรรทัด ทำได้เดี๋ยวนี้
3. เพิ่ม validator จับคำอธิบายซ้ำ          ← ไม่ใช้ subagent
4. ซ่อม 160 + 1,494 คำ                    ← ใช้ subagent opus (รอโควตา)
5. แปลด้วยเครื่อง                          ← ไม่ใช้ LLM
6. เขียนคำอธิบายด้วย subagent sonnet        ← ก้อนใหญ่สุด ทำท้ายสุด
```

ข้อ 1-3 ทำได้ทันทีโดยไม่กินโควตา และทำให้ข้อ 4-6 ถูกลงมาก
