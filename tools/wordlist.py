# -*- coding: utf-8 -*-
"""
Source word list for Phase 1 seed (~150 headwords, Oxford 3000 band A1).

DATA SOURCE NOTE (see NOTES.md section 1 for the full accounting):
The headwords + CEFR band below are now CROSS-CHECKED against a real,
machine-fetched Oxford 3000 CEFR source: the "A1"/"A2"/"B1"/"B2" word-array
JSON published at
https://raw.githubusercontent.com/Kolia951/The_Oxford_3000_CEFR/main/package.txt
(892 words in its "A1" array at the time this check was run, 2026-07-22).

Every one of the original 160 hand-typed headwords was checked against that
real A1 array. 7 were NOT actually present in the real A1 array and were
DROPPED (not swapped -- see NOTES.md for the reasoning):
  - "cry", "lady", "noisy", "rest", "smile" -- real Oxford 3000 words, just
    correctly listed under the A2 band in the source, not A1.
  - "English" -- not present in ANY band array in this source at all
    (nationality adjectives derived from proper nouns appear to be excluded
    from this CEFR list entirely).
  - "a" -- also not present in any band array (unlike "the", which IS in
    the source's A1 array). Considered swapping "a" -> "the", but Wiktionary
    itself has no Thai translation entry for either English article (Thai
    has no articles), so swapping would not have actually fixed anything for
    the Thai-sourcing pass (see NOTES.md section 2) while still costing a
    word-list change -- dropped instead of swapped.
That leaves 153 words (160 - 7), all now verified present in the real A1
array. See NOTES.md section 1 for exactly which pipeline files (thai_data.py,
llm_sentences.py, RELATED_FALLBACK in build_dataset.py) had entries for the
7 dropped words removed as a result.

`freq_rank` is NOT from the OUP frequency data (that figure isn't published
in the free source used here) -- it remains this pipeline's own sequential
ordering (renumbered 1..153 after the 7 drops), used only to control
new-card introduction order. It is not claimed as a sourced frequency
statistic.

POS tags are still hand-assigned (the fetched source has no POS field) --
per SPEC.md this is explicitly an allowed non-sourced human/LLM judgment
call (grammatical fact, not translation/definition), e.g. verifying "answer"
can be a verb needs no citation beyond any dictionary.

Each entry: (headword, pos, cefr, freq_rank)
pos: n / v / adj / adv / prep / pron / det / conj / interj / phrase
"""

WORDS = [
    ('about', 'prep', 'A1', 1), ('after', 'prep', 'A1', 2), ('again', 'adv', 'A1', 3),
    ('all', 'det', 'A1', 4), ('also', 'adv', 'A1', 5), ('and', 'conj', 'A1', 6),
    ('answer', 'v', 'A1', 7), ('ask', 'v', 'A1', 8), ('baby', 'n', 'A1', 9),
    ('bad', 'adj', 'A1', 10), ('bag', 'n', 'A1', 11), ('beautiful', 'adj', 'A1', 12),
    ('bed', 'n', 'A1', 13), ('big', 'adj', 'A1', 14), ('bird', 'n', 'A1', 15),
    ('book', 'n', 'A1', 16), ('boy', 'n', 'A1', 17), ('bread', 'n', 'A1', 18),
    ('brother', 'n', 'A1', 19), ('busy', 'adj', 'A1', 20), ('buy', 'v', 'A1', 21),
    ('car', 'n', 'A1', 22), ('cat', 'n', 'A1', 23), ('chair', 'n', 'A1', 24),
    ('child', 'n', 'A1', 25), ('city', 'n', 'A1', 26), ('clean', 'adj', 'A1', 27),
    ('clothes', 'n', 'A1', 28), ('cold', 'adj', 'A1', 29), ('come', 'v', 'A1', 30),
    ('cook', 'v', 'A1', 31), ('dance', 'v', 'A1', 32), ('day', 'n', 'A1', 33),
    ('different', 'adj', 'A1', 34), ('dog', 'n', 'A1', 35), ('door', 'n', 'A1', 36),
    ('drink', 'v', 'A1', 37), ('drive', 'v', 'A1', 38), ('early', 'adv', 'A1', 39),
    ('easy', 'adj', 'A1', 40), ('eat', 'v', 'A1', 41), ('egg', 'n', 'A1', 42),
    ('evening', 'n', 'A1', 43), ('every', 'det', 'A1', 44), ('eye', 'n', 'A1', 45),
    ('family', 'n', 'A1', 46), ('far', 'adv', 'A1', 47), ('fast', 'adj', 'A1', 48),
    ('father', 'n', 'A1', 49), ('find', 'v', 'A1', 50), ('fish', 'n', 'A1', 51),
    ('food', 'n', 'A1', 52), ('friend', 'n', 'A1', 53), ('garden', 'n', 'A1', 54),
    ('girl', 'n', 'A1', 55), ('give', 'v', 'A1', 56), ('go', 'v', 'A1', 57),
    ('good', 'adj', 'A1', 58), ('great', 'adj', 'A1', 59), ('green', 'adj', 'A1', 60),
    ('happy', 'adj', 'A1', 61), ('hard', 'adj', 'A1', 62), ('hat', 'n', 'A1', 63),
    ('have', 'v', 'A1', 64), ('hear', 'v', 'A1', 65), ('help', 'v', 'A1', 66),
    ('home', 'n', 'A1', 67), ('hope', 'v', 'A1', 68), ('hot', 'adj', 'A1', 69),
    ('house', 'n', 'A1', 70), ('hungry', 'adj', 'A1', 71), ('husband', 'n', 'A1', 72),
    ('job', 'n', 'A1', 73), ('kitchen', 'n', 'A1', 74), ('know', 'v', 'A1', 75),
    ('language', 'n', 'A1', 76), ('late', 'adj', 'A1', 77), ('laugh', 'v', 'A1', 78),
    ('learn', 'v', 'A1', 79), ('light', 'n', 'A1', 80), ('like', 'v', 'A1', 81),
    ('listen', 'v', 'A1', 82), ('little', 'adj', 'A1', 83), ('live', 'v', 'A1', 84),
    ('long', 'adj', 'A1', 85), ('look', 'v', 'A1', 86), ('love', 'v', 'A1', 87),
    ('lunch', 'n', 'A1', 88), ('make', 'v', 'A1', 89), ('man', 'n', 'A1', 90),
    ('meet', 'v', 'A1', 91), ('milk', 'n', 'A1', 92), ('money', 'n', 'A1', 93),
    ('morning', 'n', 'A1', 94), ('mother', 'n', 'A1', 95), ('music', 'n', 'A1', 96),
    ('name', 'n', 'A1', 97), ('near', 'prep', 'A1', 98), ('need', 'v', 'A1', 99),
    ('new', 'adj', 'A1', 100), ('nice', 'adj', 'A1', 101), ('night', 'n', 'A1', 102),
    ('old', 'adj', 'A1', 103), ('open', 'v', 'A1', 104), ('orange', 'n', 'A1', 105),
    ('page', 'n', 'A1', 106), ('paper', 'n', 'A1', 107), ('park', 'n', 'A1', 108),
    ('play', 'v', 'A1', 109), ('please', 'interj', 'A1', 110), ('pretty', 'adj', 'A1', 111),
    ('quiet', 'adj', 'A1', 112), ('rain', 'n', 'A1', 113), ('read', 'v', 'A1', 114),
    ('red', 'adj', 'A1', 115), ('run', 'v', 'A1', 116), ('sad', 'adj', 'A1', 117),
    ('school', 'n', 'A1', 118), ('sea', 'n', 'A1', 119), ('see', 'v', 'A1', 120),
    ('sell', 'v', 'A1', 121), ('shop', 'n', 'A1', 122), ('sing', 'v', 'A1', 123),
    ('sister', 'n', 'A1', 124), ('sit', 'v', 'A1', 125), ('sleep', 'v', 'A1', 126),
    ('slow', 'adj', 'A1', 127), ('small', 'adj', 'A1', 128), ('speak', 'v', 'A1', 129),
    ('stand', 'v', 'A1', 130), ('start', 'v', 'A1', 131), ('student', 'n', 'A1', 132),
    ('study', 'v', 'A1', 133), ('sun', 'n', 'A1', 134), ('table', 'n', 'A1', 135),
    ('talk', 'v', 'A1', 136), ('teacher', 'n', 'A1', 137), ('thank', 'v', 'A1', 138),
    ('time', 'n', 'A1', 139), ('tired', 'adj', 'A1', 140), ('today', 'adv', 'A1', 141),
    ('tomorrow', 'adv', 'A1', 142), ('tree', 'n', 'A1', 143), ('walk', 'v', 'A1', 144),
    ('want', 'v', 'A1', 145), ('water', 'n', 'A1', 146), ('weather', 'n', 'A1', 147),
    ('week', 'n', 'A1', 148), ('wife', 'n', 'A1', 149), ('window', 'n', 'A1', 150),
    ('work', 'v', 'A1', 151), ('write', 'v', 'A1', 152), ('year', 'n', 'A1', 153),
]


# --- A2/B1 extension (2026-07-23, generated by tools/extend_a2b1.py) ---
try:
    from ext_a2b1 import WORDS_EXT
    WORDS = WORDS + WORDS_EXT
except ImportError:
    pass  # extension not generated yet -- Phase 1 seed only


# --- SWOW re-rank (2026-07-24, generated by tools/rerank_swow.py) ---
# Remaps freq_rank VALUES to SWOW-EN18 response-frequency order (band-major:
# A1 < A2 < B1, SWOW freq desc within band). List order is untouched so
# build_dataset.py insert order / word ids stay stable.
try:
    from swow_rerank import RANKS as _SWOW_RANKS
    WORDS = [(_h, _p, _c, _SWOW_RANKS.get(_h, _r)) for (_h, _p, _c, _r) in WORDS]
except ImportError:
    pass  # rerank not generated yet -- keep curated order
