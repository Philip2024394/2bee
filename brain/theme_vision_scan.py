"""
Theme Vision Scanner — 2B looks at every theme image and learns the design.
Run after LLaVA is downloaded: python -m brain.theme_vision_scan
"""

import os
import time
from brain.memory import init, add_fact, search_facts
from brain.vision import analyze_image_url, is_available

SUPABASE_BASE = "https://fjvafjkzvygkhiwjuvla.supabase.co/storage/v1/object/public/assets/"

# All real theme image URLs
THEME_IMAGES = [
    # ProductsLocal
    ("shoes", "theme-shoes.png"),
    ("handbags", "theme-handbags.png"),
    ("handbags_v2", "theme-handbags-v2.png"),
    ("handbags_v3", "theme-handbags-v3.png"),
    ("handbags_v4", "theme-handbags-v4.png"),
    ("handbags_v5", "theme-handbags-v5.png"),
    ("handbags_v6", "theme-handbags-v6.png"),
    ("hijab", "theme-hijab.png"),
    ("batik", "theme-batik.png"),
    ("electronics", "theme-electrical.png"),
    ("computer_repair", "theme-computer-repair.png"),
    ("phone_cases", "theme-phone-cases.png"),
    ("phone_cases_v2", "theme-phone-cases-v2.png"),
    ("beauty", "theme-beauty-products.png"),
    ("cosmetics", "theme-cosmetics.png"),
    ("perfume", "theme-perfume.png"),
    ("home_furniture", "theme-home-furniture.png"),
    ("jewelry", "theme-jewelry.png"),
    ("jewelry_v2", "theme-jewelry-v2.png"),
    ("candles", "theme-candles.png"),
    ("baby_clothes", "theme-baby-clothes.png"),
    ("toys", "theme-childrens-toys.png"),
    ("school", "theme-school-accessories.png"),
    ("motorbike_tyres", "theme-motorbike-tyres.png"),
    ("seat_covers", "theme-seat-covers.png"),
    ("tobacco", "theme-tobacco.png"),
    ("pet_supplies", "theme-pet-supplies.png"),
    ("packaging", "theme-packaging.png"),
    ("raincoats", "theme-raincoats.png"),
    ("running_footwear", "theme-running-footwear.png"),
    ("bicycle", "theme-bicycle.png"),
]


def scan_all():
    """Have 2B look at every theme image and describe what she sees."""
    init()

    if not is_available():
        print("LLaVA not available. Run: ollama pull llava")
        return 0

    scanned = 0
    for name, filename in THEME_IMAGES:
        # Skip if already analyzed
        existing = search_facts(f"vision_scan_{name}")
        if existing:
            print(f"  Skip {name} (already scanned)")
            continue

        url = SUPABASE_BASE + filename
        print(f"  Scanning {name}...")

        question = f"""Analyze this product theme image for a mobile app ({name} category).
Describe in detail:
1. Layout composition (where products are, text placement)
2. Color palette (dominant, accent, background)
3. Products shown and how displayed
4. Text visible (language, content)
5. Overall style (modern/classic, bright/dark, clean/busy)
6. Quality rating 1-10
Keep under 150 words."""

        result, err = analyze_image_url(url, question)
        if result:
            add_fact(f"vision_scan_{name}", f"[2B Vision] {name} theme: {result}", source="user_taught")
            scanned += 1
            print(f"    OK: {result[:80]}...")
        else:
            print(f"    FAIL: {err}")

        time.sleep(2)  # Don't overload GPU

    print(f"\nScanned {scanned} themes. 2B can now see your design style.")
    return scanned


if __name__ == "__main__":
    scan_all()
