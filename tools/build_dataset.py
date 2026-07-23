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
from llm_sentences import DATA as LLM_SENTENCES
from swow_associations import SWOW_ASSOCIATIONS, SWOW_FALLBACK_EXCEPTIONS

try:
    from nltk.corpus import wordnet as _wn
    _wn.synsets("test")  # forces a load; raises LookupError if corpus isn't downloaded
    HAVE_WORDNET = True
except LookupError:
    HAVE_WORDNET = False
    print("WARNING: nltk 'wordnet' corpus not downloaded -- run "
          "python -m nltk.downloader wordnet . Falling back to is_giveaway=0 "
          "for all related_words rows and skipping hypernym/part_of rows "
          "(same as before this pass). See NOTES.md section 3.")
except ImportError:
    HAVE_WORDNET = False
    print("WARNING: nltk not installed (pip install nltk) -- see above.")

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
    # A2/B1 extension coverage (2026-07-23) -- superset is harmless, only
    # consulted for words actually tagged pos='v' in the word list:
    "be": ("was", "been"), "become": ("became", "become"), "begin": ("began", "begun"),
    "break": ("broke", "broken"), "bring": ("brought", "brought"), "build": ("built", "built"),
    "catch": ("caught", "caught"), "choose": ("chose", "chosen"), "cut": ("cut", "cut"),
    "do": ("did", "done"), "draw": ("drew", "drawn"), "fall": ("fell", "fallen"),
    "feel": ("felt", "felt"), "fight": ("fought", "fought"), "fly": ("flew", "flown"),
    "forget": ("forgot", "forgotten"), "get": ("got", "got"), "grow": ("grew", "grown"),
    "hit": ("hit", "hit"), "hold": ("held", "held"), "hurt": ("hurt", "hurt"),
    "keep": ("kept", "kept"), "leave": ("left", "left"), "lend": ("lent", "lent"),
    "let": ("let", "let"), "lie": ("lay", "lain"), "lose": ("lost", "lost"),
    "mean": ("meant", "meant"), "pay": ("paid", "paid"), "put": ("put", "put"),
    "ride": ("rode", "ridden"), "ring": ("rang", "rung"), "rise": ("rose", "risen"),
    "say": ("said", "said"), "send": ("sent", "sent"), "shine": ("shone", "shone"),
    "shut": ("shut", "shut"), "spend": ("spent", "spent"), "steal": ("stole", "stolen"),
    "swim": ("swam", "swum"), "take": ("took", "taken"), "teach": ("taught", "taught"),
    "tell": ("told", "told"), "think": ("thought", "thought"), "throw": ("threw", "thrown"),
    "understand": ("understood", "understood"), "wake": ("woke", "woken"),
    "wear": ("wore", "worn"), "win": ("won", "won"),
}

IRREGULAR_PLURALS = {
    "child": "children", "man": "men", "woman": "women",
    # A2/B1 extension coverage (2026-07-23):
    "foot": "feet", "tooth": "teeth", "person": "people",
    "mouse": "mice", "sheep": "sheep", "fish": "fish",
}

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

    # Prefer real LLM-generated (gemini-3.6-flash) sentences + grammar note
    # when present for this headword (tools/llm_sentences.py) -- falls back
    # to the SENT_TEMPLATES mechanism below only if the word is missing from
    # that dataset, or (as a safety net) if its cloze spans somehow fail to
    # resolve. See NOTES.md section 1 for which ~9 words fall back and why.
    llm = LLM_SENTENCES.get(word)
    if llm:
        out = []
        ok = True
        for s in llm["sentences"]:
            en = s["en_text"]
            target = s["cloze_target"]
            m = re.search(re.escape(target), en, re.IGNORECASE)
            cloze_start, cloze_end = (m.start(), m.end()) if m else (0, 0)
            if cloze_end <= cloze_start:
                ok = False
            out.append(dict(rank=s["rank"], en_text=en, th_text=s["th_text"],
                             cloze_start=cloze_start, cloze_end=cloze_end,
                             is_emotional=1 if s["is_emotional"] else 0,
                             form_id=None))
        if ok and len(out) == 5:
            # The LLM note explains the reasoning across all 5 sentences'
            # forms holistically (richer than the per-form template note),
            # so it replaces grammar_note_th on every word_forms row for
            # this word rather than the mechanically-generated one.
            forms = [(f[0], f[1], f[2], llm["grammar_note_th"]) for f in forms]
            return out, forms
        # cloze resolution failed unexpectedly -- fall through to templates

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


# Small manually-curated related-words fallback -- NO LONGER the primary
# association source (see tools/swow_associations.py, which now has real
# SWOW-EN18 data for all 153/153 current words). Kept only as the documented
# per-word exception path in resolve_related() below, for any future word
# that ends up in SWOW_FALLBACK_EXCEPTIONS (empty today). Historical/dead
# code for the 153-word list as it stands, intentionally left in rather than
# deleted so the fallback mechanism keeps working unattended. Only added
# where a clear, non-giveaway semantic-neighbour exists among the 160-word
# A1 seed itself (both endpoints must be in the seed).
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
    "happy": ["sad"], "sad": ["happy"],
    "laugh": ["happy"],
    "hot": ["cold", "sun"], "cold": ["hot", "rain"],
    "big": ["small"], "small": ["big", "little"],
    "fast": ["slow", "car", "run"], "slow": ["fast"],
    "food": ["eat", "cook", "lunch"], "eat": ["food", "hungry"],
    "hungry": ["eat", "food"], "cook": ["food", "kitchen"],
    "kitchen": ["cook", "food", "house"], "house": ["home", "kitchen", "door"],
    "home": ["house", "family"], "door": ["window", "house"],
    "window": ["door", "house"], "money": ["buy", "job"],
    "job": ["work", "money"], "work": ["job", "busy"],
    "city": ["house"], "park": ["garden", "tree"],
    "garden": ["park", "tree", "flower" if False else "green"],
    "tree": ["garden", "green"], "music": ["sing", "dance", "listen"],
    "sing": ["music", "song" if False else "dance"], "dance": ["music", "sing"],
    "listen": ["music", "hear"], "hear": ["listen", "sound" if False else "ask"],
    "speak": ["talk", "language"], "talk": ["speak", "ask"],
    "language": ["speak", "learn"], "learn": ["study", "school", "language"],
    "study": ["learn", "school", "book"], "child": ["baby", "boy", "girl"],
    "baby": ["child", "family"], "boy": ["girl", "child"], "girl": ["boy", "child"],
    "man": ["woman" if False else "boy"],
}


# Pairs where a purely mechanical WordNet hypernym/meronym closure check
# (see build_hypernym_meronym_rows below) finds a real relation, but through
# a WordNet SENSE that is not the sense this app actually teaches for that
# headword -- documented human/LLM sense-selection judgment call (SPEC.md
# section 5's sanctioned "เลือก sense" role), not a silent auto-accept of
# whatever WordNet returns. See NOTES.md section 3 for the reasoning per
# pair.
HYPERNYM_MERONYM_SENSE_MISMATCH_EXCLUDE = {
    # fish's ONLY WordNet member_holonym is "school.n.07" (a school OF FISH,
    # i.e. a shoal) -- but this app's headword "school" teaches school.n.01
    # ("an educational institution"), a completely unrelated sense. Showing
    # this pair in the Odd-One-Out game would be actively misleading.
    ("fish", "school"),
}

_POS_MAP = {"n": "n", "v": "v", "adj": "a", "adv": "r"}


def _wn_synsets(word, pos):
    if not HAVE_WORDNET:
        return []
    wn_pos = _POS_MAP.get(pos)
    return _wn.synsets(word, pos=wn_pos) if wn_pos else _wn.synsets(word)


def is_wn_synonym(w1, pos1, w2):
    """True if w2 is a lemma in any of w1's synsets (restricted to w1's POS
    in this app, since that's the sense actually being tested)."""
    for s in _wn_synsets(w1, pos1):
        if w2 in {l.name().lower().replace("_", " ") for l in s.lemmas()}:
            return True
    return False


def is_wn_antonym(w1, pos1, w2):
    """True if w2 is a WordNet-curated antonym of any lemma in one of w1's
    synsets (restricted to w1's POS)."""
    for s in _wn_synsets(w1, pos1):
        for lemma in s.lemmas():
            for ant in lemma.antonyms():
                if ant.name().lower().replace("_", " ") == w2:
                    return True
    return False


def resolve_related(word_ids, pos_map):
    """Association rows sourced from REAL SWOW-EN18 data
    (tools/swow_associations.py -- see that file's docstring for the exact
    source file, date, and extraction method) for every word NOT in
    SWOW_FALLBACK_EXCEPTIONS (empty for the current 153-word list -- every
    word had enough real in-vocabulary SWOW rows). `closeness` is the
    dataset's own real R123.Strength score, not a placeholder. Any word
    that WOULD be in the exception list falls back to the old hand-curated
    RELATED_FALLBACK dict with a flat 0.5 closeness, exactly as before.
    is_giveaway is computed the same way as before (real WordNet
    synonym/antonym check), now applied to the real SWOW pairs."""
    rows = []

    def emit(w, n, closeness):
        pos_w = pos_map.get(w, "n")
        is_giveaway = 0
        if HAVE_WORDNET:
            if is_wn_synonym(w, pos_w, n) or is_wn_antonym(w, pos_w, n):
                is_giveaway = 1
        rows.append((word_ids[w], word_ids[n], "association", closeness, is_giveaway))

    for w in word_ids:
        if w in SWOW_FALLBACK_EXCEPTIONS:
            for n in RELATED_FALLBACK.get(w, []):
                if n not in word_ids or n == w:
                    continue
                emit(w, n, 0.5)
        else:
            for n, strength in SWOW_ASSOCIATIONS.get(w, []):
                if n not in word_ids or n == w:
                    continue
                emit(w, n, strength)
    return rows


def build_hypernym_meronym_rows(word_ids, pos_map):
    """Real WordNet-derived category rows for the Odd-One-Out game:
    relation_type='hypernym' (w IS-A other, e.g. bread IS-A food) and
    relation_type='part_of' (w is a physical/temporal part of other, e.g.
    night is part_of day) -- restricted to pairs where BOTH headwords are
    in this app's own word set (per SPEC.md section 4's FK requirement),
    computed from each word's primary (most common) WordNet noun sense's
    hypernym-path / holonym closure. is_giveaway is left 0 for these (the
    auto-giveaway flag is specifically for synonym/antonym per SPEC.md
    section 5 -- a broader category isn't the same as revealing the
    answer). closeness is a flat placeholder (WordNet has no association-
    strength score the way SWOW does) -- NOT claimed as SWOW-sourced.
    """
    if not HAVE_WORDNET:
        return []
    noun_words = [w for w, pos in pos_map.items() if pos == "n" and w in word_ids]
    rows = []
    seen_pairs = set()  # avoid duplicating an already-known synonym/antonym pair

    # pairs already covered as association+synonym/antonym -- skip adding a
    # redundant hypernym/meronym row for the exact same two words. Sourced
    # from whichever association source resolve_related() actually used
    # per word (real SWOW_ASSOCIATIONS, or RELATED_FALLBACK for any word in
    # SWOW_FALLBACK_EXCEPTIONS -- empty for the current 153-word list).
    existing_assoc_pairs = set()
    for w in word_ids:
        if w in SWOW_FALLBACK_EXCEPTIONS:
            for n in RELATED_FALLBACK.get(w, []):
                existing_assoc_pairs.add(frozenset((w, n)))
        else:
            for n, _strength in SWOW_ASSOCIATIONS.get(w, []):
                existing_assoc_pairs.add(frozenset((w, n)))

    for w in noun_words:
        ssets = _wn_synsets(w, "n")
        if not ssets:
            continue
        primary = ssets[0]

        ancestors = set()
        for path in primary.hypernym_paths():
            for anc in path[:-1]:
                for l in anc.lemmas():
                    ancestors.add(l.name().lower().replace("_", " "))
        wholes = set()
        for holo in primary.part_holonyms() + primary.member_holonyms() + primary.substance_holonyms():
            for l in holo.lemmas():
                wholes.add(l.name().lower().replace("_", " "))

        for other in noun_words:
            if other == w:
                continue
            pair_key = (w, other)
            if pair_key in HYPERNYM_MERONYM_SENSE_MISMATCH_EXCLUDE:
                continue
            if frozenset((w, other)) in existing_assoc_pairs:
                continue
            if (w, other) in seen_pairs:
                continue
            if other in ancestors:
                rows.append((word_ids[w], word_ids[other], "hypernym", 0.6, 0))
                seen_pairs.add((w, other))
            elif other in wholes:
                rows.append((word_ids[w], word_ids[other], "part_of", 0.6, 0))
                seen_pairs.add((w, other))
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
    pos_map = {w.lower(): pos for w, pos, cefr, fr in WORDS}

    # Words whose meaning_th could NOT be verified against a real Wiktionary
    # Thai translation (tools/thai_data.py's docstring + NOTES.md section 2
    # explain why per word) -- translation_source stays flagged as
    # approximated for exactly these, instead of a blanket claim of "real"
    # sourcing that wouldn't be true for them. Everyone else got a real,
    # machine-fetched wiktapi.dev (mirrors en.wiktionary.org) Thai
    # translation cross-check in this pass.
    APPROXIMATED_TRANSLATION = {"make"}

    for headword, pos, cefr, freq_rank in WORDS:
        key = headword.lower()
        d = DATA.get(key)
        if d is None:
            warnings.append(f"MISSING thai_data for {headword}")
            continue
        if key in APPROXIMATED_TRANSLATION:
            translation_source = "Wiktionary (approximated)"
        else:
            translation_source = "Wiktionary"
        cur.execute(
            "INSERT INTO words (headword, cefr, freq_rank, thai_reading, stress_index, ipa, "
            "translation_source, translation_license, has_photo) VALUES (?,?,?,?,?,?,?,?,0)",
            (headword, cefr, freq_rank, d["thai_reading"], d["stress_index"], d["ipa"],
             translation_source, "CC BY-SA 4.0"),
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

    related_rows = resolve_related(word_ids, pos_map) + build_hypernym_meronym_rows(word_ids, pos_map)
    for row in related_rows:
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
    # cloze substring sanity: cloze text must be made only of alphabetic
    # word(s) (+ apostrophes for possessives). Allows single interior spaces
    # so multi-word comparative forms ("more beautiful", "most tired") --
    # legitimate grammatical variety from the LLM-generated content -- pass,
    # while still catching genuinely broken (empty/punctuation-only) spans.
    cur.execute("SELECT id, en_text, cloze_start, cloze_end FROM example_sentences")
    bad_slice = 0
    for _id, en_text, cs, ce in cur.fetchall():
        slice_ = en_text[cs:ce]
        words_in_slice = slice_.split(" ")
        if not slice_ or not all(w.replace("'", "").isalpha() for w in words_in_slice):
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
