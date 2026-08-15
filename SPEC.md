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

## 4. Data Model (SQLite) — content schema v2

> **v2 (2026-08-13)** สร้างโดย `tools/build_content_db.py` → `data/content_v2.db` → export เป็น
> seed ของแอปด้วย `tools/export_app_seed.py` · ของเดิม (v1) รองรับ Flashcard ตัวจริงไม่ครบ
> จึงเปลี่ยนสามเรื่อง: **sense ผูกกับ POS จริง**, **forms แยก inflection กับ derived**,
> และ **ทุก explanation เป็นข้อมูลในตาราง ไม่ generate ตอนเล่น**

```sql
-- ตารางเนื้อหา (มาจาก seed, อ่านอย่างเดียว) --------------------------------

content_meta(key TEXT PK, value TEXT)
-- content_version (ใช้ตัดสินใจ reseed), built_at, word_count, licenses

words(
  id INTEGER PK,
  headword TEXT UNIQUE,
  cefr TEXT,                 -- band ของคำ (A1/A2/B1/B2)
  freq_rank INTEGER,         -- ลำดับ intro = อันดับความถี่ SWOW
  ipa TEXT,                  -- ใช้ภายใน ไม่แสดงบนการ์ด
  thai_reading TEXT,         -- "แอน-เซอร์" (แบ่งพยางค์ด้วย -)
  stress_index INTEGER,      -- พยางค์ที่เน้น เริ่มนับ 1
  is_test_only INTEGER,      -- 1 = ชุดทดสอบยาก 30 คำ ต้องไม่ติดไปกับแอปจริง
  source_word_id INTEGER     -- ย้อนกลับไป data/vocabulary_source.db ได้
)

-- หนึ่งคำมีหลาย POS · หนึ่ง POS มีหลายความหมาย · ทุกความหมายมี source
senses(
  id INTEGER PK,
  word_id INTEGER FK,
  pos TEXT,                  -- noun / verb / adj / adv / prep / det / name
  sense_rank INTEGER,        -- ลำดับภายใน POS นั้น
  is_core INTEGER,           -- 1 = ความหมายหลักที่เกมใช้ทดสอบ
  gloss_en TEXT,             -- gloss ต้นทางแบบตรงตัว (พิสูจน์ว่าไม่ได้แต่ง)
  meaning_th TEXT,           -- สั้นพอสำหรับหนึ่งบรรทัดบนการ์ด (validator คุมความยาว)
  meaning_source TEXT,       -- provenance ของคำแปล
  source_sense_id INTEGER UNIQUE,
  source_name TEXT,
  UNIQUE(word_id, pos, sense_rank)
)

-- inflection กับ derived family เป็นคนละเรื่องสำหรับผู้เรียน จึงมี form_type คุม
word_forms(
  id INTEGER PK,
  word_id INTEGER FK,
  sense_id INTEGER NULL FK,
  form_text TEXT,            -- "drank" / "drinker"
  form_type TEXT,            -- inflection | derived
  pos TEXT,
  relation TEXT,             -- "past participle" / "plural" / "derived"
  meaning_th TEXT NULL,      -- derived ต้องมีเสมอ (validator บังคับ) · inflection ไม่ต้องมี
  is_irregular INTEGER,
  source_name TEXT, source_license TEXT,
  UNIQUE(word_id, form_text, form_type, pos)
)

-- 5 ประโยค/คำ ทุกประโยคผูก sense และมีคำอธิบายของตัวเอง
example_sentences(
  id INTEGER PK,
  word_id INTEGER FK,
  sense_id INTEGER FK,       -- ประโยคนี้สอนความหมายไหน
  rank INTEGER,              -- 1..5 (1 = emotional)
  en_text TEXT, th_text TEXT,
  cloze_target TEXT, cloze_start INTEGER, cloze_end INTEGER,
  form_used TEXT,            -- รูปคำที่ปรากฏจริงในประโยค
  is_emotional INTEGER,
  explanation_th TEXT,       -- อ่านเดี่ยว ๆ ได้ ห้ามอ้างประโยคอื่น (validator บังคับ)
  explanation_source TEXT,
  UNIQUE(word_id, rank)
)

-- related ผูกกับ sense ไม่ใช่คำ: bank(ธนาคาร) กับ bank(ริมฝั่ง) ต้องไม่ปนกัน
related_words(
  id INTEGER PK,
  word_id INTEGER FK,
  sense_id INTEGER NULL FK,
  related_word_id INTEGER NULL FK, related_headword TEXT,
  relation_type TEXT,        -- association | opposite | used_for | part_of | produces | causes | kind_of | pays
  closeness REAL,            -- ความแรงจาก SWOW
  confidence REAL,
  explanation_th TEXT,       -- เหตุผลที่คู่นี้สัมพันธ์กัน (เขียนตอน build)
  is_giveaway INTEGER,
  source_name TEXT, source_license TEXT,
  UNIQUE(word_id, related_headword, relation_type)
)

-- Odd One Out อธิบายตัวเองจากกลุ่มที่ใช้สร้างรอบนั้นจริง
relation_groups(
  id INTEGER PK, hub_word_id INTEGER FK,
  category TEXT,             -- "อาหารและการกิน"
  explanation_th TEXT,       -- "คำกลุ่มนี้เกี่ยวกับอาหาร มื้ออาหาร และของที่ใช้กิน"
  source_name TEXT
)
relation_group_members(group_id INTEGER FK, word_id INTEGER FK, closeness REAL, PK(group_id, word_id))

topics(id INTEGER PK, name TEXT, cefr TEXT)      -- ยังว่าง รอ pipeline หมวด
word_topics(word_id INTEGER FK, topic_id INTEGER FK)

-- ตารางของผู้เล่น (สร้างโดย migration ทับลงบน seed) -------------------------
-- reseed ข้ามเวอร์ชันจะย้ายตารางกลุ่มนี้ตามมาเสมอ ดู §12b

srs_state(
  word_id INTEGER PK FK, state TEXT, stability REAL, difficulty REAL,
  due_at INTEGER, last_review INTEGER, reps INTEGER, lapses INTEGER, last_direction TEXT
)
reviews_log(
  id INTEGER PK, word_id INTEGER FK, ts INTEGER, rating TEXT,
  game_type TEXT, direction TEXT, elapsed_ms INTEGER
)
daily_stats(date TEXT PK, new_introduced INTEGER, reviews_done INTEGER, streak_kept INTEGER)
settings(key TEXT PK, value TEXT)   -- new_card_cap, focus_topic, request_retention, ...
```

**ที่หายไปจาก v1 และเหตุผล:** `senses.cefr/countable/collocation_*`, `word_forms.grammar_note_th`,
`example_sentences.form_id`, `words.translation_*` และ `words.image_*` — ไม่มีข้อมูลจริงรองรับ
จาก source จึงว่างเปล่าตลอด · ความรู้ที่มันควรสื่อย้ายไปอยู่ใน `explanation_th` ต่อประโยค
(ซึ่งอธิบายเหตุผลไวยากรณ์จริง) และ `word_forms.relation` · attribution ย้ายไป `content_meta.licenses`
กับ `*.source_license` เพราะ license เป็นของทั้งชุดข้อมูล ไม่ใช่ของแต่ละคำ

### 4b. Content-version migration

`vocab.db` ของผู้เล่นมีทั้งเนื้อหาและ progress อยู่ไฟล์เดียวกัน เดิมการอัปเดตเนื้อหาต้องลบไฟล์ทิ้ง
= ข้อมูลผู้เล่นหายหมด · v2 แก้ด้วย `lib/data/content_reseed.dart`:

1. เทียบ `content_meta.content_version` ของ seed ที่ bundle มากับของไฟล์ที่ติดตั้งอยู่
2. ถ้าใหม่กว่า → เริ่มจาก seed ใหม่ แล้วคัดลอกตารางของผู้เล่นเข้าไป
3. **map `word_id` ด้วย headword** เพราะ id ของเนื้อหาเปลี่ยนทุกครั้งที่ build แต่ headword ไม่เปลี่ยน
4. แถวที่ชี้ไปยังคำที่หายไปจากเนื้อหาใหม่จะถูกทิ้ง (ไม่มีอะไรให้ทบทวนแล้ว) และรายงานจำนวนออกมา

ครอบด้วยเทสใน `test/vocab_store_sqlite_test.dart`

## 5. Content Pipeline (build-time, ทำครั้งเดียว)

> **สถานะจริง (2026-08-13):** pipeline v2 รันแล้วบน subset 100 คำ + ชุดทดสอบ 30 คำ
> ทั้งชุดใช้เวลา ~14 วินาที (เดิม ~90 วินาที ก่อนทำ SWOW cache)
>
> ```bash
> python tools/select_pilot_100.py      # เลือกคำ (โควตา band + ต้องเกาะกลุ่มความหมาย)
> python tools/build_content_db.py      # ประกอบ data/content_v2.db
> python tools/validate_content_db.py   # 17 ด่าน ต้องได้ 0 problems
> python tools/export_app_seed.py       # → vocab_app/assets/seed/vocab.db
> ```
>
> `tools/swow_cache.py` เก็บข้อมูล SWOW ที่กรองแล้วไว้ใน `data/swow_cache.json`
> (สร้างครั้งเดียว) — ทั้ง selector และ builder ใช้ร่วมกัน จึงไม่ต้องอ่านไฟล์ 53 MB ซ้ำทุกครั้ง
> และไม่มีโค้ด parse SWOW ซ้ำสองที่อีก · รายละเอียดคำที่มีอยู่จริงดู `done_vocab.md`

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
3. **Matching** — โยงเส้นจับคู่ EN–TH · อย่างน้อย **4 คู่** เสมอ (สูงสุด 6) และอย่างน้อย 2 คู่เป็นคำอ่อนสุดของผู้เล่น (weight streak×difficulty) · ใช้เฉพาะ**คำที่เคยเจอแล้ว** — เคยเจอไม่ถึง 4 คำ = เปลี่ยนรอบเป็น flashcard (แก้ไข 2026-07-24) *[Phase 1]*
4. **Word Association** — โยงคำเข้ากับคำที่รู้แล้วในโครงข่ายความหมาย · คำตอบ+ตัวลวงดึงจาก**คำที่เคยเจอแล้วเท่านั้น** (แก้ไข 2026-07-24) · **หลังเฉลยต้องอธิบายว่าคำเป้ากับคำตอบสัมพันธ์กันอย่างไร** ไม่แสดงเพียงว่าถูก/ผิด เช่น `bird → egg: นกวางไข่` หรือ `doctor → hospital: เป็นสถานที่ทำงานที่พบได้บ่อย` โดยคำอธิบายต้องอิง relation/sense ที่ใช้สร้างโจทย์จริง *[Phase 2]*
5. **Word Scramble** — เรียงตัวอักษรที่สลับให้เป็นคำ → production + desirable difficulty *[Phase 2]*
6. **Odd One Out** — เลือกคำที่ไม่เข้าพวกจากกลุ่ม → semantic categorization *[Phase 2]* · เกณฑ์ความเหมือน (แก้ไข 2026-07-24 รอบ 2): คำนับเป็นพวกเดียวกันเมื่อเป็นข้อมูลหมวดชนิด typed (hypernym/category/part_of) หรือ closeness SWOW ≥ **0.036** (เริ่ม 0.03 ≈ p75 ของข้อมูล แล้วผู้ใช้ให้เพิ่มอีก 20%) · กลุ่มต้องมี **อย่างน้อย 3 คำ** + 1 คำแปลก (ตัด fallback 2 คำทิ้ง) หาไม่ได้ = ข้ามไป flashcard · **ช่วงเริ่มเล่นแอป** (คำที่มีประวัติ ≤8) เข้มพิเศษ: ต้องมีกลุ่มผ่านเกณฑ์ **มากกว่า 2 กลุ่ม** ไม่งั้นไม่ออกเกม Odd · กลุ่มไหนผ่านเกณฑ์ = ใช้ได้เลย **สุ่ม uniform จากทุกกลุ่มที่ผ่าน** (ไม่จัดอันดับเพิ่ม) · สมาชิกกลุ่มดึงจาก**คำที่ผู้เล่นเคยเจอแล้วเท่านั้น** · ตอบผิด: บันทึก Again ทั้ง**คำเป้า**และ**คำที่กดผิด** · ตัวเลือกหลังตรวจมี icon ✓/✗ ชัดเจน · **หลังเฉลยต้องบอกว่าคำในกลุ่มสัมพันธ์กันอย่างไร และเหตุใดคำเป้าจึงไม่เข้าพวก** โดยอิง hub/category/relation ที่ใช้สร้างรอบนั้นจริง ไม่ให้โมเดลเดาเหตุผลย้อนหลัง (อนุมัติ 2026-08-12)
7. **Dictation** — ฟังเสียง (TTS) แล้วพิมพ์สะกด → listening + spelling + production *[Phase 2]*

ทุกเกมส่งผล rating กลับเข้า FSRS ผ่าน `answer_checker`

> **การคำนวณทั้งระบบ** (การสุ่ม/ความสำคัญของคำ/การเลือกคำ ทุกเกม) รวมไว้ที่ **`ALGORITHM.md`** (เพิ่ม 2026-07-24)
> **Hint ladder เกมพิมพ์คำตอบ** (Dictation/Cloze/Scramble, แก้ไข 2026-07-24): จำนวนตัวอักษร → คำใกล้เคียงที่รู้แล้ว → ตัวอักษรหน้า → ความหมาย → ตัวอักษรหน้า+ท้าย แล้วหยุด (`buildHintLadder`)
> **UI chrome เป็นอังกฤษ** (ปุ่ม/ป้าย/nav) ส่วนคำแปล/คำอ่าน/grammar note คงเป็นไทย
> **แท็บค้นหา** แสดง 5 คำ closeness สูงสุด (SWOW) แตะไปหน้าคำนั้นได้

---

### คำอธิบายหลังตอบ (ทำจริง 2026-08-13)

ทุกคำอธิบายเป็น**ข้อมูลในตาราง เขียนตอน build** ไม่ generate สดหลังตอบ:

| เกม | แสดงอะไร | มาจากไหน |
|---|---|---|
| Cloze / เติมคำ | บริบทหมายถึงอะไร ทำไมใช้คำนี้ ทำไมใช้รูปนี้ + ถ้าผิดบอกว่าตอบอะไรไป | `example_sentences.explanation_th` (ต่อประโยค) + `word_forms.relation` |
| Word Association | คำที่ถูก + ชนิดความสัมพันธ์ + เหตุผล | `related_words.relation_type` / `.explanation_th` |
| Odd One Out | คำที่ไม่เข้าพวก + hub/หมวด + เหตุผลที่กลุ่มเชื่อมกัน + เหตุผลที่คำเป้าไม่เข้าพวก | `relation_groups.category` / `.explanation_th` ของกลุ่มที่ใช้สร้างรอบนั้นจริง |

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
- **รูปแบบด้านหลัง Flashcard (อนุมัติ 2026-08-12):** แสดงแต่ละ Part of Speech เป็น **หนึ่งบรรทัด** เช่น `n. ท่าม้ากระโดดและดีดขาหลัง, ท่ากระโดดโลดเต้น` และ `v. กระโดดโลดเต้น, บังคับม้าให้แสดงท่า capriole` — หาก POS เดียวมีหลายความหมาย ให้ใช้ comma คั่นในบรรทัดเดียวกัน ไม่แตกเป็น bullet หลายบรรทัด · ใต้แต่ละ POS แสดง example ของ POS นั้น 1 ประโยคพร้อมคำแปลไทย
- **ส่วนพับได้บน Flashcard:** `Word family & forms` และ `Related words` เป็น dropdown/accordion สองส่วน แยกกันและ **ปิดไว้เป็นค่าเริ่มต้น**; เมื่อกดจึงขยายรายการลงมา · family/form ที่เปลี่ยน POS หรือความหมายต้องระบุ POS + ความหมายไทยใหม่ ส่วนรูปผันที่ความหมายเดิมไม่ต้องแปลซ้ำ · Related word แต่ละคำแสดง POS และความหมายไทยสั้น ๆ
- **Final Flashcard design ที่ยืนยันแล้ว (2026-08-12):** ด้านหน้า = headword + TTS + คำอ่านไทย โดยยังไม่เฉลยความหมาย · ด้านหลัง = headword/TTS/คำอ่าน → บรรทัด POS+ความหมายตามกติกาด้านบน → example EN+TH หนึ่งชุดต่อ POS → dropdown `Word family & forms` → dropdown `Related words` → ทางลัดเปิด Dictionary entry เต็ม · ไม่แสดง symbol, IPA หรือ CEFR บน Flashcard และไม่ย่อฟอนต์เพื่อยัดข้อมูล; ถ้ายาวให้ scroll หรือเปิด Dictionary เต็ม

### 9.2 Grammar note (ติดประโยค/คำตอบที่ใช้รูปผัน)
เมื่อประโยคหรือคำตอบใช้รูปผัน แสดงโน้ตแบบ **อธิบายเหตุผล ไม่ใช่แค่ป้ายชื่อ**:

> ❌ "Past tense เลยเป็น V2"
> ✅ "ประโยคนี้พูดถึงเหตุการณ์ในอดีต จึงใช้ Past Simple ที่มีโครงสร้าง S + V2 ซึ่ง V2 ของ *go* คือ *went* (เป็นกริยาผิดปกติ ไม่เติม -ed)"

irregular forms ถูก flag และมีโน้ตเน้นเป็นพิเศษ

**Cloze/เกมเติมคำ — คำอธิบายต้องเป็นอิสระต่อประโยค (อนุมัติ 2026-08-12):**
- ประโยคตัวอย่างแต่ละประโยคของคำศัพท์เดียวกันต้องมี explanation ของตัวเอง โดยอธิบายจากบริบทและรูปไวยากรณ์ของ **ประโยคนั้นเท่านั้น**
- ห้ามใช้คำอธิบายรวมที่อ้างว่า “ประโยคก่อนหน้า”, “ประโยคที่ 2”, “จากตัวอย่างอื่น” หรือสมมติว่าผู้เล่นได้เห็นประโยคอื่นของคำนี้แล้ว เพราะแต่ละรอบอาจสุ่มออกมาเดี่ยว ๆ
- explanation ต้องอ่านรู้เรื่องได้โดยลำพัง: บอกว่าบริบทสื่ออะไร, เหตุใดช่องว่างจึงต้องใช้คำหรือรูปผันนั้น และถ้าจำเป็นให้บอกโครงสร้างไวยากรณ์สั้น ๆ
- ดังนั้นข้อมูลต้องผูก explanation กับ `example_sentence` แต่ละแถว ไม่เก็บ grammar note รวมหนึ่งย่อหน้าต่อคำหรือคัดลอก note เดียวใช้กับทั้ง 5 ประโยค

---

## 9b. การแสดงผลคำแปล (Dictionary Entry)

แสดงแบบ dictionary: `headword (คำอ่านไทย) N. ... V. ...` แบ่งเป็น **2 ชั้นตามจังหวะใช้งาน**

### ชั้นที่ 1 — ด้านหลังการ์ด / หลังเฉลยในเกม (`widgets/word_result_card.dart`)

ลำดับล็อกแล้ว (ทำจริง 2026-08-13):

1. headword + ปุ่ม TTS + คำอ่านไทย (**พยางค์เน้นเป็นตัวหนา**)
2. **หนึ่งบรรทัดต่อ POS** — `n. เงิน, เงินตรา` · หลายความหมายของ POS เดียวกันคั่นด้วย comma
3. ตัวอย่าง EN + TH **หนึ่งชุดต่อ POS** (เลือกประโยคที่ `sense_id` อยู่ใน POS นั้นจริง)
4. dropdown **Word family & forms** — แยก "รูปผันของคำ" กับ "คำในตระกูลเดียวกัน"
5. dropdown **Related words** — คำ + ชนิดความสัมพันธ์ + เหตุผล
6. ปุ่ม **เปิด Dictionary เต็ม**

dropdown ปิดไว้เป็นค่าเริ่มต้น · ถ้าเนื้อหายาวให้ scroll **ห้ามย่อฟอนต์เพื่อยัดข้อมูล** ·
ไม่แสดง IPA, symbol หรือ CEFR บนการ์ด

### ชั้นที่ 2 — Dictionary เต็ม (`screens/word_detail_page.dart`)

อ่าน dataset ชุดเดียวกับการ์ด ไม่สร้างข้อมูลคนละชุด แต่แสดงมากกว่า:

- ทุก POS · ทุก sense พร้อม `gloss_en` ต้นทาง (ให้เห็นว่าคำแปลไทยมาจากไหน) · sense หลักติดดาว
- ตัวอย่างของแต่ละ sense อยู่ใต้ sense นั้น พร้อม **คำอธิบายของประโยคนั้นเอง**
- Forms กับ Word family แยกหัวข้อ แต่ละแถวมี relation + POS + ที่มา
- Related words พร้อมชนิดความสัมพันธ์และเหตุผลที่บันทึกไว้
- ท้ายหน้า: source attribution ที่รวบรวมจากแถวที่แสดงจริง

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
- **หน้า Progress แสดง You Pass จริงแล้ว** (2026-08-13, `widgets/progress_mastery_view.dart`) — จำนวนช่องที่ผ่าน/ทั้งหมด, เปอร์เซ็นต์, แถบความคืบหน้า, **แยกรายเกม**, บอก**คำที่ยังขาดของแต่ละเกม** (ผู้เล่นจึงเข้าใจว่าทำไมเกมถัดไปถูกเลือก) และ**แจ้งเมื่อรอบสะอาดถูกรีเซ็ต** พร้อมเวลาและคำที่ตอบผิด — เดิมคำนวณไว้แต่ไม่มี UI การรีเซ็ตจึงดูเหมือน progress หายไปเฉย ๆ · มี `ProgressMasteryChip` สำหรับหน้า Play (ยังไม่ได้ wire)
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
