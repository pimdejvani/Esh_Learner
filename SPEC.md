# แอปคำศัพท์ Oxford 3000 → ไทย — Product & Technical Spec

> Working name: **TBD** · Platform: iOS-first (Flutter) · สถาปัตยกรรม: local-first offline
> เอกสารนี้คือ spec ฉบับเต็ม แบ่ง build เป็นเฟส — Phase 1 คือสิ่งที่ลงมือทำก่อน

---

## 1. วิชัน

แอปเรียนคำศัพท์ Oxford 3000 (แปลไทย) ที่ออกแบบให้ **"ว่างนิดเล่นนิด ว่างนานเล่นนาน"** — เปิดมาเล่นได้ทันทีโดยไม่ต้องตั้งเป้า ระบบไหลต่อเนื่องและ **ปรับตัวอัตโนมัติตามงานวิจัยด้านความจำ** เพื่อให้จำคำได้นานที่สุดต่อเวลาที่ลงไป

หลักการที่มาจากงานวิจัย (แปลงเป็นกลไกในแอป):
- **Spacing effect** → เอนจิน FSRS จัดวันทวนของแต่ละคำ
- **Testing effect / retrieval practice** → ทุกเกมบังคับ "ดึงคำตอบเอง" ก่อนเฉลย
- **Desirable difficulty** → เกมยากขึ้นตามความแก่ของคำ + ปรับ target retention
- **Dual coding** → การ์ดมีภาพ + เสียง + ตัวอักษรพร้อมกัน
- **Semantic network / spreading activation** → hint และเกมใช้คำข้างเคียงจากข้อมูล association ของมนุษย์จริง (SWOW)
- **Production effect** → เกม Dictation/Scramble บังคับผลิตคำเอง
- **Interleaving** → session สลับคำจากหลายหมวด
- **Chunking** → จำกัดคำใหม่/วัน ปรับตาม backlog (จังหวะแนะนำ ไม่ใช่กำแพง — ดู §6.4)
- ~~Sleep consolidation~~ → ตัดออก 2026-07-23: ไม่บังคับรอข้ามคืน ให้ FSRS จัดเองล้วน ๆ (ดู §6.2)

---

## 2. การตัดสินใจที่ล็อคแล้ว (Locked decisions)

| # | เรื่อง | ข้อสรุป |
|---|--------|---------|
| 1 | Tech stack | **Flutter** ยืม pattern จาก Gymmer_App: layered (widgets / screens / data store abstraction + sqlite&memory impl / domain services), SQLite, numbered migrations, seed data |
| 2 | Content pipeline | **Bundle dataset สำเร็จรูป** — คำแปลจาก **dictionary สำเร็จรูป (Wiktionary CC BY-SA)**, ประโยคจาก LLM, related words จาก SWOW+WordNet, ship เป็น SQLite seed → offline 100% สำหรับข้อความ |
| 3 | รูปภาพ | **Runtime fetch + cache** จากแหล่ง open-license (Openverse / Wikimedia Commons) — เก็บ URL ใน dataset ตอน build, แอปโหลด+cache ครั้งแรกที่เจอคำ |
| 4 | เสียง | **Device TTS** (`flutter_tts` → iOS `AVSpeechSynthesizer`) — ฟรี, offline, อ่านทั้งคำและประโยค |
| 5 | Session model | **ไหลต่อเนื่อง ไม่มีเส้นจบ** — เปิดมาเล่นได้เลย หยุดเมื่อไหร่ก็ได้ |
| 6 | Game selection | **Auto ตาม maturity ของคำ** (desirable-difficulty ladder) + สุ่มสลับเพื่อ interleaving |
| 7 | Mnemonic / ภาพจำ | **ตัดออกทั้งระบบ** — ไม่มีคำเสียงคล้าย, ไม่มีแต่งภาพจำ/ประโยคเอง, ไม่มี re-prompt (ตัดสิน 22 ก.ค. 2026) |
| 8 | Word pool entry | **Auto CEFR order** + ปักหมวด focus ได้ (optional) |
| 9 | Grammar/inflection | **Lemma เป็น SRS item** — grammar note ของรูปผันติดกับประโยค/คำตอบ, flag irregular |
| 10 | Phase 1 scope | **Vertical slice บาง แต่ครบ loop** |
| 11 | Motivation layer | **Streak + heatmap + สถานะคำ แบบเบา** (ไม่ใช่ casino, XP/level เต็มไปเฟสหลัง) |
| 12 | Hint system | **Progressive hint** ในเกมยาก/คำยาก — เปิดทีละขั้น, ยิ่งใช้ rating ยิ่งถูก cap ต่ำ (ดู §8b) |
| 13 | Related-words source | **SWOW เป็นหลัก** (association มนุษย์จริง + closeness ฟรี) **+ WordNet กรอง** (flag synonym/antonym + หมวดสำหรับ Odd One Out) — แอป non-commercial จึงใช้ SWOW (CC BY-NC) ได้ |
| 14 | UI | **ทำ UX ทั้งหมดให้เสร็จก่อน แล้วค่อยทำ UI** — ใช้ template meeting-iq (shadcn) เป็น **design language reference** แปลงเป็น Flutter theme (ดู §13) |

### Default ที่ตั้งไว้ (แก้ได้)
- **ตรวจคำตอบพิมพ์:** normalize case/whitespace + ยอม typo ระยะ Levenshtein 1 (คำยาว >4 ตัว) → นับเป็น "เกือบถูก" = rating **Hard** ไม่ใช่ Again
- **FSRS:** FSRS-5 default weights, `requestRetention` เริ่มที่ **0.80** (แก้ไข 2026-07-23 — เป้า ~80% ไม่เอา ~95%)
- ~~Sleep-gap~~ — ตัดออก 2026-07-23 (ดู §6.2): due ใช้ค่า FSRS ล้วน ๆ, วันใหม่เริ่มหลังตี 3
- **New-card-cap:** เริ่ม **8 คำ/วัน** ปรับอัตโนมัติตาม backlog + accuracy (ช่วง 3–15) — เป็นจังหวะแนะนำ ไม่ใช่กำแพง (§6.4)
- **ลิขสิทธิ์:** ใช้เฉพาะ headword list + คำแปล/ประโยคที่เราเขียนเอง — **ไม่ก๊อป** definition/ตัวอย่างประโยคของ OUP; เก็บ author + license ของภาพ CC เพื่อแสดง attribution
- **การใช้งาน:** แอปนี้เป็น **non-commercial** (ส่วนตัว/GitHub) — เป็นเงื่อนไขที่ทำให้ใช้ SWOW (CC BY-NC) ได้; ถ้าวันหน้าจะขาย ต้องเปลี่ยนแหล่ง related_words

---

## 3. สถาปัตยกรรม (ยืมจาก Gymmer_App)

```
lib/
├── main.dart
├── models/                 # data classes: Word, WordForm, ExampleSentence, SrsState, ...
├── data/
│   ├── vocab_store.dart          # abstract interface (แบบ WorkoutStore)
│   ├── vocab_store_sqlite.dart   # SQLite impl (production)
│   ├── vocab_store_memory.dart   # in-memory impl (test/dev)
│   ├── migrations/               # numbered SQL migrations (0001_init.sql ...)
│   ├── seed/                     # bundled SQLite seed (generated dataset)
│   ├── image_cache.dart          # runtime open-license image fetch + local cache
│   └── tts_service.dart          # flutter_tts wrapper
├── domain/                 # rules อยู่นอก widget
│   ├── fsrs/                     # FSRS-5 scheduler (per-item)
│   ├── session_engine.dart       # endless queue + game selection ladder
│   ├── new_card_governor.dart    # adaptive new-card-cap + focus topic
│   ├── retention_tuner.dart      # adaptive requestRetention
│   ├── answer_checker.dart       # typo-tolerant grading
│   └── streaks.dart              # borrowed pattern from Gymmer
├── screens/
│   ├── play_screen.dart          # หน้าเล่นหลัก (การ์ด/เกมไหลต่อเนื่อง)
│   ├── word_detail_page.dart     # dictionary entry เต็ม: senses, forms, grammar, sentences
│   └── progress_page.dart        # streak, heatmap, สถานะคำ
├── games/                  # แต่ละเกมเป็น widget แยก (รับ payload จาก session_engine)
│   ├── flashcard_swipe.dart
│   ├── cloze.dart
│   ├── matching.dart
│   ├── word_association.dart
│   ├── word_scramble.dart
│   └── odd_one_out.dart
├── widgets/
└── theme/
```

- **offline-first:** ข้อความ/scheduling/logic ทำงานได้เต็มที่ไม่มีเน็ต; ต้องมีเน็ตเฉพาะโหลดรูปครั้งแรก + TTS ใช้ offline
- **single-device local** (เหมือน Gymmer) — ยังไม่มี account/sync ในเฟสแรก

---

## 4. Data Model (SQLite)

```sql
-- คำหลัก (lemma) = SRS item
words(
  id INTEGER PK,
  headword TEXT,             -- "answer"
  cefr TEXT,                 -- CEFR ของ core sense (ใช้เรียงลำดับ intro)
  freq_rank INTEGER,         -- ลำดับความถี่ (คุมลำดับ intro)
  thai_reading TEXT,         -- คำอ่านทับศัพท์ "แอน-เซอร์" (แบ่งพยางค์ด้วย -)
  stress_index INTEGER,      -- พยางค์ที่เน้นเสียง (แสดงตัวหนา) เริ่มนับ 1
  ipa TEXT,                  -- ใช้ภายในเท่านั้น (สร้าง thai_reading/stress/แบ่งพยางค์ Dictation hint) ไม่แสดงผล
  translation_source TEXT,   -- เช่น "Wiktionary"
  translation_license TEXT,  -- เช่น "CC BY-SA 3.0"
  has_photo INTEGER,         -- 1 ถ้าเป็นคำรูปธรรมที่หาภาพได้
  image_url TEXT,            -- open-license URL (resolve ตอน build)
  image_license TEXT,        -- เช่น "CC BY 2.0"
  image_author TEXT
)

-- ความหมายแยกตามชนิดคำ (แสดงแบบ dictionary entry ดู §9b)
senses(
  id INTEGER PK,
  word_id INTEGER FK,
  pos TEXT,                  -- N. / V. / ADJ. / ADV. ...
  meaning_th TEXT,           -- "คำตอบ, คำเฉลย"
  cefr TEXT,                 -- CEFR ต่อ sense (Oxford ให้แยกตามความหมาย)
  countable INTEGER NULL,    -- เฉพาะ N.: 1 นับได้ / 0 นับไม่ได้
  collocation_en TEXT,       -- "answer the phone"
  collocation_th TEXT,       -- "รับโทรศัพท์"
  sense_rank INTEGER,        -- ลำดับแสดงใน entry
  is_core INTEGER            -- 1 = sense หลักที่แอปใช้ทดสอบ (ติดดาว)
)

-- รูปผัน (แสดง/สอน grammar แต่ไม่ใช่ SRS item แยก)
word_forms(
  id INTEGER PK,
  word_id INTEGER FK,
  form_text TEXT,            -- "went"
  form_type TEXT,            -- past / past_participle / plural / 3sg / ving / comparative / superlative
  is_irregular INTEGER,
  grammar_note_th TEXT       -- คำอธิบายเต็ม ดูข้อ 9
)

-- ประโยคตัวอย่าง 5 ประโยค/คำ (backup)
example_sentences(
  id INTEGER PK,
  word_id INTEGER FK,
  form_id INTEGER NULL,      -- ประโยคนี้ใช้รูปผันไหน (NULL = base)
  rank INTEGER,              -- 1..5 (1 = ดีสุด/emotional/สถานการณ์จริง)
  en_text TEXT,
  th_text TEXT,
  cloze_start INTEGER,       -- ตำแหน่งคำเป้าใน en_text (สำหรับเกม Cloze)
  cloze_end INTEGER,
  is_emotional INTEGER
)

-- คำที่เกี่ยวข้องในหมวด (ดู §8b ตระกูล A)
-- ใช้ร่วม 3 ที่: hint semantic + เกม Word Association + ตัวลวง Odd One Out
-- ที่มา: SWOW (association + strength) + WordNet (flag giveaway + หมวด) — ดู §5
related_words(
  id INTEGER PK,
  word_id INTEGER FK,
  related_word_id INTEGER FK, -- FK เข้าตาราง words (คำใบ้ต้องอยู่ใน Oxford 3000 ด้วยกัน)
  relation_type TEXT,        -- association (SWOW) / hypernym / part_of (WordNet)
  closeness REAL,            -- ความแรงจากความถี่คำตอบ SWOW (คุมลำดับการใบ้/ความยาก distractor)
  is_giveaway INTEGER        -- 1 = synonym/antonym (auto-flag จาก WordNet) → ห้ามใช้เป็น hint
)
-- Dictation hint (ตระกูล B, สะกด) generate runtime จาก headword — ไม่ต้องมีตาราง

-- สถานะ FSRS ต่อคำต่อผู้ใช้
srs_state(
  word_id INTEGER PK FK,
  state TEXT,                -- new / learning / young / mature
  stability REAL,
  difficulty REAL,
  due_at INTEGER,
  last_review INTEGER,
  reps INTEGER,
  lapses INTEGER,
  last_direction TEXT        -- en_th / th_en (สลับทิศ)
)

-- log ทุกครั้งที่ตอบ (ใช้ปรับ retention + heatmap + วิเคราะห์)
reviews_log(
  id INTEGER PK,
  word_id INTEGER FK,
  ts INTEGER,
  rating TEXT,               -- again / hard / good / easy
  game_type TEXT,
  direction TEXT,
  elapsed_ms INTEGER
)

-- หมวด/ธีม (สำหรับ interleaving + focus)
topics(id INTEGER PK, name TEXT, cefr TEXT)
word_topics(word_id INTEGER FK, topic_id INTEGER FK)

daily_stats(date TEXT PK, new_introduced INTEGER, reviews_done INTEGER, streak_kept INTEGER)
settings(key TEXT PK, value TEXT)   -- new_card_cap, focus_topic, request_retention, ...
```

---

## 5. Content Pipeline (build-time, ทำครั้งเดียว)

สคริปต์แยก (Python หรือ Dart CLI) รันตอน build ไม่ได้อยู่ในแอป:

1. **Input:** รายการ Oxford 3000 headword + CEFR band + POS (มีใน GitHub/OUP PDF)

2. **คำแปลไทย — ใช้ dictionary สำเร็จรูป ไม่ให้ LLM แปลจากศูนย์:**
   - แหล่งหลัก: **Wiktionary (EN) Thai glosses** — license **CC BY-SA** (ใช้ได้ฟรี ต้องเก็บ attribution)
   - map headword+POS → เก็บเป็นแถวในตาราง `senses` (แยกตาม POS, ติด CEFR ต่อ sense ตามข้อมูล Oxford)
   - LLM/คน ทำแค่ **เลือก sense, จัด rank, mark `is_core` + เกลาให้กระชับ** (ไม่ใช่แปลใหม่)
   - เก็บ `translation_source` + `translation_license` ต่อคำ เพื่อแสดง attribution
   - ทางเลือกสำรอง: LEXiTRON/Yaitron (NECTEC) — คุณภาพดีแต่ **license ไม่ open ต้องขออนุญาตก่อนใช้**

3. **`related_words` — ใช้ dataset สำเร็จรูป ไม่ให้ LLM คำนวณเอง:**
   - **SWOW (Small World of Words) เป็นหลัก** — ข้อมูล free-association จากมนุษย์จริง (~100 คน/คำ ตอบว่า "เห็นคำนี้นึกถึงอะไร") = spreading activation ที่วัดจริง ตรงกับกลไก hint ของเรา
     - `closeness` ได้ฟรีจากความถี่คำตอบ — **ไม่ต้องใช้ LLM จัดอันดับ**
     - license CC BY-NC — ใช้ได้เพราะแอป non-commercial
   - **Princeton WordNet เป็นตัวกรอง/เสริม** — (a) synonym/antonym มีป้ายกำกับ → **auto-flag `is_giveaway`** (b) hypernym แบ่งหมวดคม ๆ สำหรับกลุ่มคำเกม **Odd One Out**
   - เหตุผลที่ไม่ใช้ ConceptNet: SWOW ทำหน้าที่เดียวกันด้วยข้อมูลมนุษย์แท้ที่สะอาดกว่า (ตัวอย่างชี้ขาด: WordNet ไม่มีเส้น doctor→hospital แต่ SWOW มีพร้อมน้ำหนัก)
   - กรอง: คำใบ้ต้อง (a) อยู่ใน Oxford 3000 ด้วยกัน (b) **CEFR ≤ คำเป้า** — ห้ามใบ้ด้วยคำที่ยากกว่าที่ผู้เรียนรู้

4. **สิ่งที่ dictionary/dataset ไม่มี → LLM สร้าง** (เก็บลง SQLite seed):
   - `example_sentences` × 5 — ตาม QC standard ด้านล่าง
   - `word_forms` — รูปผันทั้งหมด + `grammar_note_th` (รูปแบบเต็ม ดู §9), flag irregular
   - `thai_reading` + `stress_index` — คำอ่านทับศัพท์แบ่งพยางค์ (derive จาก IPA)
   - `collocation` 1 วลีต่อ sense

5. **รูปภาพ:** สำหรับคำ `has_photo=1` เรียก Openverse/Wikimedia API หา URL ภาพ open-license + เก็บ license/author (ไม่ดาวน์โหลดตอนนี้ — แอป fetch ตอน runtime)

6. **QC pass:** มนุษย์ตรวจ sample ก่อน ship (sense ผิด/ประโยคแปลก/รูปไม่ตรง)

7. **Output:** `seed/vocab.db` bundle เข้า assets ของแอป

### QC standard ของประโยคตัวอย่าง (บังคับใช้ตอน generate + ตรวจ)
1. **5 ประโยคต้องใช้รูปผัน/โครงสร้างต่างกันโดยตั้งใจ** (V2, รูปฐาน/คำสั่ง, V-ing, present, to-infinitive) — เจอคำหลายบริบทฝังลึกกว่าซ้ำบริบทเดิม
2. **rank 1 ต้องเป็นประโยค `is_emotional`** — มีอารมณ์ร่วม/สถานการณ์จริง ไม่ใช่ประโยคแห้งจากพจนานุกรม
3. **คำรอบข้างในประโยคต้อง CEFR ≤ คำเป้า** — ไม่ให้ติดคำอื่นที่ยังไม่เรียน
4. grammar note เขียนแบบ **อธิบายเหตุผล** ตามรูปแบบ §9.2 และชี้จุดเปลี่ยนการสะกด (cry → cr**ied**: เปลี่ยน y เป็น i)
5. แต่ละประโยค mark `cloze_start/end` ให้เกม Cloze ใช้ได้ทันที

> **หมายเหตุลิขสิทธิ์:**
> - headword list เป็นข้อมูลข้อเท็จจริง แต่ **ห้ามคัดลอก** definition/ตัวอย่างประโยคของ Oxford
> - คำแปลจาก Wiktionary (CC BY-SA) ต้องแสดง attribution + แอปที่ share ต่อต้องเป็น compatible license
> - SWOW เป็น **CC BY-NC** — ใช้ได้เฉพาะ non-commercial (สถานะปัจจุบันของแอป) และต้อง attribution
> - ประโยคตัวอย่างเราสร้างเอง (LLM) — ไม่ติดลิขสิทธิ์ dictionary
> - ต้องมีหน้า "Credits/Licenses" ในแอปแสดงที่มาของคำแปล, related words และภาพ

---

## 6. Scheduling Engine

### 6.1 FSRS-5 (per-item)
- ใช้ FSRS-5 default weights (มี implementation อ้างอิงเป็น open-source แปลงมา Dart ได้)
- เก็บ `stability`, `difficulty` ต่อคำ (ข้อ 4) — ไม่ใช้ interval ตายตัว
- Map input → FSRS rating:
  - **Flashcard swipe:** ซ้าย = Again, ขวา = Good (กดค้าง/ปุ่มเสริม = Hard/Easy)
  - **เกมพิมพ์:** ถูกเป๊ะเร็ว = Easy, ถูก = Good, เกือบถูก(typo)/ใช้ hint = Hard, ผิด = Again

### 6.2 Day-boundary (แก้ไข 2026-07-23 — ตัดการบังคับรอข้ามวัน)
- ~~เดิม: บังคับ `due_at` = เช้าวันถัดไปเสมอ~~ **ตัดออก** — `due_at` ของทุกคำ (รวมครั้งแรกหลัง intro) ใช้ค่าที่ FSRS-5 คำนวณเองล้วน ๆ ไม่มี floor บังคับข้ามวัน — ถ้า user พร้อมเล่นต่อก็ให้ต่อไปเลย ไม่กำหนดขนาดตายตัวว่าต้องกี่เกม/กี่วันต่อคำ
- ยังต้องรู้ "วันนี้" สำหรับ bookkeeping (streak, daily stats, new-card pacing) — ใช้ **เส้นแบ่งวันตี 3 (03:00 local)** แทนเที่ยงคืน: เล่นตอนตี 1 ยังนับเป็นเมื่อวาน, เล่นหลังตี 3 นับเป็นวันใหม่แล้ว (`logicalDateKey` ใน `streaks.dart`)

### 6.3 Adaptive success-rate targeting (`retention_tuner`)
- ตั้ง `requestRetention` เริ่ม **0.80** ขอบเขต [0.70, 0.90] เป้า accuracy ~80% (แก้ไข 2026-07-23 — ผู้ใช้เลือกโซนยากที่ตอบถูก ~80% แทนโซนสบาย ~95%: ลืมมากขึ้นต่อรอบ = ได้ retrieval effort สูงกว่า จำระยะยาวดีกว่า; โปรไฟล์เก่าที่เซฟ >0.84 ไว้จะถูก migrate ลง 0.80 ตอนบูต)
- ดู rolling accuracy 7 วัน: ถ้าถูกสูงกว่าเป้ามากติดกัน → ลด requestRetention เล็กน้อย (interval ยาวขึ้น, ท้าทายขึ้น); ถ้าต่ำกว่าเป้า → เพิ่ม (ทวนถี่ขึ้น)

### 6.4 New-card governor (chunking) — แก้ไข 2026-07-23
- `new_card_cap` เริ่ม 8/วัน ยังปรับอัตโนมัติเหมือนเดิม (backlog สูง → ลด, backlog ต่ำ+accuracy ดี → เพิ่ม, เพดาน 15) — ใช้เป็น **จังหวะแนะนำของวันปกติ** เท่านั้น
- **Hot-streak burst** (เพิ่ม 2026-07-23): ดู 20 review ล่าสุด (ไม่สนหน้าต่าง 7 วัน ต้องมีอย่างน้อย 10) — ถ้าถูก ≥92% และไม่มี backlog กด → เพิ่ม cap ทีละ **+3** แทน +1; retune ทุกครั้งที่ตอบ ดังนั้นตอบถูกรัวๆ = คำใหม่ไหลออกมาเร็วขึ้นกลาง session เลย
- **New-word share ต่อบล็อก flashcard สเกลตาม accuracy** (แก้ไข 2026-07-24 แทน hot-streak 40% queue top-up เดิม): ดู accuracy 20 คำตอบล่าสุด (ต้องมี ≥10) — สัดส่วนคำใหม่ในแต่ละบล็อก flashcard = `0.4 × ((acc − 0.5)/0.4)` clamp [0,1]: ถูก ≥90% → คำใหม่ได้ถึง **40% ของบล็อก**, ~70% → 20%, ≤50% → ไม่มีคำใหม่; ยังไม่มีข้อมูล (ผู้เล่นใหม่) → 40%; ถ้าไม่มีคำให้ทวนเลย (fresh install) ไม่ใช้ share — เติมคำใหม่ตาม cap ได้เต็มบล็อก
- **เล่น flashcard ครบ 4 รอบ/วัน → รีเซ็ต limit คำใหม่** (เพิ่ม 2026-07-24 "ไม่อยาก limit flash"): play_screen นับบล็อก flashcard ที่จบไปในวันนั้น (settings `fc_rounds`) — ทุกครั้งที่ครบ 4 รอบ ตัวนับคำใหม่ที่ใช้ไปวันนี้ถูกยกหนี้ (settings `new_intro_forgiven`; daily_stats ยังเก็บยอดจริงไว้เพื่อสถิติ) ทำให้ cap เติมกลับมาเต็มแทนที่จะเป็นกำแพงรายวัน
- **ไม่ใช่กำแพงแข็ง**: ถ้าเคลียร์ overdue + คำใหม่ตาม cap + extra practice หมดแล้ว แต่ user ยังอยากเล่นต่อ (คิวจะว่าง) และยังมีคำที่ยังไม่เคยเรียน → ระบบดึงคำใหม่ต่อ เกิน cap ได้ ไม่ตัดจบ session ทิ้งไว้ทั้งที่ยังมีเนื้อหาเหลือ (`session_engine.dart` buildQueue fallback)
- ดึงคำใหม่ตาม `freq_rank` order — **re-rank ด้วย SWOW-EN18 response frequency แล้วทั้งลิสต์** (2026-07-24): band-major (A1 < A2 < B1) ในแต่ละ band เรียงตามความถี่ที่คำถูกนึกถึงใน SWOW (A1 อันดับแรกๆ ตอนนี้: money, water, food, car, music) — `tools/rerank_swow.py` → shim ใน wordlist.py remap เฉพาะค่า rank ไม่สลับลำดับ insert ดังนั้น word id เดิมคงที่; ถ้ามี focus topic → bias คำจากหมวดนั้นก่อน

---

## 7. Session Engine (endless queue)

หน้าเล่นดึง "item ถัดไป" จาก session_engine เรื่อย ๆ ไม่มีเส้นจบ ลำดับความสำคัญ (แก้ไข 2026-07-24):

1. **คำ due ที่ค้างนานสุดก่อน** (overdue reviews)
2. **รอบวนเกม (practice cycle)** — แต่ละรอบวน**สุ่ม 3–6 เกม** จากทั้ง 7 (สูตรสามเหลี่ยม `3 + d2 + d3`: 4–5 เกมออกบ่อยสุด อย่างละ 1/3, ขอบ 3/6 เกมอย่างละ 1/6) โดย **flashcard อยู่ทุกรอบและเป็นเกมแรกเสมอ** เกมที่เหลือสุ่มจากอีก 6 เกมแต่คงลำดับตื้น→ลึกของ `kPracticeGameCycle`: flashcard (recognition) → Matching (recognition แบบชุด) → Odd One Out (จัดหมวดความหมาย) → Word Association (ดึงผ่านโครงข่ายความหมาย) → Cloze (cued recall ในบริบท) → Scramble (ประกอบรูปคำ) → Dictation (ผลิตเต็มจากเสียง) — จบรอบแล้ววนกลับมา flashcard ใหม่
   - **คำใหม่ (ตาม cap ของวัน) นับเป็นกลุ่มเดียวกับบล็อก flashcard** (แก้ไข 2026-07-24) — ไม่ใช่ segment แยกหน้าคิวอีกแล้ว: ช่องการ์ดในบล็อก flashcard ถูกเติมด้วยคำใหม่ก่อน แล้วค่อยเติมคำ practice · การ์ดพบครั้งแรก: โชว์คำ กดเผยด้านหลัง แล้วปัด **ขวา = รู้จัก (คำใหม่ = Easy) / ซ้าย = ไม่รู้จัก (Again)** — การปัดแรก = review แรกเข้า FSRS ทันที
   - **บล็อก flashcard = 4–8 ใบ** (สามเหลี่ยม `4 + d3 + d3`, 6 ออกบ่อยสุด) · **เกมอื่นเกมละ 2–4 รอบ (uniform)** คำไม่ซ้ำกันในรอบวน · Matching สุ่มขนาดรอบ 4–6 คู่
   - คำ practice = คำที่มีประวัติแล้วและยังไม่ถึงคิว due (รวม learning ด้วย ไม่ใช่แค่ young/mature) เลือกแบบถ่วงน้ำหนัก **`(1/(1+streak)) × (difficulty/5)`** (แก้ไข 2026-07-24: คูณ FSRS difficulty ต่อคำเข้าไปด้วย — คำที่ scheduler เรียนรู้ว่ายากสำหรับผู้เล่นคนนี้ (d 9) โผล่ ~1.8× ของคำกลางๆ, คำง่าย (d 2) เหลือ 0.4×) + เล็งช่อง You Pass ที่ยังขาดก่อน · เกณฑ์ "คำอ่อน" ของ Matching ใช้ weight ตัวเดียวกัน
3. **คำใหม่เกิน cap** — ถ้าทุกอย่างข้างบนหมดแล้วยังมีคำที่ไม่เคยเรียน → ดึงต่อได้เลย ไม่ตัดจบ session (§6.4)

**เริ่มวัน:** ครั้งแรกที่เข้าแอปหลังตี 3 (วันใหม่ตาม §6.2) item แรกของคิวถูกบังคับเป็น **flashcard เสมอ** — เปิดวันด้วยจังหวะเบาที่คุ้นเคยก่อนค่อยไล่ ladder
**Interleaving:** queue สลับคำจากหลายหมวด ไม่เรียงทีละบท
**Bidirectional:** ทุก review สุ่มทิศ EN→TH / TH→EN (เก็บ `last_direction` กันซ้ำติดกัน)

### Game selection ladder (ข้อ 6)
| สถานะคำ | เกมที่ระบบเลือก | เหตุผล (research) |
|---------|-----------------|-------------------|
| **new** | flashcard (โหมดพบครั้งแรก รู้จัก/ไม่รู้จัก) | encoding: dual coding + เริ่ม retrieval ทันที |
| **learning** | flashcard swipe · Matching · Odd One Out | recognition ง่าย ตั้งหลัก |
| **young** | Cloze · Word Association | retrieval มีบริบท/โยงความหมาย |
| **mature** | Dictation · Word Scramble | production ยาก ตอกย้ำระยะยาว |

> batch games (Matching / Odd One Out / Word Association) ดึงหลายคำ due พร้อมกันข้ามหมวด
> ladder ใช้กับคิว due ปกติ — รอบ extra practice วนทุกเกมข้าม tier ได้ (ความหลากหลายคือจุดประสงค์ และรอบ practice ไม่กระทบ schedule แรง)

---

## 8. เกม 7 แบบ (spec ย่อ)

1. **Flashcard swipe** — การ์ด dual-coding (ภาพ+เสียง TTS+คำ) **ปัดได้ทันทีไม่ต้องกดเผยเฉลยก่อน** (แก้ไข 2026-07-23 v2): ปัดขวา = รู้จัก / ปัดซ้าย = ไม่รู้จัก บันทึกผลทันทีที่ปัด · แตะการ์ดเพื่อพลิกดูเฉลย (ทางเลือก ไม่บังคับ) · มีแค่ 2 ปุ่ม รู้จัก/ไม่รู้จัก — **ตัดปุ่ม Hard/ง่ายมากทิ้งทุกโหมด** · **พบครั้งแรกแล้วตอบรู้จัก = Rating.easy** (รู้อยู่แล้วให้คะแนนสูงกว่าปกติ FSRS เลื่อน due ไกล) อ่านออกเสียงอัตโนมัติ — แทนการ์ด intro เดิมทั้งหมด *[Phase 1]*
2. **Cloze** — ประโยคจริงเจาะช่องคำเป้า ให้เติม (พิมพ์หรือเลือก) มีบริบทช่วย → testing + context *[Phase 1]*
3. **Matching** — โยงเส้นจับคู่ EN–TH · อย่างน้อย **4 คู่** เสมอ (สูงสุด 6) และอย่างน้อย 2 คู่เป็นคำที่ streak ต่ำสุดของผู้เล่น (แก้ไข 2026-07-23) *[Phase 1]*
4. **Word Association** — โยงคำใหม่เข้ากับคำที่รู้แล้วในโครงข่ายความหมาย *[Phase 2]*
5. **Word Scramble** — เรียงตัวอักษรที่สลับให้เป็นคำ → production + desirable difficulty *[Phase 2]*
6. **Odd One Out** — เลือกคำที่ไม่เข้าพวกจากกลุ่ม → semantic categorization *[Phase 2]* · เกณฑ์ความเหมือน (แก้ไข 2026-07-24): คำนับเป็นพวกเดียวกันเมื่อเป็นข้อมูลหมวดชนิด typed (hypernym/category/part_of) หรือ closeness SWOW ≥ **0.03** (≈p75 ของข้อมูล) · กลุ่มต้องมี **อย่างน้อย 3 คำ** + 1 คำแปลก (ตัด fallback 2 คำทิ้ง) หาไม่ได้ = ข้ามไป flashcard · **ช่วงเริ่มเล่นแอป** (คำที่มีประวัติ ≤8 ≈ 2 บล็อกคำใหม่แรก) เข้มพิเศษ: ต้องมีกลุ่มที่ผ่านเกณฑ์ **มากกว่า 2 กลุ่ม** ให้เลือก ไม่งั้นไม่ออกเกม Odd เลย · กลุ่มให้คะแนนตาม closeness รวม สุ่มจาก top ≤5 กันซ้ำ hub เดิม
7. **Dictation** — ฟังเสียง (TTS) แล้วพิมพ์สะกด → listening + spelling + production *[Phase 2]*

ทุกเกมส่งผล rating กลับเข้า FSRS ผ่าน `answer_checker`

---

## 8b. Hint System (เกมยาก / คำยาก)

**หลักการ:** hint ต้อง **ไม่บอกคำตอบกลาย ๆ** แต่ **ชี้ย่านความจำให้ผู้เรียนดึงคำออกมาเอง** — เพื่อรักษา retrieval effort ที่งานวิจัยบอกว่าสร้างความจำ (desirable difficulty) ยิ่งต้องมีปุ่ม **"ใบ้"** ในเกมที่ต้องผลิตคำเอง และคำที่ยาก (difficulty สูง / lapses เยอะ)

hint แบ่งเป็น **2 ตระกูลตามธรรมชาติของเกม:**

### (A) เกมนึกคำจากความหมาย — hint = คำที่เกี่ยวข้อง (semantic / related-word)
ใช้กับ **Cloze, flashcard โหมดผลิตคำ, Scramble** — ความยากอยู่ที่ "นึกคำออกไหม"
- hint คือคำในหมวด/ย่านความหมายเดียวกัน กระตุ้น spreading activation ให้สมองเดินตามเส้นเชื่อมไปเจอคำเป้าเอง
- ตัวอย่าง: คำเป้า **propeller (ใบพัด)** → ใบ้ *airplane / helicopter* (หมวดเครื่องบิน)
- **Double duty:** ทุกครั้งที่ดึงคำเป้าผ่านคำข้างเคียง = ตอกเส้นเชื่อมในโครงข่ายความหมายให้แน่นขึ้น → ครั้งหน้าจำง่ายขึ้น (กลไกเดียวกับเกม Word Association)
- **กติกา generate:** คำที่ใบ้ต้อง "ชี้หมวด แต่ไม่ใช่คำตอบตรง ๆ" — ห้าม synonym/antonym ที่เดาปุ๊บได้ (เช่น ห้ามใบ้ *king* เพื่อถาม *queen*)

### (B) Dictation — hint = การสะกด (spelling-specific)
Dictation ได้ยินเสียงแล้ว รู้อยู่แล้วว่าคำไหน ความยากอยู่ที่ **"สะกดถูกไหม"** → related-word ช่วยไม่ได้
- hint เป็นตัวช่วยเรื่องสะกด: แบ่งพยางค์ (**tra-vel**) → เผยตัวอักษรทีละตัว → จำนวนตัวอักษร
- เปิดทีละขั้น (เผยน้อย → เผยมาก)

### ผลต่อ rating (ตอกกลับเข้า FSRS)
- ไม่ใช้ hint + ถูก → **Good/Easy** ตามปกติ
- **ใช้ hint + ถูก → cap ที่ Hard** (ทั้งสองตระกูล — เพราะยังต้องออกแรงดึงคำ/สะกดเอง แค่มีคนชี้ทาง)
- ผิด → **Again** ตามจริง

> ตระกูล A เก็บใน **`related_words`** (ที่มา: SWOW + WordNet ดู §5) ซึ่ง **ใช้ร่วมกับเกม Word Association + ตัวลวงของ Odd One Out** — data ชิ้นเดียว 3 ประโยชน์ · ตระกูล B (สะกด) generate runtime จาก headword ได้ ไม่ต้อง pre-store · `answer_checker` รับ flag "ใช้ hint" มา cap rating

---

## 9. New-word Flow & Grammar

### 9.1 คำใหม่ = flashcard พบครั้งแรก (แก้ไข 2026-07-23 — ตัดการ์ด intro แยกทิ้ง)
- ~~เดิม: การ์ด intro แยกหน้า มีปุ่ม "ต่อไป"~~ **ตัดออก** — คำใหม่เข้า **เกม flashcard ตรง ๆ**: หน้าการ์ด = headword + ปุ่ม TTS (อ่านออกเสียงอัตโนมัติครั้งแรก), **แตะการ์ด** → พลิกโชว์ข้อมูลครบ (คำอ่านไทยเน้นพยางค์, ความหมาย core sense, ประโยคตัวอย่าง, แตะเปิด word detail เต็ม) — ไม่มีปุ่ม "เผยคำตอบ" แล้ว ปัดได้ตั้งแต่แรก
- ปัด **ขวา = รู้จัก / ซ้าย = ไม่รู้จัก (Again)** — พบครั้งแรกแล้วรู้จักเลย = **Easy** (บูสต์คะแนน), รอบถัด ๆ ไป = Good · ไม่มีปุ่ม Hard/Easy ในทุกโหมด
- การปัดครั้งแรก = review แรกของคำเข้า FSRS ทันที (นับ new_introduced ของวันด้วย) — ไม่มีขั้น "ดูเฉย ๆ" แยกจากการตอบอีกต่อไป

### 9.2 Grammar note (ติดประโยค/คำตอบที่ใช้รูปผัน)
เมื่อประโยคหรือคำตอบใช้รูปผัน แสดงโน้ตแบบ **อธิบายเหตุผล ไม่ใช่แค่ป้ายชื่อ**:

> ❌ "Past tense เลยเป็น V2"
> ✅ "ประโยคนี้พูดถึงเหตุการณ์ในอดีต จึงใช้ Past Simple ที่มีโครงสร้าง S + V2 ซึ่ง V2 ของ *go* คือ *went* (เป็นกริยาผิดปกติ ไม่เติม -ed)"

irregular forms ถูก flag และมีโน้ตเน้นเป็นพิเศษ

---

## 9b. การแสดงผลคำแปล (Dictionary Entry)

แสดงแบบ dictionary: `headword (คำอ่านไทย) N. ... V. ...` แบ่งเป็น **2 ชั้นตามจังหวะใช้งาน**

### ชั้นที่ 1 — ในเกม หลังเฉลย (ย่อ)
- headword + คำอ่านไทย (**พยางค์เน้นเสียงเป็นตัวหนา** เช่น **แอน**-เซอร์) + ปุ่มฟังเสียง TTS
- ป้าย CEFR + ป้าย POS (N. ระบุ นับได้/นับไม่ได้)
- ความหมายเฉพาะ **core sense ที่ทดสอบ** + ประโยคตัวอย่าง 1 ประโยค
- แตะการ์ดเพื่อเปิด entry เต็ม — ไม่บังคับ เพื่อไม่ถ่วงจังหวะ "ว่างนิดเล่นนิด"

### ชั้นที่ 2 — หน้า word detail (entry เต็ม)
- header เหมือนชั้น 1 (**ไม่แสดง IPA** — IPA ใช้ภายในเท่านั้น)
- sense ทุกตัวจัดกลุ่มตาม POS เรียง `sense_rank` แต่ละ sense มี: ป้าย CEFR, ความหมาย, collocation 1 วลี (EN = TH)
- sense ที่ `is_core` ติดดาว — บอกผู้ใช้ว่าเกมทดสอบความหมายไหน
- entry ของ V. โชว์รูปผัน inline (`answered · answered · answering`) — แตะเปิด grammar note เต็ม
- ประโยคตัวอย่างทั้ง 5 อยู่ล่าง entry

### แท็บค้นหาคำศัพท์ (เพิ่ม 2026-07-24)
- แท็บ "ค้นหา" ใน bottom nav (เล่น · ค้นหา · ความก้าวหน้า) — `dictionary_page.dart`
- ช่องค้นเดียว filter สด: ตรงกับ headword อังกฤษ / คำอ่านไทย / ความหมายไทยของทุก sense / รูปผัน (forms)
- ผลลัพธ์เป็นรายการ headword + ป้าย CEFR + คำอ่าน·ความหมาย core + ปุ่ม TTS; แตะ → เปิดหน้า word detail (ชั้นที่ 2) เต็ม
- โหลด bundle ทุกคำครั้งเดียวตอนเปิดแท็บ แล้ว filter ใน memory (หลักร้อยคำ — เร็วพอ ไม่ต้อง query ต่อคีย์กด)

### ตัดออก / backlog
- ~~IPA บนจอ~~ — ตัด (เก็บใน DB ใช้ภายใน)
- ~~ภาพจำ/keyword~~ — ตัดทั้งระบบ (การตัดสินใจ #7)
- "อย่าสับสนกับ" (confusables) — **น่าสนใจแต่ไม่ใช่ priority → backlog Phase 3+**

---

## 10. Motivation Layer (เบา)

- **Streak** — นับจาก "เคลียร์คำ due ครบในวันนั้น" (ไม่ใช่แค่เปิดแอป)
- **Heatmap ปฏิทิน** ความสม่ำเสมอ (ยืม pattern จาก Gymmer month_grid/calendar)
- **สถานะคำ** New → Learning → Young → Mature ให้เห็น progress จริง
- **"You Pass"** (เพิ่ม 2026-07-23, กติกาสุดท้าย) — นับเฉพาะ **4 เกมหลักที่ถูก/ผิดชัดเจน: Flashcard, Matching, Cloze, Dictation** (`kMasteryGames`) — ผ่านเมื่อทำได้ **1 รอบสมบูรณ์: ทุกคำตอบถูกครบทั้ง 4 เกมหลัก โดยไม่มีการตอบผิดในเกมหลักแทรกเลยแม้แต่ครั้งเดียว** — ตอบผิด (Again) ในเกมหลัก 1 ครั้ง**กับคำไหนก็ตาม = รีเซ็ตทั้งกระดาน เริ่มนับ 1 ใหม่** การนับมีไว้เพื่อจบรอบ clean รอบเดียวเท่านั้น (เช็คจาก `reviews_log` ผ่าน `domain/mastery.dart`) · **อีก 3 เกม (Odd One Out / Word Association / Scramble) ยังอยู่ใน loop ตามเดิมแต่นับแค่ streak** — ไม่เติมช่องกระดาน และผิดในเกมพวกนี้ไม่รีเซ็ตกระดาน · ขึ้นหน้าจอฉลองเต็มจอ "You Pass" **ครั้งเดียว** (setting `you_pass_shown`)
- **Loop ช่วยปิดรอบ + fade-out คำที่แน่น** (คู่กับกติกา reset) — แต่ละตาใน practice loop **เลือกคำที่ยังขาดช่องของเกมนั้นในรอบปัจจุบันก่อน** (ไม่เสิร์ฟช่องที่เก็บแล้วซ้ำ) และในบรรดาคำที่เข้าเกณฑ์ ใช้ weight = 1/(1+streak) โดย **streak นับต่อคำ** (ตั้งแต่ Again ล่าสุดของคำนั้นเอง — พลาดคำ A ไม่ทำให้คำ B ดูอ่อน) — หลังรีเซ็ตทั้งกระดาน คำที่เคยตอบถูกมาหลายรอบจึงโผล่น้อย เวลาส่วนใหญ่ไปลงกับคำที่พลาด/คำยาก ปิดรอบใหม่ได้เร็ว
- ⏸ XP / level / badge เต็มรูปแบบ = เก็บไว้เฟสหลัง

---

## 11. Phase Plan

### Phase 1 — Vertical slice (ครบ loop, พิสูจน์ก่อนขยาย)
- Dataset **~150 คำ band A1** (รัน pipeline เฉพาะ subset)
- ตาราง SQLite + migrations + store abstraction (sqlite + memory)
- **FSRS-5 engine** + sleep-gap + adaptive retention + new-card governor
- **Session engine** endless queue + game ladder + bidirectional + interleaving
- **3 เกม:** flashcard swipe, Cloze, Matching
- การ์ด intro (§9.1) + entry ย่อหลังเฉลย (§9b ชั้น 1)
- Device TTS + runtime image fetch/cache
- Motivation: streak + heatmap + สถานะคำ
- `answer_checker` typo-tolerant

**เกณฑ์ว่า Phase 1 สำเร็จ:** เรียนคำใหม่ → ระบบจัด due เช้าถัดไป → วันถัดมามีคำมาให้ทวนด้วยเกมที่เหมาะกับ maturity → streak เพิ่มเมื่อเคลียร์ครบ ทั้งหมดทำงาน offline (ยกเว้นโหลดรูป)

### Phase 2 — ครบเกม + grammar เต็ม
- อีก 4 เกม: Word Association, Word Scramble, Odd One Out, Dictation
- hint system เต็ม (§8b ทั้งสองตระกูล)
- grammar notes เต็มทุกรูปผัน + irregular highlighting
- focus topic, หน้า word detail เต็ม (§9b ชั้น 2)

### Phase 3 — สเกลเนื้อหา + UI polish
- รัน pipeline เต็ม 3000 คำ + QC
- ✅ **ขั้นแรกทำแล้ว (2026-07-23):** +50 คำ A2 +50 คำ B1 → รวม **253 คำ** (`tools/extend_a2b1.py` — Oxford CEFR list กรอง band ต่ำกว่าออก, จัดอันดับด้วยความถี่ SWOW, คำแปล Wiktionary จริงผ่าน wiktapi.dev, คำอ่าน/collocation/ประโยค gemini-3.6-flash ผ่าน QC ชุดเดิม, SWOW associations ครบทุกคำ)
- **UI pass:** แปลง design language จาก meeting-iq เป็น Flutter theme (§13) — ทำหลัง UX ทุกอย่างนิ่งแล้ว
- จูน FSRS/governor จาก log จริง
- backlog: confusables ("อย่าสับสนกับ")

---

## 12. คำถามที่ยังเปิด (minor — ตัดสินทีหลังได้)
- ชื่อแอป + โลโก้
- ต้องรองรับ Android/iPad ด้วยไหม หรือ iPhone อย่างเดียวก่อน
- ภายหลังอยากได้ multi-device sync (account) ไหม — เฟสแรกไม่มี
- Hybrid LLM ตอน runtime (roleplay/ประโยคเพิ่ม) — ปิดไว้ตอนนี้ เปิดได้เฟสหลัง

---

## 13. UI Design Reference

**ลำดับงาน: UX/logic ทั้งหมดเสร็จก่อน → ค่อยทำ UI** (Phase 3)

- Reference: template **meeting-iq** (shadcn.io) — Next.js + Tailwind + shadcn/ui
- **ใช้เป็น design language reference เท่านั้น** — โค้ด shadcn รันใน Flutter ไม่ได้ สิ่งที่เอามา:
  - โทนสี / palette (ผ่าน CSS variables ของ template — มี dark/light ครบ)
  - typography scale + spacing rhythm
  - สไตล์ component: การ์ดสะอาด, ขอบบาง, minimal
- ตอนลงมือ: ใช้ **Shadcn MCP** (เชื่อมไว้แล้ว) ดึง token สี/theme มาอ้างอิง แล้วเขียนเป็น Flutter `ThemeData` ใน `lib/theme/`
- ระหว่าง Phase 1–2 ใช้ UI เรียบง่ายไปก่อน (default Material + โครง layout ถูกต้อง) — ไม่ polish จนกว่า UX จะนิ่ง
