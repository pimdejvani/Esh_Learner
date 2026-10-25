# Production seed quality review — 2026-10-25

Historical findings against version 3. Subsequently resolved through
`content/editorial_corrections.json` in version 4; see `production.md` at the
repository root for the current state. The original audit below remains intact.

Status at time of this audit: findings only; no seed, source content, or application changes made.
This is an AI review, not a human editorial review. Do not treat earlier
structural validation or production promotion as proof of linguistic quality.

## Artifact and scope

- Seed: `vocab_app/assets/seed/vocab.db`
- SHA-256: `5f2cc07e0473352ada26459911c5d602d4d599c08808fdc8e179327cc2586467`
- Content version: 3; 2,967 words; 14,835 sentences; no test-only words.
- Sub-agent reviewed 25 words, all 64 senses and all 125 example sentences
  belonging to those words, including Thai readings, translations, explanations,
  sense mapping, and cloze positions.
- Reproducible sample: order words by `freq_rank`; choose zero-based index
  `floor((i + 0.5) * 2967 / 25)` for `i = 0..24`.
- Separately scanned all 14,835 sentences for partial-word cloze positions.
- Separately read 105 explanations containing the exact phrase
  `ซึ่งทั้งวลีเป็นประธานของ`, checking their English grammatical roles.
- Main agent independently confirmed the cloze scan count and checked the
  production rows for land, broad, total, round, and procedure.

## Sample results

PASS means no required correction identified within the sampled word's rows;
it is not a guarantee that every possible linguistic interpretation is correct.
The sample is not a random estimate of the entire database's error rate.

- PASS (10): customer, food, old, then, informal, oil, obvious, remote, draft,
  institution.
- NEEDS_FIX (15): be, land, same, your, character, empty, round, teenage,
  arrival, departure, graduate, total, broad, procedure, sweep.
- Of the 15, fourteen have content findings; land has a cloze-only finding.

## Confirmed content findings and proposed directions

Sentence IDs and sense IDs below belong to the seed hash above. Proposed
changes require source-evidence checks before altering POS or sense inventory.

| Word | Sentence/sense IDs | Finding and proposed correction |
|---|---|---|
| be | sentence 7145; sense 3904 | `I have been to Paris twice.` is mapped to auxiliary be. Here have is auxiliary and been expresses visiting. Use an evidenced appropriate sense or an actual auxiliary-be example. |
| same | sentence 1514 | Explanation says same must always be followed by as. Remove this false rule; `He treats them the same.` is valid. |
| your | sentence 2701 | Explanation describes Thai ของคุณ after a noun rather than English your before book. Explain possessive determiner before book in the subject your book. |
| character | sentence 3292 | `character trait` is translated as a characteristic of a fictional character. Use ลักษณะนิสัย. |
| empty | sentences 9072, 9075 | Nine o'clock is morning in translation but evening in explanation; English supplies neither. `by the door for the recycling truck` becomes beside the truck door. Use consistent unspecified time and ภาชนะเปล่าไว้ข้างประตูเพื่อรอรถเก็บวัสดุรีไซเคิล. |
| round | sense 2602; sentence 4795 | Spherical is translated เป็นวง rather than เป็นทรงกลม. `The carpenter rounded the sharp corner.` is translated as turning a corner; it means ลบมุมแหลมให้โค้งมน. |
| teenage | sentence 5386 | book drive is translated as fundraising. It is a book donation/collection drive here. |
| arrival | sentences 5976, 5977, 5979 | Translation omits born at dawn; another contains malformed เพื่อมาถึงของเที่ยวบิน. arrival time is mapped to reaching a point in time rather than arrival at a place, and arrival alone is explained as arrival time. |
| departure | sentences 6527, 6528 | departure alone is explained as departure time. departures board is mistranslated ป้ายเครื่องขึ้นเครื่อง; use ป้ายแสดงเที่ยวบินขาออก and distinguish the compound from departures. |
| graduate | sense 5226, POS adj | ผู้ที่ได้รับปริญญา is a noun phrase for an adjective sense. Use ที่ได้รับปริญญาแล้ว. Noun/adjective and verb pronunciations differ; do not call the single current reading wrong in every context. |
| total | sentences 11626, 11628; sense 5574 | total in total cost and total number is adjective but mapped/explained as noun. Check source for an adjective sense, or use actual noun examples. |
| broad | sentences 12211, 12212, 12214 | a broad channel is the object of has, the broad path follows on, and a broad stretch follows into. Explanations incorrectly call them subjects. |
| procedure | sentences 13966–13969 | Misidentifies procedure as a verb's object when nested after of; as the subject of ensures when the subject is Following the correct procedure; and as the object of reduced when The new procedure is its subject. |
| sweep | sentence 14550 | `I need to sweep...` is explained as a purpose infinitive. Explain the infinitival complement of need. Rank 3 also narrows the meaning to a broom although the example uses a brush. |

Stylistic alternatives and uncertain classifications were excluded from the
NEEDS_FIX count. Examples: devoured rendered as อิ่มอร่อย for food, then sense
taxonomy, informal examples with limited context, and transliteration variation.

## Cloze findings across the entire seed

18 rows / 14 words select part of a different word. All have an appropriate
standalone target elsewhere in the sentence. Offsets are zero-based [start,end).

| Sentence ID | Word / rank | Current offsets | Proposed offsets |
|---:|---|---|---|
| 495 | he / 5 | 1,3 (When) | 5,7 |
| 646 | i / 1 | 1,2 (Mia) | 37,38 |
| 647 | i / 2 | 10,11 (Mia) | 26,27 |
| 648 | i / 3 | 9,10 (write) | 25,26 |
| 650 | i / 5 | 1,2 (Circle) | 13,14 |
| 827 | land / 2 | 4,8 (Thailand) | 24,28 |
| 1055 | me / 5 | 9,11 (some) | 21,23 |
| 1742 | so / 2 | 4,6 (soup) | 12,14 |
| 3255 | castle / 5 | 8,14 (sandcastle) | 34,40 |
| 6976 | and / 1 | 11,14 (sandwiches) | 21,24 |
| 6980 | and / 5 | 11,14 (hands) | 16,19 |
| 7166 | bed / 1 | 20,23 (climbed) | 33,36 |
| 8381 | day / 1 | 12,15 (days) | 42,45 |
| 9169 | on / 4 | 24,26 (television) | 27,29 |
| 10728 | pot / 3 | 8,11 (potatoes) | 22,25 |
| 11247 | sharp / 2 | 6,11 (sharpening) | 48,53 |
| 12817 | edit / 2 | 4,8 (editor) | 19,23 |
| 14366 | silk / 1 | 4,8 (silkworm) | 30,34 |

## Explanation-template findings

Of the 105 matched explanations, at least 10 rows / 5 words have confirmed
grammatical-role errors. A text match alone does not establish an error.

- broad: 12211, 12212, 12214 (also counted in the sample findings).
- steep: 14466 (path after up), 14467 (angle is object of has),
  14469 (drop is object of had).
- edit: 12817 and 12819 call edit an object while its noun phrase is the subject
  of improved/removed; the explanations are internally contradictory.
- jazz: 3701; jazz follows of in the subject The first notes of jazz.
- maths: 3971; maths follows in in the subject A quick lesson in maths.

## Follow-up

Correct findings through durable content sources and the builder, then rebuild
and validate the seed. Fix cloze matching and add a boundary validation gate so
rebuilding cannot restore partial-word blanks. Recheck POS/sense mapping and
grammatical roles rather than changing translations alone. Expand linguistic
review before claiming readiness for publication. No full-corpus linguistic
review or human editorial review has been completed by this audit.
