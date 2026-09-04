# Local Qwen vocabulary workflow — English authority

เอกสารนี้เป็น authority เฉพาะเรื่องข้อมูลและการ review ของโปรเจกต์ `English`.
การติดตั้ง model, VM/PVE, systemd, GPU/RAM, การส่ง bundle และ shutdown timer อยู่ที่
[`../../../../VM TU/LOCAL_VOCAB_README.md`](../../../../VM%20TU/LOCAL_VOCAB_README.md).
คู่มือปฏิบัติสำหรับ validation, ตำแหน่งไฟล์, final goal, การเข้า server และการเรียก
Qwen API อยู่ที่
[`LOCAL_QWEN_VALIDATION_AND_SERVER.md`](LOCAL_QWEN_VALIDATION_AND_SERVER.md).

## ขอบเขตฝั่ง English

- evidence database และ manifest ที่ใช้มอบหมายคำ
- six-field English sentence contract
- deterministic validation, candidate และ quarantine
- สถานะ corpus และงาน Sol/Codex review
- การรับผล local model เข้ามาใน `staging/` ก่อน review

Local model สร้าง **candidate เท่านั้น**. Candidate ห้ามเขียนทับ canonical drafts,
review reports, repair overlays หรือ production database โดยตรง. ผลที่ final reviewer
อนุมัติแล้วจึงเข้า complete overlay และ gated autorun ได้ตาม
`LOCAL_QWEN_VALIDATION_AND_SERVER.md`

## Parallel semantic review assignment (2026-08-26)

งานตรวจ Qwen candidates เพื่อเข้า production ปัจจุบันแบ่งแบบ exclusive ให้ AI สองตัวทำพร้อมกัน:

- ChatGPT session ปัจจุบันรับผิดชอบ `seq 1976-2699`
- external AI reviewer รับผิดชอบ `seq 2700-2967`
- `seq 2700` เป็นของ external AI เท่านั้น; ห้ามสร้างผลซ้ำข้าม boundary
- ทั้งสองฝ่ายเขียน `data/sol_review_reports/` และ complete overlays เฉพาะ batch/seq ของตน
- candidate ที่อนุมัติใช้แทน canonical ต้อง report `repaired`; ห้าม report `pass` ให้ Qwen
  candidate เพียงเพราะ automatic gate ผ่าน
- ระหว่างทำพร้อมกันห้ามแก้ staging SQLite, canonical drafts, manifest, evidence DB หรือ
  report/overlay ของอีกช่วง
- รัน production progress และ `python tools/run_production_after_review.py` หลังทุก batch;
  autorun ต้อง no-op จน review ครบและ errors=0
- หลังทั้งสองฝ่ายเสร็จและ progress เป็น `2967/2967 errors=0` autorun จะทำ translation,
  content DB validation และ production import/export ภายใต้ lock

External AI ต้องอ่าน `LOCAL_QWEN_VALIDATION_AND_SERVER.md` ก่อนเริ่ม เพราะไฟล์นั้นระบุ
source paths, prompt ส่งต่องาน, quarantine exception และรูปแบบ provenance. Assignment นี้
เป็น production Sol review ที่ใช้ Qwen candidate เป็นข้อเสนอ ไม่ใช่ authority

## Authority paths

| Path | หน้าที่ |
|---|---|
| `data/vocabulary_evidence.db` | evidence แบบ read-only |
| `data/sol_review_manifest.txt` | assignment authority ของ audit/repair |
| `data/terra_missing_manifest.txt` | assignment authority ของ generate mode |
| `data/terra_english_drafts/` | canonical input blocks |
| `data/sol_review_reports/` | สถานะ human review ที่เสร็จแล้ว |
| `data/sol_review_drafts/` | human repair overlays |
| `tools/local_vocab_pipeline/` | bundle builder, validator, checkpoint worker และ verifier |
| `staging/local_qwen_outgoing/` | immutable bundles ที่รอส่งไป VM |
| `staging/local_qwen_runs/` | ผลที่ดึงกลับและตรวจแล้ว แต่ยังไม่ merge |

## สถานะข้อมูล ณ 2026-08-22

- evidence: 2,967 words / 39,765 senses / 17,951 forms / 65,641 examples
- English canonical blocks: 2,967/2,967
- Sol reviewed: 1,950/2,967
- repaired overlays: 1,571
- deterministic validator progress: `reviewed=1,950`, `repaired=1,571`; มีรายงานเก่าที่ขาด overlay 1 กลุ่ม ต้องแก้ก่อน merge
- local-Qwen full run ล่าสุด: accepted 989, quarantine 3 จาก 992 คำ

Full local-Qwen run คือ
`20260821-063552-qwen3-30b-q4-1301-2967-7eaa3afd317c` จำนวน 1,242 คำ.
Builder ตัด 1,725 คำที่ review แล้วออกด้วย `unreviewed` selection. Run ถูก pause
หลังตรวจผ่าน seq 1400: checkpoint มี accepted 59, pending 1,182 และ generating 1
ที่ worker จะ reconcile เมื่อ resume

เหตุผลที่ pause: semantic sample seq 1401–1407 พบ grammar/naturalness failure เป็นกลุ่ม
ที่ deterministic validator เดิมจับไม่ได้ เช่น `several someone`, `came soon than` และ
`the soon train`. ห้าม resume จนกว่าจะเพิ่ม semantic/grammar gate และ canary ใหม่ผ่าน

แก้เมื่อ 2026-08-21: เพิ่ม Qwen critic pass แยกหลัง generator, deterministic red flags
สำหรับ failure ที่พบ และ tests รวม 21 รายการ. เนื่องจาก human review เพิ่มเป็น
1,825/2,967 แล้ว 100 คำ unreviewed แรกปัจจุบันจึงเป็น seq 1451–1550. Critic canary
run `20260821-104212-qwen3-30b-q4-1451-1550-7eaa3afd317c` กำลังทำงาน; จะ resume
remaining corpus เฉพาะเมื่อ automatic และ semantic/grammar audit ผ่าน

## Quality contract

แต่ละคำต้องมีห้าแถว: `rank, sense_id, pos, target, memorable, sentence`.
Output ต้องผ่าน schema/source validation, exact-target validation, uniqueness,
restricted-sense rejection และ checksum ก่อนเข้าฝั่ง accepted; คำที่ยังไม่ผ่านหลัง retry
ต้องอยู่ใน quarantine

สถานะ quality gate ล่าสุด (2026-08-21):

- development regression 15 คำ: automatic 15/15, semantic word-pass 12/15
  (80%), sentence-pass 72/75 (96%), 3.09 accepted words/minute; หนึ่งคำ retry 3 ครั้ง
- held-out 25 คำ run `20260821-134341-qwen3-30b-q4-1551-1575-7eaa3afd317c`:
  automatic 25/25 first-pass, quarantine 0, 3.46 words/minute
- semantic held-out: word-pass 20/25 (80%) แต่ sentence-pass 116/125 (92.8%),
  จึง **ยังไม่ผ่าน** production gate 96% และห้ามเริ่ม full run
- failure clusters คือ sense drift ของคำหลายความหมาย (`cartoon`, `chip`, `classical`)
  และ collocation ผิดธรรมชาติ (`catch accuracy`, `faulty electrical cause`)
- ทดลอง contrastive-negative prompt กับ 25 คำเดิมแล้วคุณภาพแย่ลงและความเร็วเหลือ
  3.25 words/minute จึง rollback; VM กลับสู่ worker baseline deployment
  `1169c03f4396`
- baseline held-out ชุดถัดไป seq 1576–1600 run
  `20260821-140913-qwen3-30b-q4-1576-1600-7eaa3afd317c`: automatic 25/25
  first-pass, quarantine 0, 3.37 words/minute แต่ semantic word-pass 17/25 (68%)
  และ sentence-pass ประมาณ 110/125 (88%) จึงไม่ผ่าน
- การตรวจ evidence พบว่า assignment ไม่มี `primary_sense_id`; selector จึงเลือก sense
  จาก canonical rank 1 ตาม contract เช่น `clothing` เป็น verb, `coach` เป็นรถม้า และ
  `connected` หมายถึงมีเส้นสาย ปัญหารอบนี้จึงเป็น common-sense authority/selection
  มากกว่าการเพิ่ม RAM, critic หรือ sampling

Production gate ปัจจุบัน (กำหนด 2026-08-21): semantic sentence-pass ≥92.5%,
automatic accepted 100%, quarantine 0, ไม่มี severe/systemic error cluster และ
ความเร็ว ≥3.0 accepted words/minute. Word-level all-five-pass บันทึกเพื่อวิเคราะห์
แต่ไม่ใช่ production blocker

selector รุ่น `7b3d8804cc2c` เพิ่ม conservative common-sense fallback: ไม่ใช้ derived
`form-of/gerund/participle` เมื่อมี lexical sense และยอมเปลี่ยนจาก canonical rank 1
เฉพาะเมื่อ sense อื่นมี direct learner examples ≥5 ขณะที่ rank 1 ไม่มี direct example

- development replay seq 1576–1600: sentence-pass 121/125 (96.8%), word-pass
  22/25 (88%), automatic 25/25, quarantine 0, 3.40 words/minute
- blind held-out seq 1601–1625 run
  `20260821-143817-qwen3-30b-q4-1601-1625-7eaa3afd317c`: sentence-pass
  118/125 (94.4%), word-pass 19/25 (76%), automatic 25/25, quarantine 0,
  3.44 words/minute — ผ่าน production gate
- full unreviewed run `20260821-144804-qwen3-30b-q4-1626-2967-7eaa3afd317c`
  **completed** แล้ว: accepted 989, quarantine 3, automatic verifier `errors=[]`.
  Bundle ถูก pull และตรวจบน Windows แล้วที่
  `staging/local_qwen_runs/20260821-144804-qwen3-30b-q4-1626-2967-7eaa3afd317c/`.
  ผลยังเป็น candidate และยังไม่ merge เข้า canonical จนกว่าจะผ่าน semantic review
  ของ Codex/Sol; quarantine ต้อง review แยก

Policy ปัจจุบันเน้นหนึ่ง common modern sense ที่ถูกต้องในหลายบริบทก่อน forced sense/POS
coverage. Codex/Sol review ภายหลังเป็นผู้ตัดสิน optional coverage improvements

## เมื่อ generation จบ

จากโฟลเดอร์ `../VM TU` รัน:

```bat
PULL_LATEST_VOCAB_RESULT.cmd
```

คำสั่งจะอ่าน full run ID, ตรวจ status, pull bundle, ตรวจ SHA-256, แตกไฟล์และรัน
Windows deterministic verification. จากนั้น review เฉพาะ
`staging/local_qwen_runs/<run_id>/output/accepted/` และ review quarantine แยก

ห้าม merge ทั้งโฟลเดอร์หรือแก้ report/canonical จนกว่า semantic review จะจบ

ผล full run ที่ pull แล้วตรวจด้วย `VM_SYNC.cmd pull` เป็นหลักฐานสำหรับ review ครั้งเดียว:
ดู `output/accepted/`, `output/quarantine/`, `output/accepted_six_field.txt`,
`output/review_report.tsv` และ `summary.json` ภายในโฟลเดอร์ run ข้างต้น

## การสร้าง bundle ใหม่

คำสั่งนี้เป็นฝั่ง English เพราะเป็นผู้เลือก manifest, review state และช่วงคำ:

```bat
..\VM TU\BUILD_VOCAB_RUN.cmd <seq_start> <seq_end> audit_repair unreviewed
```

`unreviewed` เป็นค่า production ที่ปลอดภัย เพราะอ่าน human review reports และตัดคำที่
เสร็จแล้วออก ใช้ `all` เฉพาะ gold/replay ที่ตั้งใจรวมคำ review แล้ว หลังได้ verified
bundle จึงส่งต่อให้ server transport ตาม `VM TU/LOCAL_VOCAB_README.md`
