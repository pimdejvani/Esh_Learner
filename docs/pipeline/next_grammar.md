# next_grammar — ส่งต่องานตรวจ Grammar

อัปเดต 2026-09-03 (Asia/Bangkok) — อ่านไฟล์นี้ก่อนทำต่อ แล้วตรวจสถานะไฟล์จริงอีกครั้ง ห้ามถือว่าข้อความที่มีอยู่ใน `final.tsv` ผ่าน review แล้วทุกแถว

## 1. เป้าหมายและขอบเขต

AI หลักตรวจ semantic และซ่อมคำอธิบายภาษาไทยของประโยคครบ 7,830 แถว (1,566 คำ × 5 ranks) สร้าง decision ledger ให้ตรวจย้อนกลับได้ ผ่าน second-pass gates แล้วเตรียม immutable grammar-ready production candidate รวมกับ legacy ที่ผ่านการตรวจ ให้ครบ 2,967 คำ / 14,835 แถว

Production ในงานนี้หมายถึง compact drafts 8 fields ที่พร้อมตรวจรับ ไม่ใช่ full app database งาน Thai lexical content ของ words/senses/forms/relations/groups ยังแยกต่างหาก

ห้ามแก้ canonical, database หรือ app seed; ห้าม auto-promote และห้ามนำ validator pass ไปอ้างว่าเป็น semantic pass รอผู้ใช้อนุมัติหลัง candidate ผ่านการตรวจทั้งหมด

## 2. ตำแหน่งไฟล์จริง

Project root: `C:\Users\pimde\Desktop\pimdej\English`

Review directory:
`C:\Users\pimde\Desktop\pimdej\English\staging\grammar_explanation_reviews\20260831-071557-grammar-26-2967-bd9cfe09ead9`

Raw generation run:
`C:\Users\pimde\Desktop\pimdej\English\staging\grammar_explanation_runs\20260831-071557-grammar-26-2967-bd9cfe09ead9`

ไฟล์ใน review directory:

| ไฟล์ | หน้าที่ / ข้อควรระวัง |
| --- | --- |
| `candidates.jsonl` | Immutable: candidate เดิมและ source context ครบทุกแถว ห้ามเขียนทับ |
| `final.tsv` | Working explanations; 4 columns ไม่มี header: seq, headword, rank, explanation; มีทั้งข้อความที่ตรวจแล้วและยังไม่ตรวจ |
| `source_repairs.tsv` | Sentence-only overlay; 4 columns ไม่มี header: seq, headword, rank, sentence; อ่านด้วย TSV parser ที่รองรับ quoting |
| `reviewed_batches.txt` | หมายเลข batch ที่ตรวจรอบแรกจบทั้ง batch เท่านั้น |
| `manifest.json` | Run/input/candidate hashes และ batch metadata เดิม ห้ามแก้เพื่อทำให้ hash mismatch หาย |
| `REVIEW_PROGRESS.md` | Checkpoint หลัก พร้อมประวัติการซ่อม ต้องอ่าน partial checkpoint ด้วย |
| `REVIEW_REFERENCE_NOTES.md` | หลักฐานเรื่องการจัด POS ที่มีความกำกวม เช่น the และ unlike ต้องย้อนตรวจใน second pass |

Raw run มี `input.jsonl`, `manifest.json`, `config.json`, `policy.json`, `prompt.txt`, archive `.tar.zst` และ checksum; accepted/quarantine เดิมอ่านจาก `output/accepted.tsv` และ `output/quarantine.jsonl` ห้ามแก้หลักฐานเดิม

เอกสารประกอบ (หลัง restructure 2026-09-05): `grammar/GRAMMAR_EXPLANATION_LLM_SPEC.md`, `grammar/GRAMMAR_EXPLANATION_IMPROVEMENT_LOG.md`, `../app/SPEC.md`, `PLAN_CONTENT_PIPELINE.md`, `PRODUCTION.md`, `qwen/LOCAL_QWEN_VALIDATION_AND_SERVER.md`, `qwen/LOCAL_QWEN_VOCAB_WORKFLOW.md` และ `../formats/terra_compact_format.md` เอกสารยุคเก่ารวมไว้ที่ `../legacy/REVOCAB_PILOT_2026-08.md` (archive อย่านำมาแทนข้อกำหนด final review ในไฟล์นี้)

เรื่อง runtime/server/transfer อยู่ที่ `C:\Users\pimde\Desktop\pimdej\VM TU` และเอกสาร server ส่วนผลข้อมูลและ validation อยู่ใน English ไม่จำเป็นต้องเรียก server เพื่อทำ semantic review ของข้อมูลที่ดึงมาแล้ว

## 3. Checkpoint ที่ตรวจยืนยัน ณ ส่งต่อ

- ขอบเขตทั้งหมด 1,566 คำ / 7,830 แถว; key ใน `final.tsv` ตรง candidates ครบ ไม่มี duplicate
- Batch 1–40 จบรอบแรก: 1,000 คำ / 5,000 แถว
- Batch 41 (seq 2402–2426) ยังไม่จบ: seq 2402–2421 จำนวน 20 คำ / 100 แถว อ่านและบันทึกผลรอบแรกแล้ว แก้ 54 คำอธิบายเทียบ candidate; ไม่เพิ่ม source repair ในส่วนนี้
- ดังนั้นมีงานรอบแรกที่ทำแล้วรวม partial 5,100 แถว เหลือยังไม่สรุปผล 2,730 แถว แต่ตัวนับ completed batches ยังคงเป็น 5,000 แถว ห้ามเพิ่มหมายเลข 41 ก่อนอีก 25 แถวจบ
- ทั้ง 5,100 แถวที่ตรวจแล้วผ่าน `validate_text` เดิม นี่เป็น deterministic check ไม่ใช่ second-pass semantic score
- Source overlay มี 107 แถว ตัวเลขนี้อาจเพิ่มได้เมื่อพบหลักฐานว่าต้นทางผิด
- Candidate states: accepted 7,135 แถว; output quarantine 645 แถว = 129 คำ; input quarantine 50 แถว = 10 คำ รวม 7,830 แถว ไม่ใช่ 129 และ 10 แถว
- ยังไม่มี decision ledger ฉบับสมบูรณ์, second-pass gate, translation/merge audit หรือ immutable production candidate ของงาน review นี้

SHA-256 ณ ส่งต่อ (working hashes จะเปลี่ยนเมื่อแก้ต่อ):

- `candidates.jsonl`: `ee1ee92d26f04af07441f00d63871c1143fb9791b75586994f114418ba1dc805`
- `final.tsv`: `71ed1272330f26b700f9a56ae858622221545e4bb17da5485af569a996c7ed5d`
- `source_repairs.tsv`: `65801fba2c14e9314cf5ece57549f27686d41a51be91fdfd74fc4d0891239267`

ค่า final hash ที่ checkpoint จบ batch 40 เป็นค่าเก่าโดยตั้งใจ เพราะหลังจากนั้นแก้ partial batch 41 แล้ว อย่ากู้ทับไฟล์ล่าสุดเพียงเพราะไม่ตรง hash ของ checkpoint เก่า

## 4. เริ่มงานต่อทันทีตรงไหน

1. ตรวจ `reviewed_batches.txt`, hashes และ partial checkpoint เทียบไฟล์จริงก่อน อย่า regenerate working set หรือ overwrite งานเก่า
2. อ่าน source + candidate + final + effective sentence หลังใช้ overlay ของ seq 2422–2426 ครบทุก rank: `beg`, `being`, `bent`, `bet`, `beyond` รวม 25 แถว
3. ชุดนี้เคยแสดงให้ AI หลักอ่านแล้ว แต่ยังไม่ได้บันทึกการตัดสิน/ซ่อม ให้ถือว่ายัง unresolved และอ่านใหม่ก่อนตัดสิน
4. จุดที่ต้องตรวจ: beg ranks 2–5 อ้างกริยา `entreat` ที่ไม่มีในประโยค; being ranks 3–4 สลับ complement/object; bent rank 5 เรียก complement หลัง was ว่า object complement; bent rank 2 แปล drawer เป็นตู้; bent rank 3 ต้องตัดสินว่าประโยคบอก hinge ปิดไม่ได้เป็นธรรมชาติพอหรือควรซ่อม sentence ทั้งหมดนี้เป็นข้อสังเกต ไม่ใช่ผล keep/rewrite สำเร็จแล้ว
5. เมื่อครบ 125 แถวของ batch 41 ให้ audit, เพิ่ม 41 ใน marker และอัปเดต counts/hash ใน checkpoint แล้วเริ่ม batch 42 ที่ seq 2427
6. ทำต่อจน batch 63 (batch สุดท้าย 16 คำ / 80 แถว) โดยอิงลำดับ unique `(seq, headword)` ใน candidates ไม่แบ่งตาม seq ต่อเนื่องเอง เพราะ batch ช่วงก่อนหน้ามีช่องว่าง seq

## 5. วิธี review รายแถว

- AI หลักอ่าน sentence, target, POS, sense_id, gloss และ candidate จริงครบทุก rank; ถ้ามี repair ให้ใช้ effective sentence และยังเก็บ source เดิมไว้
- ตรวจความหมายตาม sense, POS, syntactic role, form trigger, modal/base form, tense, participle/gerund, countability/article, noun adjunct, idiom และภาษาไทยที่อ่าน standalone ได้
- อธิบายเฉพาะสิ่งที่มีหลักฐานในประโยค อย่าแต่ง subject/object, คำกริยา, article หรือสาเหตุเพิ่ม; อย่าคัด template เดียวมาเปลี่ยน headword
- ตัดสิน `keep` หรือ `rewrite` พร้อม final Thai explanation; ไม่มี unresolved row ตอนจบรอบแรก
- ซ่อมเฉพาะแถวที่มีเหตุผลจริง ไม่แก้เพื่อเพิ่มจำนวน rewrite และไม่ใช้จำนวน rewrite เป็นคะแนน semantic
- หาก source ผิด ให้แก้เฉพาะ sentence ใน overlay ห้ามเปลี่ยน POS, target, sense_id หรือ gloss และตรวจคำอธิบายทั้งห้า rank ของคำนั้นให้สอดคล้องกัน
- แยก grammar ที่ผิดออกจากการวิเคราะห์ได้หลายแบบ; ถ้าไม่แน่ใจเรื่อง POS/สำนวน ให้ตรวจพจนานุกรมหรือแหล่ง grammar ปฐมภูมิและบันทึกหลักฐาน
- ใช้ `apply_patch` แก้ไฟล์; scripts ช่วยอ่าน/ตรวจ key/hash/รูปแบบได้ แต่ห้ามให้กฎเชิงกลแทนการตัดสิน semantic

ตรวจทุก batch: final มี 4 columns และ exact key coverage, ranks 1–5 ครบ, duplicate เป็นศูนย์, `validate_text` ผ่านทุกแถวที่ตรวจแล้ว, repair keys อยู่ใน scope/ไม่ซ้ำ/เปลี่ยน sentence จริง/ยังมี target เดิม, immutable hash ตรง manifest แล้วบันทึก checkpoint และข้อที่แก้พร้อมเหตุผล

## 6. Decision ledger และ second pass ที่ยังต้องทำ

สร้าง ledger JSONL ใน staging โดยกำหนด schema และ serialization ก่อน hashing ต้องมีอย่างน้อย run_id, input SHA-256, original source SHA-256, candidate SHA-256, seq, headword, rank, decision, issue_codes และ final_explanation_th ถ้ามี repair ให้ผูก effective source hash และ overlay hash เพิ่ม โดยไม่ทำลาย hash ของ source เดิม

Candidate ปัจจุบันมี fields: `seq`, `headword`, `rank`, `candidate_state`, `source`, `source_sha256`, `candidate`, `candidate_sha256`; source มี `rank`, `sense_id`, `pos`, `target`, `sentence`, `gloss`

การ serialize source เดิมใช้ JSON แบบ sort_keys, ensure_ascii=False, separators คงที่ตาม `tools/prepare_grammar_review_working_set.py`; ต้องอ่าน implementation ก่อนสร้าง verifier อย่าเลือก serialization ใหม่แล้วอ้างว่า hash ตรงเดิม

`final.tsv` ต่างจาก candidate ช่วยสร้าง decision keep/rewrite ทางกลได้ แต่ไม่ใช่หลักฐานว่ามี semantic review หรือ issue code แล้วทั้งหมด AI หลักต้องตรวจ issue_codes ให้มีเหตุผลจริง โดยเฉพาะแถวที่ rewrite มาก่อนและไม่มี row-level ledger ห้ามแต่ง reviewer/timestamp/คะแนนย้อนหลัง

Second pass:

- ตรวจซ้ำทุก input/output quarantine, source repair และ anomaly รวมทั้งคำที่มีข้อควรระวังใน reference notes
- สุ่มอย่างน้อย 10% ของทั้ง 7,830 แถว (อย่างน้อย 783 แถว) กระจายตาม POS, seq และประเภทการแก้; บันทึก key, seed/วิธีเลือก, denominator และผลรายแถว
- Gate: coverage 100%, severe error 0%, sample pass ≥97.5%; ถ้าไม่ผ่านหรือพบ severe error ให้ค้นและแก้ทุกแถวใน pattern เดียวกัน แล้วใช้ fresh sample ทดสอบใหม่
- เกณฑ์ semantic 80% ที่เคยใช้เลือก generation version ไม่ใช่เกณฑ์อนุมัติ final review นี้

## 7. Concept subagent — ใช้ตัวที่ประหยัด token ที่สุด

- AI หลักเป็นผู้ตัดสินภาษาและผู้อนุมัติ patch เสมอ ไม่มอบ semantic review ให้ subagent
- หลัง ledger พร้อม ใช้ subagent **ตัวที่ประหยัด token ที่สุด** ซึ่งทำงานเชิงกลตาม acceptance criteria ได้ ไม่ล็อกชื่อรุ่น ใช้ reasoning เท่าที่จำเป็น
- ถ้ามี agent เดิมและยังเข้าถึงได้ ให้ใช้ตัวเดิมส่งงานต่อ; ชื่อเชิงบทบาทที่เคยใช้คือ `production_mechanical` แต่ session ใหม่ต้องตรวจว่า handle ยังมีจริง ห้ามอ้างว่ายังรออยู่โดยไม่ตรวจ
- ถ้าตัวเดิมไม่มีแล้ว ค่อยสร้างหนึ่งตัวสำหรับงานตายตัว ห้ามสร้างใหม่ทุก batch
- ส่งเฉพาะ schema, paths, fixture เล็ก, interface และ tests ที่ต้องผ่าน ไม่ส่งประวัติแชตหรือ corpus ทั้งหมด
- งานที่มอบได้: implement validator/merge CLI, tests, checksum/manifest และแพ็ก staging candidate ตามข้อมูลที่ AI หลัก review แล้ว
- งานที่ห้ามมอบ: keep/rewrite ทางภาษา, เติม issue codes โดยเดา, เปลี่ยน review threshold, แก้ accepted content เอง หรือ promote
- ระหว่างรอให้จบ turn และ idle ไม่ polling/ทำงานวน; main ต้องตรวจ patch ทุกบรรทัด รัน tests และตรวจ output ก่อนยอมรับ

## 8. เครื่องมือที่มี และงาน merge ที่ต้องตรวจ/พัฒนา

พบแล้วใน `English\tools`:

- `prepare_grammar_review_working_set.py`: สร้าง working set ใหม่จาก run รับ `--run-dir`, `--output-dir`, `--batch-size`; ห้ามรันเพื่อทับ review ปัจจุบัน
- `grammar_explanation_pipeline.py`: มี `prepare`, `run`, `audit` และฟังก์ชัน `validate_text`; `audit --existing-dir` ตรวจ legacy ไม่ใช่ proof ของ final review ปัจจุบัน
- `test_grammar_explanation_pipeline.py`: tests ของ pipeline เดิม
- `translate_vocab_content.py`: รับ `--input-dir`, `--output-dir`, `--cache`, `--providers`, `--dry-run`; ตรวจว่า interface/input format รองรับ repaired snapshot ก่อนใช้จริง
- `validate_content_db.py`: validator ของ content DB ไม่ใช่ตัวแทน semantic audit และไม่ทำให้ full DB พร้อมโดยอัตโนมัติ

ยังไม่ได้ยืนยันว่ามี final review ledger/merge CLI ที่ครบสเปกแล้ว ต้องค้นและอ่านของที่มีต่อก่อนสร้างใหม่; อย่าแต่งคำสั่ง merge ที่ยังไม่มี อ้างชื่อคำสั่งจริงจาก source หรือ `--help`

Merge requirements:

- ทุก path/config รับผ่าน arguments; ไม่ hardcode run ID, directory, row counts หรือ provenance ใน logic
- Precedence: reviewed run > legacy ที่ valid; overlap ต้องตรง run scope ห้าม silent overwrite
- Legacy อยู่ที่ `data/sol_review_explanations`; deterministic-valid ไม่ใช่ gold ต้องตรวจ semantic binding กับ effective sentence ตามสเปกด้วย
- Reconcile ตัวเลขแผนเดิม: legacy-valid 7,049 + reviewed 7,830 − overlap 44 = 14,835 แถว ต้องนับจากไฟล์จริงใหม่ ไม่ force ตัวเลขหรือเติมแถวหลอกให้ครบ
- Exact key coverage, ไม่มี duplicate/rank ผิด, SHA binding ถูกต้อง, explanation ผ่าน policy, field 1–7 ต้อง byte-equivalent กับ translated input; merge เติมเฉพาะ field 8
- ก่อน merge ใช้ sentence overlay สร้าง repaired immutable snapshot และแปล sentence ที่ซ่อมให้ตรงกัน อย่าใช้ translation เก่าของ sentence เดิม
- แปล field 7 ด้วย Azure เป็นหลักและ DeepL fallback ตาม quota ที่ตั้งค่าไว้; dry-run ก่อน แล้วใช้ staging/output/cache ที่ระบุชัด ห้ามเปิดเผย API keys
- ถ้า translation ล้มเหลว เก็บ partial evidence แต่ห้าม publish/นับ partial เป็น candidate
- Manifest ต้องผูก source snapshot, repair overlay, providers/provenance, ledger hash, policy hash และ checksum ทุก output; candidate ใช้ directory ใหม่ที่ยังไม่มี ไม่ overwrite

## 9. Tests และเงื่อนไขส่งมอบ

- Unit tests: missing/duplicate key, invalid rank, malformed TSV/JSONL, SHA mismatch, policy fail, overlap นอก scope, output directory มีอยู่แล้ว
- Source repair: เปลี่ยนเฉพาะ sentence และทำให้ effective source hash เปลี่ยน; old binding ต้องใช้กับ repaired input ไม่ได้
- Fixture อย่างน้อย 25 คำ มี accepted, output quarantine, input quarantine และ legacy overlap
- Merge tests: precedence ถูก, field 1–7 ไม่เปลี่ยน, field 8 ครบ; full audit ยืนยัน 2,967 headwords × ranks 1–5 = 14,835 แถวจากข้อมูลจริง
- Translation: Thai sentence ไม่ว่างทุกแถว, provider provenance ครบ, checksum ตรง และไม่มี partial file ถูกนับรวม
- หากมีการส่ง archive ให้ตรวจว่า zstd จริงด้วย magic/checksum ทุก hop ไม่ใช่เปลี่ยนนามสกุลไฟล์
- ส่งมอบ immutable staging candidate, ledger, second-pass report, deterministic audit, manifest/checksum และคำสั่งนำไปใช้ที่ทดสอบแล้ว จากนั้นรอผู้ใช้อนุมัติก่อน promote
- ไม่ลบเอกสารเก่าเอง ถ้าพบล้าสมัยให้ทำรายชื่อพร้อมเหตุผลรอผู้ใช้สั่งลบ

## 10. Prompt สั้นสำหรับ AI ตัวถัดไป

> อ่าน next_grammar.md และ REVIEW_PROGRESS.md แล้วตรวจไฟล์จริง ต่อจาก partial batch 41 ที่ seq 2422–2426 ให้ AI หลักตรวจ semantic เองครบทุก rank รักษางานที่ตรวจแล้วไว้ สร้าง ledger และผ่าน second-pass gates ก่อนใช้ subagent ตัวที่ประหยัด token ที่สุดทำเฉพาะ validator/merge เชิงกล เตรียม immutable staging candidate โดยไม่แก้ canonical/database/app seed และไม่ auto-promote อัปเดต checkpoint ทุก batch และอย่าอ้างว่าผ่าน semantic จาก validator อย่างเดียว
