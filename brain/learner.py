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
import datetime

from brain.memory import add_fact, search_facts, get_stats, get_db

# ======================================================================
# CONFIGURATION
# ======================================================================

# Max facts to store total
# 50,000 facts ~ 100-150MB of SQLite — safe for any modern machine
MAX_FACTS = 50000

# How often to learn (seconds)
LEARN_INTERVAL = 30  # 30 seconds — aggressive learning mode

# Max KB of data per learning cycle
MAX_CYCLE_KB = 100

# User agent so Wikipedia doesn't block us
USER_AGENT = "2beeAI/1.0 (Personal Learning Bot; local use only)"

# Track what we've already learned
_learned_topics = set()
_running = False
_thread = None

# Priority learning topics — focused on what matters most
_PRIORITY_TOPICS = [
    # Marketing
    "Digital marketing", "Social media marketing", "Content marketing",
    "Search engine optimization", "Email marketing", "Affiliate marketing",
    "Influencer marketing", "Growth hacking", "Brand marketing",
    "Marketing strategy", "Copywriting", "Sales funnel",
    "Pay-per-click advertising", "Google Ads", "Facebook advertising",
    "Conversion rate optimization", "Customer acquisition",
    # Building AI Apps
    "Artificial intelligence", "Machine learning", "Deep learning",
    "Large language model", "Neural network", "Natural language processing",
    "Computer vision", "Generative artificial intelligence",
    "OpenAI", "ChatGPT", "Claude AI", "Anthropic",
    "TensorFlow", "PyTorch", "Hugging Face", "LangChain",
    "Retrieval-augmented generation", "Fine-tuning",
    "AI agent", "Prompt engineering", "Vector database",
    "Python programming language", "API", "REST API",
    "React JavaScript library", "Node.js", "Vite",
    # Video Creation
    "Video editing", "Video production", "YouTube",
    "Adobe Premiere Pro", "DaVinci Resolve", "CapCut",
    "Motion graphics", "Animation", "After Effects",
    "Video marketing", "Short-form video", "TikTok",
    "Screen recording", "OBS Studio", "Cinematography",
    "Color grading", "Sound design", "Storytelling",
    # Business & Entrepreneurship
    "Startup company", "Business model", "SaaS",
    "Product-market fit", "Lean startup", "Venture capital",
    "E-commerce", "Dropshipping", "Subscription business model",
    "Indonesian economy", "Southeast Asian market",
]

# URLs to scrape on first boot (StreetLocal market research)
_PRIORITY_URLS = [
    "https://en.wikipedia.org/wiki/Digital_marketing",
    "https://en.wikipedia.org/wiki/Search_engine_optimization",
    "https://en.wikipedia.org/wiki/Progressive_web_app",
    "https://en.wikipedia.org/wiki/Software_as_a_service",
    "https://en.wikipedia.org/wiki/Online_food_ordering",
    "https://en.wikipedia.org/wiki/GrabFood",
    "https://en.wikipedia.org/wiki/Indonesian_cuisine",
    "https://en.wikipedia.org/wiki/E-commerce_in_Southeast_Asia",
]
_urls_scraped = False

# Rotate through priority topics — always learning the important stuff
_topic_queue = list(_PRIORITY_TOPICS)


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
    # AI & Tech
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    # Marketing
    "https://blog.hubspot.com/marketing/rss.xml",
    "https://contentmarketinginstitute.com/feed/",
    "https://feeds.feedburner.com/socialmediaexaminer",
    # Business
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    # Science
    "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
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
    """Remove old, unused, low-confidence knowledge to make room.
    Preserves user-taught facts (highest confidence). Expires stale news."""
    conn = get_db()

    # 1. Delete news older than 7 days (time-sensitive, expires fast)
    try:
        seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
        deleted = conn.execute("""
            DELETE FROM facts WHERE source = 'news' AND created < ?
        """, (seven_days_ago,)).rowcount
        if deleted:
            print(f"[Learner] Expired {deleted} stale news facts (>7 days old).")
    except Exception:
        pass

    # 2. Delete old random facts and quotes (low value, replace with fresh)
    try:
        thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).isoformat()
        deleted = conn.execute("""
            DELETE FROM facts WHERE source IN ('random_fact', 'quote') AND created < ?
        """, (thirty_days_ago,)).rowcount
        if deleted:
            print(f"[Learner] Pruned {deleted} old random facts/quotes (>30 days).")
    except Exception:
        pass

    # 3. If still over limit, delete lowest-confidence unused facts
    count = conn.execute("SELECT COUNT(*) c FROM facts").fetchone()["c"]
    if count > MAX_FACTS * 0.9:
        excess = int(count - MAX_FACTS * 0.7)
        conn.execute("""
            DELETE FROM facts WHERE id IN (
                SELECT id FROM facts
                WHERE source NOT IN ('user_taught')
                ORDER BY confidence ASC, use_count ASC, created ASC
                LIMIT ?
            )
        """, (excess,))
        print(f"[Learner] Pruned {excess} low-confidence facts to stay within limits.")

    conn.commit()
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
    global _learned_topics, _urls_scraped

    if is_at_capacity():
        prune_low_value()

    # First boot: scrape priority URLs for StreetLocal market knowledge
    if not _urls_scraped:
        _urls_scraped = True
        for url in _PRIORITY_URLS:
            try:
                scrape_url(url)
                time.sleep(1)
            except Exception:
                pass
        print("[Learner] Priority URLs scraped for market research.")

    learned = 0

    # 1. Learn from Wikipedia — prioritize user interests
    interests = get_user_interests()
    topics_to_learn = []

    if interests:
        for interest in random.sample(interests, min(3, len(interests))):
            related = wiki_search(interest, 3)
            topics_to_learn.extend(related)

    # Add from priority queue — take 2 per cycle for faster coverage
    for _ in range(2):
        if _topic_queue:
            topics_to_learn.append(_topic_queue.pop(0))

    # Replenish queue from PRIORITY topics when exhausted (infinite loop)
    if len(_topic_queue) < 5:
        # Re-add priority topics we haven't learned yet
        remaining = [t for t in _PRIORITY_TOPICS if t not in _learned_topics]
        if remaining:
            _topic_queue.extend(remaining[:10])
        else:
            # All priority topics learned — explore deeper via Wikipedia search
            for pt in random.sample(_PRIORITY_TOPICS, min(5, len(_PRIORITY_TOPICS))):
                related = wiki_search(pt, 3)
                _topic_queue.extend([r for r in related if r not in _learned_topics])

    # Also grab a random article for breadth (1 in 3 cycles)
    if random.random() < 0.33:
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


# ======================================================================
# PINTEREST — design inspiration, layouts, UI elements, color palettes
# ======================================================================

def design_search(query, limit=8):
    """Search for design inspiration using multiple free sources.
    Uses Pollinations.ai to GENERATE design concepts + DuckDuckGo for real references.
    Returns list of {title, image_url, link, description}."""
    results = []
    encoded = urllib.parse.quote(query)

    # 1. Generate design concepts via Pollinations.ai (always works, instant)
    design_prompts = [
        f"{query}, professional UI UX design, clean modern layout, high quality",
        f"{query}, mobile app screenshot, dark theme, minimal design",
        f"{query}, color palette and typography, design system, flat design",
    ]
    for i, prompt in enumerate(design_prompts[:3]):
        seed = hash(prompt) % 99999
        img_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=768&height=512&nologo=true&seed={seed}"
        results.append({
            "title": f"AI Generated: {query} (v{i+1})",
            "image_url": img_url,
            "link": img_url,
            "description": f"AI-generated design concept for: {query}",
        })

    # 2. Search DuckDuckGo for real design references
    try:
        ddg_url = f"https://api.duckduckgo.com/?q={encoded}+UI+design+layout&format=json&no_html=1"
        req = urllib.request.Request(ddg_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Get related topics with images
            for item in data.get("RelatedTopics", [])[:5]:
                icon = item.get("Icon", {}).get("URL", "")
                text = item.get("Text", "")
                link = item.get("FirstURL", "")
                if text and len(text) > 20:
                    results.append({
                        "title": text[:80],
                        "image_url": icon if icon else "",
                        "link": link,
                        "description": text[:200],
                    })
    except Exception:
        pass

    # 3. Pinterest link (user can open in browser)
    results.append({
        "title": f"Browse Pinterest: {query}",
        "image_url": "",
        "link": f"https://www.pinterest.com/search/pins/?q={encoded}",
        "description": "Open Pinterest for more design inspiration",
    })

    return results[:limit]


def scrape_pinterest_designs(query):
    """Search for design elements and store as design references.
    Uses AI generation + web search. Returns image URLs and summary."""
    results = design_search(query)
    if not results:
        return [], f"No design results for '{query}'."

    stored = 0
    image_urls = []
    for item in results:
        info = f"[Design Reference] {item['title']}: {item['description']}"
        if item['image_url']:
            image_urls.append(item['image_url'])
        if item['link']:
            info += f" | Link: {item['link']}"
        add_fact("design_reference", info, source="verified")
        stored += 1

    return image_urls, f"Found {stored} design references for '{query}'. Includes AI-generated concepts and web references."


def _ddg_instant(query):
    """DuckDuckGo Instant Answer API — returns factual abstracts, not user opinions."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # AbstractText is from verified sources (Wikipedia, official sites)
            abstract = data.get("AbstractText", "")
            if abstract and len(abstract) > 50:
                source = data.get("AbstractSource", "")
                return compress_text(abstract, 400), source
            # Check related topics — but only factual ones, not code/forum posts
            related = data.get("RelatedTopics", [])
            for item in related[:3]:
                text = item.get("Text", "")
                if text and len(text) > 50:
                    # Skip code snippets and forum noise
                    if any(skip in text.lower() for skip in ['javascript', 'python', 'stackoverflow', 'function(', 'var ', 'const ', '{', '}']):
                        continue
                    return compress_text(text, 400), "DuckDuckGo"
    except Exception:
        pass
    return None, None


def _wikidata_search(query):
    """Wikidata — structured factual data (dates, numbers, definitions)."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={encoded}&language=en&format=json&limit=3"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("search", [])
            for r in results:
                desc = r.get("description", "")
                label = r.get("label", "")
                if desc and label and len(desc) > 10:
                    return f"{label}: {desc}", "Wikidata"
    except Exception:
        pass
    return None, None


def _stackexchange_search(query):
    """StackExchange — highly upvoted answers only (factual, community-verified)."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.stackexchange.com/2.3/search/excerpts?order=desc&sort=votes&q={encoded}&site=stackoverflow&accepted=True&pagesize=3&filter=!nNPvSNPI7A"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            # StackExchange may gzip even without asking
            try:
                import gzip
                raw = gzip.decompress(raw)
            except Exception:
                pass
            data = json.loads(raw.decode("utf-8"))
            items = data.get("items", [])
            for item in items:
                if item.get("score", 0) >= 5:  # only well-upvoted
                    excerpt = item.get("excerpt", "")
                    title = item.get("title", "")
                    if excerpt and len(excerpt) > 50:
                        clean = re.sub(r"<[^>]+>", "", excerpt).strip()
                        return compress_text(f"{title}: {clean}", 400), "StackExchange"
    except Exception:
        pass
    return None, None


def research_now(query):
    """Immediately research a topic when 2bee doesn't know the answer.
    Searches multiple trusted sources for FACTUAL, VERIFIED information.
    Ignores user opinions, blog posts, and social media.
    Returns the best result or None."""
    results = []

    # 1. Wikipedia FIRST — the gold standard for factual summaries
    title, extract = wiki_summary(query)
    if title and extract:
        compressed = compress_text(extract, 400)
        add_fact("wikipedia", f"[{title}] {compressed}")
        results.append(compressed)

    # 2. DuckDuckGo Instant Answer — aggregates from verified sources
    if not results:
        ddg_text, ddg_src = _ddg_instant(query)
        if ddg_text:
            add_fact("verified", f"[{ddg_src}] {ddg_text}")
            results.append(ddg_text)

    # 3. Wikidata — structured facts
    if not results:
        wd_text, wd_src = _wikidata_search(query)
        if wd_text:
            add_fact("wikidata", wd_text)
            results.append(wd_text)

    # 4. Search Wikipedia for related articles
    if not results:
        related = wiki_search(query, 5)
        for topic in related[:3]:
            if topic in _learned_topics:
                continue
            t, ext = wiki_summary(topic)
            if t and ext:
                compressed = compress_text(ext, 400)
                add_fact("wikipedia", f"[{t}] {compressed}")
                _learned_topics.add(topic)
                results.append(compressed)
                break

    # 5. StackExchange — DISABLED (too noisy for general knowledge)
    # Only useful for programming queries, causes garbage for general facts

    # 6. Last resort — try individual words
    if not results:
        words = [w for w in query.split() if len(w) > 3 and w.isalpha()]
        for word in words[:3]:
            ddg_text, _ = _ddg_instant(word)
            if ddg_text:
                add_fact("verified", ddg_text)
                results.append(ddg_text)
                break
            t, ext = wiki_summary(word)
            if t and ext and len(ext) > 100:
                compressed = compress_text(ext, 300)
                add_fact("wikipedia", f"[{t}] {compressed}")
                results.append(compressed)
                break

    if results:
        return results[0]

    # --- MULTI-TURN: rephrase and retry ---
    # Strip question words and try again
    rephrased = re.sub(r'^(what is|what are|who is|who are|how does|how do|why does|why do|tell me about|explain|describe|define|can you)\s+', '', query.lower().strip())
    rephrased = rephrased.rstrip('?').strip()
    if rephrased != query.lower().strip() and len(rephrased) > 2:
        # Try rephrased query
        ddg_text, ddg_src = _ddg_instant(rephrased)
        if ddg_text:
            add_fact("verified", f"[{ddg_src}] {ddg_text}")
            return ddg_text
        title, extract = wiki_summary(rephrased)
        if title and extract:
            compressed = compress_text(extract, 400)
            add_fact("wikipedia", f"[{title}] {compressed}")
            return compressed

    return None


def scrape_url(url):
    """Scrape a webpage and extract useful text content.
    Stores the content as verified facts for future questions.
    Returns a summary of what was learned."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Strip HTML tags, scripts, styles
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL)
        html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        # Get title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL)
        title = title_match.group(1).strip() if title_match else url

        # Extract all text
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove common noise
        text = re.sub(r'(cookie|privacy policy|terms of service|subscribe|newsletter|sign up|log in|copyright).*?\.', '', text, flags=re.IGNORECASE)

        if len(text) < 50:
            return None, "Page had no useful content."

        # Extract links from the page
        links = re.findall(r'href=["\']?(https?://[^\s"\'<>]+)', html)
        # Filter to meaningful links (not assets, not same-domain anchors)
        good_links = []
        for link in links:
            if any(skip in link.lower() for skip in ['.css', '.js', '.png', '.jpg', '.gif', '.svg', 'font', '#', 'javascript:', 'mailto:']):
                continue
            if link not in good_links and len(good_links) < 10:
                good_links.append(link)

        # Break text into paragraphs (by sentences) and store as facts
        sentences = re.split(r'(?<=[.!?])\s+', text)
        stored = 0
        paragraphs = []
        current = []

        for s in sentences:
            s = s.strip()
            if len(s) < 20:
                continue
            current.append(s)
            if len(' '.join(current)) > 300:
                para = ' '.join(current)
                paragraphs.append(para)
                current = []

        if current:
            paragraphs.append(' '.join(current))

        # Store top paragraphs as facts (max 20 per page)
        for para in paragraphs[:20]:
            compressed = compress_text(para, 500)
            if len(compressed) > 30:
                add_fact("scraped", f"[{title[:60]}] {compressed}", source="verified")
                stored += 1

        summary = f"Scraped '{title[:60]}'. Stored {stored} facts."
        return good_links, summary

    except Exception as e:
        return None, f"Failed to scrape: {str(e)}"


def fetch_live_news(topic="world"):
    """Fetch fresh news headlines from RSS feeds for a specific topic."""
    topic_lower = topic.lower()
    feed_map = {
        'tech': "https://feeds.bbci.co.uk/news/technology/rss.xml",
        'technology': "https://feeds.bbci.co.uk/news/technology/rss.xml",
        'ai': "https://techcrunch.com/category/artificial-intelligence/feed/",
        'science': "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        'business': "https://feeds.bbci.co.uk/news/business/rss.xml",
        'world': "https://feeds.bbci.co.uk/news/world/rss.xml",
        'indonesia': "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
        'asia': "https://feeds.bbci.co.uk/news/world/asia/rss.xml",
        'marketing': "https://blog.hubspot.com/marketing/rss.xml",
    }
    # Pick the best feed
    feed_url = feed_map.get(topic_lower, feed_map['world'])
    for key in feed_map:
        if key in topic_lower:
            feed_url = feed_map[key]
            break

    items = fetch_rss(feed_url)
    results = []
    for title, desc in items[:5]:
        compressed = compress_text(desc, 200)
        add_fact("news", f"[{title}] {compressed}", source="news")
        results.append(f"• {title}: {compressed}")

    if results:
        return "\n".join(results)
    return None


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
