# -*- coding: utf-8 -*-
r"""
Real word-association / closeness data for related_words rows with
relation_type='association', sourced from the actual SWOW-EN18 dataset
(Small World of Words, English, 2018 release), replacing the old hand-curated
RELATED_FALLBACK approximation documented in NOTES.md as a temporary stand-in
while the real data was gated behind a name/email request form on
smallworldofwords.org.

SOURCE: strength.SWOW-EN.R123.20180827.csv (2018-08-27 release), the official
cue-response associative-strength file from the SWOW-EN18 project (De Deyne,
S., Navarro, D.J., Perfors, A., Brysbaert, M., & Storms, G. (2019). "The Small
World of Words English word association norms for over 12,000 cue words."
Behavior Research Methods.) Manually downloaded by the user via the project's
own request form at smallworldofwords.org (that form requires a human name +
email and cannot be automated) and handed to this pipeline at
C:\Users\pimde\Downloads\SWOW-EN18\. `R123.Strength` is the dataset's own
cue -> response conditional-probability score (fraction of participants who
gave that response to that cue), pooled across all 3 response positions --
used here verbatim as `closeness`, not a placeholder.

METHOD: loaded the full ~1.39M-row strength file, restricted to rows where
BOTH `cue` and `response` are (case-insensitively) one of this app's 153
seed headwords (tools/wordlist.py), dropped self-loops, then for each of the
153 words took its rows as cue sorted by `R123.Strength` descending and kept
the top 6 (SWOW itself is directional/asymmetric -- e.g. "cat"->"dog" and
"dog"->"cat" are two different real rows with different strengths, both kept
if both survive the cap -- this mirrors how SWOW actually collected the data,
not an artifact of this pipeline).

RESULT: all 153/153 words had at least 2 real in-vocabulary
associations (min 4, max 28, avg ~14.3 real candidate rows before capping --
see NOTES.md for the full distribution) -- so, unlike the original worry that
some words might have too little real data and need to stay on the old
hand-curated RELATED_FALLBACK, that fallback path ended up NOT being needed
for any word this pass. `build_dataset.py`'s `resolve_related()` still checks
a (currently empty) per-word exception list before falling back to
RELATED_FALLBACK, purely so the mechanism keeps working unattended if a future
word-list change ever introduces a word SWOW has too little data for -- it is
not exercised by any of the current 153 words.
"""

# word -> [(related_word, closeness), ...] sorted by closeness (SWOW
# R123.Strength) descending, capped to the top 6 per cue word.
SWOW_ASSOCIATIONS = {
    "about": [("time", 0.033582), ("near", 0.033582), ("book", 0.007463), ("work", 0.003731), ("nice", 0.003731), ("all", 0.003731)],
    "after": [("late", 0.013889), ("work", 0.010417), ("school", 0.010417), ("morning", 0.006944), ("all", 0.006944), ("time", 0.003472)],
    "again": [("and", 0.036630), ("time", 0.010989), ("also", 0.007326), ("come", 0.007326), ("go", 0.003663), ("home", 0.003663)],
    "all": [("every", 0.062718), ("love", 0.006969), ("family", 0.006969), ("about", 0.003484), ("big", 0.003484), ("bread", 0.003484)],
    "also": [("and", 0.163498), ("again", 0.022814), ("like", 0.007605), ("love", 0.003802)],
    "and": [("also", 0.123675), ("again", 0.007067), ("music", 0.003534), ("fast", 0.003534)],
    "answer": [("ask", 0.013793), ("know", 0.010345), ("give", 0.006897), ("good", 0.003448), ("door", 0.003448), ("find", 0.003448)],
    "ask": [("answer", 0.051370), ("help", 0.010274), ("please", 0.010274), ("talk", 0.006849), ("speak", 0.003425), ("student", 0.003425)],
    "baby": [("child", 0.058219), ("boy", 0.030822), ("small", 0.023973), ("girl", 0.023973), ("talk", 0.010274), ("little", 0.010274)],
    "bad": [("good", 0.155405), ("boy", 0.027027), ("dog", 0.016892), ("man", 0.016892), ("day", 0.010135), ("sad", 0.006757)],
    "bag": [("paper", 0.058621), ("man", 0.017241), ("money", 0.006897), ("lunch", 0.006897), ("old", 0.006897), ("food", 0.003448)],
    "beautiful": [("pretty", 0.114187), ("girl", 0.065744), ("hot", 0.017301), ("nice", 0.017301), ("sun", 0.010381), ("eye", 0.006920)],
    "bed": [("sleep", 0.251678), ("time", 0.033557), ("night", 0.013423), ("make", 0.010067), ("tired", 0.006711), ("clothes", 0.006711)],
    "big": [("small", 0.089965), ("little", 0.069204), ("boy", 0.017301), ("house", 0.006920), ("fish", 0.006920), ("great", 0.006920)],
    "bird": [("tree", 0.013559), ("egg", 0.010169), ("beautiful", 0.006780), ("sing", 0.006780), ("small", 0.006780), ("dog", 0.003390)],
    "book": [("read", 0.178451), ("paper", 0.030303), ("page", 0.026936), ("write", 0.013468), ("study", 0.013468), ("love", 0.010101)],
    "boy": [("girl", 0.237113), ("child", 0.092784), ("man", 0.058419), ("friend", 0.044674), ("play", 0.027491), ("baby", 0.013746)],
    "bread": [("food", 0.093960), ("money", 0.026846), ("water", 0.016779), ("eat", 0.016779), ("hungry", 0.010067), ("home", 0.006711)],
    "brother": [("sister", 0.217687), ("family", 0.078231), ("mother", 0.071429), ("father", 0.064626), ("friend", 0.037415), ("love", 0.037415)],
    "busy": [("work", 0.082192), ("time", 0.017123), ("happy", 0.017123), ("tired", 0.017123), ("fast", 0.010274), ("day", 0.010274)],
    "buy": [("sell", 0.096886), ("money", 0.096886), ("shop", 0.051903), ("food", 0.020761), ("time", 0.013841), ("clothes", 0.010381)],
    "car": [("drive", 0.068493), ("red", 0.013699), ("go", 0.010274), ("park", 0.006849), ("door", 0.006849), ("home", 0.003425)],
    "cat": [("dog", 0.204698), ("house", 0.006711), ("hat", 0.006711), ("fish", 0.006711), ("food", 0.003356), ("home", 0.003356)],
    "chair": [("sit", 0.171930), ("table", 0.105263), ("hard", 0.010526), ("work", 0.007018), ("man", 0.007018), ("house", 0.003509)],
    "child": [("baby", 0.091837), ("boy", 0.044218), ("girl", 0.030612), ("small", 0.023810), ("mother", 0.023810), ("little", 0.017007)],
    "city": [("busy", 0.027397), ("big", 0.027397), ("home", 0.013699), ("live", 0.006849), ("bad", 0.003425), ("light", 0.003425)],
    "clean": [("house", 0.045139), ("work", 0.013889), ("nice", 0.013889), ("clothes", 0.010417), ("eat", 0.006944), ("green", 0.006944)],
    "clothes": [("hat", 0.006873), ("shop", 0.006873), ("red", 0.006873), ("bag", 0.003436), ("big", 0.003436), ("clean", 0.003436)],
    "cold": [("hot", 0.066890), ("weather", 0.040134), ("drink", 0.013378), ("water", 0.013378), ("sea", 0.003344), ("sun", 0.003344)],
    "come": [("go", 0.123675), ("home", 0.049470), ("again", 0.017668), ("sit", 0.010601), ("dog", 0.007067), ("start", 0.003534)],
    "cook": [("food", 0.133562), ("kitchen", 0.058219), ("eat", 0.047945), ("book", 0.020548), ("clean", 0.013699), ("make", 0.006849)],
    "dance": [("music", 0.068027), ("sing", 0.020408), ("play", 0.006803), ("beautiful", 0.003401), ("fast", 0.003401), ("girl", 0.003401)],
    "day": [("night", 0.191919), ("light", 0.121212), ("sun", 0.077441), ("time", 0.070707), ("work", 0.030303), ("morning", 0.026936)],
    "different": [("new", 0.023973), ("good", 0.017123), ("bad", 0.003425), ("cold", 0.003425), ("language", 0.003425), ("sad", 0.003425)],
    "dog": [("cat", 0.175862), ("friend", 0.051724), ("happy", 0.013793), ("run", 0.013793), ("love", 0.013793), ("walk", 0.010345)],
    "door": [("open", 0.128378), ("window", 0.087838), ("house", 0.016892), ("red", 0.006757), ("car", 0.003378), ("light", 0.003378)],
    "drink": [("water", 0.160959), ("milk", 0.027397), ("eat", 0.023973), ("cold", 0.006849), ("bird", 0.003425), ("drive", 0.003425)],
    "drive": [("car", 0.238754), ("fast", 0.034602), ("go", 0.013841), ("hard", 0.010381), ("time", 0.010381), ("home", 0.006920)],
    "early": [("morning", 0.185567), ("late", 0.113402), ("bird", 0.109966), ("bed", 0.017182), ("sun", 0.013746), ("tired", 0.013746)],
    "easy": [("hard", 0.141343), ("fast", 0.031802), ("chair", 0.010601), ("come", 0.007067), ("time", 0.007067), ("money", 0.007067)],
    "eat": [("food", 0.175862), ("drink", 0.082759), ("hungry", 0.024138), ("love", 0.010345), ("table", 0.010345), ("dog", 0.006897)],
    "egg": [("food", 0.013514), ("eat", 0.010135), ("good", 0.006757), ("bird", 0.006757), ("kitchen", 0.003378), ("light", 0.003378)],
    "evening": [("night", 0.138514), ("morning", 0.050676), ("good", 0.027027), ("day", 0.013514), ("sleep", 0.013514), ("late", 0.010135)],
    "every": [("all", 0.182759), ("day", 0.075862), ("time", 0.055172), ("man", 0.006897), ("week", 0.006897), ("year", 0.003448)],
    "eye": [("see", 0.090909), ("look", 0.026936), ("window", 0.010101), ("light", 0.003367), ("beautiful", 0.003367)],
    "family": [("love", 0.074576), ("home", 0.030508), ("mother", 0.023729), ("sister", 0.023729), ("brother", 0.020339), ("time", 0.016949)],
    "far": [("near", 0.101399), ("long", 0.055944), ("time", 0.013986), ("go", 0.006993), ("walk", 0.003497), ("work", 0.003497)],
    "fast": [("slow", 0.083045), ("car", 0.048443), ("run", 0.038062), ("food", 0.034602), ("hungry", 0.006920), ("easy", 0.006920)],
    "father": [("mother", 0.184300), ("brother", 0.027304), ("family", 0.027304), ("sister", 0.017065), ("man", 0.017065), ("love", 0.010239)],
    "find": [("look", 0.044118), ("money", 0.011029), ("happy", 0.007353), ("see", 0.007353), ("open", 0.003676), ("learn", 0.003676)],
    "fish": [("water", 0.060403), ("food", 0.046980), ("sea", 0.020134), ("eat", 0.013423), ("cat", 0.003356), ("eye", 0.003356)],
    "food": [("eat", 0.133562), ("cook", 0.030822), ("good", 0.030822), ("hungry", 0.023973), ("drink", 0.020548), ("lunch", 0.010274)],
    "friend": [("love", 0.024648), ("girl", 0.021127), ("family", 0.017606), ("school", 0.014085), ("happy", 0.014085), ("brother", 0.007042)],
    "garden": [("green", 0.060201), ("food", 0.020067), ("water", 0.016722), ("work", 0.016722), ("beautiful", 0.006689), ("bed", 0.003344)],
    "girl": [("boy", 0.178451), ("friend", 0.057239), ("child", 0.053872), ("pretty", 0.030303), ("baby", 0.016835), ("hot", 0.013468)],
    "give": [("money", 0.016835), ("love", 0.006734), ("hope", 0.006734), ("time", 0.006734), ("nice", 0.006734), ("thank", 0.003367)],
    "go": [("come", 0.031359), ("fast", 0.027875), ("home", 0.024390), ("run", 0.024390), ("start", 0.020906), ("green", 0.020906)],
    "good": [("bad", 0.139456), ("nice", 0.027211), ("great", 0.027211), ("food", 0.020408), ("job", 0.017007), ("boy", 0.017007)],
    "great": [("good", 0.068966), ("big", 0.058621), ("job", 0.010345), ("man", 0.010345), ("small", 0.010345), ("happy", 0.006897)],
    "green": [("money", 0.044218), ("red", 0.030612), ("tree", 0.023810), ("new", 0.013605), ("light", 0.013605), ("garden", 0.010204)],
    "happy": [("sad", 0.112245), ("day", 0.013605), ("love", 0.013605), ("dog", 0.010204), ("sun", 0.006803), ("good", 0.006803)],
    "hard": [("easy", 0.061433), ("work", 0.020478), ("hat", 0.010239), ("water", 0.010239), ("table", 0.006826), ("time", 0.006826)],
    "hat": [("cat", 0.059859), ("man", 0.010563), ("cold", 0.010563), ("stand", 0.007042), ("hot", 0.003521), ("red", 0.003521)],
    "have": [("want", 0.034965), ("need", 0.017483), ("give", 0.010490), ("like", 0.006993), ("money", 0.006993), ("clothes", 0.003497)],
    "hear": [("listen", 0.166667), ("music", 0.054422), ("see", 0.040816), ("speak", 0.017007), ("learn", 0.006803), ("quiet", 0.006803)],
    "help": [("need", 0.038194), ("give", 0.013889), ("good", 0.013889), ("please", 0.010417), ("friend", 0.006944), ("nice", 0.006944)],
    "home": [("house", 0.163880), ("family", 0.086957), ("love", 0.033445), ("sleep", 0.006689), ("school", 0.006689), ("work", 0.006689)],
    "hope": [("love", 0.061224), ("happy", 0.020408), ("light", 0.010204), ("family", 0.006803), ("want", 0.006803), ("good", 0.006803)],
    "hot": [("cold", 0.113712), ("water", 0.033445), ("sun", 0.026756), ("red", 0.026756), ("weather", 0.020067), ("fast", 0.006689)],
    "house": [("home", 0.257627), ("live", 0.027119), ("family", 0.013559), ("cat", 0.010169), ("door", 0.010169), ("love", 0.010169)],
    "hungry": [("food", 0.192308), ("eat", 0.052448), ("tired", 0.017483), ("lunch", 0.013986), ("man", 0.010490), ("need", 0.003497)],
    "husband": [("wife", 0.225694), ("man", 0.097222), ("love", 0.031250), ("father", 0.020833), ("friend", 0.010417), ("family", 0.006944)],
    "job": [("work", 0.209622), ("money", 0.037801), ("hard", 0.013746), ("happy", 0.006873), ("study", 0.003436), ("sit", 0.003436)],
    "kitchen": [("food", 0.132653), ("cook", 0.088435), ("table", 0.030612), ("eat", 0.017007), ("house", 0.013605), ("family", 0.010204)],
    "know": [("learn", 0.035088), ("book", 0.017544), ("study", 0.017544), ("about", 0.010526), ("ask", 0.007018), ("all", 0.007018)],
    "language": [("speak", 0.060606), ("talk", 0.020202), ("study", 0.013468), ("learn", 0.010101), ("different", 0.006734), ("listen", 0.003367)],
    "late": [("early", 0.083624), ("night", 0.052265), ("time", 0.031359), ("work", 0.017422), ("again", 0.013937), ("slow", 0.013937)],
    "laugh": [("happy", 0.097973), ("love", 0.016892), ("good", 0.006757), ("play", 0.006757), ("again", 0.003378), ("wife", 0.003378)],
    "learn": [("school", 0.093103), ("study", 0.082759), ("read", 0.058621), ("know", 0.020690), ("book", 0.013793), ("teacher", 0.013793)],
    "light": [("sun", 0.046667), ("day", 0.020000), ("easy", 0.016667), ("house", 0.013333), ("dog", 0.003333), ("rain", 0.003333)],
    "like": [("love", 0.156794), ("happy", 0.017422), ("want", 0.017422), ("food", 0.013937), ("friend", 0.010453), ("good", 0.006969)],
    "listen": [("hear", 0.224913), ("music", 0.038062), ("quiet", 0.034602), ("speak", 0.027682), ("learn", 0.024221), ("look", 0.017301)],
    "little": [("small", 0.209622), ("big", 0.072165), ("boy", 0.013746), ("house", 0.013746), ("child", 0.013746), ("bird", 0.010309)],
    "live": [("long", 0.040404), ("love", 0.026936), ("music", 0.016835), ("home", 0.013468), ("laugh", 0.013468), ("today", 0.010101)],
    "long": [("time", 0.060201), ("far", 0.016722), ("day", 0.010033), ("hard", 0.010033), ("want", 0.006689), ("slow", 0.003344)],
    "look": [("see", 0.221477), ("listen", 0.026846), ("book", 0.026846), ("eye", 0.026846), ("like", 0.006711), ("about", 0.003356)],
    "love": [("family", 0.050847), ("like", 0.027119), ("husband", 0.016949), ("girl", 0.006780), ("wife", 0.006780), ("hope", 0.006780)],
    "lunch": [("food", 0.081911), ("eat", 0.075085), ("time", 0.044369), ("hungry", 0.027304), ("bag", 0.010239), ("table", 0.006826)],
    "make": [("cook", 0.020906), ("love", 0.017422), ("money", 0.013937), ("bed", 0.013937), ("car", 0.010453), ("work", 0.010453)],
    "man": [("child", 0.054608), ("boy", 0.034130), ("husband", 0.017065), ("father", 0.013652), ("dog", 0.010239), ("family", 0.010239)],
    "meet": [("see", 0.021053), ("friend", 0.017544), ("new", 0.014035), ("talk", 0.010526), ("know", 0.007018), ("find", 0.003509)],
    "milk": [("drink", 0.057047), ("cold", 0.016779), ("mother", 0.013423), ("baby", 0.013423), ("man", 0.006711), ("water", 0.006711)],
    "money": [("green", 0.037415), ("work", 0.013605), ("time", 0.010204), ("buy", 0.010204), ("have", 0.006803), ("love", 0.006803)],
    "morning": [("sun", 0.058419), ("day", 0.048110), ("good", 0.044674), ("evening", 0.037801), ("night", 0.037801), ("early", 0.037801)],
    "mother": [("father", 0.117450), ("love", 0.090604), ("child", 0.033557), ("sister", 0.023490), ("brother", 0.023490), ("family", 0.016779)],
    "music": [("dance", 0.034247), ("sing", 0.023973), ("play", 0.020548), ("listen", 0.013699), ("beautiful", 0.010274), ("love", 0.006849)],
    "name": [("baby", 0.013986), ("family", 0.006993), ("friend", 0.003497), ("day", 0.003497), ("husband", 0.003497), ("good", 0.003497)],
    "near": [("far", 0.224199), ("home", 0.014235), ("love", 0.010676), ("about", 0.007117), ("friend", 0.007117), ("family", 0.003559)],
    "need": [("want", 0.220280), ("have", 0.027972), ("food", 0.024476), ("love", 0.017483), ("money", 0.017483), ("help", 0.013986)],
    "new": [("old", 0.120567), ("clean", 0.028369), ("baby", 0.021277), ("clothes", 0.017730), ("different", 0.010638), ("nice", 0.010638)],
    "nice": [("good", 0.079038), ("pretty", 0.030928), ("easy", 0.024055), ("day", 0.020619), ("happy", 0.013746), ("dog", 0.010309)],
    "night": [("day", 0.104730), ("sleep", 0.070946), ("time", 0.060811), ("evening", 0.047297), ("light", 0.033784), ("good", 0.016892)],
    "old": [("new", 0.071186), ("man", 0.030508), ("dog", 0.013559), ("mother", 0.010169), ("time", 0.006780), ("clothes", 0.006780)],
    "open": [("door", 0.106164), ("window", 0.020548), ("house", 0.006849), ("book", 0.006849), ("shop", 0.006849), ("easy", 0.003425)],
    "orange": [("red", 0.030612), ("tree", 0.010204), ("sun", 0.010204), ("green", 0.006803), ("food", 0.003401), ("good", 0.003401)],
    "page": [("book", 0.209790), ("paper", 0.080420), ("boy", 0.041958), ("read", 0.034965), ("name", 0.006993), ("time", 0.003497)],
    "paper": [("write", 0.054054), ("make", 0.030405), ("book", 0.020270), ("tree", 0.013514), ("bag", 0.013514), ("read", 0.010135)],
    "park": [("car", 0.145763), ("green", 0.054237), ("play", 0.040678), ("walk", 0.027119), ("dog", 0.020339), ("garden", 0.016949)],
    "play": [("music", 0.016949), ("child", 0.013559), ("time", 0.013559), ("work", 0.013559), ("boy", 0.010169), ("hard", 0.010169)],
    "please": [("ask", 0.042105), ("help", 0.031579), ("happy", 0.017544), ("nice", 0.017544), ("pretty", 0.014035), ("want", 0.007018)],
    "pretty": [("girl", 0.113014), ("beautiful", 0.106164), ("nice", 0.044521), ("good", 0.023973), ("hot", 0.010274), ("clean", 0.006849)],
    "quiet": [("time", 0.030405), ("sleep", 0.013514), ("small", 0.010135), ("please", 0.003378), ("read", 0.003378), ("teacher", 0.003378)],
    "rain": [("water", 0.093960), ("cold", 0.040268), ("weather", 0.023490), ("beautiful", 0.003356), ("hard", 0.003356), ("sun", 0.003356)],
    "read": [("book", 0.178947), ("write", 0.073684), ("learn", 0.035088), ("page", 0.017544), ("paper", 0.017544), ("see", 0.017544)],
    "red": [("green", 0.033784), ("orange", 0.013514), ("light", 0.010135), ("hot", 0.010135), ("love", 0.006757), ("eye", 0.006757)],
    "run": [("fast", 0.127586), ("walk", 0.058621), ("far", 0.010345), ("go", 0.006897), ("good", 0.006897), ("work", 0.006897)],
    "sad": [("happy", 0.071685), ("bad", 0.021505), ("rain", 0.007168), ("day", 0.007168), ("ask", 0.003584), ("child", 0.003584)],
    "school": [("learn", 0.068729), ("work", 0.061856), ("teacher", 0.037801), ("lunch", 0.013746), ("fish", 0.013746), ("book", 0.013746)],
    "sea": [("water", 0.090000), ("fish", 0.023333), ("green", 0.010000), ("see", 0.010000), ("big", 0.010000), ("food", 0.003333)],
    "see": [("look", 0.098305), ("eye", 0.040678), ("hear", 0.040678), ("sea", 0.020339), ("know", 0.016949), ("far", 0.006780)],
    "sell": [("buy", 0.214035), ("money", 0.070175), ("car", 0.014035), ("house", 0.014035), ("shop", 0.003509), ("food", 0.003509)],
    "shop": [("buy", 0.123675), ("money", 0.028269), ("clothes", 0.021201), ("food", 0.021201), ("window", 0.017668), ("work", 0.010601)],
    "sing": [("music", 0.078498), ("happy", 0.020478), ("bird", 0.020478), ("dance", 0.017065), ("laugh", 0.003413), ("listen", 0.003413)],
    "sister": [("brother", 0.171329), ("family", 0.083916), ("friend", 0.062937), ("girl", 0.034965), ("mother", 0.020979), ("love", 0.017483)],
    "sit": [("chair", 0.150685), ("stand", 0.065068), ("dog", 0.054795), ("work", 0.010274), ("baby", 0.006849), ("table", 0.006849)],
    "sleep": [("bed", 0.105085), ("tired", 0.047458), ("night", 0.040678), ("quiet", 0.016949), ("time", 0.013559), ("late", 0.013559)],
    "slow": [("fast", 0.118467), ("walk", 0.013937), ("time", 0.010453), ("food", 0.010453), ("quiet", 0.006969), ("car", 0.006969)],
    "small": [("little", 0.121107), ("big", 0.038062), ("baby", 0.017301), ("child", 0.013841), ("time", 0.003460), ("late", 0.003460)],
    "speak": [("talk", 0.191126), ("language", 0.044369), ("listen", 0.037543), ("easy", 0.030717), ("dog", 0.020478), ("hear", 0.010239)],
    "stand": [("sit", 0.073427), ("table", 0.017483), ("music", 0.013986), ("walk", 0.010490), ("tired", 0.010490), ("book", 0.006993)],
    "start": [("go", 0.054608), ("new", 0.013652), ("again", 0.006826), ("early", 0.003413), ("day", 0.003413), ("fast", 0.003413)],
    "student": [("teacher", 0.115646), ("school", 0.105442), ("study", 0.057823), ("learn", 0.027211), ("work", 0.020408), ("child", 0.010204)],
    "study": [("learn", 0.102389), ("hard", 0.051195), ("school", 0.044369), ("read", 0.037543), ("book", 0.034130), ("work", 0.027304)],
    "sun": [("light", 0.068027), ("hot", 0.061224), ("day", 0.034014), ("happy", 0.010204), ("beautiful", 0.003401), ("big", 0.003401)],
    "table": [("chair", 0.118243), ("food", 0.033784), ("eat", 0.033784), ("kitchen", 0.010135), ("sit", 0.010135), ("work", 0.010135)],
    "talk": [("speak", 0.119863), ("listen", 0.037671), ("walk", 0.010274), ("hear", 0.010274), ("language", 0.006849), ("about", 0.006849)],
    "teacher": [("school", 0.122449), ("student", 0.095238), ("learn", 0.020408), ("study", 0.020408), ("book", 0.010204), ("mother", 0.006803)],
    "thank": [("please", 0.021352), ("friend", 0.007117), ("give", 0.007117), ("nice", 0.007117), ("happy", 0.003559), ("help", 0.003559)],
    "time": [("late", 0.017241), ("day", 0.010345), ("money", 0.006897), ("go", 0.006897), ("early", 0.006897), ("fast", 0.006897)],
    "tired": [("sleep", 0.068966), ("bed", 0.068966), ("work", 0.041379), ("night", 0.013793), ("sad", 0.006897), ("old", 0.006897)],
    "today": [("tomorrow", 0.165493), ("day", 0.017606), ("time", 0.014085), ("busy", 0.010563), ("week", 0.007042), ("sun", 0.003521)],
    "tomorrow": [("today", 0.165493), ("day", 0.052817), ("morning", 0.031690), ("hope", 0.017606), ("new", 0.017606), ("work", 0.014085)],
    "tree": [("green", 0.085911), ("house", 0.017182), ("big", 0.013746), ("park", 0.006873), ("paper", 0.003436), ("bird", 0.003436)],
    "walk": [("run", 0.130137), ("talk", 0.054795), ("dog", 0.051370), ("fast", 0.013699), ("slow", 0.013699), ("far", 0.006849)],
    "want": [("need", 0.228873), ("have", 0.024648), ("ask", 0.010563), ("food", 0.010563), ("like", 0.010563), ("long", 0.007042)],
    "water": [("drink", 0.094915), ("clean", 0.016949), ("sea", 0.013559), ("cold", 0.010169), ("rain", 0.010169), ("hot", 0.006780)],
    "weather": [("rain", 0.161074), ("sun", 0.073826), ("cold", 0.057047), ("man", 0.016779), ("hot", 0.016779), ("bad", 0.010067)],
    "week": [("day", 0.141869), ("work", 0.065744), ("year", 0.058824), ("time", 0.041522), ("long", 0.020761), ("today", 0.006920)],
    "wife": [("husband", 0.154639), ("mother", 0.054983), ("love", 0.048110), ("friend", 0.020619), ("good", 0.013746), ("house", 0.013746)],
    "window": [("door", 0.060811), ("open", 0.043919), ("see", 0.027027), ("look", 0.016892), ("light", 0.016892), ("house", 0.016892)],
    "work": [("hard", 0.100346), ("play", 0.093426), ("job", 0.058824), ("money", 0.027682), ("study", 0.024221), ("time", 0.010381)],
    "write": [("read", 0.061644), ("paper", 0.054795), ("book", 0.044521), ("friend", 0.006849), ("language", 0.006849), ("work", 0.003425)],
    "year": [("time", 0.106164), ("day", 0.030822), ("long", 0.030822), ("new", 0.017123), ("week", 0.010274), ("old", 0.010274)],
}

# Words where real SWOW data restricted to this 153-word vocabulary was too
# sparse (< 2 rows) to build a useful round -- documented per-word
# exception, kept on the old hand-curated RELATED_FALLBACK in build_dataset.py.
# Empty for the current 153-word list (see RESULT above) -- kept as a named,
# always-checked set so this stays correct if the word list ever changes.
SWOW_FALLBACK_EXCEPTIONS = []

