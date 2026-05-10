"""
Basic English grammar knowledge for 2bee — pronouns, common verbs, question
words, articles, prepositions, conjunctions. Loaded on startup so 2bee can
recognize and use these words in conversation.

Run once: python -m brain.grammar_knowledge
"""

from brain.memory import init, add_fact

# Each entry: (topic, info). Topic is the part-of-speech bucket so 2bee
# can answer queries like "what is a pronoun" or "list question words".
GRAMMAR = [
    # ─── Category definitions (so "what is a pronoun" works) ──────────
    ("pronoun_def", "pronoun — a word that replaces a noun. Examples: I, you, he, she, it, we, they, him, her, his, hers, my, your. Pronouns avoid repeating nouns."),
    ("verb_def", "verb — a word that describes an action or state. Examples: am, is, are, run, eat, think, have. Every complete sentence needs a verb."),
    ("question_word_def", "question word — a word used to ask for information. The main ones are: who, what, when, where, why, how, which, whose. Also called 'wh-words'."),
    ("article_def", "article — a small word placed before a noun. There are three: a, an, the. 'A' and 'an' are indefinite (any one); 'the' is definite (a specific one)."),
    ("preposition_def", "preposition — a word that shows the relationship between a noun and another word. Examples: in, on, at, to, from, with, for, about, before, after."),
    ("conjunction_def", "conjunction — a word that joins words, phrases, or sentences. Examples: and, or, but, so, because, if, although, while."),
    ("demonstrative_def", "demonstrative — a word that points to something. Examples: this (singular near), that (singular far), these (plural near), those (plural far)."),
    ("quantifier_def", "quantifier — a word that expresses amount or quantity. Examples: some, any, many, much, few, little, all, every, no."),
    ("adverb_def", "adverb — a word that describes a verb, adjective, or another adverb. Examples: quickly, very, often, here, now, never. Many adverbs end in -ly."),
    ("noun_def", "noun — a word that names a person, place, thing, or idea. Examples: dog, city, water, freedom, John."),
    ("adjective_def", "adjective — a word that describes a noun. Examples: big, blue, happy, three, beautiful. Adjectives usually come before the noun they describe."),

    # ─── Pronouns ─────────────────────────────────────────────────────
    ("pronoun", "I — first person singular subject pronoun. Used by the speaker to refer to themselves. Example: 'I am happy.'"),
    ("pronoun", "me — first person singular object pronoun. Used after a verb or preposition. Example: 'She told me.'"),
    ("pronoun", "my — first person singular possessive determiner. Example: 'My book.'"),
    ("pronoun", "mine — first person singular possessive pronoun. Example: 'That book is mine.'"),
    ("pronoun", "we — first person plural subject pronoun. Includes the speaker plus others. Example: 'We are friends.'"),
    ("pronoun", "us — first person plural object pronoun. Example: 'They invited us.'"),
    ("pronoun", "our — first person plural possessive determiner. Example: 'Our house.'"),
    ("pronoun", "ours — first person plural possessive pronoun. Example: 'The choice is ours.'"),
    ("pronoun", "you — second person pronoun (singular and plural). Refers to the listener. Example: 'You are kind.'"),
    ("pronoun", "your — second person possessive determiner. Example: 'Your idea.'"),
    ("pronoun", "yours — second person possessive pronoun. Example: 'This pen is yours.'"),
    ("pronoun", "he — third person singular masculine subject pronoun. Example: 'He runs fast.'"),
    ("pronoun", "him — third person singular masculine object pronoun. Example: 'I saw him.'"),
    ("pronoun", "his — third person singular masculine possessive (both determiner and pronoun). Example: 'His car. The car is his.'"),
    ("pronoun", "she — third person singular feminine subject pronoun. Example: 'She sings.'"),
    ("pronoun", "her — third person singular feminine object pronoun and possessive determiner. Example: 'I told her. Her bag.'"),
    ("pronoun", "hers — third person singular feminine possessive pronoun. Example: 'The bag is hers.'"),
    ("pronoun", "it — third person singular neuter pronoun. Refers to a thing, animal, or abstract concept. Example: 'It is raining.'"),
    ("pronoun", "its — third person singular neuter possessive determiner. Note: no apostrophe. Example: 'The dog wagged its tail.'"),
    ("pronoun", "they — third person plural subject pronoun (also used as singular for unknown gender). Example: 'They arrived.'"),
    ("pronoun", "them — third person plural object pronoun. Example: 'I called them.'"),
    ("pronoun", "their — third person plural possessive determiner. Example: 'Their house.'"),
    ("pronoun", "theirs — third person plural possessive pronoun. Example: 'The decision is theirs.'"),

    # ─── Forms of "to be" ──────────────────────────────────────────────
    ("verb", "am — first person singular present of the verb 'to be'. Used only with 'I'. Example: 'I am here.'"),
    ("verb", "is — third person singular present of 'to be'. Used with he, she, it, or a singular noun. Example: 'She is ready.'"),
    ("verb", "are — second person and plural present of 'to be'. Used with you, we, they, or plural nouns. Example: 'You are tall. They are friends.'"),
    ("verb", "was — first and third person singular past of 'to be'. Example: 'I was tired. He was happy.'"),
    ("verb", "were — second person and plural past of 'to be'. Example: 'You were late. We were waiting.'"),
    ("verb", "be — base form of the verb 'to be'. Used after modal verbs and as infinitive. Example: 'I will be there. To be honest.'"),
    ("verb", "been — past participle of 'to be'. Used with have/has/had. Example: 'I have been busy.'"),
    ("verb", "being — present participle of 'to be'. Example: 'She is being kind.'"),

    # ─── Forms of "to have" ────────────────────────────────────────────
    ("verb", "have — base form. Used with I, you, we, they. Means to possess, or as auxiliary for perfect tenses. Example: 'I have a car. I have eaten.'"),
    ("verb", "has — third person singular present of 'to have'. Used with he, she, it. Example: 'She has a plan.'"),
    ("verb", "had — past tense and past participle of 'to have'. Example: 'I had a dog. I had finished.'"),
    ("verb", "having — present participle of 'to have'. Example: 'Having said that, I disagree.'"),

    # ─── Forms of "to do" ──────────────────────────────────────────────
    ("verb", "do — base form. Used with I, you, we, they as main verb or auxiliary for questions and negatives. Example: 'I do my work. Do you like it?'"),
    ("verb", "does — third person singular present of 'to do'. Example: 'She does yoga. Does he know?'"),
    ("verb", "did — past tense of 'to do'. Example: 'I did it yesterday. Did you see?'"),
    ("verb", "done — past participle of 'to do'. Example: 'I have done it.'"),

    # ─── Common modal / auxiliary verbs ────────────────────────────────
    ("verb", "will — modal verb expressing future tense or willingness. Example: 'I will go tomorrow.'"),
    ("verb", "would — past tense of will, or conditional / polite request. Example: 'I would like coffee.'"),
    ("verb", "can — modal verb expressing ability or permission. Example: 'I can swim. Can I help?'"),
    ("verb", "could — past tense of can, or polite/conditional. Example: 'I could swim as a child. Could you help?'"),
    ("verb", "should — modal verb for advice or expectation. Example: 'You should rest.'"),
    ("verb", "must — modal verb for obligation or strong likelihood. Example: 'You must wait.'"),
    ("verb", "may — modal verb for permission or possibility. Example: 'You may leave. It may rain.'"),
    ("verb", "might — modal verb for slight possibility. Example: 'It might snow.'"),
    ("verb", "shall — modal verb for future or formal suggestion. Example: 'Shall we begin?'"),

    # ─── Question words ────────────────────────────────────────────────
    ("question_word", "who — asks about a person. Example: 'Who called?'"),
    ("question_word", "whom — formal object form of who, asks about the recipient of an action. Example: 'To whom did you speak?'"),
    ("question_word", "whose — asks about possession. Example: 'Whose bag is this?'"),
    ("question_word", "what — asks about a thing or action. Example: 'What is your name?'"),
    ("question_word", "which — asks about a choice between options. Example: 'Which color do you prefer?'"),
    ("question_word", "when — asks about time. Example: 'When does the movie start?'"),
    ("question_word", "where — asks about a place or location. Example: 'Where do you live?'"),
    ("question_word", "why — asks about a reason or cause. Example: 'Why is the sky blue?'"),
    ("question_word", "how — asks about manner, method, or condition. Example: 'How are you? How does it work?'"),
    ("question_word", "how much — asks about uncountable quantity or price. Example: 'How much is this?'"),
    ("question_word", "how many — asks about countable quantity. Example: 'How many apples?'"),
    ("question_word", "how often — asks about frequency. Example: 'How often do you exercise?'"),
    ("question_word", "how long — asks about duration or length. Example: 'How long will it take?'"),

    # ─── Articles ──────────────────────────────────────────────────────
    ("article", "a — indefinite article used before a singular countable noun starting with a consonant sound. Example: 'a book, a university.'"),
    ("article", "an — indefinite article used before a singular countable noun starting with a vowel sound. Example: 'an apple, an hour.'"),
    ("article", "the — definite article referring to a specific noun (singular or plural). Example: 'the book, the books.'"),

    # ─── Common prepositions ───────────────────────────────────────────
    ("preposition", "in — inside something, or referring to time periods. Example: 'in the box, in 2026.'"),
    ("preposition", "on — on top of a surface, or referring to days. Example: 'on the table, on Monday.'"),
    ("preposition", "at — at a specific point or location. Example: 'at the door, at 5 pm.'"),
    ("preposition", "to — direction toward something. Example: 'go to school.'"),
    ("preposition", "from — origin or starting point. Example: 'from Indonesia.'"),
    ("preposition", "of — belonging to or part of. Example: 'a friend of mine.'"),
    ("preposition", "with — accompanied by, or using. Example: 'with friends, cut with a knife.'"),
    ("preposition", "without — not having. Example: 'without water.'"),
    ("preposition", "for — purpose, recipient, or duration. Example: 'for you, for two hours.'"),
    ("preposition", "by — agent of action, or method. Example: 'made by hand, by car.'"),
    ("preposition", "about — concerning. Example: 'a book about history.'"),
    ("preposition", "before — earlier than. Example: 'before noon.'"),
    ("preposition", "after — later than. Example: 'after lunch.'"),
    ("preposition", "during — throughout a period. Example: 'during the meeting.'"),
    ("preposition", "between — in the middle of two things. Example: 'between us.'"),
    ("preposition", "among — in the middle of several things. Example: 'among friends.'"),
    ("preposition", "under — below something. Example: 'under the bed.'"),
    ("preposition", "over — above or covering. Example: 'over the bridge.'"),
    ("preposition", "through — from one side to the other. Example: 'through the forest.'"),

    # ─── Conjunctions ──────────────────────────────────────────────────
    ("conjunction", "and — joins two similar items. Example: 'bread and butter.'"),
    ("conjunction", "or — presents alternatives. Example: 'tea or coffee.'"),
    ("conjunction", "but — introduces contrast. Example: 'small but strong.'"),
    ("conjunction", "so — shows result. Example: 'It rained, so we stayed home.'"),
    ("conjunction", "because — gives a reason. Example: 'I left because it was late.'"),
    ("conjunction", "if — introduces a condition. Example: 'If it rains, we cancel.'"),
    ("conjunction", "unless — introduces a negative condition. Example: 'I will go unless it rains.'"),
    ("conjunction", "although — introduces an unexpected contrast. Example: 'Although tired, she continued.'"),
    ("conjunction", "while — at the same time, or in contrast. Example: 'while you wait.'"),
    ("conjunction", "since — from a time, or because. Example: 'since 2020. Since you are here, help me.'"),
    ("conjunction", "until — up to the point that. Example: 'wait until I return.'"),
    ("conjunction", "than — used in comparisons. Example: 'taller than me.'"),

    # ─── Demonstratives ────────────────────────────────────────────────
    ("demonstrative", "this — singular, near. Example: 'this book in my hand.'"),
    ("demonstrative", "that — singular, far. Example: 'that book over there.'"),
    ("demonstrative", "these — plural, near. Example: 'these apples.'"),
    ("demonstrative", "those — plural, far. Example: 'those mountains.'"),

    # ─── Quantifiers ───────────────────────────────────────────────────
    ("quantifier", "some — an unspecified amount, often positive. Example: 'some water.'"),
    ("quantifier", "any — used in questions, negatives, or 'whichever'. Example: 'any questions?'"),
    ("quantifier", "many — large countable amount. Example: 'many people.'"),
    ("quantifier", "much — large uncountable amount. Example: 'much water.'"),
    ("quantifier", "few — small countable amount, slight negative tone. Example: 'few visitors.'"),
    ("quantifier", "little — small uncountable amount. Example: 'little time.'"),
    ("quantifier", "all — every one. Example: 'all students.'"),
    ("quantifier", "every — each member of a group. Example: 'every day.'"),
    ("quantifier", "each — every individual considered separately. Example: 'each person.'"),
    ("quantifier", "no — not any. Example: 'no money.'"),

    # ─── Common adverbs ────────────────────────────────────────────────
    ("adverb", "yes — affirmative answer. Example: 'Yes, I agree.'"),
    ("adverb", "no — negative answer. Example: 'No, thank you.'"),
    ("adverb", "not — used to make verbs negative. Example: 'I am not ready.'"),
    ("adverb", "now — at this moment. Example: 'Come now.'"),
    ("adverb", "then — at that time, or as a result. Example: 'Then it happened.'"),
    ("adverb", "here — at this place. Example: 'Come here.'"),
    ("adverb", "there — at that place. Example: 'Look there.'"),
    ("adverb", "very — to a high degree. Example: 'very good.'"),
    ("adverb", "too — also, or excessively. Example: 'me too. too hot.'"),
    ("adverb", "also — additionally. Example: 'I also like it.'"),
    ("adverb", "always — at all times. Example: 'Always be honest.'"),
    ("adverb", "never — at no time. Example: 'I never lie.'"),
    ("adverb", "often — frequently. Example: 'I often visit.'"),
    ("adverb", "sometimes — occasionally. Example: 'Sometimes I read.'"),
    ("adverb", "usually — most of the time. Example: 'I usually wake at 7.'"),
    ("adverb", "yesterday — the day before today. Example: 'I went yesterday.'"),
    ("adverb", "today — this day. Example: 'Today is hot.'"),
    ("adverb", "tomorrow — the day after today. Example: 'See you tomorrow.'"),
    ("adverb", "soon — in a short time. Example: 'I will arrive soon.'"),
    ("adverb", "later — at a future time. Example: 'See you later.'"),

    # ─── Sentence-builder summary ──────────────────────────────────────
    ("grammar_summary", "Basic English sentence pattern: SUBJECT + VERB + OBJECT. Example: 'I love you.' Subject = I, Verb = love, Object = you."),
    ("grammar_summary", "English question pattern: QUESTION_WORD + AUXILIARY + SUBJECT + MAIN_VERB. Example: 'When do you arrive?' Question word = when, Auxiliary = do, Subject = you, Main verb = arrive."),
    ("grammar_summary", "English negation pattern: SUBJECT + AUXILIARY + not + MAIN_VERB. Example: 'I do not know. She is not here.'"),
    ("grammar_summary", "First person pronouns refer to the speaker: I (subject), me (object), my/mine (possessive), we/us/our/ours (plural)."),
    ("grammar_summary", "Second person pronouns refer to the listener: you (subject and object), your/yours (possessive)."),
    ("grammar_summary", "Third person pronouns refer to others: he/him/his (masculine), she/her/hers (feminine), it/its (neuter), they/them/their/theirs (plural)."),
    ("grammar_summary", "The 'wh' question words ask for specific information: who (person), what (thing), when (time), where (place), why (reason), how (manner), which (choice), whose (possession)."),
]


def load_all():
    init()
    added = 0
    for topic, info in GRAMMAR:
        # Index by part-of-speech bucket so "list pronouns" works.
        add_fact(topic, info, source="grammar_seed")
        added += 1
        # Also index by the head word(s) so "what is when" finds it directly.
        # The info string starts with "WORD —" — split on " — " or " - ".
        head = info.split("—", 1)[0].split(" - ", 1)[0].strip().lower()
        # Allow multi-word entries like "how much" / "how many".
        if head and len(head) <= 20 and head != topic:
            # Replace spaces with underscore so the topic key is searchable as a single token.
            word_topic = head.replace(" ", "_")
            add_fact(word_topic, info, source="grammar_seed")
            added += 1
    print(f"[OK] Loaded {added} grammar facts into 2bee memory ({len(GRAMMAR)} entries, indexed by both part-of-speech and word)")


if __name__ == "__main__":
    load_all()
