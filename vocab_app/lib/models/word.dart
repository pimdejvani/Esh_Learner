/// Data classes for the vocab domain. Mirrors the SQLite schema in
/// SPEC.md section 4.
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
    required this.translationSource,
    required this.translationLicense,
    required this.hasPhoto,
    this.imageUrl,
    this.imageLicense,
    this.imageAuthor,
  });

  final int id;
  final String headword;
  final String cefr;
  final int freqRank;
  final String thaiReading;
  final int stressIndex;
  final String ipa;
  final String translationSource;
  final String translationLicense;
  final bool hasPhoto;
  final String? imageUrl;
  final String? imageLicense;
  final String? imageAuthor;

  factory Word.fromMap(Map<String, Object?> m) => Word(
    id: m['id'] as int,
    headword: m['headword'] as String,
    cefr: m['cefr'] as String? ?? '',
    freqRank: m['freq_rank'] as int? ?? 0,
    thaiReading: m['thai_reading'] as String? ?? '',
    stressIndex: m['stress_index'] as int? ?? 1,
    ipa: m['ipa'] as String? ?? '',
    translationSource: m['translation_source'] as String? ?? '',
    translationLicense: m['translation_license'] as String? ?? '',
    hasPhoto: (m['has_photo'] as int? ?? 0) == 1,
    imageUrl: m['image_url'] as String?,
    imageLicense: m['image_license'] as String?,
    imageAuthor: m['image_author'] as String?,
  );
}

class Sense {
  const Sense({
    required this.id,
    required this.wordId,
    required this.pos,
    required this.meaningTh,
    required this.cefr,
    this.countable,
    this.collocationEn,
    this.collocationTh,
    required this.senseRank,
    required this.isCore,
  });

  final int id;
  final int wordId;
  final String pos;
  final String meaningTh;
  final String cefr;
  final int? countable;
  final String? collocationEn;
  final String? collocationTh;
  final int senseRank;
  final bool isCore;

  factory Sense.fromMap(Map<String, Object?> m) => Sense(
    id: m['id'] as int,
    wordId: m['word_id'] as int,
    pos: m['pos'] as String? ?? '',
    meaningTh: m['meaning_th'] as String? ?? '',
    cefr: m['cefr'] as String? ?? '',
    countable: m['countable'] as int?,
    collocationEn: m['collocation_en'] as String?,
    collocationTh: m['collocation_th'] as String?,
    senseRank: m['sense_rank'] as int? ?? 1,
    isCore: (m['is_core'] as int? ?? 0) == 1,
  );
}

class WordForm {
  const WordForm({
    required this.id,
    required this.wordId,
    required this.formText,
    required this.formType,
    required this.isIrregular,
    required this.grammarNoteTh,
  });

  final int id;
  final int wordId;
  final String formText;
  final String formType;
  final bool isIrregular;
  final String grammarNoteTh;

  factory WordForm.fromMap(Map<String, Object?> m) => WordForm(
    id: m['id'] as int,
    wordId: m['word_id'] as int,
    formText: m['form_text'] as String? ?? '',
    formType: m['form_type'] as String? ?? '',
    isIrregular: (m['is_irregular'] as int? ?? 0) == 1,
    grammarNoteTh: m['grammar_note_th'] as String? ?? '',
  );
}

class ExampleSentence {
  const ExampleSentence({
    required this.id,
    required this.wordId,
    this.formId,
    required this.rank,
    required this.enText,
    required this.thText,
    required this.clozeStart,
    required this.clozeEnd,
    required this.isEmotional,
  });

  final int id;
  final int wordId;
  final int? formId;
  final int rank;
  final String enText;
  final String thText;
  final int clozeStart;
  final int clozeEnd;
  final bool isEmotional;

  String get clozeTarget => enText.substring(clozeStart, clozeEnd);

  factory ExampleSentence.fromMap(Map<String, Object?> m) => ExampleSentence(
    id: m['id'] as int,
    wordId: m['word_id'] as int,
    formId: m['form_id'] as int?,
    rank: m['rank'] as int? ?? 1,
    enText: m['en_text'] as String? ?? '',
    thText: m['th_text'] as String? ?? '',
    clozeStart: m['cloze_start'] as int? ?? 0,
    clozeEnd: m['cloze_end'] as int? ?? 0,
    isEmotional: (m['is_emotional'] as int? ?? 0) == 1,
  );
}

class RelatedWord {
  const RelatedWord({
    required this.id,
    required this.wordId,
    required this.relatedWordId,
    required this.relationType,
    required this.closeness,
    required this.isGiveaway,
  });

  final int id;
  final int wordId;
  final int relatedWordId;
  final String relationType;
  final double closeness;
  final bool isGiveaway;

  factory RelatedWord.fromMap(Map<String, Object?> m) => RelatedWord(
    id: m['id'] as int,
    wordId: m['word_id'] as int,
    relatedWordId: m['related_word_id'] as int,
    relationType: m['relation_type'] as String? ?? '',
    closeness: (m['closeness'] as num?)?.toDouble() ?? 0,
    isGiveaway: (m['is_giveaway'] as int? ?? 0) == 1,
  );
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

  /// All senses for the word (not just the core one), sorted by
  /// `sense_rank` — used by the full dictionary entry (word_detail_page,
  /// SPEC.md 9b layer 2). Phase 1 only ever populated the single core
  /// sense per word in [coreSense]; this list degrades gracefully to that
  /// same single sense when the seed data hasn't grown extra senses yet.
  final List<Sense> senses;
  final List<WordForm> forms;
  final List<ExampleSentence> sentences;
  final List<RelatedWord> related;
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
