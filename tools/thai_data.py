# -*- coding: utf-8 -*-
"""
Thai gloss / reading / collocation data per headword.

SOURCE (2026-07-22 pass): meaning_th is now cross-checked against REAL
Thai-language translation data fetched from wiktapi.dev
(GET https://api.wiktapi.dev/v1/en/word/{word}/translations), which mirrors
en.wiktionary.org's own Translations tables (CC BY-SA -- see NOTES.md for
the exact current license version, corrected from the previously-recorded
3.0). For each of the 153 headwords below, every Thai (lang_code="th")
translation entry returned for the word's part of speech was collected,
then one was picked using this priority:
  1. If one of those real Wiktionary Thai words is an EXACT match for a
     term already in this file's previous hand-authored meaning_th (split
     on comma/slash), keep that word -- this both validates the prior
     manual gloss as a real, correctly-sensed dictionary word AND preserves
     the original author's sense-priority ordering (e.g. "old":
     "แก่, เก่า" kept แก่ since it was listed first).
  2. Else, among the real candidates for that POS, prefer whichever one
     is a substring of this word's own collocation_th -- the collocation
     was hand-authored earlier to demonstrate the specific sense this app
     actually drills, so it is a reliable sense-disambiguator when the
     original meaning_th was a compound/paraphrase not itself listed as a
     separate Wiktionary translation entry (11 words needed this:
     after, again, beautiful, different, evening, eye, kitchen, live,
     sleep, talk, and light as a same-tier fallback -- see NOTES.md
     section 2 for the exact before/after list and reasoning per word).
  3. If wiktapi.dev returned NO Thai translation at all for the word's POS
     (this happened for exactly one word, "make" -- a very polysemous verb
     whose Wiktionary translation table apparently has no Thai row for any
     of its senses), the previous hand-authored value is KEPT UNCHANGED
     and NOTES.md explicitly flags it as still-approximated, per this
     pass's brief -- not silently left looking equally "sourced" as the
     other 152.
40 of 153 words changed meaning_th value as a result of this cross-check
(113 already matched a real Wiktionary word exactly, unchanged). The
"roman" field wiktapi.dev returns alongside each Thai word was used only
to sanity-check that the wiktapi entry and this file's existing
thai_reading refer to the same word/sense -- thai_reading and stress_index
themselves are still derived by hand from "ipa" (a specific Thai-script
transliteration with syllable-break hyphens is more detailed than
wiktapi's loose romanization), exactly as before this pass.

translation_source is now recorded in build_dataset.py as a clean
"Wiktionary" (previously "Wiktionary (approximated)") for all headwords
except "make", which keeps the approximated marker. See NOTES.md section 2
for the full per-word accounting, the license correction, and the "make"
exception.
"""

DATA = {
'about': dict(meaning_th='เกี่ยวกับ', thai_reading='อะ-เบาท์', stress_index=2, ipa='/əˈbaʊt/', countable=None, collocation_en='talk about it', collocation_th='พูดถึงเรื่องนั้น'),
'after': dict(meaning_th='หลัง', thai_reading='อาฟ-เทอะ', stress_index=1, ipa='/ˈɑːftə/', countable=None, collocation_en='after school', collocation_th='หลังเลิกเรียน'),
'again': dict(meaning_th='อีก', thai_reading='อะ-เกน', stress_index=2, ipa='/əˈɡen/', countable=None, collocation_en='try again', collocation_th='ลองอีกครั้ง'),
'all': dict(meaning_th='ทั้งหมด', thai_reading='ออล', stress_index=1, ipa='/ɔːl/', countable=None, collocation_en='all day', collocation_th='ทั้งวัน'),
'also': dict(meaning_th='ด้วย', thai_reading='ออล-โซว', stress_index=1, ipa='/ˈɔːlsəʊ/', countable=None, collocation_en='also like', collocation_th='ชอบด้วยเหมือนกัน'),
'and': dict(meaning_th='และ', thai_reading='แอนด์', stress_index=1, ipa='/ænd/', countable=None, collocation_en='you and me', collocation_th='คุณกับฉัน'),
'answer': dict(meaning_th='ตอบ', thai_reading='แอน-เซอะ', stress_index=1, ipa='/ˈɑːnsə/', countable=1, collocation_en='answer the phone', collocation_th='รับโทรศัพท์'),
'ask': dict(meaning_th='ถาม', thai_reading='อาสก์', stress_index=1, ipa='/ɑːsk/', countable=None, collocation_en='ask a question', collocation_th='ถามคำถาม'),
'baby': dict(meaning_th='ทารก', thai_reading='เบ-บี', stress_index=1, ipa='/ˈbeɪbi/', countable=1, collocation_en='a new baby', collocation_th='ทารกแรกเกิด'),
'bad': dict(meaning_th='แย่', thai_reading='แบด', stress_index=1, ipa='/bæd/', countable=None, collocation_en='a bad day', collocation_th='วันที่แย่'),
'bag': dict(meaning_th='กระเป๋า', thai_reading='แบก', stress_index=1, ipa='/bæɡ/', countable=1, collocation_en='carry a bag', collocation_th='ถือกระเป๋า'),
'beautiful': dict(meaning_th='สวย', thai_reading='บิว-ทิ-ฟุล', stress_index=1, ipa='/ˈbjuːtɪfl/', countable=None, collocation_en='a beautiful view', collocation_th='วิวที่สวยงาม'),
'bed': dict(meaning_th='เตียง', thai_reading='เบด', stress_index=1, ipa='/bed/', countable=1, collocation_en='go to bed', collocation_th='เข้านอน'),
'big': dict(meaning_th='ใหญ่', thai_reading='บิก', stress_index=1, ipa='/bɪɡ/', countable=None, collocation_en='a big house', collocation_th='บ้านหลังใหญ่'),
'bird': dict(meaning_th='นก', thai_reading='เบิร์ด', stress_index=1, ipa='/bɜːd/', countable=1, collocation_en='a small bird', collocation_th='นกตัวเล็ก'),
'book': dict(meaning_th='หนังสือ', thai_reading='บุค', stress_index=1, ipa='/bʊk/', countable=1, collocation_en='read a book', collocation_th='อ่านหนังสือ'),
'boy': dict(meaning_th='เด็กชาย', thai_reading='บอย', stress_index=1, ipa='/bɔɪ/', countable=1, collocation_en='a young boy', collocation_th='เด็กชายตัวเล็ก'),
'bread': dict(meaning_th='ขนมปัง', thai_reading='เบรด', stress_index=1, ipa='/bred/', countable=0, collocation_en='fresh bread', collocation_th='ขนมปังสด'),
'brother': dict(meaning_th='พี่ชาย', thai_reading='บรา-เธอะ', stress_index=1, ipa='/ˈbrʌðə/', countable=1, collocation_en='my older brother', collocation_th='พี่ชายของฉัน'),
'busy': dict(meaning_th='ยุ่ง', thai_reading='บิ-ซี', stress_index=1, ipa='/ˈbɪzi/', countable=None, collocation_en='a busy day', collocation_th='วันที่ยุ่ง'),
'buy': dict(meaning_th='ซื้อ', thai_reading='บาย', stress_index=1, ipa='/baɪ/', countable=None, collocation_en='buy food', collocation_th='ซื้ออาหาร'),
'car': dict(meaning_th='รถยนต์', thai_reading='คาร์', stress_index=1, ipa='/kɑː/', countable=1, collocation_en='drive a car', collocation_th='ขับรถ'),
'cat': dict(meaning_th='แมว', thai_reading='แคท', stress_index=1, ipa='/kæt/', countable=1, collocation_en='feed the cat', collocation_th='ให้อาหารแมว'),
'chair': dict(meaning_th='เก้าอี้', thai_reading='แชร์', stress_index=1, ipa='/tʃeə/', countable=1, collocation_en='sit on a chair', collocation_th='นั่งบนเก้าอี้'),
'child': dict(meaning_th='เด็ก', thai_reading='ไชลด์', stress_index=1, ipa='/tʃaɪld/', countable=1, collocation_en='a young child', collocation_th='เด็กเล็ก'),
'city': dict(meaning_th='เมือง', thai_reading='ซิ-ที', stress_index=1, ipa='/ˈsɪti/', countable=1, collocation_en='a big city', collocation_th='เมืองใหญ่'),
'clean': dict(meaning_th='สะอาด', thai_reading='คลีน', stress_index=1, ipa='/kliːn/', countable=None, collocation_en='clean the house', collocation_th='ทำความสะอาดบ้าน'),
'clothes': dict(meaning_th='เสื้อผ้า', thai_reading='โคลธซ์', stress_index=1, ipa='/kləʊðz/', countable=0, collocation_en='new clothes', collocation_th='เสื้อผ้าใหม่'),
'cold': dict(meaning_th='หนาว', thai_reading='โคลด์', stress_index=1, ipa='/kəʊld/', countable=None, collocation_en='a cold day', collocation_th='วันที่หนาว'),
'come': dict(meaning_th='มา', thai_reading='คัม', stress_index=1, ipa='/kʌm/', countable=None, collocation_en='come home', collocation_th='กลับบ้าน'),
'cook': dict(meaning_th='ทำอาหาร', thai_reading='คุค', stress_index=1, ipa='/kʊk/', countable=None, collocation_en='cook dinner', collocation_th='ทำอาหารเย็น'),
'dance': dict(meaning_th='เต้นรำ', thai_reading='ดานซ์', stress_index=1, ipa='/dɑːns/', countable=None, collocation_en='dance all night', collocation_th='เต้นรำทั้งคืน'),
'day': dict(meaning_th='วัน', thai_reading='เดย์', stress_index=1, ipa='/deɪ/', countable=1, collocation_en='every day', collocation_th='ทุกวัน'),
'different': dict(meaning_th='ต่าง', thai_reading='ดิฟ-เฟอ-เรินท์', stress_index=1, ipa='/ˈdɪfrənt/', countable=None, collocation_en='a different place', collocation_th='สถานที่ที่แตกต่าง'),
'dog': dict(meaning_th='สุนัข', thai_reading='ดอก', stress_index=1, ipa='/dɒɡ/', countable=1, collocation_en='walk the dog', collocation_th='พาสุนัขไปเดิน'),
'door': dict(meaning_th='ประตู', thai_reading='ดอร์', stress_index=1, ipa='/dɔː/', countable=1, collocation_en='open the door', collocation_th='เปิดประตู'),
'drink': dict(meaning_th='ดื่ม', thai_reading='ดริงค์', stress_index=1, ipa='/drɪŋk/', countable=1, collocation_en='drink water', collocation_th='ดื่มน้ำ'),
'drive': dict(meaning_th='ขับรถ', thai_reading='ไดรฟ์', stress_index=1, ipa='/draɪv/', countable=None, collocation_en='drive to work', collocation_th='ขับรถไปทำงาน'),
'early': dict(meaning_th='เช้า', thai_reading='เอิร์-ลี', stress_index=1, ipa='/ˈɜːli/', countable=None, collocation_en='wake up early', collocation_th='ตื่นแต่เช้า'),
'easy': dict(meaning_th='ง่าย', thai_reading='อี-ซี', stress_index=1, ipa='/ˈiːzi/', countable=None, collocation_en='an easy question', collocation_th='คำถามที่ง่าย'),
'eat': dict(meaning_th='กิน', thai_reading='อีท', stress_index=1, ipa='/iːt/', countable=None, collocation_en='eat breakfast', collocation_th='กินอาหารเช้า'),
'egg': dict(meaning_th='ไข่', thai_reading='เอก', stress_index=1, ipa='/eɡ/', countable=1, collocation_en='a boiled egg', collocation_th='ไข่ต้ม'),
'evening': dict(meaning_th='เย็น', thai_reading='อีฟ-นิง', stress_index=1, ipa='/ˈiːvnɪŋ/', countable=1, collocation_en='this evening', collocation_th='เย็นนี้'),
'every': dict(meaning_th='ทุก ๆ', thai_reading='เอฟ-รี', stress_index=1, ipa='/ˈevri/', countable=None, collocation_en='every morning', collocation_th='ทุกเช้า'),
'eye': dict(meaning_th='ตา', thai_reading='อาย', stress_index=1, ipa='/aɪ/', countable=1, collocation_en='close your eyes', collocation_th='หลับตา'),
'family': dict(meaning_th='ครอบครัว', thai_reading='แฟม-อิ-ลี', stress_index=1, ipa='/ˈfæməli/', countable=1, collocation_en='a happy family', collocation_th='ครอบครัวที่มีความสุข'),
'far': dict(meaning_th='ไกล', thai_reading='ฟาร์', stress_index=1, ipa='/fɑː/', countable=None, collocation_en='far away', collocation_th='ไกลออกไป'),
'fast': dict(meaning_th='เร็ว', thai_reading='ฟาสท์', stress_index=1, ipa='/fɑːst/', countable=None, collocation_en='run fast', collocation_th='วิ่งเร็ว'),
'father': dict(meaning_th='พ่อ', thai_reading='ฟา-เธอะ', stress_index=1, ipa='/ˈfɑːðə/', countable=1, collocation_en='my father', collocation_th='พ่อของฉัน'),
'find': dict(meaning_th='พบ', thai_reading='ไฟนด์', stress_index=1, ipa='/faɪnd/', countable=None, collocation_en='find a job', collocation_th='หางาน'),
'fish': dict(meaning_th='ปลา', thai_reading='ฟิช', stress_index=1, ipa='/fɪʃ/', countable=1, collocation_en='catch a fish', collocation_th='จับปลา'),
'food': dict(meaning_th='อาหาร', thai_reading='ฟูด', stress_index=1, ipa='/fuːd/', countable=0, collocation_en='tasty food', collocation_th='อาหารอร่อย'),
'friend': dict(meaning_th='เพื่อน', thai_reading='เฟรนด์', stress_index=1, ipa='/frend/', countable=1, collocation_en='a good friend', collocation_th='เพื่อนที่ดี'),
'garden': dict(meaning_th='สวน', thai_reading='การ์-เดิน', stress_index=1, ipa='/ˈɡɑːdn/', countable=1, collocation_en='in the garden', collocation_th='ในสวน'),
'girl': dict(meaning_th='เด็กหญิง', thai_reading='เกิร์ล', stress_index=1, ipa='/ɡɜːl/', countable=1, collocation_en='a little girl', collocation_th='เด็กหญิงตัวเล็ก'),
'give': dict(meaning_th='ให้', thai_reading='กิฟ', stress_index=1, ipa='/ɡɪv/', countable=None, collocation_en='give a gift', collocation_th='ให้ของขวัญ'),
'go': dict(meaning_th='ไป', thai_reading='โกว', stress_index=1, ipa='/ɡəʊ/', countable=None, collocation_en='go home', collocation_th='กลับบ้าน'),
'good': dict(meaning_th='ดี', thai_reading='กุด', stress_index=1, ipa='/ɡʊd/', countable=None, collocation_en='a good idea', collocation_th='ความคิดที่ดี'),
'great': dict(meaning_th='ยอดเยี่ยม', thai_reading='เกรท', stress_index=1, ipa='/ɡreɪt/', countable=None, collocation_en='a great time', collocation_th='ช่วงเวลาที่ยอดเยี่ยม'),
'green': dict(meaning_th='สีเขียว', thai_reading='กรีน', stress_index=1, ipa='/ɡriːn/', countable=None, collocation_en='green grass', collocation_th='หญ้าสีเขียว'),
'happy': dict(meaning_th='มีความสุข', thai_reading='แฮพ-พี', stress_index=1, ipa='/ˈhæpi/', countable=None, collocation_en='a happy family', collocation_th='ครอบครัวที่มีความสุข'),
'hard': dict(meaning_th='ยาก', thai_reading='ฮาร์ด', stress_index=1, ipa='/hɑːd/', countable=None, collocation_en='a hard question', collocation_th='คำถามที่ยาก'),
'hat': dict(meaning_th='หมวก', thai_reading='แฮท', stress_index=1, ipa='/hæt/', countable=1, collocation_en='wear a hat', collocation_th='สวมหมวก'),
'have': dict(meaning_th='มี', thai_reading='แฮฟ', stress_index=1, ipa='/hæv/', countable=None, collocation_en='have time', collocation_th='มีเวลา'),
'hear': dict(meaning_th='ได้ยิน', thai_reading='เฮียร์', stress_index=1, ipa='/hɪə/', countable=None, collocation_en='hear a sound', collocation_th='ได้ยินเสียง'),
'help': dict(meaning_th='ช่วยเหลือ', thai_reading='เฮลพ์', stress_index=1, ipa='/help/', countable=None, collocation_en='help a friend', collocation_th='ช่วยเพื่อน'),
'home': dict(meaning_th='บ้าน', thai_reading='โฮม', stress_index=1, ipa='/həʊm/', countable=1, collocation_en='at home', collocation_th='ที่บ้าน'),
'hope': dict(meaning_th='หวัง', thai_reading='โฮพ', stress_index=1, ipa='/həʊp/', countable=None, collocation_en='hope for the best', collocation_th='หวังว่าจะดีที่สุด'),
'hot': dict(meaning_th='ร้อน', thai_reading='ฮอท', stress_index=1, ipa='/hɒt/', countable=None, collocation_en='a hot day', collocation_th='วันที่ร้อน'),
'house': dict(meaning_th='บ้าน', thai_reading='เฮาส์', stress_index=1, ipa='/haʊs/', countable=1, collocation_en='a big house', collocation_th='บ้านหลังใหญ่'),
'hungry': dict(meaning_th='หิว', thai_reading='ฮัง-กรี', stress_index=1, ipa='/ˈhʌŋɡri/', countable=None, collocation_en='very hungry', collocation_th='หิวมาก'),
'husband': dict(meaning_th='สามี', thai_reading='ฮัส-เบินด์', stress_index=1, ipa='/ˈhʌzbənd/', countable=1, collocation_en='my husband', collocation_th='สามีของฉัน'),
'job': dict(meaning_th='งาน', thai_reading='จอบ', stress_index=1, ipa='/dʒɒb/', countable=1, collocation_en='a new job', collocation_th='งานใหม่'),
'kitchen': dict(meaning_th='ครัว', thai_reading='คิท-เชิน', stress_index=1, ipa='/ˈkɪtʃɪn/', countable=1, collocation_en='in the kitchen', collocation_th='ในห้องครัว'),
'know': dict(meaning_th='รู้', thai_reading='โนว', stress_index=1, ipa='/nəʊ/', countable=None, collocation_en='know the answer', collocation_th='รู้คำตอบ'),
'language': dict(meaning_th='ภาษา', thai_reading='แลง-กวิจ', stress_index=1, ipa='/ˈlæŋɡwɪdʒ/', countable=1, collocation_en='learn a language', collocation_th='เรียนภาษา'),
'late': dict(meaning_th='สาย', thai_reading='เลท', stress_index=1, ipa='/leɪt/', countable=None, collocation_en='arrive late', collocation_th='มาสาย'),
'laugh': dict(meaning_th='หัวเราะ', thai_reading='ลาฟ', stress_index=1, ipa='/lɑːf/', countable=None, collocation_en='laugh loudly', collocation_th='หัวเราะเสียงดัง'),
'learn': dict(meaning_th='เรียนรู้', thai_reading='เลิร์น', stress_index=1, ipa='/lɜːn/', countable=None, collocation_en='learn English', collocation_th='เรียนภาษาอังกฤษ'),
'light': dict(meaning_th='แสง', thai_reading='ไลท์', stress_index=1, ipa='/laɪt/', countable=1, collocation_en='turn on the light', collocation_th='เปิดไฟ'),
'like': dict(meaning_th='ชอบ', thai_reading='ไลค์', stress_index=1, ipa='/laɪk/', countable=None, collocation_en='like music', collocation_th='ชอบเพลง'),
'listen': dict(meaning_th='ฟัง', thai_reading='ลิส-เซิน', stress_index=1, ipa='/ˈlɪsn/', countable=None, collocation_en='listen to music', collocation_th='ฟังเพลง'),
'little': dict(meaning_th='เล็ก', thai_reading='ลิท-เทิล', stress_index=1, ipa='/ˈlɪtl/', countable=None, collocation_en='a little water', collocation_th='น้ำนิดหน่อย'),
'live': dict(meaning_th='อยู่', thai_reading='ลิฟ', stress_index=1, ipa='/lɪv/', countable=None, collocation_en='live in a city', collocation_th='อาศัยอยู่ในเมือง'),
'long': dict(meaning_th='ยาว', thai_reading='ลอง', stress_index=1, ipa='/lɒŋ/', countable=None, collocation_en='a long day', collocation_th='วันที่ยาวนาน'),
'look': dict(meaning_th='มอง', thai_reading='ลุค', stress_index=1, ipa='/lʊk/', countable=None, collocation_en='look at the sky', collocation_th='มองท้องฟ้า'),
'love': dict(meaning_th='รัก', thai_reading='ลัฟ', stress_index=1, ipa='/lʌv/', countable=None, collocation_en='love your family', collocation_th='รักครอบครัวของคุณ'),
'lunch': dict(meaning_th='อาหารกลางวัน', thai_reading='ลันช์', stress_index=1, ipa='/lʌntʃ/', countable=1, collocation_en='have lunch', collocation_th='กินข้าวเที่ยง'),
'make': dict(meaning_th='ทำ, สร้าง', thai_reading='เมค', stress_index=1, ipa='/meɪk/', countable=None, collocation_en='make a cake', collocation_th='ทำเค้ก'),
'man': dict(meaning_th='ผู้ชาย', thai_reading='แมน', stress_index=1, ipa='/mæn/', countable=1, collocation_en='a tall man', collocation_th='ผู้ชายตัวสูง'),
'meet': dict(meaning_th='พบ', thai_reading='มีท', stress_index=1, ipa='/miːt/', countable=None, collocation_en='meet a friend', collocation_th='เจอเพื่อน'),
'milk': dict(meaning_th='นม', thai_reading='มิลค์', stress_index=1, ipa='/mɪlk/', countable=0, collocation_en='drink milk', collocation_th='ดื่มนม'),
'money': dict(meaning_th='เงิน', thai_reading='มัน-นี', stress_index=1, ipa='/ˈmʌni/', countable=0, collocation_en='save money', collocation_th='เก็บเงิน'),
'morning': dict(meaning_th='ตอนเช้า', thai_reading='มอร์-นิง', stress_index=1, ipa='/ˈmɔːnɪŋ/', countable=1, collocation_en='this morning', collocation_th='เช้านี้'),
'mother': dict(meaning_th='แม่', thai_reading='มา-เธอะ', stress_index=1, ipa='/ˈmʌðə/', countable=1, collocation_en='my mother', collocation_th='แม่ของฉัน'),
'music': dict(meaning_th='ดนตรี', thai_reading='มิว-สิค', stress_index=1, ipa='/ˈmjuːzɪk/', countable=0, collocation_en='listen to music', collocation_th='ฟังเพลง'),
'name': dict(meaning_th='ชื่อ', thai_reading='เนม', stress_index=1, ipa='/neɪm/', countable=1, collocation_en='my name', collocation_th='ชื่อของฉัน'),
'near': dict(meaning_th='ใกล้', thai_reading='เนียร์', stress_index=1, ipa='/nɪə/', countable=None, collocation_en='near the park', collocation_th='ใกล้สวนสาธารณะ'),
'need': dict(meaning_th='ต้องการ', thai_reading='นีด', stress_index=1, ipa='/niːd/', countable=None, collocation_en='need help', collocation_th='ต้องการความช่วยเหลือ'),
'new': dict(meaning_th='ใหม่', thai_reading='นิว', stress_index=1, ipa='/njuː/', countable=None, collocation_en='a new car', collocation_th='รถคันใหม่'),
'nice': dict(meaning_th='ดี', thai_reading='ไนซ์', stress_index=1, ipa='/naɪs/', countable=None, collocation_en='a nice day', collocation_th='วันที่ดี'),
'night': dict(meaning_th='กลางคืน', thai_reading='ไนท์', stress_index=1, ipa='/naɪt/', countable=1, collocation_en='at night', collocation_th='ตอนกลางคืน'),
'old': dict(meaning_th='แก่', thai_reading='โอลด์', stress_index=1, ipa='/əʊld/', countable=None, collocation_en='an old friend', collocation_th='เพื่อนเก่า'),
'open': dict(meaning_th='เปิด', thai_reading='โอ-เพิน', stress_index=1, ipa='/ˈəʊpən/', countable=None, collocation_en='open the window', collocation_th='เปิดหน้าต่าง'),
'orange': dict(meaning_th='ส้ม', thai_reading='ออ-รินจ์', stress_index=1, ipa='/ˈɒrɪndʒ/', countable=1, collocation_en='eat an orange', collocation_th='กินส้ม'),
'page': dict(meaning_th='หน้า', thai_reading='เพจ', stress_index=1, ipa='/peɪdʒ/', countable=1, collocation_en='turn the page', collocation_th='พลิกหน้ากระดาษ'),
'paper': dict(meaning_th='กระดาษ', thai_reading='เพ-เพอะ', stress_index=1, ipa='/ˈpeɪpə/', countable=0, collocation_en='a piece of paper', collocation_th='กระดาษหนึ่งแผ่น'),
'park': dict(meaning_th='สวนสาธารณะ', thai_reading='พาร์ค', stress_index=1, ipa='/pɑːk/', countable=1, collocation_en='walk in the park', collocation_th='เดินเล่นในสวนสาธารณะ'),
'play': dict(meaning_th='เล่น', thai_reading='เพลย์', stress_index=1, ipa='/pleɪ/', countable=None, collocation_en='play football', collocation_th='เล่นฟุตบอล'),
'please': dict(meaning_th='กรุณา', thai_reading='พลีซ', stress_index=1, ipa='/pliːz/', countable=None, collocation_en='please wait', collocation_th='กรุณารอสักครู่'),
'pretty': dict(meaning_th='สวย', thai_reading='พริท-ที', stress_index=1, ipa='/ˈprɪti/', countable=None, collocation_en='a pretty flower', collocation_th='ดอกไม้ที่สวย'),
'quiet': dict(meaning_th='เงียบ', thai_reading='ไคว-เอิท', stress_index=1, ipa='/ˈkwaɪət/', countable=None, collocation_en='a quiet room', collocation_th='ห้องที่เงียบ'),
'rain': dict(meaning_th='ฝน', thai_reading='เรน', stress_index=1, ipa='/reɪn/', countable=0, collocation_en='heavy rain', collocation_th='ฝนตกหนัก'),
'read': dict(meaning_th='อ่าน', thai_reading='รีด', stress_index=1, ipa='/riːd/', countable=None, collocation_en='read a book', collocation_th='อ่านหนังสือ'),
'red': dict(meaning_th='สีแดง', thai_reading='เรด', stress_index=1, ipa='/red/', countable=None, collocation_en='a red car', collocation_th='รถสีแดง'),
'run': dict(meaning_th='วิ่ง', thai_reading='รัน', stress_index=1, ipa='/rʌn/', countable=None, collocation_en='run fast', collocation_th='วิ่งเร็ว'),
'sad': dict(meaning_th='เศร้า', thai_reading='แซด', stress_index=1, ipa='/sæd/', countable=None, collocation_en='feel sad', collocation_th='รู้สึกเศร้า'),
'school': dict(meaning_th='โรงเรียน', thai_reading='สคูล', stress_index=1, ipa='/skuːl/', countable=1, collocation_en='go to school', collocation_th='ไปโรงเรียน'),
'sea': dict(meaning_th='ทะเล', thai_reading='ซี', stress_index=1, ipa='/siː/', countable=1, collocation_en='swim in the sea', collocation_th='ว่ายน้ำในทะเล'),
'see': dict(meaning_th='เห็น', thai_reading='ซี', stress_index=1, ipa='/siː/', countable=None, collocation_en='see a friend', collocation_th='เจอเพื่อน'),
'sell': dict(meaning_th='ขาย', thai_reading='เซล', stress_index=1, ipa='/sel/', countable=None, collocation_en='sell a car', collocation_th='ขายรถ'),
'shop': dict(meaning_th='ร้านค้า', thai_reading='ชอพ', stress_index=1, ipa='/ʃɒp/', countable=1, collocation_en='go to the shop', collocation_th='ไปร้านค้า'),
'sing': dict(meaning_th='ร้องเพลง', thai_reading='ซิง', stress_index=1, ipa='/sɪŋ/', countable=None, collocation_en='sing a song', collocation_th='ร้องเพลง'),
'sister': dict(meaning_th='พี่สาว', thai_reading='ซิส-เทอะ', stress_index=1, ipa='/ˈsɪstə/', countable=1, collocation_en='my little sister', collocation_th='น้องสาวของฉัน'),
'sit': dict(meaning_th='นั่ง', thai_reading='ซิท', stress_index=1, ipa='/sɪt/', countable=None, collocation_en='sit down', collocation_th='นั่งลง'),
'sleep': dict(meaning_th='นอน', thai_reading='สลีพ', stress_index=1, ipa='/sliːp/', countable=None, collocation_en='sleep well', collocation_th='นอนหลับสบาย'),
'slow': dict(meaning_th='ช้า', thai_reading='สโลว์', stress_index=1, ipa='/sləʊ/', countable=None, collocation_en='a slow car', collocation_th='รถที่วิ่งช้า'),
'small': dict(meaning_th='เล็ก', thai_reading='สมอล', stress_index=1, ipa='/smɔːl/', countable=None, collocation_en='a small room', collocation_th='ห้องเล็ก'),
'speak': dict(meaning_th='พูด', thai_reading='สปีค', stress_index=1, ipa='/spiːk/', countable=None, collocation_en='speak English', collocation_th='พูดภาษาอังกฤษ'),
'stand': dict(meaning_th='ยืน', thai_reading='สแตนด์', stress_index=1, ipa='/stænd/', countable=None, collocation_en='stand up', collocation_th='ยืนขึ้น'),
'start': dict(meaning_th='เริ่มต้น', thai_reading='สตาร์ท', stress_index=1, ipa='/stɑːt/', countable=None, collocation_en='start work', collocation_th='เริ่มทำงาน'),
'student': dict(meaning_th='นักเรียน', thai_reading='สทิว-เดินท์', stress_index=1, ipa='/ˈstjuːdənt/', countable=1, collocation_en='a good student', collocation_th='นักเรียนที่ดี'),
'study': dict(meaning_th='เรียน', thai_reading='สทัด-ดี', stress_index=1, ipa='/ˈstʌdi/', countable=None, collocation_en='study English', collocation_th='เรียนภาษาอังกฤษ'),
'sun': dict(meaning_th='ดวงอาทิตย์', thai_reading='ซัน', stress_index=1, ipa='/sʌn/', countable=1, collocation_en='the hot sun', collocation_th='แดดร้อน'),
'table': dict(meaning_th='โต๊ะ', thai_reading='เท-เบิล', stress_index=1, ipa='/ˈteɪbl/', countable=1, collocation_en='a wooden table', collocation_th='โต๊ะไม้'),
'talk': dict(meaning_th='พูด', thai_reading='ทอค', stress_index=1, ipa='/tɔːk/', countable=None, collocation_en='talk to a friend', collocation_th='พูดคุยกับเพื่อน'),
'teacher': dict(meaning_th='ครู', thai_reading='ที-เชอะ', stress_index=1, ipa='/ˈtiːtʃə/', countable=1, collocation_en='a kind teacher', collocation_th='ครูที่ใจดี'),
'thank': dict(meaning_th='ขอบคุณ', thai_reading='แธงค์', stress_index=1, ipa='/θæŋk/', countable=None, collocation_en='thank you', collocation_th='ขอบคุณ'),
'time': dict(meaning_th='เวลา', thai_reading='ไทม์', stress_index=1, ipa='/taɪm/', countable=0, collocation_en='free time', collocation_th='เวลาว่าง'),
'tired': dict(meaning_th='เหนื่อย', thai_reading='ไทร์ด', stress_index=1, ipa='/taɪəd/', countable=None, collocation_en='feel tired', collocation_th='รู้สึกเหนื่อย'),
'today': dict(meaning_th='วันนี้', thai_reading='ทู-เดย์', stress_index=2, ipa='/təˈdeɪ/', countable=None, collocation_en="today's weather", collocation_th='อากาศวันนี้'),
'tomorrow': dict(meaning_th='พรุ่งนี้', thai_reading='ทู-มอร์-โรว', stress_index=2, ipa='/təˈmɒrəʊ/', countable=None, collocation_en='see you tomorrow', collocation_th='พบกันพรุ่งนี้'),
'tree': dict(meaning_th='ต้นไม้', thai_reading='ทรี', stress_index=1, ipa='/triː/', countable=1, collocation_en='climb a tree', collocation_th='ปีนต้นไม้'),
'walk': dict(meaning_th='เดิน', thai_reading='วอค', stress_index=1, ipa='/wɔːk/', countable=None, collocation_en='walk to school', collocation_th='เดินไปโรงเรียน'),
'want': dict(meaning_th='ต้องการ', thai_reading='วอนท์', stress_index=1, ipa='/wɒnt/', countable=None, collocation_en='want a coffee', collocation_th='อยากได้กาแฟ'),
'water': dict(meaning_th='น้ำ', thai_reading='วอ-เทอะ', stress_index=1, ipa='/ˈwɔːtə/', countable=0, collocation_en='drink water', collocation_th='ดื่มน้ำ'),
'weather': dict(meaning_th='อากาศ', thai_reading='เวธ-เธอะ', stress_index=1, ipa='/ˈweðə/', countable=0, collocation_en='nice weather', collocation_th='อากาศดี'),
'week': dict(meaning_th='สัปดาห์', thai_reading='วีค', stress_index=1, ipa='/wiːk/', countable=1, collocation_en='next week', collocation_th='สัปดาห์หน้า'),
'wife': dict(meaning_th='ภรรยา', thai_reading='ไวฟ์', stress_index=1, ipa='/waɪf/', countable=1, collocation_en='my wife', collocation_th='ภรรยาของฉัน'),
'window': dict(meaning_th='หน้าต่าง', thai_reading='วิน-โดว', stress_index=1, ipa='/ˈwɪndəʊ/', countable=1, collocation_en='open the window', collocation_th='เปิดหน้าต่าง'),
'work': dict(meaning_th='ทำงาน', thai_reading='เวิร์ค', stress_index=1, ipa='/wɜːk/', countable=0, collocation_en='go to work', collocation_th='ไปทำงาน'),
'write': dict(meaning_th='เขียน', thai_reading='ไรท์', stress_index=1, ipa='/raɪt/', countable=None, collocation_en='write a letter', collocation_th='เขียนจดหมาย'),
'year': dict(meaning_th='ปี', thai_reading='เยียร์', stress_index=1, ipa='/jɪə/', countable=1, collocation_en='next year', collocation_th='ปีหน้า'),
}


# --- A2/B1 extension (2026-07-23, generated by tools/extend_a2b1.py) ---
try:
    from ext_a2b1 import THAI_EXT
    DATA.update(THAI_EXT)
except ImportError:
    pass
