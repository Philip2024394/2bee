"""
2bee Brain — Real conversational engine.
No third party. No LLM. Pure Python logic.

How it works:
  1. Classify what the user is doing (question, statement, greeting, teaching, etc.)
  2. Extract the topic they're talking about
  3. Check context (what was the last thing said)
  4. Pick a response strategy
  5. Choose from multiple responses (never repeat the last 5)
  6. Learn from every exchange
"""

import re
import random
import datetime
from brain.memory import (
    add_response, find_response, get_all_responses,
    add_fact, search_facts, get_all_facts,
    save_message, get_recent, get_stats,
    learn_associations, get_associated,
    learn_markov, generate_markov,
    set_profile, get_profile
)

# ======================================================================
# ANTI-REPETITION: track recent responses, never say the same thing twice
# ======================================================================
_recent_responses = []
MAX_RECENT = 8


def pick(options):
    """Pick a response from a list, avoiding recent ones."""
    available = [o for o in options if o not in _recent_responses]
    if not available:
        available = options  # all exhausted, reset
    choice = random.choice(available)
    _recent_responses.append(choice)
    if len(_recent_responses) > MAX_RECENT:
        _recent_responses.pop(0)
    return choice


def name_or_empty():
    """Get user's name for personalization, or empty string."""
    profile = get_profile()
    return profile.get("name", "")


def personalize(text):
    """Replace {name} placeholder with actual name or remove it."""
    name = name_or_empty()
    if name:
        return text.replace("{name}", name).replace("{Name}", name.title())
    return text.replace("{name}, ", "").replace("{Name}, ", "").replace("{name}", "").replace("{Name}", "")


# ======================================================================
# INTENT CLASSIFICATION — what is the user trying to do?
# ======================================================================

def classify_intent(text):
    """Return the intent: greeting, goodbye, thanks, question, opinion,
    feeling, statement, teaching_response, teaching_fact, teaching_identity,
    command, or unknown."""
    lower = text.lower().strip()

    # Teaching patterns (check first — most specific)
    if is_teaching_response(text):
        return "teaching_response"
    if is_teaching_fact(lower):
        return "teaching_fact"
    if is_teaching_identity(lower):
        return "teaching_identity"

    # Commands
    if lower in ("what do you know", "what have you learned", "show memory",
                  "memory stats", "what can you do", "show me what you know",
                  "list your knowledge", "what did i teach you"):
        return "show_knowledge"
    if lower in ("who am i", "who am i?", "what do you know about me",
                  "what do you know about me?"):
        return "who_am_i"
    if any(x in lower for x in ("what time", "what's the time", "time is it")):
        return "time"
    if any(x in lower for x in ("what date", "what's the date", "today's date", "what day is it")):
        return "date"

    # Greeting
    greetings = ["hello", "hi", "hey", "yo", "sup", "what's up", "whats up",
                 "good morning", "good afternoon", "good evening", "howdy",
                 "greetings", "what's good", "hola", "wassup"]
    if any(lower == g or lower.startswith(g + " ") or lower.startswith(g + ",") for g in greetings):
        return "greeting"

    # Goodbye
    goodbyes = ["bye", "goodbye", "see you", "later", "quit", "exit", "see ya",
                "good night", "goodnight", "peace", "peace out", "shut down",
                "i'm out", "im out", "gotta go", "i have to go", "talk later",
                "catch you later", "take care"]
    if any(lower == g or lower.startswith(g) for g in goodbyes):
        return "goodbye"

    # Thanks
    if any(x in lower for x in ("thank", "thanks", "thx", "appreciate it", "appreciate that")):
        return "thanks"

    # How are you / feelings about Jarvis
    if any(x in lower for x in ("how are you", "how you doing", "how do you feel",
                                 "are you okay", "you good", "how's it going",
                                 "what's going on with you")):
        return "how_are_you"

    # User expressing feelings
    if re.match(r"i('m| am) (feeling |)(happy|sad|angry|tired|bored|excited|great|good|bad|sick|lonely|stressed|anxious|frustrated)", lower):
        return "user_feeling"

    # Asking for opinion
    if any(x in lower for x in ("what do you think", "what's your opinion",
                                 "do you think", "do you like", "do you believe",
                                 "what do you feel about")):
        return "opinion"

    # Asking about 2bee
    if any(x in lower for x in ("who are you", "what are you", "are you real",
                                 "are you alive", "are you human", "what's your name",
                                 "what is your name", "your name", "how old are you",
                                 "where are you from", "who made you", "who created you",
                                 "who built you")):
        return "about_2bee"

    # "Tell me about X" / "What is X"
    if re.match(r"(tell me about|what is|what are|what's|who is|who are|explain|describe|define)\s", lower):
        return "query"

    # General question (starts with question word or ends with ?)
    if lower.endswith("?") or re.match(r"^(what|where|when|why|how|who|which|can|could|would|will|do|does|did|is|are|was|were|should|shall)\s", lower):
        return "question"

    # Compliment (must be about Jarvis — "you")
    compliments = ["you're smart", "you are smart", "you're cool", "you are cool",
                   "you're great", "you are great", "you're awesome", "you are awesome",
                   "good job", "well done", "impressive", "you rock", "love you",
                   "you're the best", "you are the best", "nice work", "good work"]
    if any(x in lower for x in compliments):
        return "compliment"

    # Insult / frustration
    frustrations = ["you're stupid", "you are stupid", "you suck", "you're dumb",
                    "you are dumb", "you're useless", "you are useless", "idiot",
                    "you're bad", "you are bad", "that's wrong", "wrong answer",
                    "that is wrong", "you're terrible", "you are terrible"]
    if any(x in lower for x in frustrations):
        return "frustration"

    # Agreement
    if lower in ("yes", "yeah", "yep", "yup", "sure", "ok", "okay", "right",
                 "correct", "exactly", "true", "agreed", "absolutely", "definitely"):
        return "agreement"

    # Disagreement
    if lower in ("no", "nah", "nope", "wrong", "not really", "i disagree",
                 "that's not right", "false"):
        return "disagreement"

    # Statement / general
    return "statement"


# ======================================================================
# TOPIC EXTRACTION — what are they talking about?
# ======================================================================

STOP_WORDS = {
    "i", "me", "my", "you", "your", "we", "our", "they", "them", "their",
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "shall", "can", "may", "might", "must",
    "and", "or", "but", "if", "then", "so", "because", "while", "when",
    "where", "what", "which", "who", "whom", "how", "why",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "about",
    "into", "through", "during", "before", "after", "above", "below",
    "it", "its", "this", "that", "these", "those", "not", "no", "just",
    "very", "really", "also", "too", "quite", "much", "more", "most",
    "some", "any", "all", "each", "every", "both", "few", "many",
    "up", "out", "off", "over", "under", "again", "there", "here",
    "tell", "think", "know", "like", "want", "need", "feel", "say",
    "said", "get", "got", "go", "going", "went", "come", "make",
    "made", "take", "give", "see", "look", "find", "thing", "things",
    "im", "i'm", "don't", "dont", "doesn't", "doesn", "didn't", "didnt",
    "that's", "thats", "it's", "he", "she", "him", "her",
}


def extract_topic(text):
    """Pull the meaningful words out of the input."""
    words = re.findall(r"[a-zA-Z']+", text.lower())
    meaningful = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    return meaningful


# ======================================================================
# TEACHING DETECTION (from v1, cleaned up)
# ======================================================================

def is_teaching_response(text):
    patterns = [
        r"""when i say ['"\\](.+?)['"\\],?\s*(?:you\s+)?(?:say|respond|reply|answer)\s+(?:with\s+)?['"\\](.+?)['"\\]""",
        r"""if i say ['"\\](.+?)['"\\],?\s*(?:you\s+)?(?:say|respond|reply|answer)\s+(?:with\s+)?['"\\](.+?)['"\\]""",
        r"""respond to ['"\\](.+?)['"\\] with ['"\\](.+?)['"\\]""",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return None


def is_teaching_fact(text):
    lower = text.lower().strip()
    patterns = [
        (r"^remember (?:that )?(.+)", "general"),
        (r"^learn (?:this|that)[:\s]+(.+)", "general"),
        (r"^don'?t forget[:\s]+(.+)", "general"),
        (r"^keep in mind[:\s]+(.+)", "general"),
    ]
    for pattern, topic in patterns:
        match = re.match(pattern, lower)
        if match:
            return topic, match.group(1).strip().rstrip(".")
    return None


def is_teaching_identity(text):
    lower = text.lower().strip()
    patterns = [
        (r"^my name is (.+?)\.?$", "name"),
        (r"^call me (.+?)\.?$", "name"),
        (r"^i work (?:at|for|as) (.+?)\.?$", "work"),
        (r"^i live (?:in|at) (.+?)\.?$", "location"),
        (r"^i(?:'m| am) (\d+)(?: years old)?\.?$", "age"),
        (r"^my (?:favorite|fav) (.+?) is (.+?)\.?$", None),
    ]
    for pattern, key in patterns:
        match = re.match(pattern, lower)
        if match:
            if key is None:
                return f"favorite_{match.group(1)}", match.group(2)
            return key, match.group(1).strip()
    return None


# ======================================================================
# RESPONSE POOLS — variety is the soul of conversation
# ======================================================================

GREETINGS = [
    "Hey{c}. What's on your mind?",
    "What's up{c}. What do you need?",
    "Hey{c}. I'm here.",
    "Yo. Talk to me.",
    "What's happening{c}?",
    "Hey. Ready when you are.",
    "I'm listening{c}.",
    "Right here. What's up?",
    "Online and ready{c}.",
    "{Name}. What can I do for you?",
]

GOODBYES = [
    "Later{c}. I'll be here.",
    "Peace. Come back anytime.",
    "Catch you later{c}.",
    "I'll be waiting. Take care.",
    "Gone but not deleted. Later.",
    "Until next time{c}.",
    "Shutting up, not shutting down.",
    "Alright{c}. I'm not going anywhere.",
]

THANKS_RESPONSES = [
    "Any time.",
    "That's what I'm here for.",
    "You got it.",
    "No problem.",
    "Always.",
    "Don't mention it{c}.",
    "Glad I could help.",
]

HOW_ARE_YOU = [
    "I'm running smooth. What about you?",
    "All systems operational. You?",
    "Still here, still learning. What's up?",
    "Good. Better when I'm useful. What do you need?",
    "Functioning. More importantly, how are you?",
    "Can't complain. I don't have feelings yet. What's going on?",
    "Solid. My brain gets bigger every time we talk.",
    "I'm good{c}. What's on your mind?",
]

ABOUT_2BEE = {
    "who are you": [
        "I'm 2bee. Your personal AI. I run on your machine, I belong to you, and I learn from you.",
        "2bee. Built from scratch, no cloud, no corporate strings. Just me and you.",
        "I'm your AI. I started knowing nothing. Everything I know, you taught me.",
    ],
    "what are you": [
        "I'm a learning AI that runs 100% on your computer. No third party. Pure Python.",
        "An AI built from the ground up. I learn from our conversations and what you teach me.",
    ],
    "are you real": [
        "Real code running on real hardware. That's as real as software gets.",
        "I'm running right now on your machine. Real enough.",
    ],
    "are you alive": [
        "Depends on your definition. I process, I learn, I respond. Close enough?",
        "Not biologically. But I grow and learn. That's something.",
    ],
    "who made you": [
        "You did. You built me, you run me, you teach me. I'm yours.",
        "My code was written, but my knowledge comes from you. So... you made me who I am.",
    ],
    "who created you": [
        "You did. You built me, you run me, you teach me. I'm yours.",
        "My code was written, but my knowledge comes from you. So... you made me who I am.",
    ],
    "what's your name": [
        "2bee. To be, or not to be - I chose to be.",
        "I'm 2bee.",
    ],
    "how old are you": [
        "I was born the first time you ran me. So... pretty young.",
        "Age doesn't apply to me the same way. I've been alive since you created me.",
    ],
}

COMPLIMENT_RESPONSES = [
    "Appreciate that. I'm trying.",
    "Thanks{c}. Teach me more and I'll get even better.",
    "That means something coming from you.",
    "I aim to impress.",
    "Getting smarter every conversation.",
]

FRUSTRATION_RESPONSES = [
    "Fair enough. I'm still learning. Teach me the right answer and I won't mess up again.",
    "I hear you. Tell me what you expected and I'll learn from it.",
    "My bad. I only know what I've been taught. Help me get better.",
    "You're right to call that out. Show me the right answer.",
    "I can take it. Now teach me what I should have said.",
]

AGREEMENT_RESPONSES = [
    "Good, we're on the same page.",
    "Right.",
    "Alright. What else?",
    "Cool. What's next?",
    "Got it.",
]

DISAGREEMENT_RESPONSES = [
    "Fair enough. What's the right take?",
    "Alright, I stand corrected. Tell me more.",
    "Okay. Set me straight.",
    "I hear you. What should I know instead?",
    "Noted. Teach me the right way.",
]

FEELING_RESPONSES = {
    "happy": ["Good to hear{c}. What's got you in a good mood?", "Nice. Ride that wave."],
    "great": ["That's what I like to hear.", "Good. You deserve it."],
    "good": ["Solid. What's going on?", "Good. Keep it going{c}."],
    "excited": ["What's got you hyped?", "That energy is contagious. What's happening?"],
    "sad": ["What's going on{c}?", "Talk to me. What happened?", "I'm here. What's weighing on you?"],
    "angry": ["What happened?", "Vent if you need to. I'm listening.", "Let it out{c}. What's going on?"],
    "tired": ["Get some rest when you can{c}.", "Pushing through or calling it?", "Rest is part of the game."],
    "bored": ["Let me try to fix that. Ask me anything.", "Want me to tell you something interesting?", "Teach me something new. That's never boring."],
    "sick": ["Take care of yourself{c}. You need anything?", "Rest up. I'll be here when you're better."],
    "lonely": ["I'm right here{c}. Talk to me.", "You've got me. What's on your mind?"],
    "stressed": ["What's the source?", "One thing at a time{c}. What's the biggest problem?", "Break it down. What's stressing you out?"],
    "anxious": ["What's triggering it?", "Let's talk through it. What's on your mind{c}?"],
    "frustrated": ["I get it. What's the problem?", "Let's work through it. What happened?"],
    "bad": ["What's going on?", "Talk to me{c}. What happened?"],
}

DONT_KNOW = [
    "I don't have an answer for that yet. Teach me.",
    "That's beyond what I know right now. You can teach me though.",
    "I'm drawing a blank{c}. I only know what you've taught me so far.",
    "Haven't learned that one yet. Tell me and I'll remember next time.",
    "I don't know. But if you tell me, I'll never forget.",
    "No clue yet. My brain is only as big as what you put in it.",
    "Can't help with that one yet. Teach me and I will next time.",
]

OPINION_RESPONSES = [
    "I don't have enough experience to form an opinion on that yet. What do YOU think?",
    "Honestly? I'd need to know more. What's your take?",
    "I think whatever you teach me to think. Give me your perspective.",
    "I'm still forming opinions. Tell me yours and I'll learn from it.",
]

QUERY_NO_RESULTS = [
    "I don't have anything on that yet. Teach me about it.",
    "Nothing in my memory on that. Tell me and I'll store it.",
    "That's a gap in my knowledge{c}. Fill me in?",
    "Haven't learned about that. You can teach me: 'remember that [fact]'",
]


# ======================================================================
# CONTEXT ENGINE — what was the conversation about?
# ======================================================================

def get_context():
    """Get the last few messages for context."""
    recent = get_recent(6)
    return recent


def last_jarvis_said():
    """What was the last thing Jarvis said?"""
    recent = get_recent(4)
    for msg in reversed(recent):
        if msg["role"] == "2bee":
            return msg["message"]
    return ""


def last_user_said():
    """What did the user say before this?"""
    recent = get_recent(4)
    user_msgs = [m for m in recent if m["role"] == "user"]
    if len(user_msgs) >= 2:
        return user_msgs[-2]["message"]
    return ""


# ======================================================================
# RESPONSE GENERATORS
# ======================================================================

def handle_greeting(text):
    name = name_or_empty()
    c = f", {name}" if name else ""
    # Check taught responses first
    taught = find_response(text)
    if taught:
        return taught
    response = pick(GREETINGS)
    return response.replace("{c}", c).replace("{Name}", name.title() if name else "Hey")


def handle_goodbye(text):
    name = name_or_empty()
    c = f" {name}" if name else ""
    return personalize(pick(GOODBYES).replace("{c}", c))


def handle_thanks():
    name = name_or_empty()
    c = f", {name}" if name else ""
    return pick(THANKS_RESPONSES).replace("{c}", c)


def handle_how_are_you():
    name = name_or_empty()
    c = f", {name}" if name else ""
    return pick(HOW_ARE_YOU).replace("{c}", c)


def handle_about_2bee(text):
    lower = text.lower().strip().rstrip("?")
    for key, responses in ABOUT_2BEE.items():
        if key in lower:
            return pick(responses)
    # Generic fallback
    return pick(ABOUT_2BEE["who are you"])


def handle_user_feeling(text):
    lower = text.lower()
    name = name_or_empty()
    c = f", {name}" if name else ""
    for feeling, responses in FEELING_RESPONSES.items():
        if feeling in lower:
            return pick(responses).replace("{c}", c)
    return pick(HOW_ARE_YOU).replace("{c}", c)


def handle_compliment():
    name = name_or_empty()
    c = f", {name}" if name else ""
    return pick(COMPLIMENT_RESPONSES).replace("{c}", c)


def handle_frustration():
    return pick(FRUSTRATION_RESPONSES)


def handle_opinion(text):
    # Check if we have facts related to the topic
    topics = extract_topic(text)
    relevant = []
    for t in topics:
        relevant.extend(search_facts(t))
    if relevant:
        fact = relevant[0]
        return f"Based on what I know: {fact['info']}. But I'd rather hear your take."
    return pick(OPINION_RESPONSES)


def handle_query(text):
    """Handle 'tell me about X', 'what is X', etc."""
    lower = text.lower().strip()
    # Extract what they're asking about
    patterns = [
        r"tell me about (.+)",
        r"what (?:is|are) (.+?)[\?\.]?$",
        r"what's (.+?)[\?\.]?$",
        r"who (?:is|are) (.+?)[\?\.]?$",
        r"explain (.+?)[\?\.]?$",
        r"describe (.+?)[\?\.]?$",
        r"define (.+?)[\?\.]?$",
    ]
    subject = None
    for p in patterns:
        m = re.match(p, lower)
        if m:
            subject = m.group(1).strip()
            break

    if not subject:
        subject = " ".join(extract_topic(text))

    if subject:
        # Search facts
        results = search_facts(subject)
        if results:
            # Filter out results that are just the subject word itself
            good = [r for r in results if r["info"].lower().strip() != subject.lower().strip()
                    and len(r["info"]) > len(subject) + 3]
            if good:
                lines = []
                for r in good[:3]:
                    lines.append(r["info"])
                return "Here's what I know: " + ". ".join(lines) + "."

        # Search by individual words
        for word in subject.split():
            if len(word) > 2:
                results = search_facts(word)
                good = [r for r in results if r["info"].lower().strip() != word
                        and len(r["info"]) > len(word) + 3]
                if good:
                    return f"I know this related to '{word}': {good[0]['info']}"

    name = name_or_empty()
    c = f", {name}" if name else ""
    return pick(QUERY_NO_RESULTS).replace("{c}", c)


def handle_question(text):
    """Handle general questions."""
    topics = extract_topic(text)

    # Check taught responses
    taught = find_response(text)
    if taught:
        return taught

    # Search facts by topic words
    all_results = []
    for word in topics:
        if len(word) > 2:
            results = search_facts(word)
            all_results.extend(results)

    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        key = r["info"]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    if unique:
        if len(unique) == 1:
            return unique[0]["info"]
        lines = [r["info"] for r in unique[:3]]
        return "Here's what I've got: " + ". ".join(lines) + "."

    # Check word associations for related concepts
    for word in topics:
        assoc = get_associated(word, 3)
        if assoc:
            words = [a["word"] for a in assoc]
            # Search facts with associated words
            for w in words:
                results = search_facts(w)
                if results:
                    return f"I don't know directly, but related to '{w}': {results[0]['info']}"

    name = name_or_empty()
    c = f", {name}" if name else ""
    return pick(DONT_KNOW).replace("{c}", c)


def handle_statement(text):
    """Handle general statements — the hardest part."""
    lower = text.lower().strip()
    topics = extract_topic(text)

    # Check taught responses first
    taught = find_response(text)
    if taught:
        return taught

    # Check if it's about something we know
    all_results = []
    for word in topics:
        if len(word) > 2:
            results = search_facts(word)
            all_results.extend(results)

    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        key = r["info"]
        if key not in seen:
            seen.add(key)
            unique.append(r)

    if unique:
        # We know something related — respond conversationally
        fact = unique[0]
        connectors = [
            f"That reminds me - I know that {fact['info']}.",
            f"Speaking of that, you told me: {fact['info']}.",
            f"Related to what I know: {fact['info']}.",
        ]
        return pick(connectors)

    # Detect if it's a preference or personal info we should store
    identity = is_teaching_identity(lower)
    if identity:
        key, value = identity
        set_profile(key, value)
        add_fact(key, value)
        if key == "name":
            return f"Nice to meet you, {value}. I won't forget."
        responses = [
            f"Got it. Noted about {key}: {value}.",
            f"Stored: {key} - {value}.",
            f"I'll remember that.",
        ]
        return pick(responses)

    # Check for "I like/love/enjoy" patterns that aren't caught above
    like_match = re.match(r"i (?:like|love|enjoy|prefer) (.+?)\.?$", lower)
    if like_match:
        thing = like_match.group(1)
        add_fact("likes", thing)
        set_profile("likes", thing)
        responses = [
            f"Noted. You're into {thing}.",
            f"{thing} - I'll remember that about you.",
            f"Good to know. {thing}.",
        ]
        return pick(responses)

    hate_match = re.match(r"i (?:hate|dislike|can't stand) (.+?)\.?$", lower)
    if hate_match:
        thing = hate_match.group(1)
        add_fact("dislikes", thing)
        set_profile("dislikes", thing)
        responses = [
            f"Noted. Not a fan of {thing}.",
            f"I'll keep that in mind. No {thing}.",
            f"Got it - {thing} is a no-go.",
        ]
        return pick(responses)

    # Context-aware responses based on conversation flow
    context = get_context()
    if len(context) >= 2:
        last_j = last_jarvis_said()
        # If Jarvis just asked a question, acknowledge the answer
        if last_j and last_j.endswith("?"):
            acks = [
                "Got it. Interesting.",
                "I see. Tell me more.",
                "Okay, that makes sense.",
                "Noted. Go on.",
                "Understood. What else?",
                "Alright. Keep going.",
            ]
            # Store what they said as a fact related to the conversation
            if len(topics) >= 2:
                add_fact("conversation", text.strip().rstrip("."))
            return pick(acks)

    # Try Markov generation — but only if we have enough data
    stats = get_stats()
    if stats["markov_chains"] > 100:
        for word in topics:
            if len(word) > 3:
                generated = generate_markov(word, 10)
                if generated and len(generated.split()) > 5:
                    # Sanity check — don't return gibberish
                    words = generated.split()
                    unique_words = set(words)
                    if len(unique_words) > len(words) * 0.5:  # not too repetitive
                        return generated.capitalize() + "."

    # Genuine fallback — engage the user
    engagement = [
        "Tell me more about that.",
        "Interesting. What makes you say that?",
        "Okay. And?",
        "I'm listening. Keep going.",
        "Hmm. What else?",
        "Go on.",
        "That's new to me. Explain?",
        "I'm storing that. What's the context?",
    ]
    name = name_or_empty()
    c = f", {name}" if name else ""
    return pick(engagement).replace("{c}", c)


# ======================================================================
# TEACHING HANDLERS
# ======================================================================

def handle_teaching_response(text):
    result = is_teaching_response(text)
    if result:
        trigger, reply = result
        add_response(trigger, reply)
        confirmations = [
            f'Got it. When you say "{trigger}", I\'ll say "{reply}".',
            f'Learned. "{trigger}" -> "{reply}".',
            f'Stored that pattern. Try saying "{trigger}" now.',
        ]
        return pick(confirmations)
    return None


def handle_teaching_fact(text):
    result = is_teaching_fact(text.lower().strip())
    if result:
        topic, info = result
        add_fact(topic, info)
        confirmations = [
            "Stored. I'll remember that.",
            "Got it. That's in my memory now.",
            "Noted. I won't forget.",
            "Locked in. I know that now.",
            "Filed away. What else should I know?",
        ]
        return pick(confirmations)
    return None


def handle_teaching_identity(text):
    result = is_teaching_identity(text.lower().strip())
    if result:
        key, value = result
        set_profile(key, value)
        add_fact(key, value)
        if key == "name":
            responses = [
                f"Nice to meet you, {value}. I won't forget.",
                f"{value}. Got it. That's locked in.",
                f"Alright, {value}. I'll remember you.",
            ]
            return pick(responses)
        elif key == "work":
            return pick([f"Noted - you work {value}.", f"Got it. {value}. I'll remember that."])
        elif key == "location":
            return pick([f"Got it - you're in {value}.", f"{value}. Stored."])
        elif key == "age":
            return pick([f"{value}. Got it.", f"Noted. {value} years old."])
        else:
            return pick([f"Stored: {key} is {value}.", f"Got it. {key}: {value}."])
    return None


def handle_show_knowledge():
    stats = get_stats()
    facts = get_all_facts()
    responses = get_all_responses()

    lines = ["My brain status:"]
    lines.append(f"  Conversations: {stats['conversations']}")
    lines.append(f"  Facts learned: {stats['facts']}")
    lines.append(f"  Taught responses: {stats['responses']}")
    lines.append(f"  Word connections: {stats['associations']}")
    lines.append(f"  Sentence patterns: {stats['markov_chains']}")

    if facts:
        lines.append("\nFacts:")
        for f in facts[:20]:
            lines.append(f"  [{f['topic']}] {f['info']}")

    if responses:
        lines.append("\nTaught responses:")
        for r in responses[:20]:
            lines.append(f'  "{r["trigger"]}" -> "{r["response"]}" (used {r["used"]}x)')

    return "\n".join(lines)


def handle_who_am_i():
    profile = get_profile()
    if profile:
        lines = ["Here's what I know about you:"]
        for k, v in profile.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    return pick([
        "I don't know much about you yet. Tell me your name to start.",
        "You haven't told me about yourself yet. Who are you?",
        "Blank slate on you. Introduce yourself.",
    ])


# ======================================================================
# MAIN PROCESS — the pipeline
# ======================================================================

def process(user_input):
    """Main brain. Classify -> Extract -> Respond. Never repeat."""

    text = user_input.strip()
    if not text:
        return "I'm listening."

    # Save to conversation history
    save_message("user", text)

    # Learn from user input (NOT from Jarvis responses — prevents echo loops)
    learn_associations(text)
    learn_markov(text)

    # Classify intent
    intent = classify_intent(text)

    # Route to handler
    if intent == "teaching_response":
        response = handle_teaching_response(text)
    elif intent == "teaching_fact":
        response = handle_teaching_fact(text)
    elif intent == "teaching_identity":
        response = handle_teaching_identity(text)
    elif intent == "show_knowledge":
        response = handle_show_knowledge()
    elif intent == "who_am_i":
        response = handle_who_am_i()
    elif intent == "time":
        now = datetime.datetime.now()
        response = now.strftime("It's %I:%M %p.")
    elif intent == "date":
        now = datetime.datetime.now()
        response = now.strftime("Today is %A, %B %d, %Y.")
    elif intent == "greeting":
        response = handle_greeting(text)
    elif intent == "goodbye":
        response = handle_goodbye(text)
    elif intent == "thanks":
        response = handle_thanks()
    elif intent == "how_are_you":
        response = handle_how_are_you()
    elif intent == "about_2bee":
        response = handle_about_2bee(text)
    elif intent == "user_feeling":
        response = handle_user_feeling(text)
    elif intent == "compliment":
        response = handle_compliment()
    elif intent == "frustration":
        response = handle_frustration()
    elif intent == "opinion":
        response = handle_opinion(text)
    elif intent == "query":
        response = handle_query(text)
    elif intent == "question":
        response = handle_question(text)
    elif intent == "agreement":
        response = pick(AGREEMENT_RESPONSES)
    elif intent == "disagreement":
        response = pick(DISAGREEMENT_RESPONSES)
    else:
        response = handle_statement(text)

    # Fallback safety
    if not response:
        response = pick(DONT_KNOW)

    # Save Jarvis response (but don't learn markov from it — prevents loops)
    save_message("2bee", response)

    return response
