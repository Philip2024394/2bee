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
    conn = sqlite3.connect(DB_PATH)
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
            created TEXT NOT NULL
        )
    """)

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

def add_fact(topic, info):
    conn = get_db()
    # Don't duplicate
    existing = conn.execute(
        "SELECT id FROM facts WHERE topic = ? AND info = ?", (topic.lower(), info)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO facts (topic, info, created) VALUES (?, ?, ?)",
            (topic.lower(), info, datetime.now().isoformat())
        )
        conn.commit()
    conn.close()


def search_facts(query):
    conn = get_db()
    words = query.lower().split()
    results = []
    for word in words:
        rows = conn.execute(
            "SELECT topic, info FROM facts WHERE LOWER(topic) LIKE ? OR LOWER(info) LIKE ?",
            (f"%{word}%", f"%{word}%")
        ).fetchall()
        results.extend(rows)
    conn.close()
    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        key = (r["topic"], r["info"])
        if key not in seen:
            seen.add(key)
            unique.append({"topic": r["topic"], "info": r["info"]})
    return unique


def get_all_facts():
    conn = get_db()
    rows = conn.execute("SELECT topic, info FROM facts ORDER BY topic").fetchall()
    conn.close()
    return [{"topic": r["topic"], "info": r["info"]} for r in rows]


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
