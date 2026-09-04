# Local Qwen output validation, server access และ final goal

เอกสารนี้เป็นคู่มือปฏิบัติงานสำหรับผล vocabulary ที่ Qwen สร้างบน VM 100:
ไฟล์อยู่ที่ไหน, ตรวจอะไรด้วยคำสั่งใด, เข้า server อย่างไร, เรียก LLM อย่างไร และ
จุดจบของงานคืออะไร

ข้อมูลเชิง corpus/review ให้ยึด
[`LOCAL_QWEN_VOCAB_WORKFLOW.md`](LOCAL_QWEN_VOCAB_WORKFLOW.md) เป็น authority.
ข้อมูลติดตั้ง VM/PVE/model/systemd ให้ยึด
[`../../../../VM TU/LOCAL_VOCAB_README.md`](../../../../VM%20TU/LOCAL_VOCAB_README.md).

## Handoff ล่าสุดสำหรับ LLM ผู้รีวิว (อ่านส่วนนี้ก่อน)

สถานะ Qwen บน VM ณ 2026-08-25: **หยุด Qwen validation/review ตามคำสั่งผู้ใช้แล้ว**
ไม่มี Qwen service ที่ต้อง monitor หรือ resume. ตรวจครั้งสุดท้ายได้
`vocab-qwen-server.service=inactive` และ `glimmer-server.service=active` จากนั้นปิด SSH
session แล้ว. ตั้งแต่ 2026-08-26 ผู้ใช้อนุญาตให้ AI สองตัวทำ final production review
จาก verified Qwen bundle ที่ดึงมาแล้ว และอนุญาต gated autorun หลังแต่ละ batch; ไม่ต้อง
start Qwen ใหม่

### Parallel assignment และจุดเริ่มงาน

ตั้งแต่ 2026-08-26 งาน semantic review แบ่งให้ทำพร้อมกันโดยไม่มี seq ทับกัน:

| เจ้าของช่วง | ช่วงที่รับผิดชอบ | จุดเริ่ม | จุดหยุด |
|---|---:|---|---|
| ChatGPT session ปัจจุบัน | `1976-2699` | `1976 historical` | `2699` เท่านั้น |
| AI reviewer ตัวใหม่ | `2700-2967` | `2700` | `2967 zone` |

ChatGPT ปิด production batchถึง `2351-2375` แล้ว; batch ถัดไปของช่วงนี้เริ่ม `2376`.
Progress ล่าสุด `reviewed=2435/2967 errors=1`; error เดิมเป็น overlay ช่วงเก่าที่ไม่มี
report คู่กัน. External AI ยังเริ่ม `2700` เหมือนเดิม

รูปแบบทำงานใน session นี้: ตัวหลักทำ semantic review, สร้าง decision และ deterministic
preflight; Luna low-token sub-agent เป็น executor เท่านั้นสำหรับเขียน production
report/overlay และรัน progress + gated autorun. Luna ห้ามแก้หรือ review decision เอง

`seq 2700` เป็นของ AI reviewer ตัวใหม่เท่านั้น; ChatGPT session ปัจจุบันห้ามตรวจหรือ
เขียนผลของ `2700`. AI ตัวใหม่ห้ามย้อนมาตรวจ `2699` หรือต่ำกว่า. verified Qwen bundle
มีผลถึง `2967`; staging review DB มี candidate ถึง `2325` เท่านั้น จึงต้องอ่าน
`output/accepted` จาก verified bundle สำหรับช่วงที่สูงกว่านั้น

ผู้ใช้อนุญาตแล้วให้ผล review/repair รอบนี้เข้าสู่ production pipeline หลังผ่าน validator.
กติกาป้องกันงานชนกัน:

1. แต่ละ reviewer เขียนเฉพาะ production report/overlay ของ seq ที่ตนถือ ห้ามแก้ไฟล์ของอีกฝ่าย
2. ใช้ batch ต่อเนื่อง 15 คำตาม `CONTINUE_VOCAB_PROMPT.md`; ชื่อไฟล์ต้องตรงช่วงจริง
3. ถ้าอนุมัติ Qwen candidate ให้ใช้ใน production ให้ report เป็น `repaired` และเขียน
   complete five-row overlay; ถ้ามีบาง rank ผิดให้ซ่อมเฉพาะแถวนั้นและคัดลอกแถวที่ผ่าน
   จาก candidate แบบคำต่อคำลง overlay ให้ครบห้าแถว
4. ถ้า Qwen candidate หรือ quarantine ใช้ไม่ได้ ให้กลับไปตรวจ canonical block ตาม evidence;
   canonical ผ่านให้ report `pass`, ไม่ผ่านให้สร้าง repaired overlay ที่ปลอดภัย
5. ห้ามแก้ canonical drafts, manifest, evidence DB, staging SQLite หรือ report/overlay
   นอกช่วงที่ได้รับมอบหมาย
6. รัน `sol_review_progress.py` หลังทุก batch. หลัง ChatGPT ปิด batch `2351-2375`
   สถานะคือ `reviewed=2435/2967 errors=1`; error ที่เหลือเป็น overlay ช่วงเก่าซึ่งยัง
   ไม่มี report คู่กัน. batch ใหม่ต้องไม่เพิ่ม error และห้ามแก้ช่วงนอก assignment
7. หลัง progress ให้เรียก `python tools/run_production_after_review.py`. คำสั่งนี้ no-op
   จนกว่าจะได้ `reviewed=2967/2967 errors=0`; เมื่อครบแล้วจะ lock, recheck, แปล, build,
   validate, export และ promote production อัตโนมัติเพียงหนึ่ง run

ดังนั้น AI ตัวถัดไปให้ทำตามลำดับนี้:

```text
ChatGPT ปัจจุบัน: production review/repair seq 1976-2699; ห้ามแตะ 2700+
AI ตัวใหม่: production review/repair seq 2700-2967; ห้ามแตะ 2699 หรือต่ำกว่า
ข้อยกเว้นฝั่ง AI ตัวใหม่: seq 2853 (self) อยู่ output/quarantine และไม่มี sentence rows
หลังแต่ละ batch: รัน progress และ gated autorun; เมื่อจบ assignment ให้หยุดและรายงานไฟล์
```

คำสั่งงานฉบับสั้นสำหรับส่งให้ AI ตัวอื่น:

```text
อ่าน LOCAL_QWEN_VALIDATION_AND_SERVER.md และ LOCAL_QWEN_VOCAB_WORKFLOW.md.
คุณเป็น external AI production reviewer และถือสิทธิ์เฉพาะ seq 2700-2967. ห้ามออกผล
หรือเขียนไฟล์ของ seq 2699 หรือต่ำกว่า เพราะ ChatGPT อีก session กำลังทำช่วงนั้น.
อ่าน candidate จาก verified bundle output/accepted และเทียบทุก rank กับ
input/evidence.jsonl ของ seq เดียวกัน. seq 2853 (self) เป็น quarantine ที่ไม่มี
sentence rows ให้กลับไปตรวจ canonical block ตาม evidence และห้ามสร้างผลโดยเดา.
ทำ batch ละ 15 คำตาม CONTINUE_VOCAB_PROMPT.md. ถ้าใช้ Qwen candidate ให้เขียน
sol_review report เป็น repaired และเขียน complete five-row overlay; ถ้าบาง rank ผิด
ให้ซ่อมเฉพาะ rank นั้นและคัดลอก rank ที่ผ่านแบบคำต่อคำ. ห้ามแก้ canonical, manifest,
evidence DB, staging SQLite, ช่วงของ reviewer อื่น หรือ start Qwen. หลังทุก batch รัน
`$env:ESH_SOURCE_DB="$PWD/data/vocabulary_evidence.db"`,
`python tools/sol_review_progress.py` และ `python tools/run_production_after_review.py`.
คำสั่งหลังต้อง no-op จน review ครบและ errors=0. หยุดเมื่อจบ 2967 แล้วรายงานไฟล์ที่สร้าง.
```

นี่เป็น cursor ของ **staging Qwen/ChatGPT experiment** ไม่ใช่ cursor ของ production
Sol review. อย่านำตัวเลข `2309/2325` ไปแทน progress `reviewed/2967` ของ production
corpus

### ไฟล์ที่ AI ตัวถัดไปต้องอ่าน

อ่านตามลำดับนี้:

1. `LOCAL_QWEN_VALIDATION_AND_SERVER.md` — handoff, cursor, status และข้อห้าม
2. `LOCAL_QWEN_VOCAB_WORKFLOW.md` — authority ของเกณฑ์ corpus/review
3. `CONTINUE_VOCAB_PROMPT.md` — รูปแบบ audit/report/repair ถ้าผู้ใช้อนุญาตให้เขียนผล
4. `staging/semantic_reviews/20260825-qwen-chatgpt-review.sqlite` — candidate และ
   review state ช่วง `2151-2325`; เปิดแบบ read-only
5. `staging/local_qwen_runs/20260825-064000-qwen3-30b-q4-2151-2325-7eaa3afd317c/input/evidence.jsonl`
   — evidence และ `safe_profile` ที่ใช้ตัดสิน
6. `staging/local_qwen_runs/20260825-064000-qwen3-30b-q4-2151-2325-7eaa3afd317c/output/accepted/*.json`
   — candidate ช่วงต่อไปจนถึง `2967`
7. `staging/local_qwen_runs/20260825-064000-qwen3-30b-q4-2151-2325-7eaa3afd317c/output/quarantine/*.json`
   — quarantine เดิม; ห้ามนับเป็น accepted

verified bundle มี selected outputs 992 คำ (`accepted=989`, `quarantine=3`) ไม่ใช่
candidate ครบทั้ง corpus 2,967 คำ. อย่างไรก็ตาม ช่วง continuation `2326-2967` มี seq
ต่อเนื่องครบ 642 คำ: accepted 641 คำมี 3,205 sentence rows และ `2853 self` เป็น
quarantine เพียงคำเดียวในช่วงนี้โดยไม่มี sentence rows

source run เดิมคือ:

```text
20260821-144804-qwen3-30b-q4-1626-2967-7eaa3afd317c
```

verified handoff snapshot ที่รวม original run และ semantic/repair iterations คือ:

```text
C:\Users\pimde\Desktop\pimdej\English\staging\local_qwen_runs\
  20260825-064000-qwen3-30b-q4-2151-2325-7eaa3afd317c\
```

snapshot นี้ผ่าน transport SHA, safe extraction และ pipeline verifier แล้ว:

```text
accepted=989, quarantine=3, errors=[], ok=true, status=completed
```

ผล review เฉพาะงานช่วง seq 2151-2325 ถูกรวมไว้ใน staging SQLite:

```text
C:\Users\pimde\Desktop\pimdej\English\staging\semantic_reviews\
  20260825-qwen-chatgpt-review.sqlite
```

SHA-256 ของฐานนี้:

```text
ec4ffd092c7fa3a08a46a2dd08c1a83ca963e28cbc650de2d6a22c801aac8784
```

ไฟล์ประกอบ:

- `20260825-qwen-chatgpt-review.sqlite.sha256` — checksum sidecar
- `20260825-qwen-chatgpt-review.summary.json` — machine-readable summary
- `staging/semantic_reviews/*.json` — ChatGPT audits, blind selections และ repair prompts
- `tools/build_semantic_review_snapshot.py` — สร้าง staging DB ซ้ำแบบตรวจสอบได้

ฐาน staging นี้มี:

| รายการ | จำนวน |
|---|---:|
| words | 175 |
| sentences | 875 |
| Qwen candidate versions ที่เก็บ provenance ไว้ | 386 |
| review artifacts | 26 |
| `reviewed_pass` | 108 คำ |
| `reviewed_with_failures` | 18 คำ |
| `reviewed_quarantine` | 5 คำ |
| `pending_post_repair_review` | 28 คำ |
| `pending_chatgpt_review` | 16 คำ |

`reviewed_pass` เป็นผลใน staging snapshot เท่านั้น ไม่ได้แปลว่า merge เข้า canonical หรือ
production แล้ว. ฐาน `data/vocabulary_evidence.db`, canonical drafts, production DB และ
Sol review reports/overlays ไม่ได้ถูกแก้ในขั้นตอนสร้าง snapshot นี้

### ความหมายของสถานะ review

| `review_state` | ความหมาย |
|---|---|
| `reviewed_pass` | ChatGPT ตรวจ candidate ฉบับปัจจุบันแล้วและไม่เหลือ failed sentence |
| `reviewed_with_failures` | ตรวจฉบับปัจจุบันแล้ว แต่ยังมี sentence ที่ผิดอย่างน้อยหนึ่งแถว |
| `reviewed_quarantine` | ตรวจแล้วและเห็นชอบให้แยกคำนี้ออกเพราะ safe sense ใช้จริงไม่ได้ |
| `pending_post_repair_review` | ChatGPT เคยตรวจคำนี้ แต่ Qwen ซ่อม candidate ภายหลังและยังไม่ได้ตรวจฉบับล่าสุดซ้ำ |
| `pending_chatgpt_review` | candidate ฉบับนี้ยังไม่เคยได้รับ ChatGPT semantic review |

อย่าใช้ `seen_by_chatgpt=1` แทนการสรุปว่าฉบับล่าสุดผ่าน ต้องตรวจ
`final_candidate_reviewed=1` และ `review_state` ด้วย

### คิวที่แยกไว้ให้ผู้รีวิวคนถัดไป

ยังไม่เคยให้ ChatGPT ตรวจ 16 คำ (`seq 2310-2325`):

```text
2310 till, 2311 tin, 2312 tiny, 2313 toe, 2314 tongue, 2315 total,
2316 totally, 2317 trade, 2318 translate, 2319 translation, 2320 treat,
2321 treatment, 2322 trend, 2323 trick, 2324 truth, 2325 tube
```

เคยตรวจคำเดิม แต่ candidate ฉบับซ่อมล่าสุดยังไม่ได้ ChatGPT re-audit 28 คำ:

```text
2152 producer, 2153 production, 2154 profession, 2157 proper, 2159 property,
2162 prove, 2163 punish, 2164 punishment, 2165 qualification, 2167 qualify,
2169 quit, 2173 range, 2174 rare, 2175 rarely, 2176 reaction, 2177 reality,
2178 receipt, 2180 reference, 2182 regularly, 2187 relative, 2188 relaxed,
2189 relaxing, 2191 reliable, 2198 repeated, 2199 represent, 2234 sex,
2249 similarly, 2250 simply
```

คำที่ตรวจแล้วแต่ยังมี failed sentence 18 คำ:

```text
2201 reservation, 2202 resource, 2203 respect, 2206 retire, 2207 retired,
2210 robot, 2211 roll, 2216 royal, 2217 rugby, 2218 safety, 2224 script,
2269 standard, 2285 summary, 2292 symptom, 2302 theirs, 2303 theme,
2305 therefore, 2306 though
```

quarantine ที่ ChatGPT ตรวจและยืนยันแล้ว 5 คำ:

```text
2239 shift, 2253 slightly, 2270 statistic, 2288 surely, 2300 tend
```

### Schema และ query สำหรับตรวจแบบ read-only

ตารางหลัก:

- `words` — candidate ปัจจุบัน, Qwen state และ ChatGPT review state ต่อคำ
- `sentences` — ห้าแถวต่อคำ พร้อม `pass`, `fail`, `pending_*` หรือ
  `excluded_quarantine`
- `candidate_versions` — original และ semantic/repair ทุกเวอร์ชัน พร้อม source path,
  SHA และ `selected_as_current`
- `review_artifacts` — audit JSON ทุกไฟล์พร้อม SHA และ payload เดิม
- `review_batches` — สรุป calibration และ blind test 01-05
- `snapshot_meta` — run/snapshot identity และข้อยืนยันว่าไม่ได้แก้ canonical DB

views ที่เตรียมไว้:

- `pending_chatgpt_words` — 16 คำที่ยังไม่เคยตรวจ
- `pending_final_candidate_review` — รวม 16 คำที่ยังไม่เคยตรวจกับ 28 คำที่ต้อง re-audit
- `reviewed_words` — เคยผ่านตา ChatGPT; **ไม่ได้รับรองว่าฉบับล่าสุดผ่าน**
- `release_ready_words` — 108 คำที่ฉบับปัจจุบัน accepted และ ChatGPT ตรวจผ่านใน snapshot

ตัวอย่าง SQL สำหรับผู้รีวิว:

```sql
SELECT seq, headword, candidate_source
FROM pending_chatgpt_words
ORDER BY seq;

SELECT seq, headword, review_state, candidate_source
FROM pending_final_candidate_review
ORDER BY seq;

SELECT s.seq, w.headword, s.rank, s.sentence,
       s.review_state, s.failure_codes_json, s.review_reason
FROM sentences AS s
JOIN words AS w USING (seq)
WHERE w.review_state IN ('pending_chatgpt_review',
                         'pending_post_repair_review')
ORDER BY s.seq, s.rank;

SELECT seq, qwen_state, source, source_path, sha256, selected_as_current
FROM candidate_versions
WHERE seq = 2250
ORDER BY id;
```

ตรวจฐานและ checksum ก่อนเริ่ม review:

```powershell
$db = "staging/semantic_reviews/20260825-qwen-chatgpt-review.sqlite"
python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute('PRAGMA integrity_check').fetchone()); print(c.execute('PRAGMA foreign_key_check').fetchall())" $db
Get-FileHash $db -Algorithm SHA256
```

ค่าที่ต้องได้คือ `integrity_check=ok`, `foreign_key_check=[]` และ SHA ตรงกับค่าด้านบน

### ขอบเขตงานของ LLM ผู้รีวิวคนถัดไป

งานรอบนี้ผู้ใช้อนุญาต production review/repair แล้ว. ให้เทียบ Qwen candidate กับ evidence
และ canonical จาก manifest ก่อนเขียน `data/sol_review_reports/` กับ
`data/sol_review_drafts/` ตาม contract ใน `CONTINUE_VOCAB_PROMPT.md`. Qwen accepted
ไม่ใช่เหตุผลเพียงพอที่จะ pass; candidate ที่เลือกใช้แทน canonical ต้องเป็น `repaired` พร้อม
complete overlay. ห้ามแก้ canonical, manifest, evidence DB หรือ staging SQLite

ChatGPT session ปัจจุบันเริ่ม production review ใหม่ที่ `1976` และตรวจต่อถึง `2699`
เท่านั้น โดยอาจใช้ staging audits ช่วง `2151-2400` เป็นหลักฐานประกอบแต่ต้องเขียนผลตาม
production contract. External AI เริ่มที่ `2700` และตรวจถึง `2967`.
เมื่อทั้งสองฝ่ายจบจึงค่อยกลับมาตรวจ `pending_post_repair_review` 28 คำ. เกณฑ์ทดลองของรอบนี้
คือ sentence passอย่างน้อย 90% และไม่มี severe/systemic cluster; เกณฑ์ production canary
92.5% ด้านล่างยังคงเข้มกว่าและ final corpus ต้อง review ทุกคำ

## สถานะ original full run (ข้อมูลพื้นฐาน)

Original run:

```text
20260821-144804-qwen3-30b-q4-1626-2967-7eaa3afd317c
```

ผล original ถูกดึงจาก VM, ตรวจ SHA-256 และแตกไฟล์แล้วที่:

```text
C:\Users\pimde\Desktop\pimdej\English\staging\local_qwen_runs\
  20260821-144804-qwen3-30b-q4-1626-2967-7eaa3afd317c\
```

สถานะที่ verifier ยืนยันเมื่อ 2026-08-25:

- total 992 คำ
- automatic accepted 989 คำ
- quarantine 3 คำ: `nut`, `reliable`, `self`
- breaker ไม่มี
- throughput 3.486 accepted words/minute
- Windows deterministic verifier: `ok=true`, `errors=[]`

คำว่า **automatic accepted** หมายถึงผ่าน schema/source/rule-based validator เท่านั้น
ยังไม่ใช่ผลที่ Codex/Sol อนุมัติเพื่อ merge. Full run นี้ตั้ง `critic_pass=false` จึงไม่มี
Qwen critic รอบที่สอง แม้ worker รองรับ critic สำหรับ run ใหม่ก็ตาม

## เป้าหมายสุดท้าย

ลำดับที่ต้องการคือ:

```text
Qwen candidate
  -> deterministic verification
  -> Codex/Sol semantic + grammar + naturalness review
  -> human review report + complete repair overlay
  -> re-validate corpus ทั้ง 2,967 คำด้วย errors=0
  -> แปลไทยด้วย Azure; ใช้ DeepL ซ่อม failure
  -> audit คำแปลและบริบท
  -> build final JSON/SQLite
  -> export production seed ให้ Flutter
```

ห้ามนำ `output/accepted/` ไปทับ canonical หรือ production database โดยตรง

## ไฟล์สำคัญอยู่ตรงไหน

| ตำแหน่ง | ใช้ทำอะไร |
|---|---|
| `data/vocabulary_evidence.db` | source evidence แบบ read-only: sense, POS, form, example |
| `data/sol_review_manifest.txt` | authority ของ seq/headword สำหรับ audit/repair |
| `data/terra_english_drafts/` | canonical English drafts; ห้ามแก้ตรง ๆ |
| `data/sol_review_reports/` | ผลตัดสินของ Codex/Sol ต่อคำ |
| `data/sol_review_drafts/` | complete five-row repair overlays |
| `tools/local_vocab_pipeline/` | builder, worker, deterministic validator และ verifier |
| `staging/local_qwen_outgoing/` | immutable input bundles ที่สร้างบน Windows |
| `staging/local_qwen_runs/<run_id>/` | verified result bundles ที่ดึงกลับจาก VM |

ภายใน run ที่ดึงกลับ:

| ตำแหน่ง | ใช้ทำอะไร |
|---|---|
| `input/evidence.jsonl` | evidence และ `safe_profile.gloss` ที่ Qwen ได้เห็น |
| `input/assignment.tsv` | seq/headword ของ run |
| `input/canonical_blocks.txt` | canonical rows ตอนสร้าง bundle |
| `output/accepted/*.json` | candidate ที่ผ่าน automatic gate |
| `output/quarantine/*.json` | candidate ที่ retry แล้วยังผิด; ต้องตรวจทุกคำ |
| `output/accepted_six_field.txt` | accepted candidates ในรูปแบบ six-field อ่านต่อเนื่อง |
| `output/review_report.tsv` | machine run status; **ไม่ใช่** final Sol review report |
| `logs/events.jsonl` | attempts, retries, validator/critic events |
| `state/run.sqlite` | checkpoint และสถานะต่อคำ |
| `summary.json` | counts, throughput, hashes, runtime และ breaker |

## Validation ที่ต้องทำ

รันคำสั่งจาก:

```powershell
cd C:\Users\pimde\Desktop\pimdej\English
```

### 1. ตรวจ source library

```powershell
python tools/build_vocab_library.py validate
```

ต้องได้ `words=2967`, `words_without_cefr=0` และ source counts ครบโดยไม่มี exception

### 2. ตรวจ bundle และ candidate แบบ deterministic

```powershell
$run = "staging/local_qwen_runs/20260821-144804-qwen3-30b-q4-1626-2967-7eaa3afd317c"
python -m tools.local_vocab_pipeline verify $run
```

ต้องได้ `ok=true`, `status=completed`, `errors=[]` และ counts ตรงกับไฟล์จริง
คำสั่งนี้ตรวจ manifest/hash, JSON/schema, sense ID, POS, target form, rank, uniqueness,
canonical lock และจำนวน accepted/quarantine แต่ตัดสินความเป็นธรรมชาติทั้งหมดไม่ได้

### 3. ตรวจ semantic ทุก candidate

สำหรับแต่ละคำ ให้เทียบทุก rank กับ record ของคำเดียวกันใน `input/evidence.jsonl`:

- sentence ใช้ความหมายเดียวกับ `safe_profile.gloss`
- `sense_id` และ `pos` มีอยู่จริงใน evidence
- `target` ปรากฏเป็นคำเต็มและทำหน้าที่เป็น POS ที่ประกาศ
- grammar, article, number, tense, preposition และ collocation เป็นธรรมชาติ
- ประโยคสั้น ชัด เหมาะกับผู้เรียน และไม่มีข้อเท็จจริงที่แต่งขึ้น
- rank 1 memorable ได้โดยไม่บิดความหมาย
- rank 2 เมื่อลบ target แล้วบริบทยังบอกคำตอบได้ชัด
- ห้าประโยคไม่ซ้ำบริบทหรือเป็น template
- rare, archaic, technical, restricted หรือคนละ sense ต้องไม่หลุดมา

เกณฑ์ production ที่ใช้กับ canary คือ sentence-level semantic + naturalness pass
อย่างน้อย 92.5%, ไม่มี severe/systemic error cluster และ automatic gate ต้องผ่าน
แต่ final corpus ยังต้อง review ทุกคำ ไม่ใช้ sampling แทน final review

### 4. บันทึกผล review ให้ถูกที่

รูปแบบและกฎเต็มอยู่ใน [`legacy/REVOCAB_PILOT_2026-08.md` §8](../../legacy/REVOCAB_PILOT_2026-08.md).

- candidate ที่ไม่ควรแทน canonical: review/ซ่อมจาก canonical ตามปกติ
- candidate ที่อนุมัติให้นำมาใช้: บันทึกคำนั้นเป็น `repaired` และเขียน block ครบห้าแถว
  ลง `data/sol_review_drafts/sol_repair_<start>_<end>.txt`
- คำที่แก้บาง rank ก็ต้องเขียน overlay ครบห้าแถว โดยคัดลอก rank ที่ผ่านแบบคำต่อคำ
- ทุกคำใน batch ต้องมีบรรทัดใน
  `data/sol_review_reports/sol_review_<start>_<end>.tsv`
- ห้ามแก้ `data/terra_english_drafts/`, manifest หรือ evidence DB

ตรวจ progress หลังทุก batch:

```powershell
$env:ESH_SOURCE_DB = "$PWD/data/vocabulary_evidence.db"
python tools/sol_review_progress.py
```

ก่อน merge ต้องได้ `reviewed=2967/2967` และ `errors=0`. หลัง batch `1976-2000`
ตัวตรวจรายงาน `reviewed=2025/2967 errors=1`; รายละเอียด error ต้องอ่านจาก output ของ
`sol_review_progress.py` และแก้เฉพาะช่วงที่ได้รับมอบหมาย

### 5. ตรวจหลัง review และเตรียม production

หลังแต่ละ batch เรียกคำสั่งเดียวนี้ได้ทันที:

```powershell
python tools/run_production_after_review.py
```

ถ้ายังไม่ครบหรือมี error จะได้ `gate=not_ready action=noop production_unchanged=true`.
เมื่อครบ `2967/2967 errors=0` คำสั่งจะทำทั้งหมดภายใต้ production lock:

1. validate source library
2. สร้าง immutable English snapshot จาก canonical + complete overlays โดยไม่แก้ canonical
3. dry-run ตรวจ English ทั้ง corpus
4. แปลผ่าน Azure และ fallback DeepL โดยใช้ translation cache
5. build และ validate staged content DB
6. export staged Flutter seed
7. promote `data/content_v2.db` และ `vocab_app/assets/seed/vocab.db` หลังทุก gate ผ่าน

log, checksum และ artifact ของแต่ละ run อยู่ใน `staging/production_pipeline/<run_id>/`.
ถ้า command ใด fail จะไม่ promote production files

## อะไรใช้ช่วยงานได้บ้าง

- Qwen3-30B-A3B Q4: generate candidate และใช้เป็น prompt-based pre-reviewer ได้
- deterministic Python validator: blocking gate สำหรับ structure/source/rules
- Codex/Sol: final semantic, grammar และ naturalness authority
- `vocabulary_evidence.db`: หลักฐานตัดสิน sense/POS/form; ห้ามเดาแทน source
- Azure Translator: ตัวแปลไทยหลักหลัง English ผ่านแล้ว
- DeepL: ซ่อม translation failure; ไม่ใช่ authority ของ English sense
- `translation_cache.db`: cache งานแปลเพื่อลดการใช้ quota ซ้ำ

Qwen critic เหมาะกับการคัดกรองและ repair ก่อน final review แต่ห้ามนับว่าแทน Codex/Sol
เพราะ generator และ critic เป็นโมเดลเดียวกันและอาจมี blind spot ร่วมกัน

## เข้า server อย่างไร

จาก Windows PowerShell:

```powershell
Set-Location "C:\Users\pimde\Desktop\pimdej\VM TU"
.\VM_SSH.cmd
```

ถ้าใช้ Command Prompt ให้ใช้ `cd /d "C:\Users\pimde\Desktop\pimdej\VM TU"`
แล้วรัน `VM_SSH.cmd`

ถ้าติดตั้ง alias แล้ว ใช้ `vm-ssh` ได้เหมือนกัน. คำสั่งนี้เลือกสาย Management ก่อน
ถ้าไม่ถึงจะใช้ Tailscale เข้า Proxmox แล้ว hop เข้า VM 100 ให้อัตโนมัติ

`PVE_SSH.cmd` หรือ `pve-ssh` เข้า **Proxmox host**, ส่วน `VM_SSH.cmd` หรือ `vm-ssh`
เข้า **Ubuntu VM 100**; อย่าสับสนกัน

ถ้า VM ปิดอยู่:

```text
pve-ssh
qm status 100
qm start 100
```

รอ VM boot แล้วออกจาก PVE shell จากนั้นใช้ `vm-ssh` อีกครั้ง. Credentials ถูกอ่านจาก
DPAPI credential ที่ setup ไว้; ห้ามคัดลอกรหัสผ่านหรือ key ลงเอกสาร/โปรเจกต์

## เปิดและเรียก local Qwen LLM

Qwen API bind เฉพาะ `127.0.0.1:8082` ภายใน VM เพื่อไม่เปิด model สู่ network.
เข้า VM ด้วย `vm-ssh` ก่อน แล้วสลับ GPU จาก Glimmer ไป Qwen:

```bash
sudo /opt/vocab-pipeline/bin/vocab-model-switch.sh qwen
/opt/vocab-pipeline/bin/vocab-wait-api.sh
curl -fsS http://127.0.0.1:8082/health
```

เรียก OpenAI-compatible chat completion:

```bash
curl -fsS http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-30B-A3B-Instruct-2507-Q4_K_M",
    "messages": [
      {"role": "system", "content": "You are a careful English vocabulary reviewer."},
      {"role": "user", "content": "Check whether: She made a decision after reviewing the evidence. is natural English."}
    ],
    "temperature": 0.2,
    "max_tokens": 300
  }'
```

ดู service/resource เมื่อมีปัญหา:

```bash
systemctl --no-pager --full status vocab-qwen-server.service
journalctl -u vocab-qwen-server.service -n 100 --no-pager
nvidia-smi
free -h
```

เมื่อใช้งาน Qwen เสร็จให้คืน GPU ให้ Glimmer:

```bash
sudo /opt/vocab-pipeline/bin/vocab-model-switch.sh glimmer
```

Qwen และ Glimmer ใช้ GPU ใบเดียวกัน ห้าม start สอง service พร้อมกัน. สำหรับ production
run ให้ใช้ `VM_SYNC.cmd start <run_id>` เพราะ systemd จะจัดการ model switch, checkpoint,
publication และการคืน Glimmer ให้เอง

## คำสั่งจัดการ production run จาก Windows

รันจาก `C:\Users\pimde\Desktop\pimdej\VM TU`:

```bat
BUILD_VOCAB_RUN.cmd <seq_start> <seq_end> audit_repair unreviewed
VM_SYNC.cmd push <run_id.tar.zst>
VM_SYNC.cmd start <run_id>
VM_SYNC.cmd status <run_id>
VM_SYNC.cmd pull <run_id>
```

`BUILD_VOCAB_RUN.cmd` เลือกข้อมูลจาก English; `VM_SYNC.cmd` ส่ง bundle ผ่าน PVE/VM
พร้อม checksum. ระบบไม่ใช้ shared mount และไม่ต้อง copy database ด้วยมือ
