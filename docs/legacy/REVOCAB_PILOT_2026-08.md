# Legacy archive — RE-Vocab / pilot era (2026-08)

> ⚠️ **ARCHIVED — บันทึกประวัติ ไม่ใช่คำสั่งปัจจุบัน**
>
> ไฟล์นี้รวมเอกสารยุค re-vocab / pilot (ส.ค. 2026) ที่ถูกแทนที่แล้ว เก็บไว้เพื่อ
> ตามรอยที่มาของข้อมูลและการตัดสินใจเดิมเท่านั้น **ห้ามใช้เป็นคู่มือปฏิบัติ**
>
> เอกสารที่เป็น authority ปัจจุบัน:
> - สถานะ pipeline นำเข้า production → [`docs/pipeline/PRODUCTION.md`](../pipeline/PRODUCTION.md)
> - ข้อมูล/review ฝั่ง English → [`docs/pipeline/qwen/LOCAL_QWEN_VOCAB_WORKFLOW.md`](../pipeline/qwen/LOCAL_QWEN_VOCAB_WORKFLOW.md)
> - งานตรวจ grammar → [`docs/pipeline/next_grammar.md`](../pipeline/next_grammar.md)
> - รูปแบบ draft 8 fields → [`docs/formats/terra_compact_format.md`](../formats/terra_compact_format.md)

## สารบัญ (ไฟล์ที่ถูกรวมไว้)

| # | ไฟล์เดิม | วันที่ | เนื้อหา |
|---|---|---|---|
| 1 | `re vocab.md` | 2026-08-13 | สเปกต้นฉบับ source-grounded generation |
| 2 | `continue_revocab.md` | 2026-08-13 | continuation guide (ประกาศตัวเองว่า historical) |
| 3 | `after_revocab.md` | 2026-08-13 | สรุปงานที่ทำครบหลัง re-vocab |
| 4 | `done_vocab.md` | 2026-08-13 | snapshot pilot 130 คำ / content_v2.db |
| 5 | `test.md` | 2026-08-13 | test-data handoff ของ pilot |
| 6 | `terra_subagent.md` | 2026-08-15 | contract เติมคำให้ครบ 2,967 (first pass) |
| 7 | `sol_subagent.md` | 2026-08-15 | contract review/repair corpus |
| 8 | `CONTINUE_VOCAB_PROMPT.md` | 2026-08-26 | prompt Qwen-assisted production review |

**เหตุผลที่ถูก archive:** ทั้งหมดอธิบายรอบงาน pilot 130 คำ (`content_v2.db`) และรอบเติม/ตรวจ
corpus 2,967 คำ ซึ่งจบไปแล้ว pipeline ปัจจุบันย้ายไปใช้ compact draft 8 fields +
grammar review ledger + immutable staging candidate ตาม `PRODUCTION.md` และ `next_grammar.md`



---

<!-- ===== ARCHIVED SOURCE 1/8: re vocab.md ===== -->

# [ARCHIVED 1/8] เดิมคือไฟล์ `re vocab.md`

_เนื้อหาด้านล่างคัดลอกคำต่อคำจากไฟล์เดิม ไม่มีการแก้ไข_

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



---

<!-- ===== ARCHIVED SOURCE 2/8: continue_revocab.md ===== -->

# [ARCHIVED 2/8] เดิมคือไฟล์ `continue_revocab.md`

_เนื้อหาด้านล่างคัดลอกคำต่อคำจากไฟล์เดิม ไม่มีการแก้ไข_

# RE Vocab — Continuation Guide

> Historical continuation guide. For the current local-Qwen run, corpus counts,
> and review handoff, use `LOCAL_QWEN_VOCAB_WORKFLOW.md` as the authority.

## Current objective

**Updated 2026-08-13.** The pilot phase is done: 100 real words plus a 30-word
hard test set are built, validated and shipped into the app seed as content
schema v2, and the app reads them (see `done_vocab.md` and `after_revocab.md`).
The app is no longer off-limits — content v2 and the Flutter layer moved together.

The next content objective is the **remaining corpus**: generate the 969
headwords in `data/terra_missing_manifest.txt`.  The manifest is the only
authority for Terra assignments; do not select ranges directly from the DB.

The user wants Terra/Codex generation only — never Gemini or another external
generation API.  Use the smallest practical token format for drafts.

## Current data state

- Source DB: `data/vocabulary_source.db`
- Source list: 2,967 unique Oxford-list headwords, all harvested successfully
- Normalized evidence currently includes source senses, forms, pronunciations,
  Thai translation candidates, and source examples.
- Source collection command: `python tools/build_vocab_library.py validate`
- Source collector: `tools/build_vocab_library.py`
- Existing app and unrelated worktree edits must remain untouched.

## Generated content state

- Canonical draft directory: `data/terra_english_drafts/`
- Canonical coverage: 2,967 unique headwords, 0 duplicate headwords, 0 parse errors
- Terra missing manifest: completed 969/969, remaining 0
- JSON, compact and retired legacy directories were consolidated and deleted on
  2026-08-13.  Do not recreate those parallel draft stores.
- Sol review manifest: `data/sol_review_manifest.txt` (2,967 words; 725
  deterministic-failure priority, then 2,242 semantic-audit priority)
- Source-fidelity validator: `tools/validate_vocab_generation.py`
- Generated-table contract: `tools/generate_source_cloze.py`
- **Content validator (schema v2): `tools/validate_content_db.py`** — the one that
  catches content a learner cannot use, not just content the source disagrees with
- Consolidation report: `data/draft_consolidation_report.txt`

Rebuild the immutable missing-word manifest:

```powershell
python tools/build_missing_draft_manifest.py
```

## Required generation format from now on

Do not use full JSON drafts for new generation. Terra now writes the six-field
English-only format documented in `terra_english_format.md`: one `@ headword`
header followed by five tab-separated sentence rows. Each row uses a numeric
`sense_id`, so the long dictionary gloss and all Thai text are omitted from
model output. `tools/translate_vocab_content.py` validates those facts against
the source DB, translates the accepted rows, and writes the eight-field compact
format to a separate directory without changing the source drafts.

The compact importer is implemented at `tools/import_terra_compact.py`. It:

1. Read translated eight-field files from `data/terra_translated_drafts/*.txt`.
2. Parse the header plus eight tab-separated fields per sentence.
3. Group five rows per headword.
4. Convert them to the existing generated-sentence table format.
5. Use the existing source-grounded validation logic before saving.
6. Be idempotent and require no API key, Gemini package, or network call.
7. Store failures as `failed`; continue importing later drafts.

The draft generator must use only the normalized source values:

- POS and `sense_gloss` must be exact DB values.
- `cloze_target` must be the headword or a source-supported form for that POS.
- Each headword has 5 unique lines/ranks 1–5; rank 1 is a memorable contextual
  sentence, not necessarily dramatic, and rank 2 must be an unambiguous Cloze.
- Terra does not write Thai. Azure Translator F0 is the primary translator;
  DeepL is the context-aware repair provider. Translation results are cached in
  `data/translation_cache.db` so identical work never consumes quota twice.

## Process order (locked)

1. Generate English-only Terra `.txt` drafts for every headword that does not yet
   have a completed five-sentence draft. **Do not import them to SQLite during
   this first pass.**
2. After all 2,967 first-pass drafts exist, parse every English draft and run
   deterministic validation in memory. Create a manifest of failed words.
3. Use `gpt-5.6-sol` medium subagents to review and repair that complete
   manifest. Do not start Sol while headwords are still missing.
4. Re-parse and validate the complete English corpus.
5. Translate accepted English sentences with Azure, then DeepL for failures;
   keep production and the 30 test-only words in separate directories/DBs.
6. Use `gpt-5.6-sol` medium to audit remaining translation/context failures.
7. Combine all compact drafts into one JSON export, preserving source IDs and
   validation status.  Then import the finalized JSON into SQLite in one build
   step.
8. Only after content is finalized, design/apply a separate extraction/export
   step for Flutter.  Do not modify `vocab_app` during this work.

## Commands and checks

Source integrity:

```powershell
python tools/build_vocab_library.py validate
```

Validate English-only drafts without using an API key or writing output:

```powershell
python tools/translate_vocab_content.py --input-dir data/terra_english_drafts --dry-run
```

Validate one Terra batch against its exact immutable assignment:

```powershell
python tools/validate_english_draft_batch.py data/terra_english_drafts/terra_missing_0001_0025.txt --seq-start 1 --seq-end 25
```

Translate after credentials have been added to `.env`:

```powershell
python tools/translate_vocab_content.py --input-dir data/terra_english_drafts
```

Validate already-imported output (after generation; do not make it block
first-pass generation):

```powershell
python tools/validate_vocab_generation.py --entry-table generation --run-id terra-source-cloze-v1 --status passed
```

## Cautions

- `re vocab.md` is the governing source-first policy.
- The 2,967 count is the unique-word count in the Oxford source used by this
  project; do not invent 33 words merely to make the number 3,000.
- Preserve all existing unrelated git changes.
- Every Terra assignment must use disjoint `seq` ranges from
  `data/terra_missing_manifest.txt`, with at most 25 words per agent turn.
- Terra generation does not access `.env`; only the translation step reads
  `AZURE_TRANSLATOR_KEY`/`AZURE_TRANSLATOR_REGION` and optional
  `DEEPL_AUTH_KEY`.
- The current parallel limit is 4 total agents, so use at most 3 Terra
  generators alongside the root agent.


---

<!-- ===== ARCHIVED SOURCE 3/8: after_revocab.md ===== -->

# [ARCHIVED 3/8] เดิมคือไฟล์ `after_revocab.md`

_เนื้อหาด้านล่างคัดลอกคำต่อคำจากไฟล์เดิม ไม่มีการแก้ไข_

# After RE Vocab

## สถานะ (2026-08-13)

ทำครบทุกข้อแล้ว รายละเอียดคำศัพท์และวิธีทำอยู่ใน `done_vocab.md`

| ข้อ | งาน | สถานะ |
|---|---|---|
| 2 | โครงสร้าง Sense และ POS ที่สมบูรณ์ | ✅ `senses` ผูก POS + rank + source, 386 sense |
| 3 | ตาราง Word family และ forms | ✅ `word_forms` แยก inflection / derived, 688 แถว |
| 4 | explanation ต่อประโยค | ✅ `example_sentences.explanation_th` 650 ประโยค อ่านเดี่ยวได้ |
| 5 | ข้อมูลอธิบายความสัมพันธ์ | ✅ `related_words` 526 แถว + `relation_groups` 83 กลุ่ม |
| 6 | สร้าง Content Pipeline รุ่นใหม่ | ✅ `tools/select_pilot_100.py` → `build_content_db.py` → `export_app_seed.py` |
| 7 | Validator | ✅ `tools/validate_content_db.py` 17 ด่าน · 0 problems |
| 8 | คำศัพท์ชุดยาก 30 คำ + hook หลาย POS ใน flashcard | ✅ `data/hard_test_30.json` + `lib/domain/test_hooks.dart` — **ต้องลบก่อนทำแอปจริง** |
| 9 | ด้านหลังการ์ด | ✅ `widgets/word_result_card.dart` |
| 10 | Dictionary เต็ม | ✅ `screens/word_detail_page.dart` อ่าน dataset เดียวกับการ์ด |
| 11 | คำอธิบายในเกม | ✅ Cloze / Word Association / Odd One Out ดึงจากตาราง ไม่ generate สด |
| 12 | Motivation และ Progress | ✅ `widgets/progress_mastery_view.dart` |
| 13 | Content-version migration | ✅ `lib/data/content_reseed.dart` + เทสครอบ |

ตรวจแล้ว: `flutter analyze` 0 errors · `flutter test` 127/127 ผ่าน · pipeline ทั้งชุด ~14 วินาที

## ที่ยังเหลือ

- regenerate 241 คำที่ปลดออกจาก legacy batch (`data/regenerate_manifest.json`) ก่อนขยาย corpus
- ขยายจาก 100 คำเป็นชุดเต็ม ตามขั้นใน `action_plan.txt` ระยะที่ 8
- ลบ scaffolding ชุดทดสอบ 30 คำ ก่อน ship (ดู `done_vocab.md` ข้อ 3)


---

<!-- ===== ARCHIVED SOURCE 4/8: done_vocab.md ===== -->

# [ARCHIVED 4/8] เดิมคือไฟล์ `done_vocab.md`

_เนื้อหาด้านล่างคัดลอกคำต่อคำจากไฟล์เดิม ไม่มีการแก้ไข_

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


---

<!-- ===== ARCHIVED SOURCE 5/8: test.md ===== -->

# [ARCHIVED 5/8] เดิมคือไฟล์ `test.md`

_เนื้อหาด้านล่างคัดลอกคำต่อคำจากไฟล์เดิม ไม่มีการแก้ไข_

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


---

<!-- ===== ARCHIVED SOURCE 6/8: terra_subagent.md ===== -->

# [ARCHIVED 6/8] เดิมคือไฟล์ `terra_subagent.md`

_เนื้อหาด้านล่างคัดลอกคำต่อคำจากไฟล์เดิม ไม่มีการแก้ไข_

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


---

<!-- ===== ARCHIVED SOURCE 7/8: sol_subagent.md ===== -->

# [ARCHIVED 7/8] เดิมคือไฟล์ `sol_subagent.md`

_เนื้อหาด้านล่างคัดลอกคำต่อคำจากไฟล์เดิม ไม่มีการแก้ไข_

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


---

<!-- ===== ARCHIVED SOURCE 8/8: CONTINUE_VOCAB_PROMPT.md ===== -->

# [ARCHIVED 8/8] เดิมคือไฟล์ `CONTINUE_VOCAB_PROMPT.md`

_เนื้อหาด้านล่างคัดลอกคำต่อคำจากไฟล์เดิม ไม่มีการแก้ไข_

# Continue Vocab — prompt เดียวจบ

> **Qwen-assisted production review (2026-08-26):** อ่าน
> `LOCAL_QWEN_VALIDATION_AND_SERVER.md` ก่อน. ChatGPT session ปัจจุบันถือ
> `1976-2699`; external AI ถือ `2700-2967`. ห้ามช่วงทับกัน. ใช้ Qwen candidate เป็น
> ข้อเสนอและเทียบ evidence/canonical ทุก rank. Candidate ที่อนุมัติใช้แทน canonical ต้อง
> report `repaired` พร้อม complete five-row overlay; ถ้าบาง rank ผิดให้ซ่อมเฉพาะแถวนั้น
> และคัดลอกแถวที่ผ่านแบบคำต่อคำ. ห้ามแก้ canonical, manifest, evidence DB, staging SQLite
> หรือไฟล์ของอีกช่วง. หลังทุก batch รัน progress แล้วรัน
> `python tools/run_production_after_review.py`; autorun จะ no-op จนรวมครบ
> `2967/2967 errors=0` แล้วจึงแปล, build, validate และ promote production ภายใต้ lock

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
