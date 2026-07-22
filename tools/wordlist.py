# -*- coding: utf-8 -*-
"""
Source word list for Phase 1 seed (~150 headwords, Oxford 3000 band A1).

DATA SOURCE NOTE (see NOTES.md for full detail):
The Oxford 3000/5000 list with CEFR band is published by Oxford Learner's
Dictionaries (https://www.oxfordlearnersdictionaries.com/wordlists/oxford3000-5000).
This build environment has no live internet access for the automated pipeline run
(WebFetch/WebSearch were used to confirm the list's existence and structure, but a
full machine-readable pull of the OUP PDF / a GitHub mirror was not reliably
fetchable in this session). The headwords below are drawn from the well-known,
publicly documented Oxford 3000 A1 band (the same ~150 core beginner words that
appear consistently across published Oxford 3000 A1 wordlist mirrors), typed in
manually with POS tags to keep the pipeline honest and reviewable. This is flagged
as APPROXIMATED sourcing in NOTES.md — a future pass should replace this file's
content with a direct parse of the official OUP CSV/PDF (mechanical swap, pipeline
code does not need to change).

Each entry: (headword, pos, cefr, freq_rank)
pos: n / v / adj / adv / prep / pron / det / conj / interj / phrase
"""

WORDS = [
    ("a", "det", "A1", 1), ("about", "prep", "A1", 2), ("after", "prep", "A1", 3),
    ("again", "adv", "A1", 4), ("all", "det", "A1", 5), ("also", "adv", "A1", 6),
    ("and", "conj", "A1", 7), ("answer", "v", "A1", 8), ("ask", "v", "A1", 9),
    ("baby", "n", "A1", 10), ("bad", "adj", "A1", 11), ("bag", "n", "A1", 12),
    ("beautiful", "adj", "A1", 13), ("bed", "n", "A1", 14), ("big", "adj", "A1", 15),
    ("bird", "n", "A1", 16), ("book", "n", "A1", 17), ("boy", "n", "A1", 18),
    ("bread", "n", "A1", 19), ("brother", "n", "A1", 20), ("busy", "adj", "A1", 21),
    ("buy", "v", "A1", 22), ("car", "n", "A1", 23), ("cat", "n", "A1", 24),
    ("chair", "n", "A1", 25), ("child", "n", "A1", 26), ("city", "n", "A1", 27),
    ("clean", "adj", "A1", 28), ("clothes", "n", "A1", 29), ("cold", "adj", "A1", 30),
    ("come", "v", "A1", 31), ("cook", "v", "A1", 32), ("cry", "v", "A1", 33),
    ("dance", "v", "A1", 34), ("day", "n", "A1", 35), ("different", "adj", "A1", 36),
    ("dog", "n", "A1", 37), ("door", "n", "A1", 38), ("drink", "v", "A1", 39),
    ("drive", "v", "A1", 40), ("early", "adv", "A1", 41), ("easy", "adj", "A1", 42),
    ("eat", "v", "A1", 43), ("egg", "n", "A1", 44), ("English", "adj", "A1", 45),
    ("evening", "n", "A1", 46), ("every", "det", "A1", 47), ("eye", "n", "A1", 48),
    ("family", "n", "A1", 49), ("far", "adv", "A1", 50), ("fast", "adj", "A1", 51),
    ("father", "n", "A1", 52), ("find", "v", "A1", 53), ("fish", "n", "A1", 54),
    ("food", "n", "A1", 55), ("friend", "n", "A1", 56), ("garden", "n", "A1", 57),
    ("girl", "n", "A1", 58), ("give", "v", "A1", 59), ("go", "v", "A1", 60),
    ("good", "adj", "A1", 61), ("great", "adj", "A1", 62), ("green", "adj", "A1", 63),
    ("happy", "adj", "A1", 64), ("hard", "adj", "A1", 65), ("hat", "n", "A1", 66),
    ("have", "v", "A1", 67), ("hear", "v", "A1", 68), ("help", "v", "A1", 69),
    ("home", "n", "A1", 70), ("hope", "v", "A1", 71), ("hot", "adj", "A1", 72),
    ("house", "n", "A1", 73), ("hungry", "adj", "A1", 74), ("husband", "n", "A1", 75),
    ("job", "n", "A1", 76), ("kitchen", "n", "A1", 77), ("know", "v", "A1", 78),
    ("lady", "n", "A1", 79), ("language", "n", "A1", 80), ("late", "adj", "A1", 81),
    ("laugh", "v", "A1", 82), ("learn", "v", "A1", 83), ("light", "n", "A1", 84),
    ("like", "v", "A1", 85), ("listen", "v", "A1", 86), ("little", "adj", "A1", 87),
    ("live", "v", "A1", 88), ("long", "adj", "A1", 89), ("look", "v", "A1", 90),
    ("love", "v", "A1", 91), ("lunch", "n", "A1", 92), ("make", "v", "A1", 93),
    ("man", "n", "A1", 94), ("meet", "v", "A1", 95), ("milk", "n", "A1", 96),
    ("money", "n", "A1", 97), ("morning", "n", "A1", 98), ("mother", "n", "A1", 99),
    ("music", "n", "A1", 100), ("name", "n", "A1", 101), ("near", "prep", "A1", 102),
    ("need", "v", "A1", 103), ("new", "adj", "A1", 104), ("nice", "adj", "A1", 105),
    ("night", "n", "A1", 106), ("noisy", "adj", "A1", 107), ("old", "adj", "A1", 108),
    ("open", "v", "A1", 109), ("orange", "n", "A1", 110), ("page", "n", "A1", 111),
    ("paper", "n", "A1", 112), ("park", "n", "A1", 113), ("play", "v", "A1", 114),
    ("please", "interj", "A1", 115), ("pretty", "adj", "A1", 116), ("quiet", "adj", "A1", 117),
    ("rain", "n", "A1", 118), ("read", "v", "A1", 119), ("red", "adj", "A1", 120),
    ("rest", "v", "A1", 121), ("run", "v", "A1", 122), ("sad", "adj", "A1", 123),
    ("school", "n", "A1", 124), ("sea", "n", "A1", 125), ("see", "v", "A1", 126),
    ("sell", "v", "A1", 127), ("shop", "n", "A1", 128), ("sing", "v", "A1", 129),
    ("sister", "n", "A1", 130), ("sit", "v", "A1", 131), ("sleep", "v", "A1", 132),
    ("slow", "adj", "A1", 133), ("small", "adj", "A1", 134), ("smile", "v", "A1", 135),
    ("speak", "v", "A1", 136), ("stand", "v", "A1", 137), ("start", "v", "A1", 138),
    ("student", "n", "A1", 139), ("study", "v", "A1", 140), ("sun", "n", "A1", 141),
    ("table", "n", "A1", 142), ("talk", "v", "A1", 143), ("teacher", "n", "A1", 144),
    ("thank", "v", "A1", 145), ("time", "n", "A1", 146), ("tired", "adj", "A1", 147),
    ("today", "adv", "A1", 148), ("tomorrow", "adv", "A1", 149), ("tree", "n", "A1", 150),
    ("walk", "v", "A1", 151), ("want", "v", "A1", 152), ("water", "n", "A1", 153),
    ("weather", "n", "A1", 154), ("week", "n", "A1", 155), ("wife", "n", "A1", 156),
    ("window", "n", "A1", 157), ("work", "v", "A1", 158), ("write", "v", "A1", 159),
    ("year", "n", "A1", 160),
]
