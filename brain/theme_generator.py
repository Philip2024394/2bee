"""
2B Theme Generator — Auto-generates product themes and queues for review.
Philip reviews daily: accept → goes live, reject + comment → 2B regenerates.
"""

import os
import json
import time
import re
import urllib.request
import urllib.parse
import threading
from datetime import datetime
from brain.memory import add_fact, search_facts, get_db

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "theme_queue.json")
SUPABASE_URL = "https://fjvafjkzvygkhiwjuvla.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZqdmFmamt6dnlna2hpd2p1dmxhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMDk0NDEsImV4cCI6MjA5MDY4NTQ0MX0.UoXfKznY9gAEqZDSTegDjIfYAeAeFg6Eh1D40Hoe2KM"

# Categories and their style prompts
CATEGORIES = {
    "clothing": {"accent": "#4A90D9", "prompt": "Clothing store display folded shirts jeans sneakers on dark wooden shelves warm lighting"},
    "shoes": {"accent": "#8B4513", "prompt": "Luxury sneaker shoe collection on dark display shelf dramatic spotlight"},
    "handbags": {"accent": "#8B4513", "prompt": "Designer handbags leather bags arranged on dark marble surface elegant lighting"},
    "hijab": {"accent": "#9B59B6", "prompt": "Beautiful hijab scarves accessories arranged on dark velvet display elegant"},
    "batik": {"accent": "#B8860B", "prompt": "Indonesian batik fabric rolls clothing displayed on dark wood table traditional patterns"},
    "electronics": {"accent": "#2ECC71", "prompt": "Electronics gadgets smartphones earbuds smartwatch on dark reflective surface neon accents"},
    "computer_repair": {"accent": "#1E90FF", "prompt": "Computer repair tools motherboard components on dark workbench technical"},
    "phone_cases": {"accent": "#3498DB", "prompt": "Phone cases colorful protective cases arranged on dark table modern"},
    "beauty": {"accent": "#E91E90", "prompt": "Beauty products serums moisturizers on marble surface flowers dark background"},
    "cosmetics": {"accent": "#C0392B", "prompt": "Makeup cosmetics lipsticks palettes brushes on dark velvet luxury display"},
    "perfume": {"accent": "#8E44AD", "prompt": "Luxury perfume bottles on dark reflective surface smoke golden light"},
    "home_decor": {"accent": "#D4A373", "prompt": "Home decor items candles vases cushions on wooden shelf cozy dark interior"},
    "furniture": {"accent": "#795548", "prompt": "Modern minimalist furniture chair side table dark room accent lighting"},
    "kitchenware": {"accent": "#FF6B35", "prompt": "Kitchen utensils pots pans wooden cutting boards on dark counter top"},
    "packaging": {"accent": "#795548", "prompt": "Product packaging boxes bags on dark surface professional branding"},
    "handicrafts": {"accent": "#e8992c", "prompt": "Handmade crafts woven baskets pottery ceramics on rustic dark wood table"},
    "jewelry": {"accent": "#FFD700", "prompt": "Handmade jewelry rings necklaces bracelets on dark velvet display gold accents"},
    "candles": {"accent": "#e8b92c", "prompt": "Artisan scented candles decorative jars on dark wooden shelf warm glow"},
    "sports": {"accent": "#27AE60", "prompt": "Sports equipment sneakers basketball dumbbells water bottle on dark gym floor"},
    "baby_clothes": {"accent": "#FF69B4", "prompt": "Baby clothes toys accessories on soft dark background pastel colors"},
    "school": {"accent": "#4A90D9", "prompt": "School accessories notebooks pens backpack on dark desk organized"},
    "motorbike_tyres": {"accent": "#dc2626", "prompt": "Motorbike tyres wheels on dark garage floor industrial"},
    "seat_covers": {"accent": "#795548", "prompt": "Car seat covers leather fabric on dark display professional"},
    "automotive": {"accent": "#dc2626", "prompt": "Car accessories parts tools detailing products on dark garage workbench"},
    "pet_supplies": {"accent": "#6b8a0f", "prompt": "Pet supplies toys leashes treats accessories on dark surface cute"},
    "grocery": {"accent": "#c15d15", "prompt": "Packaged snacks chips cookies grocery items on dark shelves store"},
    "tobacco": {"accent": "#8B0000", "prompt": "Tobacco products cigars on dark wooden surface vintage"},
    "herbal": {"accent": "#4d8a0f", "prompt": "Traditional herbal medicine jamu bottles spices natural remedies dark wood"},
    "digital": {"accent": "#8E44AD", "prompt": "Digital products gift cards software boxes futuristic dark desk neon glow"},
    "general": {"accent": "#4A90D9", "prompt": "Mixed merchandise products variety items on dark display table organized"},
}

# Quality suffix — 80% bright modern, 20% dark moody
# NO prices, NO discounts, NO brand names. Indonesian text for Indonesia market.
QUALITY_SUFFIX_BRIGHT = ", fresh modern bright design, clean professional layout, vibrant colors, product clearly visible, high detail, modern 2026 style, 4k quality, portrait orientation, brand-neutral, NO prices NO discounts displayed, Indonesian language text Bahasa Indonesia, lifestyle product photography"
QUALITY_SUFFIX_DARK = ", dark moody background, professional product photography, cinematic lighting, high detail, modern 2026 style, 4k quality, portrait orientation, NO prices NO discounts displayed, Indonesian language text Bahasa Indonesia"

# Layout variations — rotate through all 4 types
LAYOUT_TYPES = [
    "products centered or slightly right, clean background",
    "split layout with product image on right and Indonesian text on left side",
    "hero header with Indonesian slogan at top like Koleksi Terbaru and product below",
    "call to action layout with product and Indonesian CTA text like Belanja Sekarang",
]


def load_queue():
    """Load the theme review queue."""
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r") as f:
            return json.load(f)
    return {"pending": [], "accepted": [], "rejected": [], "stats": {"generated": 0, "accepted": 0, "rejected": 0}}


def save_queue(data):
    """Save the theme review queue."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)


def generate_theme_image(category, variation=0, reject_comment=None):
    """Generate a theme image for a category using Pollinations."""
    cat_data = CATEGORIES.get(category, CATEGORIES["general"])
    base_prompt = cat_data["prompt"]

    # If regenerating after rejection, improve the prompt
    if reject_comment:
        base_prompt = f"{base_prompt}, {reject_comment}"

    # Rotate through layout types
    layout = LAYOUT_TYPES[variation % len(LAYOUT_TYPES)]
    base_prompt += f", {layout}"

    # 80% bright modern, 20% dark moody
    import random as _rnd
    suffix = QUALITY_SUFFIX_BRIGHT if _rnd.random() < 0.8 else QUALITY_SUFFIX_DARK
    full_prompt = base_prompt + suffix
    seed = int(time.time()) + variation

    try:
        encoded = urllib.parse.quote(full_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=480&height=854&nologo=true&seed={seed}"

        req = urllib.request.Request(url, headers={"User-Agent": "2B-AI/1.0"})
        # Pollinations can take 15-30 seconds to generate
        with urllib.request.urlopen(req, timeout=90) as resp:
            img_data = resp.read()

        if len(img_data) < 1000:
            return None

        # Save locally first
        local_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "theme_candidates")
        os.makedirs(local_dir, exist_ok=True)
        filename = f"theme-{category}-{int(time.time())}-v{variation}.png"
        local_path = os.path.join(local_dir, filename)
        with open(local_path, "wb") as f:
            f.write(img_data)

        return {
            "id": f"{category}-{int(time.time())}-v{variation}",
            "category": category,
            "accent": cat_data["accent"],
            "prompt": full_prompt,
            "local_path": local_path,
            "filename": filename,
            "size": len(img_data),
            "generated_at": datetime.now().isoformat(),
            "status": "pending",
            "reject_comment": None,
            "supabase_url": None,
        }
    except Exception as e:
        print(f"[ThemeGen] Failed to generate {category}: {e}")
        return None


def generate_batch(category, count=3, reject_comment=None):
    """Generate multiple theme candidates for a category."""
    results = []
    for i in range(count):
        theme = generate_theme_image(category, variation=i, reject_comment=reject_comment)
        if theme:
            results.append(theme)
        time.sleep(5)  # spacing between Pollinations requests to avoid rate limiting
    return results


def accept_theme(theme_id):
    """Accept a theme — upload to Supabase and mark as live."""
    queue = load_queue()

    theme = None
    for t in queue["pending"]:
        if t["id"] == theme_id:
            theme = t
            break

    if not theme:
        return {"error": "Theme not found in pending queue"}

    # Upload to Supabase Storage
    try:
        with open(theme["local_path"], "rb") as f:
            img_data = f.read()

        upload_path = f"themes/{theme['filename']}"
        req = urllib.request.Request(
            f"{SUPABASE_URL}/storage/v1/object/assets/{upload_path}",
            data=img_data,
            headers={
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "image/png",
                "x-upsert": "true",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()

        supabase_url = f"{SUPABASE_URL}/storage/v1/object/public/assets/{upload_path}"
        theme["supabase_url"] = supabase_url
        theme["status"] = "accepted"
        theme["accepted_at"] = datetime.now().isoformat()

        # Move from pending to accepted
        queue["pending"] = [t for t in queue["pending"] if t["id"] != theme_id]
        queue["accepted"].append(theme)
        queue["stats"]["accepted"] += 1
        save_queue(queue)

        # Store in 2B memory
        add_fact("accepted_theme", f"Accepted theme for {theme['category']}: {supabase_url} | Accent: {theme['accent']}", source="user_taught")

        return {"success": True, "url": supabase_url, "category": theme["category"], "accent": theme["accent"]}

    except Exception as e:
        return {"error": str(e)}


def reject_theme(theme_id, comment=""):
    """Reject a theme with feedback — 2B learns and regenerates."""
    queue = load_queue()

    theme = None
    for t in queue["pending"]:
        if t["id"] == theme_id:
            theme = t
            break

    if not theme:
        return {"error": "Theme not found"}

    theme["status"] = "rejected"
    theme["reject_comment"] = comment
    theme["rejected_at"] = datetime.now().isoformat()

    queue["pending"] = [t for t in queue["pending"] if t["id"] != theme_id]
    queue["rejected"].append(theme)
    queue["stats"]["rejected"] += 1
    save_queue(queue)

    # Store rejection feedback in 2B memory
    add_fact("theme_feedback", f"REJECTED theme for {theme['category']}: {comment}. Avoid this style.", source="user_taught")

    # Auto-regenerate with the feedback
    new_themes = generate_batch(theme["category"], count=2, reject_comment=comment)
    for nt in new_themes:
        queue["pending"].append(nt)
        queue["stats"]["generated"] += 1
    save_queue(queue)

    return {"success": True, "regenerated": len(new_themes), "comment": comment}


def get_pending():
    """Get all pending themes for review."""
    queue = load_queue()
    return queue["pending"]


def get_stats():
    """Get theme generation stats."""
    queue = load_queue()
    return queue["stats"]


def auto_generate_check():
    """Check which categories need more themes and generate."""
    queue = load_queue()
    pending_cats = {}
    accepted_cats = {}

    for t in queue["pending"]:
        pending_cats[t["category"]] = pending_cats.get(t["category"], 0) + 1
    for t in queue["accepted"]:
        accepted_cats[t["category"]] = accepted_cats.get(t["category"], 0) + 1

    generated = 0
    for category in CATEGORIES:
        total = pending_cats.get(category, 0) + accepted_cats.get(category, 0)
        if total < 30 and pending_cats.get(category, 0) < 3:
            # Generate 2 candidates for this category
            themes = generate_batch(category, count=2)
            for t in themes:
                queue["pending"].append(t)
                queue["stats"]["generated"] += 1
                generated += 1
            if generated >= 6:  # max 6 per cycle
                break
            time.sleep(3)

    save_queue(queue)
    return generated
