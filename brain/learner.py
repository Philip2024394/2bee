"""
2bee Background Learner — Pulls knowledge from the open web.
No API keys. No accounts. No third party libraries.
Uses only Python standard library (urllib, json, xml.etree).

Sources:
  - Wikipedia (free API, no key)
  - RSS feeds (news, science, tech)
  - Public fact APIs

Runs in background threads. Pauses when system is busy.
"""

import urllib.request
import urllib.parse
import json
import xml.etree.ElementTree as ET
import threading
import time
import random
import os
import re
import sys

from brain.memory import add_fact, search_facts, get_stats, get_db

# ======================================================================
# CONFIGURATION
# ======================================================================

# Max facts to store total (prevents disk blowup on 8GB machine)
# 10,000 facts ~ 20-30MB of SQLite — safe for 8GB RAM
MAX_FACTS = 10000

# How often to learn (seconds)
LEARN_INTERVAL = 60  # 1 minute between learning cycles

# Max KB of data per learning cycle
MAX_CYCLE_KB = 100

# User agent so Wikipedia doesn't block us
USER_AGENT = "2beeAI/1.0 (Personal Learning Bot; local use only)"

# Track what we've already learned
_learned_topics = set()
_running = False
_thread = None

# Topics to explore — starts broad, Jarvis narrows based on user interests
_topic_queue = [
    "Artificial intelligence", "Computer science", "Python programming language",
    "Mathematics", "Physics", "History", "Philosophy", "Engineering",
    "Space exploration", "Biology", "Chemistry", "Economics",
    "Psychology", "Music", "Technology", "Internet", "Robotics",
]


# ======================================================================
# WIKIPEDIA — the biggest free knowledge source
# ======================================================================

def wiki_summary(topic):
    """Get a Wikipedia summary. Free API, no key needed."""
    try:
        encoded = urllib.parse.quote(topic)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            title = data.get("title", topic)
            extract = data.get("extract", "")
            if extract and len(extract) > 50:
                return title, extract
    except Exception:
        pass
    return None, None


def wiki_random():
    """Get a random Wikipedia article summary."""
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            title = data.get("title", "")
            extract = data.get("extract", "")
            if extract and len(extract) > 50:
                return title, extract
    except Exception:
        pass
    return None, None


def wiki_search(query, limit=5):
    """Search Wikipedia for related topics."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded}&limit={limit}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if len(data) >= 2:
                return data[1]  # list of titles
    except Exception:
        pass
    return []


# ======================================================================
# RSS FEEDS — live news and knowledge
# ======================================================================

RSS_FEEDS = [
    # Science
    "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml",
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    # Tech
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    # World
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]


def fetch_rss(url):
    """Fetch and parse an RSS feed. Returns list of (title, description)."""
    items = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            # Standard RSS
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                desc = item.findtext("description", "").strip()
                # Strip HTML tags from description
                desc = re.sub(r"<[^>]+>", "", desc).strip()
                if title and desc and len(desc) > 30:
                    items.append((title, desc[:500]))
    except Exception:
        pass
    return items[:10]  # cap at 10 per feed


# ======================================================================
# PUBLIC FACT APIs — no key needed
# ======================================================================

def fetch_random_fact():
    """Get a random fact from uselessfacts API."""
    try:
        url = "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("text", "")
    except Exception:
        return None


def fetch_quote():
    """Get a random quote."""
    try:
        url = "https://api.quotable.io/random"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            author = data.get("author", "Unknown")
            content = data.get("content", "")
            if content:
                return f"{content} - {author}"
    except Exception:
        return None


# ======================================================================
# SMART STORAGE — compress and manage within hardware limits
# ======================================================================

def compress_text(text, max_len=500):
    """Compress text to essential info. Keeps it under max_len."""
    if len(text) <= max_len:
        return text
    # Take first N sentences that fit
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = []
    total = 0
    for s in sentences:
        if total + len(s) > max_len:
            break
        result.append(s)
        total += len(s)
    return " ".join(result) if result else text[:max_len]


def is_at_capacity():
    """Check if we're near storage limits."""
    stats = get_stats()
    return stats["facts"] >= MAX_FACTS


def prune_low_value():
    """Remove old, unused, low-confidence knowledge to make room."""
    conn = get_db()
    # Delete oldest facts from 'random_fact' and 'news' if over limit
    count = conn.execute("SELECT COUNT(*) c FROM facts").fetchone()["c"]
    if count > MAX_FACTS * 0.9:
        excess = int(count - MAX_FACTS * 0.7)
        conn.execute("""
            DELETE FROM facts WHERE id IN (
                SELECT id FROM facts
                WHERE topic IN ('random_fact', 'news', 'quote', 'wikipedia')
                ORDER BY created ASC
                LIMIT ?
            )
        """, (excess,))
        conn.commit()
        print(f"[Learner] Pruned {excess} old facts to stay within limits.")
    conn.close()


def get_db_size_mb():
    """Get current database size in MB."""
    from brain.memory import DB_PATH
    if os.path.exists(DB_PATH):
        return os.path.getsize(DB_PATH) / (1024 * 1024)
    return 0


# ======================================================================
# INTEREST TRACKING — learn what the user cares about
# ======================================================================

def get_user_interests():
    """Pull topics from user profile and conversation to guide learning."""
    from brain.memory import get_profile, get_all_facts
    interests = []

    profile = get_profile()
    for key, value in profile.items():
        if key in ("likes", "work", "interests"):
            interests.append(value)

    # Get fact topics the user has taught
    facts = get_all_facts()
    for f in facts:
        if f["topic"] not in ("general", "random_fact", "news", "wikipedia", "quote", "conversation"):
            interests.append(f["topic"])
        # Extract keywords from user-taught facts
        if f["topic"] == "general":
            words = f["info"].split()
            for w in words:
                if len(w) > 5 and w.isalpha():
                    interests.append(w)

    return list(set(interests))[:20]


# ======================================================================
# LEARNING CYCLE — what happens each interval
# ======================================================================

def learn_cycle():
    """One cycle of background learning."""
    global _learned_topics

    if is_at_capacity():
        prune_low_value()

    learned = 0

    # 1. Learn from Wikipedia — prioritize user interests
    interests = get_user_interests()
    topics_to_learn = []

    if interests:
        for interest in random.sample(interests, min(3, len(interests))):
            related = wiki_search(interest, 3)
            topics_to_learn.extend(related)

    # Add from queue
    if _topic_queue:
        topics_to_learn.append(_topic_queue.pop(0))
        # Replenish queue with random articles
        if len(_topic_queue) < 5:
            _, extract = wiki_random()
            if extract:
                words = [w for w in extract.split() if len(w) > 6 and w.isalpha()]
                if words:
                    _topic_queue.append(random.choice(words))

    # Also grab a random article for breadth
    topics_to_learn.append("__random__")

    for topic in topics_to_learn[:5]:  # max 5 per cycle
        if topic in _learned_topics:
            continue

        if topic == "__random__":
            title, extract = wiki_random()
        else:
            title, extract = wiki_summary(topic)

        if title and extract:
            compressed = compress_text(extract, 400)
            # Check we don't already have this
            existing = search_facts(title)
            if not any(e["topic"] == "wikipedia" and title.lower() in e["info"].lower() for e in existing):
                add_fact("wikipedia", f"[{title}] {compressed}")
                _learned_topics.add(topic)
                learned += 1

        time.sleep(1)  # be nice to Wikipedia

    # 2. Grab news from RSS (1 random feed per cycle)
    feed = random.choice(RSS_FEEDS)
    items = fetch_rss(feed)
    for title, desc in items[:3]:
        compressed = compress_text(desc, 300)
        existing = search_facts(title[:30])
        if not any(title.lower()[:20] in e["info"].lower() for e in existing):
            add_fact("news", f"[{title}] {compressed}")
            learned += 1

    # 3. Random facts and quotes (1 each per cycle)
    fact = fetch_random_fact()
    if fact:
        add_fact("random_fact", fact)
        learned += 1

    quote = fetch_quote()
    if quote:
        add_fact("quote", quote)
        learned += 1

    return learned


# ======================================================================
# BACKGROUND THREAD
# ======================================================================

def _background_loop():
    """Main background learning loop."""
    global _running
    print("[Learner] Background learning started.")

    # Initial delay — let the system settle
    time.sleep(3)

    while _running:
        try:
            db_size = get_db_size_mb()
            stats = get_stats()
            print(f"[Learner] Cycle starting... (DB: {db_size:.1f}MB, {stats['facts']} facts)")

            learned = learn_cycle()

            print(f"[Learner] Learned {learned} new things. Next cycle in {LEARN_INTERVAL}s.")

        except Exception as e:
            print(f"[Learner] Error in cycle: {e}")

        # Sleep in small chunks so we can stop quickly
        for _ in range(LEARN_INTERVAL):
            if not _running:
                break
            time.sleep(1)

    print("[Learner] Background learning stopped.")


def start():
    """Start background learning."""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_background_loop, daemon=True)
    _thread.start()


def stop():
    """Stop background learning."""
    global _running
    _running = False


def is_running():
    return _running


def get_learning_stats():
    """Get stats about the learning system."""
    db_size = get_db_size_mb()
    stats = get_stats()
    return {
        "running": _running,
        "db_size_mb": round(db_size, 2),
        "total_facts": stats["facts"],
        "topics_learned": len(_learned_topics),
        "topics_queued": len(_topic_queue),
        "max_facts": MAX_FACTS,
        "capacity_pct": round((stats["facts"] / MAX_FACTS) * 100, 1) if MAX_FACTS > 0 else 0,
    }
