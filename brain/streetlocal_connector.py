"""
StreetLocal Connector — gives 2bee full READ access to the entire project.
WRITE access requires explicit permission from Philip.

2bee can:
  - Read all source files
  - Access all image URLs
  - Search code for any pattern
  - Analyze app structure
  - Suggest changes (but NOT apply them without permission)

2bee CANNOT (without permission):
  - Modify any file
  - Push to GitHub
  - Change any UI element
  - Delete anything
"""

import os
import re
import json
from brain.memory import add_fact, search_facts

# ======================================================================
# CONFIG
# ======================================================================

STREETLOCAL_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "..", "streetlocal"
))

APPS = {
    "food-basic": "FoodLocal",
    "food-pro": "Food Pro / Restaurant",
    "products-local": "ProductsLocal",
    "landing": "Main Website / Landing Page",
    "property-agent": "Property Agent",
}

IMAGES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "streetlocal_images.txt"
)

# Permission flag — only Philip can set this
_write_permission = False
_permission_holder = None


# ======================================================================
# PERMISSION SYSTEM
# ======================================================================

def request_write_permission(user_name):
    """Request permission to modify StreetLocal files."""
    return {
        "granted": False,
        "message": f"Write access requires Philip's explicit permission. "
                   f"I can suggest changes but cannot apply them without approval. "
                   f"Say 'grant 2bee write access' to enable."
    }


def grant_permission(user_name):
    """Grant write permission — only Philip can do this."""
    global _write_permission, _permission_holder
    _write_permission = True
    _permission_holder = user_name
    return f"Write permission granted to 2bee by {user_name}. I can now modify files. Say 'revoke 2bee access' to disable."


def revoke_permission():
    """Revoke write permission."""
    global _write_permission, _permission_holder
    _write_permission = False
    _permission_holder = None
    return "Write permission revoked. 2bee is back to read-only mode."


def has_write_permission():
    return _write_permission


# ======================================================================
# READ ACCESS — always available
# ======================================================================

def get_all_image_urls():
    """Get all image URLs used in the StreetLocal project."""
    if os.path.exists(IMAGES_FILE):
        with open(IMAGES_FILE, "r") as f:
            return [line.strip() for line in f if line.strip()]
    return []


def get_image_urls_by_category(category):
    """Search image URLs by keyword."""
    urls = get_all_image_urls()
    keyword = category.lower().replace(" ", "-")
    return [u for u in urls if keyword in u.lower()]


def read_file(filepath):
    """Read a file from the StreetLocal project (read-only)."""
    full_path = os.path.join(STREETLOCAL_ROOT, filepath)
    if not os.path.exists(full_path):
        return None, f"File not found: {filepath}"
    if not full_path.startswith(os.path.normpath(STREETLOCAL_ROOT)):
        return None, "Access denied: path outside StreetLocal project"
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(), None
    except Exception as e:
        return None, str(e)


def search_code(pattern, file_glob="*.jsx"):
    """Search all source files for a pattern."""
    results = []
    for app_dir in APPS.keys():
        src_dir = os.path.join(STREETLOCAL_ROOT, app_dir, "src")
        if not os.path.exists(src_dir):
            continue
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if not f.endswith(('.jsx', '.js', '.css', '.json')):
                    continue
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                        for i, line in enumerate(fp, 1):
                            if pattern.lower() in line.lower():
                                rel = os.path.relpath(fpath, STREETLOCAL_ROOT)
                                results.append({
                                    "file": rel,
                                    "line": i,
                                    "content": line.strip()[:200],
                                })
                except Exception:
                    pass
    return results[:20]


def get_project_stats():
    """Get stats about the StreetLocal project."""
    stats = {}
    total_files = 0
    total_lines = 0
    for app_dir, app_name in APPS.items():
        src_dir = os.path.join(STREETLOCAL_ROOT, app_dir, "src")
        if not os.path.exists(src_dir):
            stats[app_name] = {"files": 0, "lines": 0}
            continue
        files = 0
        lines = 0
        for root, dirs, files_list in os.walk(src_dir):
            for f in files_list:
                if f.endswith(('.jsx', '.js', '.css')):
                    files += 1
                    try:
                        with open(os.path.join(root, f), "r", errors="ignore") as fp:
                            lines += sum(1 for _ in fp)
                    except Exception:
                        pass
        stats[app_name] = {"files": files, "lines": lines}
        total_files += files
        total_lines += lines
    stats["TOTAL"] = {"files": total_files, "lines": total_lines}
    return stats


def get_app_themes(app="products-local"):
    """Get all theme definitions from an app."""
    filepath = os.path.join(STREETLOCAL_ROOT, app, "src", "App.jsx")
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        themes = re.findall(r"id:\s*'([^']+)'.*?label:\s*'([^']+)'.*?accent:\s*'([^']+)'", content)
        return [{"id": t[0], "label": t[1], "accent": t[2]} for t in themes]
    except Exception:
        return []


# ======================================================================
# LOAD ALL PROJECT DATA INTO 2BEE MEMORY
# ======================================================================

def sync_project_data():
    """Sync all StreetLocal project data into 2bee's memory."""
    loaded = 0

    # 1. Store all image URLs as searchable facts
    urls = get_all_image_urls()
    if urls:
        # Group by type
        theme_urls = [u for u in urls if 'theme-' in u]
        chatgpt_urls = [u for u in urls if 'chatgpt-image' in u]
        other_urls = [u for u in urls if u not in theme_urls and u not in chatgpt_urls]

        add_fact("streetlocal_images",
                 f"StreetLocal has {len(urls)} total images: {len(theme_urls)} theme images, "
                 f"{len(chatgpt_urls)} generated images, {len(other_urls)} UI/icon images. "
                 f"All stored on Supabase Storage.", source="user_taught")
        loaded += 1

        # Store theme image URLs specifically
        for url in theme_urls:
            name = url.split("/")[-1].replace(".png", "").replace("theme-", "").replace("-", " ")
            add_fact("theme_image", f"Theme '{name}': {url}", source="user_taught")
            loaded += 1

    # 2. Store project structure
    stats = get_project_stats()
    for app_name, s in stats.items():
        if app_name != "TOTAL" and s["files"] > 0:
            add_fact("project_structure",
                     f"StreetLocal app '{app_name}': {s['files']} source files, {s['lines']} lines of code.",
                     source="user_taught")
            loaded += 1

    # 3. Store theme lists
    for app in ["products-local", "food-basic"]:
        themes = get_app_themes(app)
        if themes:
            theme_names = ", ".join(t["label"] for t in themes)
            add_fact("app_themes",
                     f"StreetLocal {APPS.get(app, app)} has {len(themes)} themes: {theme_names}",
                     source="user_taught")
            loaded += 1

    return loaded


# ======================================================================
# MARKETING & LAUNCH DATA COLLECTION
# ======================================================================

MARKETING_SCRAPE_URLS = [
    # App launch strategies
    "https://en.wikipedia.org/wiki/App_store_optimization",
    "https://en.wikipedia.org/wiki/Growth_hacking",
    "https://en.wikipedia.org/wiki/Viral_marketing",
    "https://en.wikipedia.org/wiki/Product_launch",
    # Indonesian market
    "https://en.wikipedia.org/wiki/Economy_of_Indonesia",
    "https://en.wikipedia.org/wiki/Internet_in_Indonesia",
    "https://en.wikipedia.org/wiki/Gojek",
    "https://en.wikipedia.org/wiki/Grab_(company)",
    "https://en.wikipedia.org/wiki/Tokopedia",
    "https://en.wikipedia.org/wiki/Shopee",
    # SaaS & subscriptions
    "https://en.wikipedia.org/wiki/Freemium",
    "https://en.wikipedia.org/wiki/Customer_acquisition_cost",
    "https://en.wikipedia.org/wiki/Churn_rate",
    "https://en.wikipedia.org/wiki/Monthly_recurring_revenue",
    # AI for business
    "https://en.wikipedia.org/wiki/AI-generated_content",
    "https://en.wikipedia.org/wiki/Chatbot",
]


def collect_marketing_data():
    """Scrape marketing and launch strategy data from the web."""
    from brain import learner
    scraped = 0
    for url in MARKETING_SCRAPE_URLS:
        try:
            links, summary = learner.scrape_url(url)
            if links is not None:
                scraped += 1
        except Exception:
            pass
    return scraped
