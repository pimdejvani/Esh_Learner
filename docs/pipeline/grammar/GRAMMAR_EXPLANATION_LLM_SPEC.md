# Local LLM grammar-explanation pipeline

สถานะ: Qwen low ผ่าน development mini v6; v7 config-driven regression กำลังรัน; ห้าม promote อัตโนมัติ  
อัปเดต: 2026-08-29  
ขอบเขต: คำอธิบายภาษาไทยรายประโยคใน `example_sentences.explanation_th`

เอกสารนี้เป็น authority ของขั้น authoring คำอธิบาย grammar เท่านั้น สถานะ corpus
และ production โดยรวมอยู่ใน `PRODUCTION.md`; การตั้งค่า VM/GPU/model อยู่ใน
`../VM TU/LOCAL_VOCAB_README.md` และ `../VM TU/document/VM_SETUP.md`.

## 1. เป้าหมายและสถานะข้อมูล

- corpus: 2,967 คำ × 5 ประโยค = 14,835 คำอธิบาย
- legacy candidate ที่พบ: 7,060 แถวที่ rank ถูกต้อง แต่ deterministic validator
  รับได้ 7,050 แถว; เมื่อนับเฉพาะคำที่ทั้ง 5 rank ผ่านครบ ใช้ได้ 1,402 คำ = 7,010 แถว
- production input ที่ต้องสร้างใหม่: 1,565 คำ = 7,825 คำอธิบาย
  (รวม 10 คำที่มี legacy cross-reference ต้องห้ามและจึง regenerate ใหม่ทั้งคำ)
- deadline: 10 ชั่วโมงนับจากเริ่ม production run
- throughput ขั้นต่ำเพื่อจบ generation ใน 9 ชั่วโมงและเหลือเวลา final audit 1 ชั่วโมง:
  173.89 accepted words/hour หรือ 2.90 accepted words/minute รวม validation และ retry

คำอธิบายหนึ่งรายการต้องอ่านประโยคของตัวเองและบอกอย่างน้อย: ความหมายในบริบท,
หน้าที่ทางไวยากรณ์ และเหตุผลที่ใช้ target/form นั้น ห้ามใช้ note กลางของคำเดียวกัน
คัดลอกลงทั้งห้าประโยค (`SPEC.md` กำหนด contract นี้)

## 2. ความน่าเชื่อถือของของเดิม

`data/sol_review_explanations/*.tsv` เป็น **legacy candidate ไม่ใช่ gold set** เพราะ:

- ไม่มีไฟล์ provenance ที่บันทึก model, prompt version, input SHA-256 หรือ reviewer
- ไฟล์ทั้งหมดไม่อยู่ใน Git ณ วันที่ตรวจ จึงย้อนประวัติผู้สร้าง/การแก้รายแถวไม่ได้
- เอกสารเดิมระบุเพียงว่าสร้างเป็น batch โดย Opus subagents
- deterministic audit พบ rank 1–5 จำนวน 7,060 แถวและ anomaly 12 จุด:
  cross-reference ต้องห้าม 10 จุด และ `rank=0 placeholder` 2 จุด
- semantic audit แบบจับคู่ประโยคจริงต้องผ่านก่อนนำแถวเดิมไป merge; ห้ามใช้ของเดิม
  เป็นคำตอบอ้างอิงเพื่อให้คะแนน Qwen/Glimmer โดยอัตโนมัติ

รอบใหม่ทุก run ต้องมี immutable `input.jsonl`, `prompt.txt`, `policy.json` และมี
`state.sqlite3`, `provenance.json`,
`events.jsonl`, `accepted.tsv`, `quarantine.jsonl` และ `summary.json` อยู่ใน staging
เดียวกัน โดย provenance/summary เก็บ input SHA-256, prompt version/hash, model และ config.
`state.sqlite3` เป็น checkpoint authority; ไฟล์ข้อความทั้งหมด rebuild แบบ atomic จาก state.
checkpoint binding ต้องรวม pipeline-state version, validator version, output-schema,
prompt SHA และ policy SHA ด้วย เพื่อห้าม resume ข้าม semantics/config. หนึ่ง run directoryมี writer
ได้เพียง process เดียว; worker ต้องถือ `.run.lock` ตลอด run และใช้ temporary filename ที่
ไม่ซ้ำกันก่อน atomic replace.

## 3. Input/output contract

Input ต่อคำ:

- `seq`, `headword`, attested `forms`
- 5 ประโยคสุดท้ายหลัง Sol review
- ต่อประโยค: `rank`, `sense_id`, source `pos`, exact `target`, English sentence,
  source gloss

ยังไม่บังคับ `th_text`: การวิเคราะห์ grammar ทำจากประโยคอังกฤษ, target และ evidence
ได้โดยตรง และไม่ควรผูก deadline นี้กับ translation API. ถ้ามีคำแปลที่ผ่าน review แล้ว
สามารถเพิ่มเป็นบริบทได้ แต่ห้ามใช้คำแปลแทนการอ่านประโยคอังกฤษ

Output staging เป็น TSV สาม field:

```text
headword<TAB>rank<TAB>explanation_th
```

โมเดลตอบ JSON schema ภายใน แล้ว worker แปลงเป็น TSV หลัง validator ผ่านเท่านั้น.
ไม่มีขั้นตอนใดเขียนทับ `data/sol_review_drafts`, canonical draft หรือ production
content SQLite; SQLite ที่ worker สร้างเป็น checkpoint ภายใน staging เท่านั้น.
`accepted.tsv` หมายถึงผ่าน deterministic validator เท่านั้น ยังไม่นับเป็น semantic
production pass จนกว่าจะผ่าน blind rubric ในหัวข้อ 4 และ final review.

## 4. A/B ที่ใช้เลือกโมเดล

1. ใช้ immutable input เดียวกัน seq 26–50 จำนวน 25 คำ/125 ประโยค
2. input SHA-256 ต้องเป็น
   `7976fa590eda33f3d7a4d5cf7931c82f11d010b75002d454126a848df959e0a7`
3. รันทีละโมเดลเพราะ Tesla T4 รัน Qwen กับ Glimmer พร้อมกันไม่ได้
4. ใช้ prompt/schema/temperature/max token/retry เท่ากัน
5. สลับชื่อผลเป็น A/B ก่อน Codex review เพื่อลดอคติจากชื่อโมเดล
6. ให้คะแนนทุก 125 แถว ไม่ใช้ legacy explanation เป็น gold

Rubric ต่อแถว:

| มิติ | ผ่านเมื่อ |
|---|---|
| semantic | อธิบายความหมายของ target ในบริบทนี้ถูกต้อง |
| grammar | POS/หน้าที่/tense/number/agreement/construction ถูกต้อง |
| form reason | เหตุผลของรูปคำตรงกับประธาน เวลา จำนวน หรือโครงสร้างจริง |
| grounded | ไม่แต่งกฎหรือรายละเอียดที่ไม่มีในประโยค/evidence |
| standalone | ไม่อ้าง rank/ประโยคอื่น และอ่านเดี่ยวรู้เรื่อง |
| Thai | เป็นธรรมชาติ กระชับ และไม่กำกวม |

ระดับผล: `pass`, `minor` (แก้ถ้อยคำแต่แก่นถูก), `severe` (ความหมาย/POS/form/
grammar ผิดหรือแต่งข้อเท็จจริง). หนึ่งแถวจะนับผ่าน production เฉพาะ `pass`.

Gate เลือก production model:

- sentence pass rate ≥ 80% (ปรับโดยผู้ใช้ 2026-08-30)
- severe error ≤ 1.0%
- deterministic acceptance ≥ 98%
- effective throughput ≥ 2.90 accepted words/minute
- ไม่มี error pattern เดียวกันตั้งแต่ 3 แถวขึ้นไป

ค่าปรับได้ของ gate/validator/grounding checks อยู่ใน `config/grammar_explanation_policy_v4.json`;
production prompt อยู่ใน `config/grammar_explanation_prompt_production_v15.txt`
(เนื้อหาเดียวกับ v15 blind หลัง normalize newline) และใช้ `critic_mode=none` เพราะ
v17 rewrite critic ช้าลงและ semantic แย่ลง. ประวัติการทดลองอยู่ใน
`GRAMMAR_EXPLANATION_IMPROVEMENT_LOG.md`.

ถ้าทั้งสองผ่าน ให้เลือก pass rate สูงกว่า; ถ้าต่างกันน้อยกว่า 1 จุดเปอร์เซ็นต์ให้เลือก
ตัวที่เร็วกว่า. ถ้าไม่มีตัวใดผ่าน ห้ามเริ่ม full run: ปรับ prompt ด้วย error taxonomy แล้ว
rerun canary ใหม่ 25 คำที่ยังไม่เคยใช้.

## 5. Improvement loop

### Correctness

1. แยก error เป็น `wrong-sense`, `wrong-pos/function`, `wrong-form-reason`,
   `invented-rule`, `cross-reference`, `template-copy`, `thai-unclear`.
2. แก้ prompt เฉพาะ pattern ที่เกิดซ้ำ ห้ามเพิ่มตัวอย่างยาวจำนวนมากจนลด throughput.
   Prompt production ปัจจุบันต้องตรวจ POS/บทบาทวากยสัมพันธ์จากประโยคจริง, ห้ามเรียก
   adjective/participle ว่า auxiliary, ผูกเหตุผลของรูปคำกับ overt trigger, แยก -ing
   เป็น progressive/gerund/participial modifier และระวัง `according` อาจเป็น participle
   ของ `accord`. การอธิบาย article/determiner/countability ต้องยึด noun phrase จริงและ
   ห้ามใช้คำไทยว่า “คำบุคคล”. ตั้ง `input_ok=false` เฉพาะ error ที่พิสูจน์ได้และคำแก้ต้อง
   ถูก grammar; เป้าความยาวคำตอบคือ 45–110 ตัวอักษร.
3. deterministic validator ตรวจ exact schema, 5 ranks, ไทย 30–180 ตัวอักษร,
   cross-reference ทั้งไทย/อังกฤษ, exact duplicate, near-identical template แบบ threshold
   อนุรักษนิยม และห้าม tab/newline ที่ทำให้ TSV เสียรูปก่อน retry.
4. retry เฉพาะคำที่ตก gate สูงสุด 1 ครั้ง; หลังจากนั้นเข้า quarantine.
5. ทุก prompt/config รุ่นใหม่ต้องทดสอบกับ fresh 25 words และเทียบกับ baseline เดิม.

### Speed

วัด `accepted words/minute` เป็นหลัก ไม่ใช้ tokens/s เพียงอย่างเดียว:

- Qwen baseline: `CPU_MOE=16`, 8 threads, GPU layers 999, parallel 1,
  context 8,192, q8 KV; ห้ามใช้ CPU_MOE 0/8 เพราะเคย OOM
- Glimmer baseline: full GPU Q3_K_M, parallel 1; ลด context จาก 65,536 เป็น
  4,096–8,192 สำหรับงานนี้หลัง baseline เพื่อทดสอบผลต่อ prompt latency/VRAM
- จำกัด output 1,000 tokens/word; ลดได้เมื่อ p99 ไม่ถูกตัด
- ทดลอง batch 1 เทียบ 3 words/request เฉพาะหลัง one-word schema ผ่าน; ยอมใช้ batch
  3 เมื่อ quality ไม่ลดและ accepted words/minute ดีขึ้นอย่างน้อย 10%
- เก็บ model weights ใน page cache ได้เมื่อ RAM available ยังปลอดภัย แต่ห้ามตั้งเป้า
  “ใช้ RAM 80%” เพราะ RAM usage ไม่ได้ทำให้ token generation เร็วขึ้นโดยตรง
- resource gate: swap growth = 0 ระหว่าง canary, host/guest available RAM ≥ 4 GiB,
  ไม่มี CUDA OOM, service restart หรือ sustained thermal/power throttling

## 6. Production run ภายใน 10 ชั่วโมง

ก่อนเริ่มคำนวณ ETA จาก canary:

```text
ETA hours = remaining_words / accepted_words_per_minute / 60
```

ต้องได้ ETA ≤ 9 ชั่วโมง เพื่อเผื่อ pull/checksum/final deterministic audit 1 ชั่วโมง.
Worker ต้อง checkpoint ต่อ attempt/คำใน `state.sqlite3`; terminal ปิดได้ และ resume
จะยอมทำต่อเมื่อ input SHA-256, model, endpoint, prompt hash, config, pipeline-state,
validator และ output-schema version ตรงกันเท่านั้น.
Quarantine เป็น terminal state และแยกใน `quarantine.jsonl`; หากต้องการลองใหม่ต้องเริ่ม
run directory ใหม่. Circuit
breaker หยุดเมื่อ request/schema failure ต่อเนื่อง 5 คำ, resource gate แตก หรือผล canary
ไม่ผ่าน ห้ามแก้ accepted output เก่าอัตโนมัติ. เมื่อ breaker หยุด `summary.json` ต้องมี
`complete=false`, pending count และเหตุผล และคำสั่ง `run` คืน exit code 2.

exit code ของ worker มีความหมายตายตัว: `0` เฉพาะเมื่อ `deterministic_ready=true`, `2`
เมื่อ breaker หยุดและยังมี pending, และ `3` เมื่อทุกคำเป็น terminal แล้วแต่มี quarantine
หรือ input-quarantine. ตัว orchestrator ต้องอ่าน `summary.json` และยืนยัน
`deterministic_ready=true` ก่อนขั้น pull/review/promotion; ห้ามตีความเพียงว่า process จบ.
metric ของ accepted, quarantine และ input-quarantine ต้องเป็นหมวดไม่ทับกัน และ
deterministic acceptance ใช้ terminal ทั้งสามหมวดเป็น denominator.

resource gate และ canary gate เป็น mandatory external preflight/monitor ของ orchestrator
ไม่ใช่ OS probe ภายใน portable worker. Orchestrator ต้องตรวจ swap/RAM/CUDA/service/
thermal และผล canary ตามหัวข้อ 4–5 ก่อนเริ่มและระหว่าง run; เมื่อ gate แตกให้หยุด worker
พร้อมบันทึกเหตุผลภายนอก และห้ามดำเนินขั้นถัดไปแม้ checkpoint จะ resume ได้.

ลำดับ production:

1. สร้าง immutable input 1,565 คำ: 1,555 คำที่ขาดและ 10 คำที่ regenerate anomaly
2. เก็บ prompt/config/model/input hash
3. รัน selected model ต่อเนื่องและ checkpoint ต่อคำ
4. deterministic audit ทุก output; quarantine แยก
5. pull bundle กลับ Windows พร้อม SHA-256
6. Codex review รอบสุดท้ายแบบ stratified + ทุก quarantine/anomaly
7. merge ลง field 8 และ build/validate database หลังผู้ใช้อนุมัติเท่านั้น

## 7. คำสั่งปัจจุบัน

สร้าง snapshot และ A/B input บน Windows:

```powershell
python tools/build_reviewed_english_drafts.py --output-dir staging/grammar_explanation_audit/reviewed_english_snapshot
python tools/grammar_explanation_pipeline.py prepare `
  --snapshot staging/grammar_explanation_audit/reviewed_english_snapshot `
  --ranges 26-50 --only-missing `
  --output staging/grammar_explanation_audit/ab_input_0026_0050.jsonl
python tools/grammar_explanation_pipeline.py audit
python -m unittest discover -s tools -p "test_grammar_explanation_pipeline.py" -v
```

ใน VM API อยู่ loopback เท่านั้น:

- Glimmer: `http://127.0.0.1:8080/v1`
- Qwen: `http://127.0.0.1:8082/v1`
- switch: `/opt/vocab-pipeline/bin/vocab-model-switch.sh glimmer|qwen`

CLI ปฏิเสธ endpoint ที่ไม่ใช่ `127.0.0.1`, `::1` หรือ `localhost` และต้องระบุ port.
ห้ามเปิดสอง port ออก LAN/Tailscale และห้ามรันสองโมเดลพร้อมกันบน T4.
