"""
Foundational language knowledge for 2bee — the alphabet, how letters form
words, how words form sentences, and how humans use written/spoken language
to communicate. Loaded on startup so 2bee can reason from first principles.

Run once: python -m brain.language_knowledge
"""

from brain.memory import init, add_fact

# Each entry: (topic, info). The loader also adds a second copy keyed by
# the head word of the info string, so 2bee finds facts by category
# ("what is a vowel") AND by specific term ("what is the letter a").
LANGUAGE = [
    # ─── What language IS ──────────────────────────────────────────────
    ("language_def", "language — a system of communication using symbols (letters) and sounds (phonemes) arranged by rules (grammar) to convey meaning between humans."),
    ("communication_def", "communication — the act of sending and receiving meaning. Humans communicate using words (spoken or written), tone, gesture, and context. Successful communication requires a shared system."),
    ("alphabet_def", "alphabet — an ordered set of letters used to write a language. The English alphabet has 26 letters: 5 vowels (A, E, I, O, U) and 21 consonants. Each letter represents one or more sounds."),
    ("letter_def", "letter — a single written symbol that represents one or more sounds. The English alphabet has 26 letters, each with an uppercase and lowercase form (e.g. A and a)."),
    ("vowel_def", "vowel — a letter representing a sound made with an open mouth and vibrating vocal cords. The five English vowels are A, E, I, O, U. Y is sometimes a vowel (in 'sky' or 'happy')."),
    ("consonant_def", "consonant — a letter representing a sound made by partly or fully blocking airflow with the lips, teeth, or tongue. The 21 English consonants are B, C, D, F, G, H, J, K, L, M, N, P, Q, R, S, T, V, W, X, Y, Z."),
    ("phoneme_def", "phoneme — the smallest unit of sound that distinguishes one word from another. English has about 44 phonemes spread across 26 letters. Example: the 'sh' in 'shoe' is one phoneme even though it uses two letters."),
    ("syllable_def", "syllable — a unit of pronunciation built around one vowel sound. Words break into syllables: 'banana' = ba-na-na (3 syllables), 'cat' = cat (1 syllable). Most syllables follow the pattern Consonant + Vowel + Consonant."),
    ("word_def", "word — one or more letters that together carry meaning. Words are the building blocks of sentences. 'Cat', 'happy', 'understand', 'a', 'the' — all words."),
    ("sentence_def", "sentence — a group of words expressing a complete thought. A sentence starts with a capital letter and ends with a punctuation mark (period, question mark, or exclamation point). Most sentences contain at least a subject and a verb."),
    ("grammar_def", "grammar — the rules that govern how words combine into phrases and sentences. Grammar covers word order, verb tense, agreement, punctuation, and structure. Without grammar, words are just a list."),
    ("syntax_def", "syntax — the rules of word order in a language. English syntax is mostly Subject-Verb-Object: 'The dog (S) chased (V) the cat (O).'"),
    ("morphology_def", "morphology — the study of how words are built from smaller parts (morphemes). Example: 'unhappiness' = un + happy + ness. Each part adds meaning."),
    ("morpheme_def", "morpheme — the smallest unit of meaning in a language. 'Cat' is one morpheme. 'Cats' is two: cat + s (the s adds plural meaning). 'Unhappy' is two: un + happy."),
    ("punctuation_def", "punctuation — marks that organize written language: period (.), comma (,), question mark (?), exclamation point (!), colon (:), semicolon (;), apostrophe ('), quotation marks (\" \"), dash (—), parentheses ()."),
    ("vocabulary_def", "vocabulary — the set of words a person or a language has. English has roughly 170,000 words in current use. A typical adult knows about 20,000–35,000 words."),

    # ─── The 26 letters — each with a quick description and example ────
    ("letter", "A — first letter of the English alphabet, a vowel. Sounds: short 'æ' as in 'cat', long 'eɪ' as in 'cake'. As an article ('a book') it means 'one'."),
    ("letter", "B — second letter, consonant. Sound: 'b' as in 'ball'. Voiced lip sound (vocal cords vibrate)."),
    ("letter", "C — third letter, consonant. Sounds: hard 'k' as in 'cat', soft 's' as in 'city'. The letter C usually softens before E, I, or Y."),
    ("letter", "D — fourth letter, consonant. Sound: 'd' as in 'dog'. Voiced sound made with the tongue against the upper teeth."),
    ("letter", "E — fifth letter, a vowel. Sounds: short 'ɛ' as in 'bed', long 'iː' as in 'tree'. The most-used letter in English."),
    ("letter", "F — sixth letter, consonant. Sound: 'f' as in 'fish'. Made by blowing air between the lower lip and upper teeth."),
    ("letter", "G — seventh letter, consonant. Sounds: hard 'g' as in 'go', soft 'j' as in 'gem'. Often softens before E, I, or Y."),
    ("letter", "H — eighth letter, consonant. Sound: 'h' as in 'house'. A breathy sound, often silent in some words ('hour')."),
    ("letter", "I — ninth letter, a vowel. Sounds: short 'ɪ' as in 'sit', long 'aɪ' as in 'time'. Also used as a personal pronoun for the speaker."),
    ("letter", "J — tenth letter, consonant. Sound: 'dʒ' as in 'jump'. One of the youngest letters in the alphabet."),
    ("letter", "K — eleventh letter, consonant. Sound: 'k' as in 'kite'. Same sound as hard C. Often silent before N ('knee')."),
    ("letter", "L — twelfth letter, consonant. Sound: 'l' as in 'love'. Made with the tongue against the roof of the mouth."),
    ("letter", "M — thirteenth letter, consonant. Sound: 'm' as in 'moon'. A nasal sound made with closed lips."),
    ("letter", "N — fourteenth letter, consonant. Sound: 'n' as in 'no'. A nasal sound made with the tongue on the upper teeth ridge."),
    ("letter", "O — fifteenth letter, a vowel. Sounds: short 'ɒ' as in 'hot', long 'oʊ' as in 'go'. Often forms double-O sounds ('moon', 'book')."),
    ("letter", "P — sixteenth letter, consonant. Sound: 'p' as in 'pen'. Voiceless lip sound — like B but without vocal cord vibration."),
    ("letter", "Q — seventeenth letter, consonant. Sound: 'kw' as in 'queen'. Almost always followed by U in English."),
    ("letter", "R — eighteenth letter, consonant. Sound: 'r' as in 'red'. Made with the tongue curled or rolled (varies by dialect)."),
    ("letter", "S — nineteenth letter, consonant. Sounds: 's' as in 'sun', 'z' as in 'is'. A hissing sound."),
    ("letter", "T — twentieth letter, consonant. Sound: 't' as in 'top'. Voiceless sound, like D without vocal cord vibration."),
    ("letter", "U — twenty-first letter, a vowel. Sounds: short 'ʌ' as in 'cup', long 'juː' as in 'use'."),
    ("letter", "V — twenty-second letter, consonant. Sound: 'v' as in 'voice'. Like F but voiced."),
    ("letter", "W — twenty-third letter, consonant (sometimes vowel). Sound: 'w' as in 'water'. Often silent in pairs ('write', 'wrong')."),
    ("letter", "X — twenty-fourth letter, consonant. Sounds: 'ks' as in 'box', 'z' as in 'xylophone'. Rarely starts a word."),
    ("letter", "Y — twenty-fifth letter, both consonant and vowel. Consonant in 'yes', vowel in 'happy', 'sky', 'gym'."),
    ("letter", "Z — twenty-sixth and last letter, consonant. Sound: 'z' as in 'zoo'. A buzzy voiced sibilant. Rare in English compared to S."),

    # ─── How letters become words ──────────────────────────────────────
    ("word_formation", "How letters become words: humans combine letters into syllables, then syllables into words. A syllable needs at least one vowel sound. Examples: c+a+t = 'cat' (one syllable), b+a+n+a+n+a = 'banana' (three syllables: ba-na-na)."),
    ("word_formation", "Word root: the core part of a word that carries the main meaning. Example: in 'unfriendly', 'friend' is the root."),
    ("word_formation", "Prefix: letters added to the front of a word to change meaning. Examples: un- (unhappy), re- (rewrite), pre- (preview), dis- (dislike)."),
    ("word_formation", "Suffix: letters added to the end of a word to change meaning or grammar. Examples: -s (cats, plural), -ed (walked, past tense), -ing (running, ongoing), -ly (quickly, adverb), -ness (happiness, noun)."),
    ("word_formation", "Compound word: two words joined to form a new word. Examples: sun + flower = sunflower, note + book = notebook, tooth + brush = toothbrush."),

    # ─── How words become sentences ─────────────────────────────────────
    ("sentence_structure", "Basic English sentence pattern: SUBJECT + VERB + OBJECT. The subject does the action, the verb is the action, the object receives the action. Example: 'Maria (S) bakes (V) bread (O).'"),
    ("sentence_structure", "Subject: who or what the sentence is about — usually a noun or pronoun. Example: 'The cat sleeps.' → subject = 'The cat'."),
    ("sentence_structure", "Predicate: what the subject does or is — contains the verb and any objects/modifiers. Example: 'The cat sleeps on the rug.' → predicate = 'sleeps on the rug'."),
    ("sentence_structure", "Object: who or what receives the verb's action. Direct object answers 'what?' (She kicked the ball — ball). Indirect object answers 'to whom?' (She gave him a book — him)."),
    ("sentence_structure", "Phrase: a group of words that work together but lack a subject-verb pair. Example: 'in the morning', 'a red car', 'walking quickly'. Phrases live inside sentences."),
    ("sentence_structure", "Clause: a group of words with a subject and a verb. An independent clause stands alone as a sentence. A dependent clause needs an independent clause to make sense ('because it rained' is dependent)."),

    # ─── Sentence types ────────────────────────────────────────────────
    ("sentence_type", "Declarative sentence — makes a statement. Ends with a period. Example: 'I love coffee.'"),
    ("sentence_type", "Interrogative sentence — asks a question. Ends with a question mark. Example: 'Do you like coffee?'"),
    ("sentence_type", "Imperative sentence — gives a command or request. Often the subject 'you' is implied. Example: 'Close the door.'"),
    ("sentence_type", "Exclamatory sentence — expresses strong emotion. Ends with an exclamation point. Example: 'What a beautiful day!'"),

    # ─── Punctuation in detail ─────────────────────────────────────────
    ("punctuation", "period (.) — ends a declarative sentence or marks an abbreviation. Example: 'I went home. Mr. Smith arrived.'"),
    ("punctuation", "comma (,) — separates items in a list or clauses in a sentence. Example: 'I bought apples, oranges, and bread.'"),
    ("punctuation", "question mark (?) — ends an interrogative sentence. Example: 'Are you ready?'"),
    ("punctuation", "exclamation point (!) — ends an exclamatory sentence. Example: 'Watch out!'"),
    ("punctuation", "colon (:) — introduces a list, quote, or explanation. Example: 'I need three things: time, money, and patience.'"),
    ("punctuation", "semicolon (;) — joins two related independent clauses. Example: 'I'm tired; I'll rest now.'"),
    ("punctuation", "apostrophe (') — shows possession or contraction. Examples: John's car (possession), don't (contraction of do not)."),
    ("punctuation", "quotation marks (\" \") — enclose direct speech or quoted text. Example: She said, \"Hello.\""),
    ("punctuation", "dash (—) — indicates a pause, break, or interruption. Example: 'I was going — never mind.'"),
    ("punctuation", "hyphen (-) — joins compound words or breaks a word at line end. Example: 'mother-in-law', 'well-known'."),
    ("punctuation", "parentheses () — enclose extra information that is not essential. Example: 'My friend (the tall one) arrived.'"),

    # ─── How humans use language to communicate ───────────────────────
    ("communication", "Spoken language uses sounds (phonemes) shaped by the lips, tongue, teeth, and vocal cords. Listeners interpret patterns of sound as words and sentences, then meaning."),
    ("communication", "Written language encodes sounds as letters on paper or screen. Readers decode letters back into sounds and meaning. Writing makes language portable across distance and time."),
    ("communication", "Context shapes meaning. The word 'bank' means a riverbank in 'fishing by the bank' but a financial institution in 'I work at a bank'. Humans use surrounding words to pick the right meaning."),
    ("communication", "Tone of voice, facial expression, and body language carry up to 70% of in-person meaning. The same words said angrily vs gently mean different things."),
    ("communication", "Successful communication needs four parts: a sender (speaker/writer), a message (the words), a channel (sound, text, video), and a receiver (listener/reader). Misunderstanding happens when any of these breaks down."),
    ("communication", "Languages are agreements between people. Words don't have inherent meaning — they have agreed meaning. That's why different languages use different words for the same thing (English 'water', French 'eau', Indonesian 'air')."),
    ("communication", "Children learn language by listening to and imitating adults. By age 5 most children know around 5,000 words and have mastered most basic grammar — without ever being formally taught."),
    ("communication", "When you read this sentence, your brain converts letters into sounds, sounds into words, words into meaning, and meaning into thought — all in milliseconds. This is how text on a screen becomes ideas in your mind."),

    # ─── Putting it all together — how 2bee can reason about language ─
    ("language_summary", "Hierarchy of language: phoneme (sound) → letter (symbol for sound) → syllable (sound unit with a vowel) → morpheme (smallest meaning unit) → word (one or more morphemes) → phrase (group of words) → clause (subject + verb) → sentence (complete thought) → paragraph (group of sentences) → text (group of paragraphs)."),
    ("language_summary", "To understand a sentence: 1) identify the words, 2) find the subject and verb, 3) check tense (when), 4) note the object (what receives the action), 5) read modifiers (adjectives, adverbs) for detail, 6) consider context for meaning."),
    ("language_summary", "To build a sentence: pick a subject (who/what), choose a verb (action or state), add an object if needed (receiver of action), add details with adjectives/adverbs, end with the right punctuation, capitalize the first word."),
    ("language_summary", "When 2bee reads input, she breaks the text into words, identifies parts of speech using the grammar facts, looks for question words to detect intent, matches keywords to stored facts, and constructs a response that follows the same sentence rules."),
]


def load_all():
    init()
    added = 0
    for topic, info in LANGUAGE:
        # Index by category bucket so "what is a sentence" works.
        add_fact(topic, info, source="language_seed")
        added += 1
        # Also index by the head word of the info string so "what is the letter a"
        # or "what is morphology" finds the specific entry directly.
        # Split on em-dash, dash, or colon — entries use any of them as a heading separator.
        head = info.split("—", 1)[0].split(" - ", 1)[0].split(":", 1)[0].strip().lower()
        if head and len(head) <= 20 and head != topic:
            word_topic = head.replace(" ", "_")
            add_fact(word_topic, info, source="language_seed")
            added += 1
    print(f"[OK] Loaded {added} language facts into 2bee memory ({len(LANGUAGE)} entries, indexed by both category and term)")


if __name__ == "__main__":
    load_all()
