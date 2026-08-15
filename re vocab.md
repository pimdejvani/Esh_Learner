# RE Vocab — Source-Grounded Vocabulary Generation Specification

สถานะ: Draft สำหรับอนุมัติก่อนเริ่มสร้างข้อมูลคำศัพท์ทั้งหมด  
ปรับปรุงล่าสุด: 2026-08-13

## 1. เป้าหมาย

สร้างข้อมูลคำศัพท์สำหรับแอปเรียนภาษาอังกฤษโดยใช้ pipeline แบบ source-first:

1. Dictionary และ dataset เป็นแหล่งข้อเท็จจริงหลัก
2. โมเดลขนาดเล็กสร้าง draft จาก source ที่กำหนด
3. Code validator ตรวจข้อผิดพลาดที่ตรวจแบบ deterministic ได้
4. โมเดลขนาดใหญ่ซ่อมเฉพาะรายการที่ไม่ผ่าน
5. ตรวจซ้ำก่อนเขียนลงฐานข้อมูล
6. รายการที่ยังไม่ผ่านต้องเข้าคิวตรวจด้วยคน ห้ามนำเข้าแอปอัตโนมัติ

โมเดลไม่มีสิทธิ์สร้าง POS, sense, word form, word family, related word หรือแหล่งอ้างอิงขึ้นเอง

## 2. Architecture

```text
Dictionary / Dataset Sources
             │
             ▼
      Normalize SOURCE_JSON
             │
             ▼
       Small Model Draft
             │
             ▼
     Deterministic Validator
        │              │
      ผ่าน             ไม่ผ่าน
        │              │
        │              ▼
        │       Large Model Repair
        │              │
        │              ▼
        │       Validator ตรวจซ้ำ
        │         │           │
        │       ผ่าน        ยังไม่ผ่าน
        │         │           │
        ▼         ▼           ▼
      Save      Save      Human Review
```

## 3. Source policy

### 3.1 ข้อมูลที่ต้องมาจาก dictionary/dataset

- Headword
- Part of speech
- English source gloss ของแต่ละ sense
- Countability เมื่อมีข้อมูล
- Word forms
- Word-family members
- Related-word candidates
- Pronunciation/IPA เมื่อ source มีให้
- Source name และ license

### 3.2 งานที่โมเดลทำได้

- แปล source gloss เป็นภาษาไทยแบบสั้นและเป็นธรรมชาติ
- เลือกคำแปลที่เหมาะกับ sense จาก candidate ที่ source ให้มา
- สร้างคำอ่านไทย โดยต้องระบุว่าเป็นการอนุมานเมื่อไม่มี pronunciation source
- สร้าง collocation จาก sense ที่มีอยู่
- สร้างตัวอย่างภาษาอังกฤษและคำแปลไทย
- สร้าง Cloze sentence และคำอธิบายที่ผูกกับประโยคนั้น
- เลือก related words จาก candidate ที่ให้มา
- อธิบายว่าคำสัมพันธ์กันอย่างไร โดยห้ามกล่าวเกิน source

### 3.3 งานที่โมเดลห้ามทำ

- สร้าง sense หรือ POS เพิ่มเอง
- สร้าง word form หรือ word-family member เพิ่มเอง
- สร้าง related word ที่ไม่มีใน candidate list
- อ้าง dictionary/source ที่ไม่ได้ส่งให้
- ระบุ pronunciation ว่ามาจาก dictionary ทั้งที่เป็นการคาดเดา
- ใช้ความรู้จากความจำของโมเดลแทน source
- ซ่อนข้อมูลที่ไม่แน่ใจด้วยการแต่งคำตอบให้ดูสมจริง

เมื่อ source ไม่พอ ให้คืน `needs_source: true` แทนการเดา

## 4. Production output schema

```json
{
  "headword": "capriole",
  "thai_reading": "แคพ-รี-โอล",
  "stress_index": 1,
  "reading_origin": "dictionary|model_pronunciation_inference|needs_source",
  "parts_of_speech": [
    {
      "pos": "noun",
      "countability": "countable|uncountable|null",
      "meanings": [
        {
          "thai": "ท่ากระโดดดีดขาหลังของม้า",
          "source_gloss": "Exact source gloss",
          "meaning_origin": "dictionary_translation|model_translation_of_source_gloss"
        }
      ],
      "collocation_en": "perform a capriole",
      "collocation_th": "แสดงท่ากระโดดแคพริโอล",
      "flashcard_example": {
        "en": "The horse performed a capriole.",
        "th": "ม้าแสดงท่ากระโดดแคพริโอล",
        "cloze_target": "capriole"
      }
    }
  ],
  "word_family_and_forms": [
    {
      "word": "caprioles",
      "kind": "inflection|derived",
      "pos": ["noun", "verb"],
      "meaning_th": null,
      "form_note_th": "รูปพหูพจน์ของคำนาม หรือกริยาที่ใช้กับประธานเอกพจน์บุรุษที่สาม",
      "source": "kaikki"
    }
  ],
  "related_words": [
    {
      "word": "leap",
      "pos": ["noun"],
      "meaning_th": "การกระโดด",
      "relation_keyword": "คำที่กว้างกว่า",
      "relationship_th": "leap หมายถึงการกระโดดทั่วไป ส่วน capriole เป็นท่ากระโดดชนิดเฉพาะ",
      "source": "datamuse"
    }
  ],
  "cloze_examples": [
    {
      "rank": 1,
      "pos": "verb",
      "en_text": "The dancer caprioled with joy.",
      "th_text": "นักเต้นกระโดดโลดเต้นด้วยความดีใจ",
      "cloze_target": "caprioled",
      "is_emotional": true,
      "explanation_th": "ประโยคกล่าวถึงการกระโดดโลดเต้นที่เกิดขึ้นแล้ว จึงใช้ caprioled ซึ่งเป็นรูปอดีตของ capriole"
    }
  ]
}
```

ข้อกำหนดด้าน type:

- `null` ต้องเป็น JSON null ห้ามใช้ string `"null"`
- Field ที่รองรับหลาย POS ต้องใช้ array เช่น `["noun", "verb"]` ห้ามใช้ string `"noun|verb"`
- Form ที่สะกดเหมือนกันต้องมีเพียงหนึ่ง record แล้วรวม POS ใน array
- `source_gloss` ต้องตรงกับ source เดิมทุกตัวอักษร

## 5. Flashcard rendering requirements

### 5.1 ด้านหน้า

- Headword
- ปุ่ม TTS
- คำอ่านไทยพร้อม stress
- ยังไม่แสดงความหมาย
- ไม่แสดง symbol, IPA หรือ CEFR

### 5.2 ด้านหลัง

- Headword, TTS และคำอ่านไทย
- หนึ่งบรรทัดต่อหนึ่ง POS
- หลายความหมายใน POS เดียวกันคั่นด้วย comma
- ตัวอย่างภาษาอังกฤษและคำแปลไทยหนึ่งชุดต่อ POS
- Dropdown `Word family & forms` ปิดเป็นค่าเริ่มต้น
- Dropdown `Related words` ปิดเป็นค่าเริ่มต้น
- Related word แต่ละคำต้องมี POS และความหมายไทยสั้น ๆ
- มีทางลัดเปิด Dictionary entry เต็ม
- เนื้อหายาวให้ scroll ห้ามย่อ font เพื่อยัดข้อมูล

ตัวอย่าง:

```text
capriole  🔊
แคพ-รี-โอล

n. ท่ากระโดดดีดขาหลังของม้า, ท่ากระโดดในการเต้นรำ
   The horse performed a capriole.
   ม้าแสดงท่ากระโดดแคพริโอล

v. กระโดดโลดเต้น, บังคับม้าให้แสดงท่า capriole
   The dancer caprioled across the stage.
   นักเต้นกระโดดโลดเต้นข้ามเวที

▶ Word family & forms
▶ Related words
```

## 6. Cloze requirements

- หนึ่งคำต้องมี 5 ประโยคเมื่อข้อมูลและรูปคำรองรับ
- ครอบคลุมทุก POS
- ใช้อย่างน้อย 3 รูปคำที่แตกต่างกันเมื่อมีรูปคำเพียงพอ
- `cloze_target` ต้องปรากฏตรงตัวใน `en_text`
- Rank 1 ต้องเป็นสถานการณ์ที่มีอารมณ์หรือจำง่าย
- คำศัพท์อื่นในประโยคควรอยู่ประมาณ A2/B1 หรือต่ำกว่า
- Thai translation ต้องรักษาความหมายเดียวกับประโยคอังกฤษ
- `explanation_th` ของทุกประโยคต้องอ่านเข้าใจได้โดยลำพัง
- Explanation ต้องบอกบริบท เหตุผลที่ต้องใช้คำนั้น/รูปนั้น และ grammar ที่จำเป็น
- ห้ามอ้าง “ประโยคก่อนหน้า”, “ประโยคที่ 2”, “ตัวอย่างอื่น” หรือข้อมูลที่ผู้เล่นไม่เห็น

## 7. Related-word explanation requirements

- เลือกเฉพาะ candidate จาก source
- ต้องใช้ relation/sense เดียวกับที่ใช้สร้างโจทย์
- Explanation ต้องบอกว่าคำสัมพันธ์กันอย่างไร
- ห้ามใช้ “คำพ้องความหมาย” ถ้าเหมือนกันเพียงบาง sense
- ใช้ label ที่แคบและแม่น เช่น:
  - `ความหมายใกล้เคียง`
  - `คำที่กว้างกว่า`
  - `คำที่แคบกว่า`
  - `อยู่ในหมวดเดียวกัน`
  - `ส่วนประกอบ`
  - `ท่าการเคลื่อนไหว`
- หากอธิบายเป็นประโยคได้ไม่มั่นใจ ให้ใช้ keyword ที่ตรวจสอบได้จาก source

Odd One Out ไม่ให้โมเดลเดาเหตุผลย้อนหลัง ต้องอธิบายจาก hub/category/relation ที่ระบบใช้สร้างรอบจริง

## 8. Small-model generation prompt

```text
You are a source-grounded content generator for a Thai English-learning app.

Transform SOURCE_JSON into one production-ready vocabulary entry.
Do not create lexical facts from memory.

NON-NEGOTIABLE RULES

1. Use only the POS, senses, word forms, word-family members, related-word
   candidates, pronunciation data, and source labels supplied in SOURCE_JSON.

2. Never invent a sense, POS, word form, word-family member, related word,
   pronunciation source, or dictionary citation.

3. If required information is unavailable, return needs_source: true for that
   field. Do not guess.

4. Include every supplied modern sense exactly once. Copy source_gloss
   character-for-character from SOURCE_JSON.

5. Thai meanings must be concise dictionary-style Thai, normally 2–10 words.
   Keep meanings as separate array items within their POS.

6. Produce exactly one short, natural flashcard example per POS. The
   grammatical use must match the POS field. Other vocabulary should be
   understandable to an A2/B1 learner.

7. Include only supplied word-family members and forms. Each spelling appears
   once. If a spelling supports multiple POS, store them in a POS array.
   An inflection with unchanged meaning must have meaning_th: null.

8. Select at most 3 strong related words from supplied candidates. Use only
   source-supported POS. Explain the relationship without overstating it.

9. Produce exactly 5 cloze examples. Cover every POS and at least 3 supplied
   forms when available. cloze_target must appear verbatim in en_text. Rank 1
   must be emotionally engaging.

10. Every explanation_th must stand alone and use only its sentence's context.
    Explain what the context means, why the selected word/form fits, and brief
    grammar when useful. Never refer to another sentence or sentence number.

11. Return valid JSON only. JSON null must be null, never the string "null".
    Fields supporting multiple POS must use arrays.

12. Return no IPA, CEFR, symbol metadata, markdown, or commentary.

OUTPUT_SCHEMA:
{{OUTPUT_SCHEMA}}

SOURCE_JSON:
{{SOURCE_JSON}}
```

Generation settings:

- Temperature: `0–0.2`
- Structured JSON Output: เปิดเมื่อ API รองรับ
- หนึ่งคำต่อหนึ่ง request ในช่วงทดสอบ
- เมื่อ schema และ validator เสถียรแล้วจึงทดลอง batch ขนาดเล็ก

## 9. Large-model repair prompt

```text
You are the final source-grounded reviewer and repairer.

You receive:
1. SOURCE_JSON — the only allowed lexical evidence
2. DRAFT_JSON — generated by a smaller model
3. VALIDATION_ERRORS — deterministic errors found by code

Repair DRAFT_JSON so it is production-ready.

REPAIR POLICY

1. Fix every item in VALIDATION_ERRORS.
2. Preserve valid fields exactly when no correction is necessary.
3. Make the smallest possible changes.
4. Do not rewrite the whole entry for style alone.
5. Do not add facts absent from SOURCE_JSON.
6. If the source is insufficient, mark the field as needs_source instead of
   guessing.
7. Check semantic problems that code may miss:
   - POS matches the grammatical use in every example
   - English examples sound natural
   - Thai translations preserve the same meaning
   - non-target vocabulary is suitable for A2/B1
   - pronunciation and stress match supplied evidence
   - related-word explanations do not overstate the relationship
   - every Cloze explanation is independently understandable
   - word forms are not duplicated
   - one spelling contains every source-supported POS
   - null is JSON null, not the string "null"
8. Return the complete corrected JSON object only.
9. Return no markdown or commentary outside JSON.

SOURCE_JSON:
{{SOURCE_JSON}}

DRAFT_JSON:
{{DRAFT_JSON}}

VALIDATION_ERRORS:
{{VALIDATION_ERRORS}}
```

โมเดลใหญ่ต้องทำหน้าที่ repair ไม่ใช่ rewrite เพื่อจำกัดค่าใช้จ่ายและลดโอกาสแก้ข้อมูลที่ถูกให้ผิด

## 10. Deterministic validator

Validator ต้องตรวจอย่างน้อย:

### 10.1 Source fidelity

- Headword ตรง source
- POS ครบและไม่มี POS เพิ่ม
- Source gloss ครบทุก sense และตรงทุกตัวอักษร
- Forms และ family อยู่ใน source ทั้งหมด
- Related words อยู่ใน candidate list ทั้งหมด
- Source label ตรงกับข้อมูลที่ใช้จริง

### 10.2 Schema and type

- JSON parse ได้
- Required fields ครบ
- `null` เป็น JSON null
- POS หลายค่าเป็น array
- Form spelling ไม่ซ้ำ
- Form เดียวรวม POS ครบ
- Enum values ถูกต้อง

### 10.3 Flashcard

- มี meaning ทุก POS
- มี flashcard example หนึ่งชุดต่อ POS
- Cloze target อยู่ใน example จริง
- Thai meaning และ translation มีตัวอักษรไทย

### 10.4 Cloze

- มี 5 ประโยค
- Rank ไม่ซ้ำและเรียง 1–5
- Rank 1 มี `is_emotional: true`
- ครอบคลุมทุก POS
- Target อยู่ใน sentence ตรงตัว
- Target เป็น form ที่ source รองรับ
- POS ของ target สอดคล้องกับการใช้ในประโยค
- Explanation ไม่มีการอ้างประโยคอื่น
- Explanation มีทั้งความหมายตามบริบทและเหตุผลด้านรูปคำ/grammar

### 10.5 Related words

- จำนวนไม่เกินที่กำหนด
- Related POS ตรง source
- มี meaning, keyword และ relationship explanation
- Keyword ไม่กล่าวเกินจริง เช่น synonym ทั้งที่เหมือนเพียงบาง sense

### 10.6 Pronunciation

- ใช้ dictionary pronunciation เมื่อมี
- Stress index อยู่ในช่วงจำนวนพยางค์
- คำอ่านใช้รูปแบบที่ UI แยกพยางค์ได้
- เมื่อเป็นการอนุมานต้องใช้ `model_pronunciation_inference`

## 11. Automation policy

```python
draft = generate_with_small_model(source)
errors = validate(draft, source)

if errors:
    final = repair_with_large_model(
        source=source,
        draft=draft,
        validation_errors=errors,
    )
    final_errors = validate(final, source)

    if final_errors:
        send_to_human_review(final, final_errors)
    else:
        save(final)
else:
    save(draft)
```

เพิ่มเติม:

- สุ่มงานที่ small model ผ่าน validator แล้ว 5–10% ส่งให้ large model audit
- หาก audit batch ใดมี semantic error สูงกว่าเกณฑ์ ให้หยุด batch และขยายการตรวจ
- Large model repair ได้ไม่เกิน 2 ครั้งต่อคำ
- เกิน 2 ครั้งให้เข้าคิว human review
- ห้ามลด validation rule เพื่อให้ข้อมูลผ่านง่ายขึ้น

## 12. Cost monitoring

เก็บข้อมูลต่อหนึ่งคำ:

```json
{
  "headword": "capriole",
  "generator_model": "SMALL_MODEL",
  "repair_model": "LARGE_MODEL_OR_NULL",
  "prompt_version": "re-vocab-v1",
  "input_tokens": 0,
  "candidate_tokens": 0,
  "thinking_tokens": 0,
  "billable_output_tokens": 0,
  "generator_cost_usd": 0,
  "repair_cost_usd": 0,
  "total_cost_thb": 0,
  "validation_attempts": 1,
  "repair_attempts": 0,
  "final_status": "passed|human_review",
  "validation_errors": []
}
```

สูตรประมาณราคา:

```text
input_cost  = input_tokens × input_price_per_1m / 1,000,000
output_cost = (candidate_tokens + thinking_tokens)
              × output_price_per_1m / 1,000,000
cost_thb    = (input_cost + output_cost) × USD_THB
```

ต้องเก็บราคา model และอัตราแลกเปลี่ยนพร้อมวันที่ เพราะราคาและค่าเงินเปลี่ยนได้

## 13. Benchmark baseline — capriole

ผลทดสอบหนึ่ง request ต่อ model ด้วย source และ prompt เดียวกัน:

| Model | Latency | QC หลังเพิ่ม blind-spot checks | Estimated paid-tier cost/word |
|---|---:|---:|---:|
| gemini-3.1-flash-lite | 13.7s | 90/100 | ฿0.112943 |
| gemini-3.5-flash-lite | 5.7s | 90/100 | ฿0.188739 |
| gemini-3.6-flash | 18.3s | 95/100 | ฿1.165484 |
| gemini-3.1-pro-preview | 30.4s | 90/100 | ฿1.881384 |

ข้อสรุปจาก benchmark:

- Automated schema QC เพียงอย่างเดียวไม่เพียงพอ
- Small models ทำ draft ได้ แต่ยังมี POS mismatch, duplicate forms และ pronunciation error
- Large model ยังสร้าง type/source error ได้ จึงต้องผ่าน validator เช่นกัน
- `gemini-3.6-flash` ให้สมดุลคุณภาพต่อราคาดีที่สุดในตัวอย่างนี้
- หากใช้ small model เป็น generator ต้องส่งเฉพาะงานที่ validator ไม่ผ่านไป large model
- ผลหนึ่งคำยังไม่เพียงพอสำหรับตัดสิน production model ขั้นสุดท้าย ต้อง benchmark หลายชนิดคำก่อนเริ่มทั้ง dataset

## 14. Acceptance criteria ก่อนเริ่มสร้างทั้งชุด

- Source adapter ดึงข้อมูลซ้ำได้และมี license metadata
- JSON schema ถูกล็อก version
- Small-model prompt ถูกล็อก version
- Large-model repair prompt ถูกล็อก version
- Validator มี automated tests ครอบคลุม known failure cases
- Cost logger บันทึก token และ retry จริง
- Benchmark อย่างน้อยครอบคลุม:
  - คำ POS เดียว
  - คำหลาย POS
  - คำหลาย sense
  - irregular verb
  - countable/uncountable noun
  - คำที่ source ไม่มี Thai translation
  - คำที่ source ไม่มี pronunciation
  - คำที่ related candidates อ่อนหรือกำกวม
- ผ่าน human spot-check ตาม sample rate ที่กำหนด
- ยังไม่เขียนทับ production database จนกว่าจะได้รับอนุมัติ

