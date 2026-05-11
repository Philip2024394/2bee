"""
2bee Memory — Pure Python, standard library only.
SQLite3 is built into Python. No installs needed.
"""

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "2bee.db")


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def init():
    conn = get_db()
    c = conn.cursor()

    # Everything the user teaches Jarvis directly
    # "when I say X, you say Y"
    c.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_pattern TEXT NOT NULL,
            response TEXT NOT NULL,
            created TEXT NOT NULL,
            times_used INTEGER DEFAULT 0
        )
    """)

    # Facts Jarvis has been told
    c.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            info TEXT NOT NULL,
            created TEXT NOT NULL,
            source TEXT DEFAULT 'unknown',
            confidence REAL DEFAULT 0.5,
            last_used TEXT,
            use_count INTEGER DEFAULT 0
        )
    """)

    # Migrate existing tables — add new columns if missing
    try:
        c.execute("ALTER TABLE facts ADD COLUMN source TEXT DEFAULT 'unknown'")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE facts ADD COLUMN confidence REAL DEFAULT 0.5")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE facts ADD COLUMN last_used TEXT")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE facts ADD COLUMN use_count INTEGER DEFAULT 0")
    except Exception:
        pass

    # Full conversation log — Jarvis learns patterns from this
    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    # Word associations — Jarvis builds these from conversations
    # "word_a often appears near word_b"
    c.execute("""
        CREATE TABLE IF NOT EXISTS associations (
            word_a TEXT NOT NULL,
            word_b TEXT NOT NULL,
            strength REAL DEFAULT 1.0,
            PRIMARY KEY (word_a, word_b)
        )
    """)

    # Markov chains — Jarvis learns to form sentences
    c.execute("""
        CREATE TABLE IF NOT EXISTS markov (
            word1 TEXT NOT NULL,
            word2 TEXT NOT NULL,
            next_word TEXT NOT NULL,
            count INTEGER DEFAULT 1,
            PRIMARY KEY (word1, word2, next_word)
        )
    """)

    # User profile
    c.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# --- Taught Responses ---

def add_response(trigger, response):
    conn = get_db()
    conn.execute(
        "INSERT INTO responses (trigger_pattern, response, created) VALUES (?, ?, ?)",
        (trigger.lower().strip(), response, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def find_response(user_input):
    conn = get_db()
    # Exact match first
    row = conn.execute(
        "SELECT id, response FROM responses WHERE trigger_pattern = ?",
        (user_input.lower().strip(),)
    ).fetchone()
    if row:
        conn.execute("UPDATE responses SET times_used = times_used + 1 WHERE id = ?", (row["id"],))
        conn.commit()
        conn.close()
        return row["response"]

    # Partial match — trigger is contained in input
    rows = conn.execute("SELECT id, trigger_pattern, response FROM responses").fetchall()
    conn.close()

    best = None
    best_score = 0
    words_in = set(user_input.lower().split())

    for row in rows:
        trigger_words = set(row["trigger_pattern"].split())
        if not trigger_words:
            continue
        overlap = len(words_in & trigger_words)
        score = overlap / len(trigger_words)
        if score > best_score and score >= 0.6:
            best_score = score
            best = row["response"]

    return best


def get_all_responses():
    conn = get_db()
    rows = conn.execute("SELECT trigger_pattern, response, times_used FROM responses ORDER BY times_used DESC").fetchall()
    conn.close()
    return [{"trigger": r["trigger_pattern"], "response": r["response"], "used": r["times_used"]} for r in rows]


# --- Facts ---

# Confidence levels by source
SOURCE_CONFIDENCE = {
    'user_taught': 1.0,    # User told 2bee directly — highest trust
    'wikipedia': 0.9,      # Wikipedia — verified, community-edited
    'wikidata': 0.9,       # Wikidata — structured verified data
    'verified': 0.85,      # DuckDuckGo instant answers — aggregated from trusted sites
    'stackexchange': 0.75, # StackExchange — upvoted community answers
    'news': 0.6,           # RSS news — factual but may be time-sensitive
    'general': 0.7,        # User-taught general facts
    'conversation': 0.4,   # Extracted from conversation — low confidence
    'random_fact': 0.5,    # Random fact APIs
    'quote': 0.5,          # Quotes
    'unknown': 0.5,        # Legacy/unknown source
}


def add_fact(topic, info, source=None):
    conn = get_db()
    # Don't duplicate
    existing = conn.execute(
        "SELECT id FROM facts WHERE topic = ? AND info = ?", (topic.lower(), info)
    ).fetchone()
    if not existing:
        # Auto-detect source from topic if not provided
        if source is None:
            source = topic.lower() if topic.lower() in SOURCE_CONFIDENCE else 'unknown'
        confidence = SOURCE_CONFIDENCE.get(source, 0.5)
        conn.execute(
            "INSERT INTO facts (topic, info, created, source, confidence) VALUES (?, ?, ?, ?, ?)",
            (topic.lower(), info, datetime.now().isoformat(), source, confidence)
        )
        conn.commit()
    conn.close()


def search_facts(query):
    conn = get_db()
    query_lower = query.lower().strip()
    # Strip stopwords so "who is your admin" → ["admin"] not ["who","your","admin"].
    # Stopwords would otherwise inflate the word count and push min_hits past
    # what a single-keyword fact can satisfy.
    STOPWORDS = {
        "who", "what", "where", "when", "why", "how", "which", "is", "are",
        "was", "were", "the", "a", "an", "your", "my", "you", "i", "me",
        "do", "does", "did", "can", "will", "would", "should", "could",
        "of", "on", "at", "by", "to", "for", "with", "from", "as", "this",
        "that", "these", "those", "it", "its",
    }
    all_words = [w for w in query_lower.split() if len(w) > 2]
    words = [w for w in all_words if w not in STOPWORDS]
    if not words:  # query was all stopwords — fall back to original
        words = all_words
    results = []

    # 1. Exact full-query match in info (strongest signal)
    if len(query_lower) > 3:
        rows = conn.execute(
            "SELECT topic, info, source, confidence FROM facts WHERE LOWER(info) LIKE ?",
            (f"%{query_lower}%",)
        ).fetchall()
        for r in rows:
            results.append((r, 3))  # priority boost

    # 2. Word-level matches — meaningful-word hits only
    word_hits = {}
    for word in words:
        rows = conn.execute(
            "SELECT topic, info, source, confidence FROM facts WHERE LOWER(info) LIKE ?",
            (f"%{word}%",)
        ).fetchall()
        for r in rows:
            key = (r["topic"], r["info"])
            if key not in word_hits:
                word_hits[key] = {"row": r, "hits": 0}
            word_hits[key]["hits"] += 1

    # Threshold: need at least half the meaningful words to match (rounded up).
    # 1 word query → 1 hit. 2 words → 1 hit. 3 words → 2 hits. 4 words → 2 hits.
    min_hits = max(1, (len(words) + 1) // 2)
    # If nothing meets min_hits, relax to 1 — better to surface a partial match
    # than return nothing and force the LLM to hallucinate.
    qualified = [(d, k) for k, d in word_hits.items() if d["hits"] >= min_hits]
    if not qualified and word_hits:
        qualified = [(d, k) for k, d in word_hits.items() if d["hits"] >= 1]
    for data, _ in qualified:
        results.append((data["row"], data["hits"]))

    conn.close()

    # Deduplicate, score, sort. user_taught gets a big multiplier so curated
    # knowledge always outranks scraped wikipedia/news entries when both match.
    seen = set()
    unique = []
    for r, hits in results:
        key = (r["topic"], r["info"])
        if key not in seen:
            seen.add(key)
            conf = r["confidence"] if "confidence" in r.keys() else 0.5
            source = r["source"] if "source" in r.keys() else "unknown"
            source_boost = 5.0 if source == "user_taught" else 1.0
            unique.append({
                "topic": r["topic"],
                "info": r["info"],
                "source": source,
                "confidence": conf,
                "_score": conf * hits * source_boost,
            })
    unique.sort(key=lambda x: x["_score"], reverse=True)
    return unique


def mark_fact_used(topic, info):
    """Track when a fact is used in a response — boosts its relevance."""
    conn = get_db()
    conn.execute(
        "UPDATE facts SET use_count = use_count + 1, last_used = ? WHERE topic = ? AND info = ?",
        (datetime.now().isoformat(), topic.lower(), info)
    )
    conn.commit()
    conn.close()


def get_all_facts():
    conn = get_db()
    rows = conn.execute("SELECT topic, info, source, confidence FROM facts ORDER BY confidence DESC, topic").fetchall()
    conn.close()
    return [{"topic": r["topic"], "info": r["info"],
             "source": r["source"] if "source" in r.keys() else "unknown",
             "confidence": r["confidence"] if "confidence" in r.keys() else 0.5} for r in rows]


def get_recent_facts(limit=15, source=None):
    """Most-recently-added facts first. Use for 'what did I teach you?' so
    the user sees what was just stored, not the highest-confidence legacy entries."""
    conn = get_db()
    if source:
        rows = conn.execute(
            "SELECT topic, info, source, confidence, created FROM facts WHERE source = ? ORDER BY id DESC LIMIT ?",
            (source, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT topic, info, source, confidence, created FROM facts ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [{"topic": r["topic"], "info": r["info"],
             "source": r["source"] if "source" in r.keys() else "unknown",
             "confidence": r["confidence"] if "confidence" in r.keys() else 0.5,
             "created": r["created"] if "created" in r.keys() else ""} for r in rows]


# --- Conversations ---

def save_message(role, message):
    conn = get_db()
    conn.execute(
        "INSERT INTO conversations (role, message, timestamp) VALUES (?, ?, ?)",
        (role, message, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_recent(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT role, message FROM conversations ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "message": r["message"]} for r in reversed(rows)]


# --- Word Associations ---

def learn_associations(text):
    words = text.lower().split()
    if len(words) < 2:
        return
    conn = get_db()
    for i, w1 in enumerate(words):
        for w2 in words[i+1:min(i+4, len(words))]:  # window of 3
            if w1 == w2:
                continue
            conn.execute("""
                INSERT INTO associations (word_a, word_b, strength)
                VALUES (?, ?, 1.0)
                ON CONFLICT(word_a, word_b)
                DO UPDATE SET strength = strength + 0.5
            """, (w1, w2))
    conn.commit()
    conn.close()


def get_associated(word, limit=5):
    conn = get_db()
    rows = conn.execute("""
        SELECT word_b AS word, strength FROM associations WHERE word_a = ?
        UNION
        SELECT word_a AS word, strength FROM associations WHERE word_b = ?
        ORDER BY strength DESC LIMIT ?
    """, (word.lower(), word.lower(), limit)).fetchall()
    conn.close()
    return [{"word": r["word"], "strength": r["strength"]} for r in rows]


# --- Markov Chain ---

def learn_markov(text):
    words = text.split()
    if len(words) < 3:
        return
    conn = get_db()
    for i in range(len(words) - 2):
        w1 = words[i].lower()
        w2 = words[i+1].lower()
        nxt = words[i+2].lower()
        conn.execute("""
            INSERT INTO markov (word1, word2, next_word, count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(word1, word2, next_word)
            DO UPDATE SET count = count + 1
        """, (w1, w2, nxt))
    conn.commit()
    conn.close()


def generate_markov(seed_word, length=15):
    import random
    conn = get_db()

    # Find a starting pair with the seed
    row = conn.execute(
        "SELECT word1, word2 FROM markov WHERE word1 = ? ORDER BY count DESC LIMIT 1",
        (seed_word.lower(),)
    ).fetchone()

    if not row:
        row = conn.execute(
            "SELECT word1, word2 FROM markov WHERE word2 = ? ORDER BY count DESC LIMIT 1",
            (seed_word.lower(),)
        ).fetchone()

    if not row:
        conn.close()
        return None

    result = [row["word1"], row["word2"]]

    for _ in range(length):
        w1, w2 = result[-2], result[-1]
        options = conn.execute(
            "SELECT next_word, count FROM markov WHERE word1 = ? AND word2 = ?",
            (w1, w2)
        ).fetchall()

        if not options:
            break

        # Weighted random choice
        words = [o["next_word"] for o in options]
        weights = [o["count"] for o in options]
        total = sum(weights)
        r = random.random() * total
        cumulative = 0
        chosen = words[0]
        for word, weight in zip(words, weights):
            cumulative += weight
            if r <= cumulative:
                chosen = word
                break
        result.append(chosen)

    conn.close()
    return " ".join(result)


# --- User Profile ---

def set_profile(key, value):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO profile (key, value, updated) VALUES (?, ?, ?)",
        (key, value, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_profile():
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM profile").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


# --- Stats ---

def get_stats():
    conn = get_db()
    stats = {
        "conversations": conn.execute("SELECT COUNT(*) c FROM conversations").fetchone()["c"],
        "facts": conn.execute("SELECT COUNT(*) c FROM facts").fetchone()["c"],
        "responses": conn.execute("SELECT COUNT(*) c FROM responses").fetchone()["c"],
        "associations": conn.execute("SELECT COUNT(*) c FROM associations").fetchone()["c"],
        "markov_chains": conn.execute("SELECT COUNT(*) c FROM markov").fetchone()["c"],
        "profile_items": conn.execute("SELECT COUNT(*) c FROM profile").fetchone()["c"],
    }
    conn.close()
    return stats
