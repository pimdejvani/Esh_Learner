# -*- coding: utf-8 -*-
import io, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- report: headword -> (status, reason) ----
report = [
    ("nuclear", "repaired", "3/5 rows pointed at wrong adj sense (57851 vs 57852); added noun sense 57859 for POS coverage"),
    ("obvious", "pass", "single sense in DB, all 5 rows fit and are distinct real sentences"),
    ("obviously", "pass", "correct sense throughout, real distinct sentences"),
    ("occasion", "repaired", "3 rows meant 'special event' (57903) but were tagged 57896; added verb sense 57905 for coverage"),
    ("occur", "repaired", "sense was correct but only 1 distinct form used; rewrote for occurred/occurring/occurs variety"),
    ("odd", "repaired", "replaced weakest adj row with noun sense 57920 (odds and ends) for POS coverage"),
    ("official", "repaired", "r3 sense mismatch (57922 vs 57923); replaced with noun sense 57932 (person holding office)"),
    ("old-fashioned", "pass", "adj senses correctly split between object/person meanings; noun senses (cocktail, doughnut) are niche, skipped"),
    ("operation", "pass", "5 distinct correct senses already covering surgery/business/mission/mechanism"),
    ("organized", "repaired", "added verb sense 57936 (past participle of organize) for POS coverage"),
    ("organizer", "pass", "senses correctly matched to event/notebook/box meanings"),
    ("originally", "pass", "correct sense throughout, real distinct sentences"),
    ("ought", "pass", "verb senses tagged dialectal in DB but are the standard modal usage; other POS (pron/noun/adv) are genuine archaic spellings of 'aught', correctly skipped"),
    ("ours", "pass", "correct sense throughout including r4's group-identity sense"),
    ("outdoor", "pass", "adj sense correct throughout; verb sense (publicly display a newborn) is archaic, correctly skipped"),
    ("outdoors", "repaired", "added noun sense 57978 (the outdoors as a place) for POS coverage"),
    ("package", "repaired", "r3 sense mismatch (57986 vs 57990 'package holiday'); added verb sense 57996 for coverage"),
    ("painful", "pass", "all senses correctly matched to physical/emotional/laborious meanings"),
    ("pale", "repaired", "added verb senses 58011/58012 (to turn pale / to pale in comparison) for coverage; noun senses are archaic heraldry/territory terms, skipped"),
    ("pan", "repaired", "added verb sense 58052 (idiom 'panned out') replacing a duplicate-sense row"),
    ("participate", "pass", "correct sense with 3 distinct forms already; adj sense is archaic, correctly skipped"),
    ("particularly", "repaired", "r5 sense mismatch (58005 vs 58003)"),
    ("passion", "repaired", "r4 sense mismatch (58067 vs 58070, matches DB's own 'my collection has become my passion' example)"),
    ("path", "pass", "correct senses throughout; verb senses are computing-jargon, correctly skipped"),
    ("payment", "pass", "correct senses throughout, noun-only word"),
]

# ---- repaired blocks: headword -> list of (rank, sense_id, pos, target, memorable, sentence) ----
blocks = {}

blocks["nuclear"] = [
    (1, 57852, "adj", "nuclear", 1, "The city fell silent after officials warned of a nuclear accident nearby."),
    (2, 57851, "adj", "Nuclear", 0, "Nuclear means related to the centre of an atom."),
    (3, 57852, "adj", "nuclear", 0, "Scientists study nuclear reactions that release huge amounts of energy."),
    (4, 57851, "adj", "nuclear", 0, "The book has a chapter on nuclear physics."),
    (5, 57859, "noun", "nuclear", 0, "France gets most of its electricity from nuclear."),
]

blocks["occasion"] = [
    (1, 57903, "noun", "occasion", 1, "Grandma cried with joy when the whole family gathered for the happy occasion."),
    (2, 57905, "verb", "occasioned", 0, "The heavy rain occasioned severe flooding across the valley."),
    (3, 57903, "noun", "occasion", 0, "This dress is for a formal occasion."),
    (4, 57903, "noun", "occasion", 0, "We saved the last piece of cake for a special occasion."),
    (5, 57896, "noun", "occasion", 0, "Her birthday was the perfect occasion for a family picnic."),
]

blocks["occur"] = [
    (1, 57888, "verb", "occurred", 1, "The whole village lost power when a sudden blackout occurred during the storm."),
    (2, 57888, "verb", "occur", 0, "Accidents can occur when drivers go too fast."),
    (3, 57888, "verb", "occurring", 0, "These mistakes keep occurring whenever we hurry."),
    (4, 57888, "verb", "occurs", 0, "This kind of problem rarely occurs in modern engines."),
    (5, 57888, "verb", "occur", 0, "Wildfires can occur in very dry weather."),
]

blocks["odd"] = [
    (1, 57906, "adj", "odd", 1, "It felt odd to see snow in the middle of summer."),
    (2, 57906, "adj", "odd", 0, "There was something odd about the way he avoided eye contact."),
    (3, 57906, "adj", "odd", 0, "There was an odd smell in the kitchen."),
    (4, 57920, "noun", "odds", 0, "The drawer was full of odds and ends nobody wanted."),
    (5, 57906, "adj", "odd", 0, "The machine made an odd sound."),
]

blocks["official"] = [
    (1, 57924, "adj", "official", 1, "Parents anxiously refreshed the school website until the official exam schedule finally appeared."),
    (2, 57923, "adj", "official", 0, "Wait for an official announcement before booking tickets."),
    (3, 57932, "noun", "officials", 0, "The stadium officials stopped the game because of heavy rain."),
    (4, 57924, "adj", "official", 0, "Only official documents are accepted at the border."),
    (5, 57927, "adj", "official", 0, "His official role is to check the safety rules."),
]

blocks["organized"] = [
    (1, 57934, "adj", "organized", 1, "Our organized teacher always knows where every paper is."),
    (2, 57936, "verb", "organized", 0, "The charity event was organized by a group of students."),
    (3, 57934, "adj", "organized", 0, "An organized student plans homework before the weekend."),
    (4, 57933, "adj", "organized", 0, "Her organized desk made the report easy to find."),
    (5, 57934, "adj", "organized", 0, "He is organized enough to arrive early for every meeting."),
]

blocks["outdoors"] = [
    (1, 57976, "adv", "outdoors", 1, "The children played outdoors until dinner was ready."),
    (2, 57976, "adv", "outdoors", 0, "It is too cold to eat outdoors today."),
    (3, 57976, "adv", "outdoors", 0, "We prefer exercising outdoors in the morning."),
    (4, 57978, "noun", "outdoors", 0, "She has always loved the outdoors, especially in autumn."),
    (5, 57976, "adv", "outdoors", 0, "They slept outdoors under the stars."),
]

blocks["package"] = [
    (1, 57985, "noun", "package", 1, "A package with my name on it was waiting at the door."),
    (2, 57985, "noun", "package", 0, "The courier left the package with our neighbor."),
    (3, 57990, "noun", "package", 0, "The travel package includes flights and a hotel."),
    (4, 57987, "noun", "package", 0, "Install the software package before opening the program."),
    (5, 57996, "verb", "packages", 0, "The factory packages the toys before shipping them to stores."),
]

blocks["pale"] = [
    (1, 58009, "adj", "pale", 1, "She turned pale and had to sit down when she heard the sudden news."),
    (2, 58008, "adj", "pale", 0, "He chose a pale blue shirt for the interview."),
    (3, 58011, "verb", "paled", 0, "His cheeks slowly paled as the long illness continued."),
    (4, 58008, "adj", "pale", 0, "A pale moon appeared above the trees."),
    (5, 58012, "verb", "pales", 0, "His effort pales in comparison to what she achieved."),
]

blocks["pan"] = [
    (1, 58026, "noun", "pan", 1, "Heat the oil in a pan before adding the onions."),
    (2, 58052, "verb", "panned", 0, "Their plan finally panned out after months of hard work."),
    (3, 58028, "noun", "pan", 0, "Use a deep pan to make the soup."),
    (4, 58030, "noun", "pan", 0, "They used a pan to search for gold in the stream."),
    (5, 58038, "noun", "pan", 0, "The critic gave the new movie a harsh pan."),
]

blocks["particularly"] = [
    (1, 58003, "adv", "particularly", 1, "I particularly enjoyed the last chapter of the book."),
    (2, 58003, "adv", "particularly", 0, "The road is particularly dangerous when it rains."),
    (3, 58005, "adv", "particularly", 0, "This rule applies particularly to new employees."),
    (4, 58003, "adv", "particularly", 0, "She is particularly good at explaining difficult ideas."),
    (5, 58003, "adv", "particularly", 0, "We need particularly quiet rooms for the exam."),
]

blocks["passion"] = [
    (1, 58067, "noun", "passion", 1, "Her passion for cooking began when she was a child."),
    (2, 58067, "noun", "passion", 0, "He speaks about music with real passion."),
    (3, 58068, "noun", "passion", 0, "Their shared passion brought them closer together."),
    (4, 58070, "noun", "passion", 0, "Painting is not just a hobby; it is her passion."),
    (5, 58069, "noun", "passion", 0, "The team played with passion until the final whistle."),
]

# ---- pass-word canonical sentences (unchanged), needed for explanations ----
pass_blocks = {
    "obvious": [
        (1, 57848, "adj", "obvious", 1, "It was obvious that the child was tired."),
        (2, 57848, "adj", "obvious", 0, "The answer was obvious after we read the clue."),
        (3, 57848, "adj", "obvious", 0, "Her wet coat made the rain obvious."),
        (4, 57848, "adj", "obvious", 0, "There was an obvious mistake in the total."),
        (5, 57848, "adj", "obvious", 0, "The path is obvious from the gate."),
    ],
    "obviously": [
        (1, 57849, "adv", "obviously", 1, "He was obviously happy when he saw the puppy."),
        (2, 57849, "adv", "Obviously", 0, "Obviously, we need more chairs for the guests."),
        (3, 57849, "adv", "obviously", 0, "The bag was obviously too heavy for her."),
        (4, 57849, "adv", "obviously", 0, "She obviously knew the answer."),
        (5, 57849, "adv", "obviously", 0, "It was obviously safer to wait inside."),
    ],
    "old-fashioned": [
        (1, 57892, "adj", "old-fashioned", 1, "My grandfather still uses an old-fashioned camera with film."),
        (2, 57892, "adj", "old-fashioned", 0, "The shop sells old-fashioned sweets in glass jars."),
        (3, 57893, "adj", "old-fashioned", 0, "Her old-fashioned views surprised the younger workers."),
        (4, 57892, "adj", "old-fashioned", 0, "Writing letters by hand can seem old-fashioned now."),
        (5, 57892, "adj", "old-fashioned", 0, "They chose an old-fashioned stove for the cottage."),
    ],
    "operation": [
        (1, 57945, "noun", "operation", 1, "After the operation, the patient rested in a quiet room."),
        (2, 57945, "noun", "operation", 0, "The doctor explained how long the operation would take."),
        (3, 57944, "noun", "operation", 0, "The family business is a small operation with five workers."),
        (4, 57943, "noun", "operation", 0, "The rescue operation began at sunrise."),
        (5, 57940, "noun", "operation", 0, "The manual describes the safe operation of the machine."),
    ],
    "organizer": [
        (1, 57950, "noun", "organizer", 1, "The festival organizer checked that every band had a stage time."),
        (2, 57950, "noun", "organizer", 0, "Contact the event organizer if you need a ticket refund."),
        (3, 57952, "noun", "organizer", 0, "She writes appointments in her paper organizer."),
        (4, 57954, "noun", "organizer", 0, "The drawer organizer keeps my pens and clips separate."),
        (5, 57950, "noun", "organizer", 0, "The organizer sent volunteers their instructions by email."),
    ],
    "originally": [
        (1, 57938, "adv", "originally", 1, "This building was originally a train station."),
        (2, 57938, "adv", "originally", 0, "The plan originally included a larger garden."),
        (3, 57938, "adv", "originally", 0, "She originally wanted to study music."),
        (4, 57938, "adv", "originally", 0, "The recipe was originally created by his grandmother."),
        (5, 57938, "adv", "originally", 0, "We originally booked a room for two nights."),
    ],
    "ought": [
        (1, 57968, "verb", "ought", 1, "You ought to wear a helmet when riding a bicycle."),
        (2, 57969, "verb", "ought", 0, "We ought to leave now if we want to catch the train."),
        (3, 57968, "verb", "ought", 0, "Children ought to be kind to one another."),
        (4, 57971, "verb", "ought", 0, "The package ought to arrive by Friday."),
        (5, 57970, "verb", "ought", 0, "This new key ought to open the front door."),
    ],
    "ours": [
        (1, 57958, "pron", "ours", 1, "That blue suitcase is ours, not theirs."),
        (2, 57958, "pron", "ours", 0, "The table by the window is ours."),
        (3, 57958, "pron", "ours", 0, "Your garden is bigger than ours."),
        (4, 57961, "pron", "ours", 0, "The school team defended ours with great pride."),
        (5, 57958, "pron", "ours", 0, "Those coats are ours, so please do not move them."),
    ],
    "outdoor": [
        (1, 57955, "adj", "outdoor", 1, "We planned an outdoor picnic beside the lake."),
        (2, 57955, "adj", "outdoor", 0, "The camp offers outdoor activities such as climbing and kayaking."),
        (3, 57955, "adj", "outdoor", 0, "They bought outdoor chairs for the balcony."),
        (4, 57955, "adj", "outdoor", 0, "An outdoor concert is scheduled for Saturday evening."),
        (5, 57955, "adj", "outdoor", 0, "Wear outdoor shoes if the path is muddy."),
    ],
    "painful": [
        (1, 57980, "adj", "painful", 1, "It was painful to watch her leave without saying goodbye."),
        (2, 57980, "adj", "painful", 0, "Touching the cut was painful for several days."),
        (3, 57982, "adj", "painful", 0, "Filling out all the forms was a painful process."),
        (4, 57981, "adj", "painful", 0, "His injured shoulder was still painful this morning."),
        (5, 57980, "adj", "painful", 0, "The memory of that argument is painful for both of us."),
    ],
    "participate": [
        (1, 57999, "verb", "participate", 1, "Everyone can participate in the school sports day."),
        (2, 57999, "verb", "participate", 0, "Students must participate in the group discussion."),
        (3, 57999, "verb", "participated", 0, "More than fifty people participated in the clean-up."),
        (4, 57999, "verb", "participating", 0, "She is participating in a charity run this weekend."),
        (5, 57999, "verb", "participate", 0, "You do not have to participate if you feel unwell."),
    ],
    "path": [
        (1, 58094, "noun", "path", 1, "Follow the narrow path through the woods to reach the lake."),
        (2, 58094, "noun", "path", 0, "The path becomes steep after the bridge."),
        (3, 58096, "noun", "path", 0, "College put her on a new career path."),
        (4, 58097, "noun", "path", 0, "There is no easy path to learning a language."),
        (5, 58094, "noun", "path", 0, "Leaves covered the path after the storm."),
    ],
    "payment": [
        (1, 58082, "noun", "payment", 1, "I made the payment for the concert tickets online."),
        (2, 58082, "noun", "payment", 0, "Your payment is due by the end of the month."),
        (3, 58081, "noun", "payment", 0, "The store accepts payment by card or cash."),
        (4, 58082, "noun", "payment", 0, "She received a payment for her freelance work."),
        (5, 58082, "noun", "payment", 0, "Please keep the receipt as proof of payment."),
    ],
}

all_blocks = dict(blocks)
all_blocks.update(pass_blocks)

# ---- Thai explanations: headword -> list of 5 strings ----
expl = {
"nuclear": [
    "nuclear เป็นคำคุณศัพท์ (adj) แปลว่าเกี่ยวกับพลังงานนิวเคลียร์ ขยายคำนาม accident เพื่อบอกชนิดของอุบัติเหตุ",
    "Nuclear ในที่นี้เป็น adj บอกความหมายตรงตัวว่า 'เกี่ยวกับนิวเคลียสของอะตอม' ขึ้นต้นประโยคจึงเขียนตัวใหญ่",
    "nuclear เป็น adj ขยาย reactions หมายถึงปฏิกิริยาที่เกี่ยวกับพลังงานนิวเคลียร์ ไม่ใช่แค่นิวเคลียสของอะตอมเฉยๆ",
    "nuclear เป็น adj ขยาย physics บอกว่าเป็นวิชาฟิสิกส์ที่ศึกษานิวเคลียสของอะตอม",
    "nuclear ในประโยคนี้เป็นคำนาม (noun) ใช้แทน 'พลังงานนิวเคลียร์' โดยละคำว่า power ไว้ในฐาน เหมือนพูดถึงแหล่งพลังงานชนิดหนึ่ง",
],
"obvious": [
    "obvious เป็น adj แปลว่าเห็นได้ชัด ใช้ตามหลัง was เพื่อบรรยายสภาพที่ทุกคนสังเกตเห็นได้ว่าเด็กเหนื่อย",
    "obvious เป็น adj ขยายความรู้สึกหลัง was บอกว่าคำตอบชัดเจนหลังจากอ่านคำใบ้แล้ว",
    "obvious เป็น adj อยู่หลังกรรม the rain โดยมี made...obvious แปลว่าทำให้ฝนสังเกตเห็นได้ชัด",
    "obvious เป็น adj ขยายคำนาม mistake อยู่หน้าคำนามโดยตรง บอกว่าความผิดพลาดนั้นเห็นได้ง่าย",
    "obvious เป็น adj ตามหลัง is บอกว่าทางเดินมองเห็นได้ชัดเจนตั้งแต่ประตูรั้ว",
],
"obviously": [
    "obviously เป็นคำวิเศษณ์ (adv) ขยายกริยา was happy บอกระดับความชัดเจนของความรู้สึกดีใจ",
    "Obviously วางต้นประโยคทำหน้าที่ adv แสดงความเห็นของผู้พูดว่าสิ่งที่ตามมาเป็นเรื่องชัดเจนอยู่แล้ว",
    "obviously เป็น adv ขยาย was too heavy บอกว่าเห็นได้ชัดว่ากระเป๋าหนักเกินไป",
    "obviously เป็น adv แทรกกลางประโยคขยาย knew บอกว่าเธอรู้คำตอบอย่างชัดเจน",
    "obviously เป็น adv ขยาย safer บอกว่าการรอข้างในปลอดภัยกว่าอย่างเห็นได้ชัด",
],
"occasion": [
    "occasion เป็นคำนาม (noun) แปลว่าโอกาสหรือวาระพิเศษ ในที่นี้หมายถึงงานรวมญาติที่มีความหมายพิเศษต่อครอบครัว",
    "occasioned เป็นกริยา (verb) รูปอดีตของ occasion แปลว่า 'เป็นเหตุให้เกิด' ใช้ -ed เพราะเล่าเหตุการณ์ที่ผ่านมาแล้วคือฝนทำให้น้ำท่วม",
    "occasion เป็น noun หมายถึงโอกาสหรือเหตุการณ์ที่เป็นทางการ ในที่นี้คือโอกาสที่ต้องแต่งตัวเป็นทางการ",
    "occasion เป็น noun แปลว่าโอกาสพิเศษ ใช้เก็บเค้กชิ้นสุดท้ายไว้รอโอกาสนั้น",
    "occasion เป็น noun หมายถึงโอกาสอันเหมาะสม วันเกิดของเธอคือโอกาสที่เหมาะจะไปปิกนิก",
],
"occur": [
    "occurred เป็นกริยาช่องที่ 2 (past) ของ occur แปลว่าเกิดขึ้น เติม -ed เพราะเล่าเหตุการณ์ไฟดับที่เกิดขึ้นแล้วในอดีต",
    "occur เป็นกริยาช่องพื้นฐาน (base form) หลัง can แปลว่าอาจเกิดขึ้น เมื่อมี modal verb ตามด้วยกริยาช่องที่ 1 เสมอ",
    "occurring เป็นกริยาเติม -ing หลัง keep แปลว่ายังคงเกิดขึ้นซ้ำๆ โครงสร้าง keep + V-ing บอกการกระทำต่อเนื่อง",
    "occurs เป็นกริยาเติม -s เพราะประธาน this kind of problem เป็นเอกพจน์บุรุษที่สาม ในประโยค present simple",
    "occur เป็นกริยาช่องพื้นฐานหลัง can แปลว่าไฟป่าอาจเกิดขึ้นได้ในสภาพอากาศแห้งมาก",
],
"odd": [
    "odd เป็น adj แปลว่าแปลกหรือผิดปกติ ขยายความรู้สึกที่แปลกใจเมื่อเห็นหิมะกลางฤดูร้อน",
    "odd เป็น adj ขยาย something หมายถึงมีบางอย่างแปลกๆ ในพฤติกรรมที่เขาหลบสายตา",
    "odd เป็น adj ขยาย smell บอกว่ากลิ่นในครัวนั้นผิดปกติ",
    "odds เป็นคำนาม (noun) พหูพจน์ แปลว่าของกระจุกกระจิกที่เหลือไม่เข้าชุด เติม -s เพราะเป็นสิ่งของหลายชิ้นปนกัน",
    "odd เป็น adj ขยาย sound บอกว่าเครื่องจักรส่งเสียงที่ฟังแปลกหู",
],
"official": [
    "official เป็น adj ขยาย schedule แปลว่าเป็นทางการ/ได้รับการรับรอง บอกว่าตารางสอบนั้นออกอย่างเป็นทางการแล้ว",
    "official เป็น adj ขยาย announcement แปลว่ามาจากหน่วยงานที่มีอำนาจ ต้องรอประกาศที่เป็นทางการก่อนจอง",
    "officials เป็นคำนาม (noun) พหูพจน์ แปลว่าเจ้าหน้าที่ผู้มีอำนาจ เติม -s เพราะมีเจ้าหน้าที่สนามหลายคนหยุดเกม",
    "official เป็น adj ขยาย documents แปลว่าเป็นเอกสารที่ทางการรับรอง ด่านชายแดนยอมรับเฉพาะเอกสารประเภทนี้",
    "official เป็น adj ขยาย role แปลว่าเป็นหน้าที่ทางการของเขาคือตรวจกฎความปลอดภัย",
],
"old-fashioned": [
    "old-fashioned เป็น adj ขยาย camera แปลว่าล้าสมัย ใช้บรรยายกล้องรุ่นเก่าที่ยังใช้ฟิล์มอยู่",
    "old-fashioned เป็น adj ขยาย sweets แปลว่าขนมแบบเก่าที่ไม่ทันสมัยแล้ว",
    "old-fashioned เป็น adj แต่ในที่นี้ใช้กับคน (her views) แปลว่ายึดถือธรรมเนียมแบบเก่า ไม่ใช่แค่วัตถุที่ล้าสมัย",
    "old-fashioned เป็น adj ขยาย seem แปลว่าการเขียนจดหมายด้วยมืออาจดูล้าสมัยในปัจจุบัน",
    "old-fashioned เป็น adj ขยาย stove แปลว่าพวกเขาเลือกเตาแบบเก่าสำหรับกระท่อม",
],
"operation": [
    "operation เป็นคำนาม (noun) แปลว่าการผ่าตัด หลังจากผ่าตัดเสร็จผู้ป่วยได้พักในห้องเงียบๆ",
    "operation เป็น noun ความหมายเดียวกับข้างต้นคือการผ่าตัด หมอจึงอธิบายว่าจะใช้เวลานานเท่าไร",
    "operation เป็น noun ในที่นี้แปลว่ากิจการหรือธุรกิจ ธุรกิจครอบครัวขนาดเล็กมีคนงานห้าคน",
    "operation เป็น noun แปลว่าปฏิบัติการที่วางแผนไว้ ปฏิบัติการกู้ภัยเริ่มตอนพระอาทิตย์ขึ้น",
    "operation เป็น noun แปลว่าวิธีการทำงานของอุปกรณ์ คู่มืออธิบายวิธีใช้งานเครื่องจักรอย่างปลอดภัย",
],
"organized": [
    "organized เป็น adj บรรยายลักษณะนิสัยของครูที่มีระเบียบ รู้ตำแหน่งของกระดาษทุกแผ่นเสมอ",
    "organized เป็นกริยาช่องที่ 3 (past participle) ในโครงสร้าง passive voice was organized by แปลว่าถูกจัดขึ้นโดยกลุ่มนักเรียน",
    "organized เป็น adj บรรยายนิสัยนักเรียนที่วางแผนการบ้านก่อนวันหยุด",
    "organized เป็น adj บรรยายลักษณะของโต๊ะทำงาน (สิ่งของ) ว่าเป็นระเบียบจนหารายงานเจอง่าย",
    "organized เป็น adj บรรยายนิสัยของเขาที่มีระเบียบพอจะมาประชุมก่อนเวลาเสมอ",
],
"organizer": [
    "organizer เป็นคำนาม (noun) แปลว่าผู้จัดงาน ในที่นี้คือคนที่จัดเทศกาลดนตรีให้แต่ละวงมีเวลาขึ้นเวที",
    "organizer เป็น noun แปลว่าผู้จัดงาน ให้ติดต่อผู้จัดงานหากต้องการขอเงินคืนค่าตั๋ว",
    "organizer เป็น noun ในที่นี้แปลว่าสมุดจดบันทึกนัดหมาย ไม่ใช่คนแต่เป็นสิ่งของ",
    "organizer เป็น noun แปลว่ากล่องจัดระเบียบในลิ้นชัก ใช้แยกปากกาและคลิปหนีบกระดาษ",
    "organizer เป็น noun แปลว่าผู้จัดงาน ส่งคำแนะนำให้อาสาสมัครทางอีเมล",
],
"originally": [
    "originally เป็น adv แปลว่าแต่เดิม ขยายทั้งประโยค บอกว่าอาคารนี้เดิมทีเป็นสถานีรถไฟ",
    "originally เป็น adv ขยาย included บอกว่าแผนเดิมทีมีสวนที่ใหญ่กว่านี้",
    "originally เป็น adv ขยาย wanted บอกว่าแต่แรกเธอต้องการเรียนดนตรี",
    "originally เป็น adv ขยาย was created บอกว่าสูตรอาหารนี้ถูกคิดค้นขึ้นครั้งแรกโดยยายของเขา",
    "originally เป็น adv ขยาย booked บอกว่าแต่เดิมพวกเราจองห้องพักไว้สองคืน",
],
"ought": [
    "ought เป็นกริยาช่วย (modal verb) ตามด้วย to + infinitive แสดงหน้าที่หรือข้อบังคับ ควรสวมหมวกกันน็อกตอนขี่จักรยาน",
    "ought เป็น modal verb ในที่นี้แสดงความเหมาะสม/ความรอบคอบ ควรออกเดินทางตอนนี้เพื่อให้ทันรถไฟ",
    "ought เป็น modal verb แสดงหน้าที่ทางศีลธรรม เด็กควรมีน้ำใจต่อกัน",
    "ought เป็น modal verb ในที่นี้แสดงความเป็นไปได้/การคาดคะเน พัสดุน่าจะมาถึงภายในวันศุกร์",
    "ought เป็น modal verb แสดงความคาดหวังว่ากุญแจดอกใหม่นี้น่าจะเปิดประตูหน้าได้",
],
"ours": [
    "ours เป็นสรรพนามแสดงความเป็นเจ้าของ (possessive pronoun) ใช้แทน 'ของเรา' โดยไม่ต้องตามด้วยคำนาม กระเป๋าสีฟ้าใบนั้นเป็นของเรา",
    "ours เป็น possessive pronoun ใช้แทนคำนามที่รู้กันอยู่แล้ว (the table) หมายถึงโต๊ะนั้นเป็นของเรา",
    "ours เป็น possessive pronoun เปรียบเทียบกับ your garden โดยไม่ซ้ำคำว่า garden อีกครั้ง",
    "ours ในที่นี้ยังเป็น possessive pronoun แต่หมายถึงทีมของโรงเรียนเรา (กลุ่มที่ผู้พูดสังกัดอยู่) ไม่ใช่แค่ของบุคคล",
    "ours เป็น possessive pronoun ใช้แทนเสื้อโค้ตหลายตัวที่เป็นของเรา จึงขอให้อย่าย้ายมัน",
],
"outdoor": [
    "outdoor เป็น adj ใช้ขยายคำนามเสมอ (ไม่ใช้เดี่ยวๆ) ขยาย picnic บอกว่าเป็นปิกนิกกลางแจ้งริมทะเลสาบ",
    "outdoor เป็น adj ขยาย activities บอกว่ากิจกรรมกลางแจ้งเช่นปีนเขาและพายเรือคายัค",
    "outdoor เป็น adj ขยาย chairs บอกว่าเป็นเก้าอี้สำหรับใช้กลางแจ้งที่ระเบียง",
    "outdoor เป็น adj ขยาย concert บอกว่าคอนเสิร์ตกลางแจ้งมีกำหนดจัดเย็นวันเสาร์",
    "outdoor เป็น adj ขยาย shoes บอกว่าควรใส่รองเท้าลุยกลางแจ้งถ้าทางเดินเป็นโคลน",
],
"outdoors": [
    "outdoors เป็นคำวิเศษณ์ (adv) แปลว่ากลางแจ้ง ขยายกริยา played บอกว่าเด็กๆ เล่นข้างนอกจนถึงเวลาอาหารเย็น",
    "outdoors เป็น adv ขยาย eat บอกว่าอากาศหนาวเกินกว่าจะกินอาหารกลางแจ้งวันนี้",
    "outdoors เป็น adv ขยาย exercising บอกว่าชอบออกกำลังกายกลางแจ้งตอนเช้า",
    "outdoors ในที่นี้เป็นคำนาม (noun) มักใช้กับ the นำหน้า แปลว่าธรรมชาติกลางแจ้ง เธอชอบธรรมชาติกลางแจ้งโดยเฉพาะในฤดูใบไม้ร่วง",
    "outdoors เป็น adv ขยาย slept บอกว่าพวกเขานอนกลางแจ้งใต้ดวงดาว",
],
"package": [
    "package เป็นคำนาม (noun) แปลว่าพัสดุหรือห่อของ มีพัสดุที่มีชื่อฉันรออยู่ที่ประตู",
    "package เป็น noun ความหมายเดียวกันคือห่อพัสดุ พนักงานส่งของทิ้งพัสดุไว้กับเพื่อนบ้าน",
    "package เป็น noun ในที่นี้แปลว่าแพ็กเกจท่องเที่ยวที่รวมหลายอย่างเข้าด้วยกัน (ตั๋วเครื่องบิน+โรงแรม)",
    "package เป็น noun แปลว่าชุดซอฟต์แวร์ที่ติดตั้งได้ ต้องติดตั้งแพ็กเกจซอฟต์แวร์ก่อนเปิดโปรแกรม",
    "packages เป็นกริยา (verb) เติม -s เพราะประธาน the factory เป็นเอกพจน์บุรุษที่สาม แปลว่าโรงงานบรรจุของเล่นลงกล่องก่อนส่ง",
],
"painful": [
    "painful เป็น adj แปลว่าทำให้เจ็บปวดทั้งทางกายและใจ ในที่นี้คือความเจ็บปวดใจที่เห็นเธอจากไปโดยไม่บอกลา",
    "painful เป็น adj แปลว่าทำให้เจ็บ ในที่นี้คือความเจ็บทางกายจากการแตะแผล",
    "painful เป็น adj ในที่นี้แปลว่ายากลำบาก/ต้องใช้ความพยายาม ไม่ใช่ความเจ็บทางกาย การกรอกแบบฟอร์มทั้งหมดเป็นเรื่องยุ่งยาก",
    "painful เป็น adj แปลว่ายังเจ็บอยู่ ใช้กับอวัยวะที่บาดเจ็บคือไหล่ที่ยังปวดอยู่เช้านี้",
    "painful เป็น adj แปลว่าทำให้เจ็บปวดทางใจ ความทรงจำเรื่องทะเลาะกันยังเจ็บปวดสำหรับทั้งคู่",
],
"pale": [
    "pale เป็น adj แปลว่าซีดเผือด (เนื่องจากช็อกหรือตกใจ) บรรยายอาการของเธอหลังได้ยินข่าวร้ายกะทันหัน",
    "pale เป็น adj ในที่นี้แปลว่าสีอ่อน ไม่เกี่ยวกับสุขภาพ ขยายสีฟ้าอ่อนของเสื้อเชิ้ตที่เขาเลือกใส่สัมภาษณ์งาน",
    "paled เป็นกริยาช่องที่ 2 (past) ของ pale แปลว่าซีดลงเรื่อยๆ เติม -ed เพราะเล่าการเปลี่ยนแปลงที่เกิดขึ้นตลอดช่วงที่ป่วย",
    "pale เป็น adj แปลว่าสีอ่อน ขยายดวงจันทร์ที่ปรากฏสีจางเหนือต้นไม้",
    "pales เป็นกริยาเติม -s เพราะประธาน his effort เป็นเอกพจน์บุรุษที่สาม แปลว่า 'ด้อยกว่าเมื่อเทียบกับ' ใช้ในสำนวน pale in comparison to",
],
"pan": [
    "pan เป็นคำนาม (noun) แปลว่ากระทะ ใช้ตั้งไฟใส่น้ำมันก่อนใส่หัวหอม",
    "panned เป็นกริยาช่องที่ 2 (past) ในสำนวน pan out แปลว่า 'ลงเอยด้วยดี' เติม -ed เพราะเล่าผลลัพธ์ที่เกิดขึ้นแล้วของแผนงาน",
    "pan เป็น noun ในที่นี้แปลว่าหม้อ/กระทะทรงลึกสำหรับทำซุป",
    "pan เป็น noun แปลว่าถาดหรือกระทะสำหรับร่อนหาทองในลำธาร",
    "pan เป็น noun ในที่นี้แปลว่าคำวิจารณ์ที่รุนแรง (จากกริยา pan ที่แปลว่าวิจารณ์อย่างหนัก) นักวิจารณ์ให้คำวิจารณ์รุนแรงกับหนังเรื่องใหม่",
],
"participate": [
    "participate เป็นกริยาช่องพื้นฐานหลัง can แปลว่าเข้าร่วม ทุกคนสามารถเข้าร่วมกีฬาสีของโรงเรียนได้",
    "participate เป็นกริยาช่องพื้นฐานหลัง must แปลว่านักเรียนต้องเข้าร่วมการอภิปรายกลุ่ม",
    "participated เป็นกริยาช่องที่ 2 (past) เติม -ed เพราะเล่าเหตุการณ์ที่จบแล้วคือมีคนกว่าห้าสิบคนเข้าร่วมทำความสะอาด",
    "participating เป็นกริยาเติม -ing ใช้กับ is เพื่อสร้าง present continuous บอกว่าเธอกำลังเข้าร่วมวิ่งการกุศลสุดสัปดาห์นี้",
    "participate เป็นกริยาช่องพื้นฐานหลัง have to แปลว่าไม่จำเป็นต้องเข้าร่วมถ้ารู้สึกไม่สบาย",
],
"particularly": [
    "particularly เป็น adv แปลว่าโดยเฉพาะอย่างยิ่ง ขยาย enjoyed บอกว่าชอบบทสุดท้ายของหนังสือเป็นพิเศษ",
    "particularly เป็น adv ขยาย dangerous บอกว่าถนนอันตรายเป็นพิเศษเมื่อฝนตก",
    "particularly เป็น adv ในที่นี้แปลว่าโดยเฉพาะเจาะจง (specifically) กฎนี้ใช้เจาะจงกับพนักงานใหม่",
    "particularly เป็น adv ขยาย good บอกว่าเธอเก่งเป็นพิเศษในการอธิบายเรื่องยากๆ",
    "particularly เป็น adv ขยาย quiet บอกว่าต้องการห้องที่เงียบเป็นพิเศษสำหรับการสอบ",
],
"passion": [
    "passion เป็นคำนาม (noun) แปลว่าความหลงใหล ในที่นี้คือความหลงใหลในการทำอาหารที่เริ่มตั้งแต่เด็ก",
    "passion เป็น noun แปลว่าความหลงใหล/ความกระตือรือร้น เขาพูดถึงดนตรีด้วยความหลงใหลอย่างแท้จริง",
    "passion เป็น noun ในที่นี้แปลว่าความรู้สึกอันแรงกล้าร่วมกัน ความหลงใหลที่มีร่วมกันทำให้พวกเขาสนิทกันมากขึ้น",
    "passion เป็น noun ในที่นี้แปลว่าสิ่งที่รักเป็นพิเศษ (สิ่งของ/กิจกรรมที่เป็นความหลงใหล) การวาดภาพไม่ใช่แค่งานอดิเรกแต่เป็นความหลงใหลของเธอ",
    "passion เป็น noun แปลว่าความมุ่งมั่น/ไฟในการเล่น ทีมเล่นด้วยความมุ่งมั่นจนถึงนกหวีดหมดเวลา",
],
"path": [
    "path เป็นคำนาม (noun) แปลว่าทางเดิน เดินตามทางแคบๆ ผ่านป่าเพื่อไปถึงทะเลสาบ",
    "path เป็น noun ความหมายเดียวกันคือทางเดิน บอกว่าทางเดินชันขึ้นหลังสะพาน",
    "path เป็น noun ในที่นี้ใช้เชิงเปรียบเทียบ (metaphor) แปลว่าเส้นทางอาชีพ ไม่ใช่ทางเดินจริง",
    "path เป็น noun ในที่นี้แปลว่าวิธีการหรือแนวทาง ไม่มีทางลัดง่ายๆ ในการเรียนภาษา",
    "path เป็น noun แปลว่าทางเดินจริง ใบไม้ปกคลุมทางเดินหลังพายุผ่านไป",
],
"payment": [
    "payment เป็นคำนาม (noun) แปลว่าจำนวนเงินที่จ่าย ในที่นี้คือเงินที่จ่ายค่าตั๋วคอนเสิร์ตทางออนไลน์",
    "payment เป็น noun ความหมายเดียวกันคือยอดเงินที่ต้องจ่าย ครบกำหนดสิ้นเดือนนี้",
    "payment เป็น noun ในที่นี้แปลว่าการกระทำของการจ่ายเงิน (วิธีชำระ) ร้านรับชำระด้วยบัตรหรือเงินสด",
    "payment เป็น noun แปลว่าเงินที่ได้รับจากการทำงาน เธอได้รับเงินค่าจ้างงานฟรีแลนซ์",
    "payment เป็น noun แปลว่าหลักฐานการจ่ายเงิน เก็บใบเสร็จไว้เป็นหลักฐานการชำระเงิน",
],
}

order = [
 "nuclear","obvious","obviously","occasion","occur","odd","official","old-fashioned",
 "operation","organized","organizer","originally","ought","ours","outdoor","outdoors",
 "package","painful","pale","pan","participate","particularly","passion","path","payment",
]

# sanity: report list order matches `order`
assert [r[0] for r in report] == order, "report order mismatch"

status = {hw: st for hw, st, _ in report}

# ---- write report tsv ----
rep_path = os.path.join(ROOT, "data", "sol_review_reports", "sol_review_2076_2100.tsv")
with io.open(rep_path, "w", encoding="utf-8", newline="\n") as f:
    for hw, st, reason in report:
        f.write(f"{hw}\t{st}\t{reason}\n")

# ---- write overlay draft (repaired words only) ----
draft_path = os.path.join(ROOT, "data", "sol_review_drafts", "sol_repair_2076_2100.txt")
repaired_words = [hw for hw, st, _ in report if st == "repaired"]
with io.open(draft_path, "w", encoding="utf-8", newline="\n") as f:
    for hw in repaired_words:
        f.write(f"@ {hw}\n")
        for rank, sense_id, pos, target, mem, sentence in blocks[hw]:
            f.write(f"{rank}\t{sense_id}\t{pos}\t{target}\t{mem}\t{sentence}\n")

# ---- write explanations tsv ----
expl_path = os.path.join(ROOT, "data", "sol_review_explanations", "expl_2076_2100.tsv")
with io.open(expl_path, "w", encoding="utf-8", newline="\n") as f:
    for hw in order:
        for rank in range(1, 6):
            f.write(f"{hw}\t{rank}\t{expl[hw][rank-1]}\n")

print("wrote", rep_path)
print("wrote", draft_path)
print("wrote", expl_path)

# ---- self-check ----
errors = []
for hw in order:
    blk = all_blocks[hw]
    assert len(blk) == 5, hw
    ranks = [b[0] for b in blk]
    assert ranks == [1,2,3,4,5], (hw, ranks)
    mems = [b[4] for b in blk]
    assert mems == [1,0,0,0,0], (hw, mems)
    sentences_lower = [b[5].lower() for b in blk]
    if len(set(sentences_lower)) != 5:
        errors.append((hw, "duplicate sentence"))
    r1_words = len(blk[0][5].split())
    if r1_words < 6:
        errors.append((hw, "rank1 too short"))
    banned = ["is important", "are important", "was important", "were important", "this word", "this sentence"]
    for rank, sid, pos, target, mem, sent in blk:
        low = sent.lower()
        for b in banned:
            if b in low:
                errors.append((hw, rank, "banned phrase"))
        pat = re.compile(r'(?<![A-Za-z])' + re.escape(target) + r'(?![A-Za-z])')
        matches = pat.findall(sent)
        if len(matches) != 1:
            errors.append((hw, rank, f"target '{target}' occurs {len(matches)} times"))
        # case check: exact substring present
        if target not in sent:
            errors.append((hw, rank, f"target case mismatch: '{target}' not literally in sentence"))

if errors:
    print("SELF-CHECK ERRORS:")
    for e in errors:
        print(" ", e)
else:
    print("SELF-CHECK: all good")

# explanations check
for hw in order:
    rows = expl[hw]
    assert len(rows) == 5, hw
    if len(set(rows)) != 5:
        print("EXPL DUP:", hw)
