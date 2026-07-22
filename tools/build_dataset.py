# -*- coding: utf-8 -*-
"""
Phase 1 content pipeline. Builds vocab_app/assets/seed/vocab.db from
wordlist.py + thai_data.py, generating word_forms / example_sentences /
collocations / related_words per SPEC.md section 5.

Run: python tools/build_dataset.py
Output: vocab_app/assets/seed/vocab.db (SQLite, schema = SPEC.md section 4)

See NOTES.md for exactly what is real-sourced vs. approximated/generated.
"""
import re
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from wordlist import WORDS
from thai_data import DATA

OUT_DB = os.path.join(os.path.dirname(__file__), "..", "vocab_app", "assets", "seed", "vocab.db")

IRREGULAR_VERBS = {
    # base: (past, past_participle)
    "go": ("went", "gone"), "have": ("had", "had"), "eat": ("ate", "eaten"),
    "come": ("came", "come"), "give": ("gave", "given"), "see": ("saw", "seen"),
    "find": ("found", "found"), "know": ("knew", "known"), "make": ("made", "made"),
    "sell": ("sold", "sold"), "sit": ("sat", "sat"), "stand": ("stood", "stood"),
    "sleep": ("slept", "slept"), "speak": ("spoke", "spoken"), "hear": ("heard", "heard"),
    "read": ("read", "read"), "write": ("wrote", "written"), "meet": ("met", "met"),
    "drink": ("drank", "drunk"), "drive": ("drove", "driven"), "run": ("ran", "run"),
    "sing": ("sang", "sung"), "buy": ("bought", "bought"),
}

IRREGULAR_PLURALS = {"child": "children", "man": "men", "woman": "women"}

VERBS = {w for w, pos, *_ in WORDS if pos == "v"}
NOUNS = {w for w, pos, *_ in WORDS if pos == "n"}
ADJS = {w for w, pos, *_ in WORDS if pos == "adj"}


def regular_past(v):
    if v.endswith("e"):
        return v + "d"
    if re.search(r"[^aeiou]y$", v):
        return v[:-1] + "ied"
    if re.search(r"[^aeiouwxy][aeiou][^aeiouwxy]$", v) and v not in ("open", "listen", "happen"):
        return v + v[-1] + "ed"
    return v + "ed"


def ving(v):
    if v.endswith("ie"):
        return v[:-2] + "ying"
    if v.endswith("e") and not v.endswith("ee"):
        return v[:-1] + "ing"
    if re.search(r"[^aeiou]y$", v):
        return v + "ing"
    if re.search(r"[^aeiouwxy][aeiou][^aeiouwxy]$", v) and v not in ("open", "listen", "happen"):
        return v + v[-1] + "ing"
    return v + "ing"


def s3sg(v):
    if v.endswith(("s", "sh", "ch", "x", "o")):
        return v + "es"
    if re.search(r"[^aeiou]y$", v):
        return v[:-1] + "ies"
    return v + "s"


def plural(n):
    if n in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[n]
    if n.endswith(("s", "sh", "ch", "x")):
        return n + "es"
    if re.search(r"[^aeiou]y$", n):
        return n[:-1] + "ies"
    return n + "s"


def comparative(a):
    irregular = {"good": ("better", "best"), "bad": ("worse", "worst"), "far": ("farther", "farthest")}
    if a in irregular:
        return irregular[a]
    if len(a) <= 5 and not a.endswith("ful"):
        if a.endswith("y"):
            return a[:-1] + "ier", a[:-1] + "iest"
        if a.endswith("e"):
            return a + "r", a + "st"
        if re.search(r"[^aeiou][aeiou][^aeiou]$", a):
            return a + a[-1] + "er", a + a[-1] + "est"
        return a + "er", a + "est"
    return "more " + a, "most " + a


def word_forms_for(word, pos):
    forms = []
    if pos == "v" and word not in ("please",):
        if word in IRREGULAR_VERBS:
            past, pp = IRREGULAR_VERBS[word]
            irregular = 1
            note_past = (f"{word} เป็นกริยาไม่ปกติ (irregular verb) รูปอดีตไม่เติม -ed แต่เปลี่ยนรูปเป็น '{past}' "
                         f"ต้องจำแยกเป็นคำ ๆ ไป")
        else:
            past = regular_past(word)
            pp = past
            irregular = 0
            if past.endswith("ied"):
                note_past = f"{word} ลงท้ายด้วยพยัญชนะ+y จึงเปลี่ยน y เป็น i แล้วเติม -ed เป็น '{past}'"
            elif len(past) == len(word) + len(word[-1]) + 2:
                note_past = f"{word} เป็นพยางค์เดียวลงท้ายพยัญชนะ-สระ-พยัญชนะ จึงซ้ำพยัญชนะท้ายก่อนเติม -ed เป็น '{past}'"
            else:
                note_past = f"เหตุการณ์ในอดีตใช้ Past Simple โดยเติม -ed ท้ายกริยา '{word}' เป็น '{past}'"
        ing = ving(word)
        s3 = s3sg(word)
        forms.append((past, "past", irregular, note_past))
        forms.append((pp, "past_participle", irregular, note_past))
        forms.append((ing, "ving", 0, f"เหตุการณ์กำลังดำเนินอยู่ใช้ V-ing '{ing}' หลัง be-verb (am/is/are/was/were)"))
        forms.append((s3, "3sg", 0, f"ประธานเอกพจน์บุรุษที่ 3 (he/she/it) ใน Present Simple ต้องเติม -s/-es ที่กริยาเป็น '{s3}'"))
    elif pos == "n" and DATA.get(word, {}).get("countable") == 1:
        pl = plural(word)
        note = f"นามนับได้เมื่อมีมากกว่าหนึ่งต้องเติม -s/-es ท้ายคำเป็น '{pl}'"
        if word in IRREGULAR_PLURALS:
            note = f"{word} เป็นนามพหูพจน์ไม่ปกติ เปลี่ยนรูปเป็น '{pl}' โดยตรง ไม่ใช่การเติม -s"
        forms.append((pl, "plural", 1 if word in IRREGULAR_PLURALS else 0, note))
    elif pos == "adj":
        comp, sup = comparative(word)
        forms.append((comp, "comparative", 0, f"เปรียบเทียบขั้นกว่าของคำคุณศัพท์สั้น '{word}' ทำได้โดยเติม/แปลงเป็น '{comp}'"))
        forms.append((sup, "superlative", 0, f"เปรียบเทียบขั้นสุดของคำคุณศัพท์ '{word}' ทำได้โดยเติม/แปลงเป็น '{sup}'"))
    return forms


SENT_TEMPLATES = {
    "v": [
        ("She {v3sg} every morning before school.", "เธอ{th}ทุกเช้าก่อนไปโรงเรียน", False),
        ("{Base} with me, please.", "{th}กับฉันหน่อยนะ", False),
        ("I am so happy — we finally {vpast} it together!", "ฉันดีใจมาก เราในที่สุดก็{th}มันด้วยกัน!", True),
        ("They are {ving} right now.", "พวกเขากำลัง{th}อยู่ตอนนี้", False),
        ("He wants to {v} before it gets dark.", "เขาอยากจะ{th}ก่อนที่ฟ้าจะมืด", False),
    ],
    "n": [
        ("The {n} is on the table.", "{th}อยู่บนโต๊ะ", False),
        ("I bought a new {n} yesterday.", "เมื่อวานฉันซื้อ{th}ใหม่", False),
        ("We were so excited to see the {n} again after a long time!", "เราตื่นเต้นมากที่ได้เห็น{th}อีกครั้งหลังจากนานมาก!", True),
        ("Do you have a {n}?", "คุณมี{th}ไหม", False),
        ("The {ns} are over there.", "{th}พวกนั้นอยู่ตรงนั้น", False),
    ],
    "adj": [
        ("This soup is very {a}.", "ซุปนี้{th}มาก", False),
        ("She looked {a} when she saw the surprise party.", "เธอดู{th}ตอนที่เห็นงานปาร์ตี้เซอร์ไพรส์", True),
        ("It is a {a} day today.", "วันนี้เป็นวันที่{th}", False),
        ("Try to stay {a} during the test.", "พยายาม{th}ในระหว่างสอบ", False),
        ("The children are {a} after playing all day.", "เด็ก ๆ {th}หลังจากเล่นมาทั้งวัน", False),
    ],
    "adv": [
        ("Please come {w} tomorrow.", "กรุณามา{th}ในวันพรุ่งนี้", False),
        ("I {w} think about my family.", "ฉัน{th}นึกถึงครอบครัว", False),
        ("We laughed so hard, it happened {w} out of nowhere!", "เราหัวเราะกันลั่นเลย มันเกิดขึ้น{th}แบบไม่ทันตั้งตัว!", True),
        ("She walked {w} to the station.", "เธอเดิน{th}ไปที่สถานี", False),
        ("Is the shop open {w}?", "ร้านเปิด{th}ไหม", False),
    ],
    "prep": [
        ("The cat is sitting {w} the box.", "แมวนั่งอยู่{th}กล่อง", False),
        ("We walked {w} the park together, laughing the whole way.", "เราเดิน{th}สวนสาธารณะด้วยกัน หัวเราะกันตลอดทาง", True),
        ("Put the book {w} the table.", "วางหนังสือ{th}โต๊ะ", False),
        ("She lives {w} the school.", "เธออาศัยอยู่{th}โรงเรียน", False),
        ("He looked {w} the window.", "เขามอง{th}หน้าต่าง", False),
    ],
    "det": [
        ("I need {w} help with this.", "ฉันต้องการความช่วยเหลือ{th}เรื่องนี้", False),
        ("{W} students passed the test, and we celebrated together!", "นักเรียน{th}สอบผ่าน แล้วเราก็ฉลองกัน!", True),
        ("She eats {w} morning.", "เธอกิน{th}เช้า", False),
        ("Is there {w} food left?", "มีอาหารเหลือ{th}ไหม", False),
        ("{W} day is a new chance.", "{th}วันคือโอกาสใหม่", False),
    ],
    "conj": [
        ("I like tea {w} coffee.", "ฉันชอบชา{th}กาแฟ", False),
        ("We were tired {w} happy after the trip!", "เราเหนื่อย{th}มีความสุขหลังจากทริปนั้น!", True),
        ("She sang {w} danced.", "เธอร้องเพลง{th}เต้นรำ", False),
        ("Wash your hands {w} you eat.", "ล้างมือ{th}คุณจะกิน", False),
        ("He is small {w} strong.", "เขาตัวเล็ก{th}แข็งแรง", False),
    ],
    "interj": [
        ("{W}, can you help me?", "{th} คุณช่วยฉันได้ไหม", False),
        ("\"{W}!\" she said, jumping with joy.", "\"{th}!\" เธอพูดพร้อมกระโดดด้วยความดีใจ", True),
        ("{W}, close the door.", "{th} ปิดประตูด้วย", False),
        ("Come in, {w}.", "เข้ามาสิ {th}", False),
        ("{W} tell me your name.", "{th} บอกชื่อฉันหน่อย", False),
    ],
    "pron": [
        ("{W} is my best friend.", "{th}เป็นเพื่อนสนิทของฉัน", False),
        ("We hugged {w} tightly, so happy to meet again!", "เรากอด{th}แน่น ดีใจมากที่ได้พบกันอีกครั้ง!", True),
        ("Give it to {w}.", "ให้มันกับ{th}", False),
        ("{W} lives near the park.", "{th}อาศัยอยู่ใกล้สวนสาธารณะ", False),
        ("Can {w} come with us?", "{th}มาด้วยกันได้ไหม", False),
    ],
    "phrase": [
        ("{W} everyone!", "{th}ทุกคน!", False),
        ("She said \"{w}\" with a big smile of relief.", "เธอพูดว่า \"{th}\" พร้อมรอยยิ้มโล่งใจ", True),
        ("{W}, how are you?", "{th} สบายดีไหม", False),
        ("He waved and said {w}.", "เขาโบกมือแล้วพูดว่า{th}", False),
        ("{W} to you too.", "{th}คุณเหมือนกัน", False),
    ],
}


def build_sentences(word, pos, meaning_th):
    forms = word_forms_for(word, pos)
    fmap = {f[1]: f[0] for f in forms}
    tmpl_key = pos if pos in SENT_TEMPLATES else "phrase"
    templates = SENT_TEMPLATES[tmpl_key]
    out = []
    for rank, (en_t, th_t, emotional) in enumerate(templates, start=1):
        en = en_t
        th = th_t
        target = word
        if pos == "v":
            v3sg = fmap.get("3sg", word + "s")
            vpast = fmap.get("past", word + "ed")
            vving = fmap.get("ving", word + "ing")
            repl = {"{v3sg}": v3sg, "{Base}": word.capitalize(), "{vpast}": vpast,
                    "{ving}": vving, "{v}": word}
            for k, v in repl.items():
                if k in en:
                    target = v
                en = en.replace(k, v)
            th = th.replace("{th}", meaning_th.split(",")[0].split("(")[0].strip())
        elif pos == "n":
            ns = fmap.get("plural", word + "s")
            if "{ns}" in en:
                target = ns
            en = en.replace("{n}", word).replace("{ns}", ns)
            th = th.replace("{th}", meaning_th.split(",")[0].split("(")[0].strip())
        elif pos == "adj":
            en = en.replace("{a}", word)
            target = word
            th = th.replace("{th}", meaning_th.split(",")[0].split("(")[0].strip())
        else:
            en = en.replace("{w}", word).replace("{W}", word.capitalize())
            target = word
            th = th.replace("{th}", meaning_th.split(",")[0].split("(")[0].strip())
        # find cloze span (case-insensitive) of `target`
        m = re.search(re.escape(target), en, re.IGNORECASE)
        cloze_start, cloze_end = (m.start(), m.end()) if m else (0, 0)
        out.append(dict(rank=rank, en_text=en, th_text=th, cloze_start=cloze_start,
                         cloze_end=cloze_end, is_emotional=1 if emotional else 0,
                         form_id=None))
    return out, forms


# Small manually-curated related-words fallback (documented in NOTES.md as an
# approximation of SWOW, since SWOW-EN could not be downloaded in this
# session). Only added where a clear, non-giveaway semantic-neighbour exists
# among the 160-word A1 seed itself (both endpoints must be in the seed).
RELATED_FALLBACK = {
    "cat": ["dog", "milk"], "dog": ["cat", "run"], "car": ["drive", "road" if False else "fast"],
    "book": ["read", "school"], "school": ["student", "teacher", "book"],
    "teacher": ["school", "student"], "student": ["school", "teacher", "study"],
    "rain": ["weather", "cold"], "sun": ["hot", "weather"], "water": ["drink", "sea"],
    "sea": ["water", "fish"], "fish": ["water", "sea", "eat"],
    "bed": ["sleep", "tired"], "sleep": ["bed", "tired", "night"],
    "night": ["sleep", "dark" if False else "evening"], "morning": ["evening", "day"],
    "evening": ["morning", "night"], "family": ["mother", "father", "brother", "sister"],
    "mother": ["father", "family"], "father": ["mother", "family"],
    "brother": ["sister", "family"], "sister": ["brother", "family"],
    "husband": ["wife", "family"], "wife": ["husband", "family"],
    "happy": ["sad", "smile"], "sad": ["happy", "cry"], "cry": ["sad"],
    "smile": ["happy", "laugh"], "laugh": ["smile", "happy"],
    "hot": ["cold", "sun"], "cold": ["hot", "rain"],
    "big": ["small"], "small": ["big", "little"],
    "fast": ["slow", "car", "run"], "slow": ["fast"],
    "food": ["eat", "cook", "lunch"], "eat": ["food", "hungry"],
    "hungry": ["eat", "food"], "cook": ["food", "kitchen"],
    "kitchen": ["cook", "food", "house"], "house": ["home", "kitchen", "door"],
    "home": ["house", "family"], "door": ["window", "house"],
    "window": ["door", "house"], "money": ["buy", "job"],
    "job": ["work", "money"], "work": ["job", "busy"],
    "city": ["house", "noisy"], "park": ["garden", "tree"],
    "garden": ["park", "tree", "flower" if False else "green"],
    "tree": ["garden", "green"], "music": ["sing", "dance", "listen"],
    "sing": ["music", "song" if False else "dance"], "dance": ["music", "sing"],
    "listen": ["music", "hear"], "hear": ["listen", "sound" if False else "ask"],
    "speak": ["talk", "language"], "talk": ["speak", "ask"],
    "language": ["speak", "learn"], "learn": ["study", "school", "language"],
    "study": ["learn", "school", "book"], "child": ["baby", "boy", "girl"],
    "baby": ["child", "family"], "boy": ["girl", "child"], "girl": ["boy", "child"],
    "man": ["woman" if False else "boy", "lady"], "lady": ["man", "girl"],
}


def resolve_related(word_ids):
    rows = []
    for w, neighbours in RELATED_FALLBACK.items():
        if w not in word_ids:
            continue
        for n in neighbours:
            if n not in word_ids or n == w:
                continue
            rows.append((word_ids[w], word_ids[n], "association", 0.5, 0))
    return rows


SCHEMA = """
CREATE TABLE words (
  id INTEGER PRIMARY KEY,
  headword TEXT NOT NULL,
  cefr TEXT,
  freq_rank INTEGER,
  thai_reading TEXT,
  stress_index INTEGER,
  ipa TEXT,
  translation_source TEXT,
  translation_license TEXT,
  has_photo INTEGER DEFAULT 0,
  image_url TEXT,
  image_license TEXT,
  image_author TEXT
);
CREATE TABLE senses (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id),
  pos TEXT,
  meaning_th TEXT,
  cefr TEXT,
  countable INTEGER,
  collocation_en TEXT,
  collocation_th TEXT,
  sense_rank INTEGER,
  is_core INTEGER
);
CREATE TABLE word_forms (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id),
  form_text TEXT,
  form_type TEXT,
  is_irregular INTEGER,
  grammar_note_th TEXT
);
CREATE TABLE example_sentences (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id),
  form_id INTEGER,
  rank INTEGER,
  en_text TEXT,
  th_text TEXT,
  cloze_start INTEGER,
  cloze_end INTEGER,
  is_emotional INTEGER
);
CREATE TABLE related_words (
  id INTEGER PRIMARY KEY,
  word_id INTEGER NOT NULL REFERENCES words(id),
  related_word_id INTEGER NOT NULL REFERENCES words(id),
  relation_type TEXT,
  closeness REAL,
  is_giveaway INTEGER
);
CREATE TABLE topics (id INTEGER PRIMARY KEY, name TEXT, cefr TEXT);
CREATE TABLE word_topics (word_id INTEGER REFERENCES words(id), topic_id INTEGER REFERENCES topics(id));
"""


def main():
    os.makedirs(os.path.dirname(OUT_DB), exist_ok=True)
    if os.path.exists(OUT_DB):
        os.remove(OUT_DB)
    conn = sqlite3.connect(OUT_DB)
    conn.executescript(SCHEMA)
    cur = conn.cursor()

    word_ids = {}
    warnings = []

    for headword, pos, cefr, freq_rank in WORDS:
        key = headword.lower()
        d = DATA.get(key)
        if d is None:
            warnings.append(f"MISSING thai_data for {headword}")
            continue
        cur.execute(
            "INSERT INTO words (headword, cefr, freq_rank, thai_reading, stress_index, ipa, "
            "translation_source, translation_license, has_photo) VALUES (?,?,?,?,?,?,?,?,0)",
            (headword, cefr, freq_rank, d["thai_reading"], d["stress_index"], d["ipa"],
             "Wiktionary (approximated)", "CC BY-SA 3.0"),
        )
        wid = cur.lastrowid
        word_ids[key] = wid

        cur.execute(
            "INSERT INTO senses (word_id, pos, meaning_th, cefr, countable, collocation_en, "
            "collocation_th, sense_rank, is_core) VALUES (?,?,?,?,?,?,?,1,1)",
            (wid, pos, d["meaning_th"], cefr, d.get("countable"), d["collocation_en"], d["collocation_th"]),
        )

        sentences, forms = build_sentences(key, pos, d["meaning_th"])
        for ft in forms:
            cur.execute(
                "INSERT INTO word_forms (word_id, form_text, form_type, is_irregular, grammar_note_th) "
                "VALUES (?,?,?,?,?)",
                (wid, ft[0], ft[1], ft[2], ft[3]),
            )
        for s in sentences:
            cur.execute(
                "INSERT INTO example_sentences (word_id, form_id, rank, en_text, th_text, "
                "cloze_start, cloze_end, is_emotional) VALUES (?,?,?,?,?,?,?,?)",
                (wid, s["form_id"], s["rank"], s["en_text"], s["th_text"],
                 s["cloze_start"], s["cloze_end"], s["is_emotional"]),
            )

    for row in resolve_related(word_ids):
        cur.execute(
            "INSERT INTO related_words (word_id, related_word_id, relation_type, closeness, is_giveaway) "
            "VALUES (?,?,?,?,?)",
            row,
        )

    conn.commit()

    # --- QC pass ---
    qc_errors = []
    cur.execute("SELECT COUNT(*) FROM words")
    n_words = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT headword) FROM words")
    n_distinct = cur.fetchone()[0]
    if n_words != n_distinct:
        qc_errors.append(f"duplicate headwords: {n_words} rows vs {n_distinct} distinct")
    cur.execute("SELECT COUNT(*) FROM example_sentences WHERE cloze_end<=cloze_start")
    bad_cloze = cur.fetchone()[0]
    if bad_cloze:
        qc_errors.append(f"{bad_cloze} example_sentences rows with invalid cloze span")
    cur.execute(
        "SELECT w.headword, COUNT(*) FROM example_sentences e JOIN words w ON w.id=e.word_id "
        "GROUP BY e.word_id HAVING COUNT(*)<>5"
    )
    bad_counts = cur.fetchall()
    if bad_counts:
        qc_errors.append(f"words without exactly 5 sentences: {bad_counts[:5]}...")
    # orphan FK check
    cur.execute(
        "SELECT COUNT(*) FROM related_words rw LEFT JOIN words w ON w.id=rw.word_id WHERE w.id IS NULL"
    )
    if cur.fetchone()[0]:
        qc_errors.append("related_words has dangling word_id FK")
    cur.execute(
        "SELECT COUNT(*) FROM related_words rw LEFT JOIN words w ON w.id=rw.related_word_id WHERE w.id IS NULL"
    )
    if cur.fetchone()[0]:
        qc_errors.append("related_words has dangling related_word_id FK")
    # cloze substring sanity: cloze text must be alphabetic-only slice of en_text
    cur.execute("SELECT id, en_text, cloze_start, cloze_end FROM example_sentences")
    bad_slice = 0
    for _id, en_text, cs, ce in cur.fetchall():
        slice_ = en_text[cs:ce]
        if not slice_ or not slice_.replace("'", "").isalpha():
            bad_slice += 1
    if bad_slice:
        qc_errors.append(f"{bad_slice} example_sentences with non-alphabetic cloze slice")

    conn.close()

    print(f"Built {OUT_DB}")
    print(f"words: {n_words}")
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(" -", w)
    if qc_errors:
        print("QC ERRORS:")
        for e in qc_errors:
            print(" -", e)
        sys.exit(1)
    else:
        print("QC pass: OK")


if __name__ == "__main__":
    main()
