/// Data classes for the vocab domain. Mirrors content schema v2, built by
/// `tools/build_content_db.py` and documented in SPEC.md section 4.
library;

class Word {
  const Word({
    required this.id,
    required this.headword,
    required this.cefr,
    required this.freqRank,
    required this.thaiReading,
    required this.stressIndex,
    required this.ipa,
    this.isTestOnly = false,
  });

  final int id;
  final String headword;
  final String cefr;
  final int freqRank;
  final String thaiReading;
  final int stressIndex;
  final String ipa;

  /// Part of the hard multi-POS test set rather than the real word list.
  /// Shipped builds export the seed without these (see `tools/export_app_seed.py`).
  final bool isTestOnly;

  factory Word.fromMap(Map<String, Object?> m) => Word(
    id: m['id'] as int,
    headword: m['headword'] as String,
    cefr: m['cefr'] as String? ?? '',
    freqRank: m['freq_rank'] as int? ?? 0,
    thaiReading: m['thai_reading'] as String? ?? '',
    stressIndex: m['stress_index'] as int? ?? 1,
    ipa: m['ipa'] as String? ?? '',
    isTestOnly: (m['is_test_only'] as int? ?? 0) == 1,
  );
}

class Sense {
  const Sense({
    required this.id,
    required this.wordId,
    required this.pos,
    required this.meaningTh,
    required this.glossEn,
    required this.senseRank,
    required this.isCore,
    this.meaningSource = '',
  });

  final int id;
  final int wordId;
  final String pos;
  final String meaningTh;

  /// The source gloss this sense was taken from, shown in the full Dictionary
  /// and used to prove the Thai meaning is not invented.
  final String glossEn;
  final int senseRank;
  final bool isCore;
  final String meaningSource;

  factory Sense.fromMap(Map<String, Object?> m) => Sense(
    id: m['id'] as int,
    wordId: m['word_id'] as int,
    pos: m['pos'] as String? ?? '',
    meaningTh: m['meaning_th'] as String? ?? '',
    glossEn: m['gloss_en'] as String? ?? '',
    senseRank: m['sense_rank'] as int? ?? 1,
    isCore: (m['is_core'] as int? ?? 0) == 1,
    meaningSource: m['meaning_source'] as String? ?? '',
  );
}

/// An inflection (`drink` -> `drank`) or a derived family member
/// (`employ` -> `employment`). The two are different things to a learner, so
/// [formType] decides which dropdown section a row belongs to.
class WordForm {
  const WordForm({
    required this.id,
    required this.wordId,
    required this.formText,
    required this.formType,
    required this.pos,
    required this.relation,
    required this.isIrregular,
    this.meaningTh,
    this.sourceName = '',
    this.sourceLicense = '',
  });

  static const String inflection = 'inflection';
  static const String derived = 'derived';

  final int id;
  final int wordId;
  final String formText;
  final String formType;
  final String pos;

  /// For inflections, the grammatical slot ("past participle", "plural").
  /// For derived words, the literal `derived`.
  final String relation;
  final bool isIrregular;
  final String? meaningTh;
  final String sourceName;
  final String sourceLicense;

  bool get isInflection => formType == inflection;
  bool get isDerived => formType == derived;

  factory WordForm.fromMap(Map<String, Object?> m) => WordForm(
    id: m['id'] as int,
    wordId: m['word_id'] as int,
    formText: m['form_text'] as String? ?? '',
    formType: m['form_type'] as String? ?? inflection,
    pos: m['pos'] as String? ?? '',
    relation: m['relation'] as String? ?? '',
    isIrregular: (m['is_irregular'] as int? ?? 0) == 1,
    meaningTh: m['meaning_th'] as String?,
    sourceName: m['source_name'] as String? ?? '',
    sourceLicense: m['source_license'] as String? ?? '',
  );
}

class ExampleSentence {
  const ExampleSentence({
    required this.id,
    required this.wordId,
    required this.senseId,
    required this.rank,
    required this.enText,
    required this.thText,
    required this.clozeStart,
    required this.clozeEnd,
    required this.formUsed,
    required this.isEmotional,
    required this.explanationTh,
    this.explanationSource = '',
  });

  final int id;
  final int wordId;

  /// Which sense this sentence teaches. Games and the card back use it so a
  /// noun example is never shown under a verb meaning.
  final int senseId;
  final int rank;
  final String enText;
  final String thText;
  final int clozeStart;
  final int clozeEnd;

  /// The exact form appearing in [enText] — may be an inflection of the headword.
  final String formUsed;
  final bool isEmotional;

  /// Stands alone: a player may see this sentence and nothing else, so the
  /// explanation never refers to another sentence (enforced by
  /// `tools/validate_content_db.py`).
  final String explanationTh;
  final String explanationSource;

  String get clozeTarget => enText.substring(clozeStart, clozeEnd);

  factory ExampleSentence.fromMap(Map<String, Object?> m) => ExampleSentence(
    id: m['id'] as int,
    wordId: m['word_id'] as int,
    senseId: m['sense_id'] as int? ?? 0,
    rank: m['rank'] as int? ?? 1,
    enText: m['en_text'] as String? ?? '',
    thText: m['th_text'] as String? ?? '',
    clozeStart: m['cloze_start'] as int? ?? 0,
    clozeEnd: m['cloze_end'] as int? ?? 0,
    formUsed: m['form_used'] as String? ?? '',
    isEmotional: (m['is_emotional'] as int? ?? 0) == 1,
    explanationTh: m['explanation_th'] as String? ?? '',
    explanationSource: m['explanation_source'] as String? ?? '',
  );
}

class RelatedWord {
  const RelatedWord({
    required this.id,
    required this.wordId,
    required this.relatedWordId,
    required this.relatedHeadword,
    required this.relationType,
    required this.closeness,
    required this.isGiveaway,
    this.senseId,
    this.confidence = 0,
    this.explanationTh,
  });

  final int id;
  final int wordId;
  final int relatedWordId;
  final String relatedHeadword;
  final String relationType;
  final double closeness;
  final bool isGiveaway;

  /// Related words hang off a sense, not the headword: `bank` (money) and
  /// `bank` (river) must not share a hint pool.
  final int? senseId;
  final double confidence;

  /// Why the pair is related, written when the content was built. Word
  /// Association shows this after the answer instead of guessing a reason.
  final String? explanationTh;

  factory RelatedWord.fromMap(Map<String, Object?> m) => RelatedWord(
    id: m['id'] as int,
    wordId: m['word_id'] as int,
    relatedWordId: m['related_word_id'] as int? ?? 0,
    relatedHeadword: m['related_headword'] as String? ?? '',
    relationType: m['relation_type'] as String? ?? '',
    closeness: (m['closeness'] as num?)?.toDouble() ?? 0,
    isGiveaway: (m['is_giveaway'] as int? ?? 0) == 1,
    senseId: m['sense_id'] as int?,
    confidence: (m['confidence'] as num?)?.toDouble() ?? 0,
    explanationTh: m['explanation_th'] as String?,
  );
}

/// A hub word plus the words associated with it, with the category they share.
/// Odd One Out builds a round from one of these and explains the answer with
/// [explanationTh] rather than reconstructing a reason afterwards.
class RelationGroup {
  const RelationGroup({
    required this.id,
    required this.hubWordId,
    required this.category,
    required this.explanationTh,
    required this.memberWordIds,
    this.sourceName = '',
  });

  final int id;
  final int hubWordId;
  final String category;
  final String explanationTh;
  final List<int> memberWordIds;
  final String sourceName;
}

/// A word bundled with everything the UI/game layer needs to present it.
class WordBundle {
  const WordBundle({
    required this.word,
    required this.coreSense,
    required this.senses,
    required this.forms,
    required this.sentences,
    required this.related,
  });

  final Word word;
  final Sense coreSense;

  /// Every sense of the word, ordered by POS then `sense_rank`. The Flashcard
  /// back shows one line per POS; the full Dictionary shows them all.
  final List<Sense> senses;
  final List<WordForm> forms;
  final List<ExampleSentence> sentences;
  final List<RelatedWord> related;

  /// Senses grouped by part of speech, preserving rank order within each POS.
  Map<String, List<Sense>> get sensesByPos {
    final grouped = <String, List<Sense>>{};
    for (final sense in senses) {
      grouped.putIfAbsent(sense.pos, () => []).add(sense);
    }
    return grouped;
  }

  List<WordForm> get inflections =>
      forms.where((f) => f.isInflection).toList(growable: false);

  List<WordForm> get family =>
      forms.where((f) => f.isDerived).toList(growable: false);

  /// The example that teaches [senseId], preferring the lowest rank.
  ExampleSentence? exampleForSense(int senseId) {
    for (final sentence in sentences) {
      if (sentence.senseId == senseId) return sentence;
    }
    return null;
  }
}

/// A topic/theme category (SPEC.md section 4 `topics` table) — used for
/// interleaving context and the Phase 2 "focus topic" setting (section 6.4).
class Topic {
  const Topic({required this.id, required this.name, required this.cefr});

  final int id;
  final String name;
  final String cefr;

  factory Topic.fromMap(Map<String, Object?> m) => Topic(
    id: m['id'] as int,
    name: m['name'] as String? ?? '',
    cefr: m['cefr'] as String? ?? '',
  );
}
