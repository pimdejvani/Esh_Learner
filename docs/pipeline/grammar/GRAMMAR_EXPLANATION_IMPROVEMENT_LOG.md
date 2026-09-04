# Grammar explanation improvement log

อัปเดต: 2026-08-29  
สถานะ: v7 regression mini กำลังรัน; canonical/database ยังไม่ถูกแก้

ไฟล์นี้บันทึกเหตุผลการเปลี่ยนแต่ละรุ่นและผลจริงเพื่อป้องกันการปรับ prompt แบบจำผลเฉพาะหน้า
ตัวเลข semantic มาจาก Codex อ่านครบทุกคำอธิบายใน mini; deterministic และ throughput
มาจาก `output/summary.json` ของ run ที่ระบุ

## Gate ที่ใช้ปัจจุบัน

ค่าแก้ได้อยู่ที่ `config/grammar_explanation_policy_v2.json` ไม่ได้ฝังใน worker:

- semantic pass ≥80% (ผู้ใช้ปรับจาก 85% วันที่ 2026-08-30)
- severe error ≤1%
- deterministic acceptance ≥98%
- error pattern เดียวกันได้ไม่เกิน 2 แถว
- effective throughput ≥2.90 accepted words/minute
- เวลาเฉลี่ยไม่เกิน 3 นาที/คำ

## ประวัติรุ่น

v1–v2 เป็น exploratory implementation ก่อนมี immutable pulled run/provenance contract
ในเครื่องนี้ จึงไม่มี metric ที่ตรวจย้อนกลับได้และไม่นำมาแต่งตัวเลขย้อนหลัง; ตารางเริ่มที่ v3
ซึ่งเป็นรุ่นแรกที่มีหลักฐานครบ.

| รุ่น | reasoning | run | deterministic | speed | ผล semantic และข้อสรุป |
|---|---|---|---:|---:|---|
| v3 | low | `20260829-103313-grammar-131-135-96b8dc33c252` | 4/5 (80%) | 1.903 wpm | fail: `amount`, `ankle`, `anybody`, `anyway` มี role/countability/ศัพท์จีนผิด; `ancient` quarantine |
| v3 | medium | `20260829-103315-grammar-131-135-96b8dc33c252` | 4/5 (80%) | 2.334 wpm | ใช้ได้จริง 7/20 accepted rows (35%); ยังผิด role และมี `副คำ/末尾`; fail |
| v4 | low | `20260829-111143-grammar-131-135-96b8dc33c252` | 2/5 (40%) | 0.737 wpm | เนื้อหา 20/25 แถวถูก (80%) แต่ `amount` ผิดทั้ง 5; validator ตี duplicate ที่ถูกต้องแรงเกินไป |
| v4 | medium | `20260829-111146-grammar-131-135-96b8dc33c252` | 3/5 (60%) | 1.235 wpm | แย่กว่า low: เรียก `an` ว่าบุพบท, จัด `this` ผิด และแปล `anyway` เกินหลักฐาน; เลือก low |
| v5 | low | `20260829-111931-grammar-131-135-96b8dc33c252` | 4/5 (80%) | 2.656 wpm | `amount` ถูกแล้ว แต่ semantic pass 20/25 (80%); `anyway` copy ครบ 5 และยังมี adjective/determiner, plural, surface-form defects |
| v6 | low | `20260829-112349-grammar-131-135-96b8dc33c252` | 5/5 (100%) | 3.698 wpm | pass 25/25 (100%), severe 0; retry 1 ครั้งเพราะ validator จับศัพท์ grammar ผิดแล้ว model แก้สำเร็จ |
| v7 | low | `20260829-165212-grammar-131-135-96b8dc33c252` | 5/5 (100%) | 4.590 wpm | architecture ผ่าน แต่ semantic 20/25 (80%): `anyway` ทั้ง 5 ใช้ศัพท์ผิด `คำกริยาวิเศษ`; fail gate 85% |
| v8 | low | `20260829-165654-grammar-131-135-96b8dc33c252` | 5/5 (100%) | 4.794 wpm | semantic 24/25 (96%) แต่ 1 severe (4%): แต่งเหตุผลที่ประโยค `We do it anyway.` ไม่ได้ระบุ; fail severe gate |
| v9 | low | `20260829-170033-grammar-131-135-96b8dc33c252` | 5/5 (100%) | 4.498 wpm | semantic 24/25 (96%), minor 1, severe 0; ผ่าน mini gate และ freeze เพื่อ fresh 25 |
| v9 fresh 25 | low | `20260829-170316-grammar-151-175-4bc5de8f39c4` | 24/25 (96%) | 3.567 wpm | semantic 77/125 (61.6%), minor 16, severe 32; fail ทุก quality gate แม้ speed ผ่าน |
| v10 | low | `20260829-171800-grammar-153-175-389da92aada9` | 5/5 (100%) | 4.136 wpm | semantic 20/25 (80%) แต่ severe 4/25: แต่งส่วนขยายของ `billion`, เรียก `biologies` ว่านับไม่ได้พหูพจน์ และวิเคราะห์ predicate adjective `bright` เป็น noun modifier; fail severe gate |
| v11 | low | `20260829-172511-grammar-153-175-e1b790b810eb` | 4/5 (80%) | 2.801 wpm | validator จับ `bright` หลัง `is too` ได้และ quarantine; ยังผิด role ของ `in biology` และลดค่าตรงตัวของ `a billion` เมื่อเป็นอติพจน์ จึง fail deterministic/speed/severe |
| v12 | low | `20260829-173030-grammar-153-175-e1b790b810eb` | 5/5 (100%) | 3.951 wpm | semantic ประมาณ 21/25 (84%) แต่ severe 4/25 จาก noun-role assignment (`includes`, `examines`, active object, embedded `of` phrase); fail severe gate |
| v13 | low | `20260829-173355-grammar-153-175-e1b790b810eb` | 5/5 (100%) | 3.997 wpm | semantic ประมาณ 21/25 (84%) แต่ severe 4/25; natural-language rule อย่างเดียวยังไม่หยุด subject/object inversion |
| v14 | low | `20260829-173720-grammar-153-175-e1b790b810eb` | 5/5 (100%) | 4.209 wpm | semantic 24/25 (96%), severe 1/25: `fridge` หลัง `back in` ถูกเรียกเป็นกรรมของ Put; fail severe gate |
| v15 blind 25 | low | `20260829-174057-grammar-176-200-89119b65bacd` | 23/25 (92%) | 3.372 wpm | Codex อ่านครบ 125 แถว: strict semantic 79/125 (63.2%), minor 11, severe 35; แม้นับ minor เป็น usable ได้ 72.0% จึง fail gate 80% และไม่เริ่ม production |
| v16 blind 25 | low | `20260831-063051-grammar-201-225-0c5308ca9cb5` | 23/25 (92%) | 2.921 wpm | อ่านครบ 125: strict 67 (53.6%), minor 18, severe 40; one-pass audit/error-aware retry แย่กว่า v15 |
| v17 blind 25 | low + rewrite critic | `20260831-064548-grammar-226-250-5a71f8ceccff` | 22/25 (88%) | 1.582 wpm | อ่านครบ 125: strict 73 (58.4%), minor 7, severe 45; critic สองรอบช้าลงและยังคง confident role errors จึงตัดออก |

## Blind comparison after v17

เทียบ production candidates ที่มี blind 25 คำ: v15 มี strict semantic สูงสุด 63.2%; v9 มีผลรวมปลอดภัยที่สุดด้วย usable 74.4%, severe 25.6%, deterministic 96% และ 3.567 wpm. ไม่มีรุ่นใดผ่าน strict semantic gate 80% จึงไม่เริ่ม production. ตารางเต็มอยู่ที่ `staging/grammar_explanation_audit/BLIND_VERSION_COMPARISON.md`.

ผู้ใช้อนุมัติวันที่ 2026-08-31 ให้รันคำที่เหลือทั้งหมดด้วยรุ่นที่ดีที่สุดแม้ไม่มี
candidate ถึง 80%. จึงเลือก prompt v15 ตาม strict semantic สูงสุด, ปิด v17 critic,
ใช้ repaired snapshot v4 และเก็บผลบน server จนกว่าจะเรียก
`VM TU/PULL_GRAMMAR_PRODUCTION.cmd` จากเครื่อง Windows.

## สิ่งที่แก้และเหตุผล

### v3

- เปลี่ยน instruction หลักเป็นอังกฤษและผลเป็นไทย
- บังคับเช็ค sense, POS, syntactic role, form trigger และ input validity
- เพิ่ม reasoning `low|medium` ใน provenance/resume binding
- เพิ่ม validator สำหรับ `คำบุคคล`, auxiliary/participle และ to-infinitive ที่อธิบายผิด

ผลชี้ว่า instruction เชิงนามธรรมไม่พอสำหรับ Qwen A3B และ JSON `maxLength` ทำให้บางคำตอบ
ถูกตัดกลางคำ จึงต้องเพิ่มตัวอย่างไทยจริงและเลิกใช้ schema บังคับตัดข้อความ

### v4

- เอา `maxLength` ออกจาก response schema แต่คง validator สูงสุด 240 ตัวอักษร
- เพิ่มคำตอบไทยตัวอย่างสำหรับ adjective หลัง `be`, pronoun, article/countability และ `-ing`
- ห้ามอักขระจีน/ญี่ปุ่นและกฎกว้างที่ไม่มีหลักฐาน

semantic ดีขึ้นชัดเจน แต่พบว่า validator ห้ามคำตอบซ้ำเพียง 2 rank ทั้งที่โครงสร้างจริงเหมือนกัน
จึงแก้ให้ตีตกเฉพาะการ copy template ครบทั้ง 5 ตาม contract และเพิ่มตัวอย่าง `amount`

### v5

- แก้ countability ของ `amount`: ตัว `amount` นับได้ แต่ `of sugar/water` ระบุ mass noun ที่วัด
- ผ่อน duplicate detector เฉพาะกรณี grammar ของบาง rank เหมือนกันจริง

ผลเหลือ defect แบบเฉพาะเจาะจง 4 กลุ่ม จึงไม่เพิ่ม prompt กว้าง ๆ แต่แก้เฉพาะหลักฐานที่พบ

### v6

- บังคับคง surface form เช่น `saw` ห้ามแปลงเป็น `see`
- แยก adjective “ขยาย” ออกจาก determiner “กำหนด”
- ห้ามสรุป plural ว่าเท่ากับสอง และห้ามตีความ `our` ว่า speaker+listener เสมอ
- เมื่อ grammar ซ้ำ ต้องอ้าง predicate/complement/context ที่ต่างกันของแต่ละประโยค
- validator ตีตกคำว่า `คำคุณศัพท์กำหนดคำนาม`

รุ่นนี้ผ่าน mini ทั้งคุณภาพและความเร็ว แต่ชุด 5 คำเป็น development set แล้ว จึงยังห้ามเริ่ม
production จนกว่า fresh 25 ที่ไม่เคยใช้ปรับ prompt จะผ่าน

### v7

- ย้าย prompt ไป `config/grammar_explanation_prompt_v7.txt`
- ย้ายเกณฑ์ที่ผู้ใช้ปรับได้ไป policy ภายนอกโค้ด
- bundle บรรจุ `prompt.txt` และ `policy.json`; manifest ผูก SHA ของทั้งสอง
- worker/provenance/checkpoint bind policy และ prompt เพื่อห้าม resume ข้าม config
- คง schema/path/checksum/lock/exit-code guards ในโค้ด เพราะเป็น safety invariant

ผล regression ยืนยันว่า transport/provenance ใหม่ไม่ลดความเร็ว แต่ stochastic output ทำให้
`anyway` ใช้ศัพท์ไทยผิดซ้ำครบ 5 แถว จึงต้องมี v8 และห้ามถือว่า refactor-only เท่ากับผ่าน semantic.

### v8

- prompt อยู่ที่ `config/grammar_explanation_prompt_v8.txt`
- gate และรายการ banned literal/regex อยู่ที่ `config/grammar_explanation_policy_v2.json`
- เพิ่ม calibration ว่า `anyway` เป็น “คำวิเศษณ์” และอธิบายใจความที่ยังทำต่อแม้มีอุปสรรค
- validator ตีตก `คำกริยาวิเศษ` แต่ยอมรับ `คำวิเศษณ์`

เหตุผล: defect เกิดซ้ำ 5 แถว จึงเป็น systemic pattern ตาม gate และควรปิดทั้ง prompt กับ
deterministic validator โดยไม่ฝังรายการศัพท์ใหม่ใน Python.

### v9

- แยกกรณี `anyway` ที่มี contrast ชัด (`but we went anyway`) ออกจากกรณีที่ประโยค
  ไม่บอก contrast (`We do it anyway.`)
- ห้ามแต่ง obstacle, motive, “ไม่มีเหตุผล” หรือ “ไม่จำเป็น”; ให้ระบุว่าเงื่อนไขขัดขวาง
  ไม่ได้ปรากฏในประโยคเมื่อไม่มีหลักฐาน

เหตุผล: v8 ผ่าน pass-rate แต่ severe 1/25 ยังเกินเพดาน 1%; severe gate มีลำดับเหนือ
ค่าเฉลี่ย semantic จึงห้ามไป fresh 25.

ผล v9: 24/25 pass, 1 minor จากการรวม `The huge` เป็นตัวกำหนดวลีอย่างหลวม ๆ,
ไม่มี severe, deterministic 100% และเร็วกว่าเกณฑ์ จึงอนุญาตให้ไป fresh 25 โดยยังไม่
เปลี่ยน prompt/policy เพิ่ม.

Fresh 25 เปิดเผยว่า mini development set ยังไม่ครอบคลุมเพียงพอ: automatic acceptance
24/25 และ 3.567 wpm แต่ Codex review ครบ 125 แถวได้ pass 77, minor 16, severe 32.
หลักฐานราย rank อยู่ที่
`staging/grammar_explanation_audit/fresh_canary_v9_semantic_review.json`.

### v10

- บังคับเชื่อ supplied POS โดยเฉพาะ `num`; เพิ่ม calibration `billion`
- แยก mass/count nouns จาก local noun phrase; เพิ่ม `biology`, `blood`, bare process `birth`
- แยก attributive adjective จาก complement หลัง be และตรวจว่ามี `is` จริง
- articles เป็น determiner; adjective/noun modifier เป็น modifier ไม่ใช่ determiner
- ห้ามเปลี่ยน fact ที่มองเห็น เช่น flood เป็น storm และห้าม copy gloss ยาว
- policy v3 เพิ่ม banned regex, common-prefix ceiling และ grounding checks ที่เปิด/ปิดได้
- diagnostic mini ใช้คำที่ fail จริง: `billion, biology, blood, bright, fridge`

เหตุผล: defect เป็นหลาย systemic clusters ไม่ใช่ stochastic แถวเดียว การเพิ่มเพียง retry
จะเพิ่มเวลาโดยไม่แก้ semantics จึงต้องแก้ prompt และเพิ่ม deterministic checks ก่อน.

## แผนพัฒนาถัดไป

1. v10 diagnostic mini 5 ต้องผ่าน
2. รัน fresh ใหม่ seq 176–200; ห้ามเรียก 151–175 ว่า fresh อีก
3. ถ้าผ่านจึง freeze production bundle; ถ้า fail ต้องเปลี่ยน version และใช้ fresh set ใหม่
3. ถ้า fail ให้จัด defect ตาม pattern แล้วแก้เฉพาะ pattern; เปลี่ยน prompt/policy version และ
   rerun mini 5 + fresh 25 ชุดใหม่ ห้ามใช้ seq 151–175 ซ้ำเป็น fresh set
4. ถ้าผ่าน ให้ freeze prompt/policy SHA, rebuild input 1,565 คำ และเริ่ม production
5. Qwen critic และ final Codex review เป็น read-only; ห้าม auto-merge ทุกกรณี
