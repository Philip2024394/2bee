"""
Auto-scraper daemon — pulls free public knowledge into 2b's memory 24/7.

Sources (all no-key, no-account, free-forever public APIs):
- Wikipedia random article summaries (English)
- HackerNews top stories (titles + URLs as fact pointers)
- ArXiv cs.AI recent submissions (titles + abstracts)
- Indonesian news headlines via free RSS aggregators (when reachable)

Runs as a background thread inside jarvis. Each cycle pulls 1-3 items from one
rotating source, dedups against existing facts, and stores via add_fact() with
source="autoscraper:<source_name>" so the user can audit/clear them later.

Sleep interval is randomized 90-300s between cycles so we don't hammer any
single API in lockstep. Total throughput target: ~20-40 new facts/hour, capped.
"""

import json
import random
import re
import threading
import time
import urllib.parse
import urllib.request
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime

from brain.memory import add_fact, search_facts


_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 2bee-autoscraper"
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

_active = False
_thread = None
_stats = {
    "started_at": None,
    "cycles": 0,
    "facts_added": 0,
    "skipped_duplicates": 0,
    "errors": 0,
    "last_source": None,
    "last_fact": None,
    "last_cycle_at": None,
}


def _fetch_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))


def _fetch_text(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
        return r.read().decode("utf-8", errors="ignore")


# ─── Sources ────────────────────────────────────────────────────────────

def source_wikipedia_random():
    """Pull 1 random Wikipedia summary. Returns list of (topic, info) tuples."""
    url = "https://en.wikipedia.org/api/rest_v1/page/random/summary"
    data = _fetch_json(url)
    title = (data.get("title") or "").strip()
    extract = (data.get("extract") or "").strip()
    if not title or not extract or len(extract) < 40:
        return []
    return [("wikipedia_" + re.sub(r"\W+", "_", title.lower())[:40],
             f"[{title}] {extract[:400]}")]


def source_hacker_news():
    """Pull top 2 HackerNews story titles."""
    ids = _fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")[:8]
    picks = random.sample(ids, min(2, len(ids)))
    out = []
    for sid in picks:
        try:
            story = _fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
            title = (story.get("title") or "").strip()
            url = (story.get("url") or "").strip()
            if title:
                info = title + (f" — {url}" if url else "")
                out.append((f"hn_{sid}", info[:400]))
        except Exception:
            continue
    return out


def source_arxiv_ai():
    """Pull 2 recent cs.AI papers from ArXiv."""
    url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=4"
    xml_text = _fetch_text(url, timeout=12)
    out = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        for entry in entries[:2]:
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            id_el = entry.find("atom:id", ns)
            if title_el is None or summary_el is None:
                continue
            title = (title_el.text or "").strip().replace("\n", " ")
            summary = (summary_el.text or "").strip().replace("\n", " ")[:350]
            paper_id = (id_el.text or "").split("/")[-1] if id_el is not None else ""
            if title and summary:
                out.append((f"arxiv_{paper_id}", f"[{title}] {summary}"))
    except Exception:
        pass
    return out


SOURCES = [
    ("wikipedia", source_wikipedia_random),
    ("hackernews", source_hacker_news),
    ("arxiv", source_arxiv_ai),
]


# ─── Daemon loop ────────────────────────────────────────────────────────

def _is_duplicate(info):
    """Cheap dup check — first 80 chars of info shouldn't already exist."""
    snippet = info[:80].lower()
    try:
        existing = search_facts(snippet)
        for e in existing[:5]:
            if e.get("info", "")[:80].lower() == snippet:
                return True
    except Exception:
        return False
    return False


def _cycle():
    """One pass: pick a random source, pull, store."""
    global _stats
    src_name, src_fn = random.choice(SOURCES)
    _stats["last_source"] = src_name
    _stats["cycles"] += 1
    _stats["last_cycle_at"] = datetime.utcnow().isoformat() + "Z"
    try:
        items = src_fn() or []
    except Exception as e:
        _stats["errors"] += 1
        return
    for topic, info in items:
        if _is_duplicate(info):
            _stats["skipped_duplicates"] += 1
            continue
        try:
            add_fact(topic, info, source=f"autoscraper:{src_name}")
            _stats["facts_added"] += 1
            _stats["last_fact"] = info[:120]
        except Exception:
            _stats["errors"] += 1


def _loop(min_sleep=90, max_sleep=300):
    global _active
    _stats["started_at"] = datetime.utcnow().isoformat() + "Z"
    while _active:
        _cycle()
        if not _active:
            break
        # Randomized sleep so we don't hammer one API on a fixed beat
        delay = random.randint(min_sleep, max_sleep)
        slept = 0
        while slept < delay and _active:
            time.sleep(1)
            slept += 1


def start(min_sleep=90, max_sleep=300):
    """Start the background daemon. Safe to call multiple times — only one
    thread runs at a time."""
    global _active, _thread
    if _active:
        return False
    _active = True
    _thread = threading.Thread(target=_loop, args=(min_sleep, max_sleep), daemon=True)
    _thread.start()
    return True


def stop():
    global _active
    _active = False


def get_stats():
    return dict(_stats, active=_active)
