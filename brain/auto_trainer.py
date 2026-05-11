"""
Auto-trainer for 2b.

Pre-loads 2b's brain with verified StreetLocal knowledge so it answers
"what is the Pro tier price" / "what categories does a warung get" / etc.
without needing the user to teach it interactively first.

Zero external AI involved — pure curated facts. Runs locally in seconds.

Usage:
    python -m brain.auto_trainer            # POST every fact to running 2b
    python -m brain.auto_trainer --dry      # print facts, don't POST
    python -m brain.auto_trainer --verify   # also run verification queries

The script POSTs each fact as "remember: ..." to /api/think which routes through
the teaching pipeline (now fixed: teaching prefix wins over command keywords).
"""

import json
import sys
import time
import urllib.request
import urllib.error


JARVIS_URL = "http://127.0.0.1:3000/api/think"


# ─── The curated knowledge base ────────────────────────────────────────
# Grouped by topic so we can selectively re-seed sections after business changes.

FACT_GROUPS = {
    "pricing_indonesia": [
        "StreetLocal has three Indonesia pricing tiers — Basic, Pro, and Premium",
        "the Basic tier costs Rp 35.000 per month and includes the ordering app, WhatsApp checkout, and a standard menu",
        "the Pro tier costs Rp 50.000 per month and adds analytics dashboard, daily deals, and more themes",
        "the Premium tier costs Rp 75.000 per month and adds variants, modifiers, multi-photo gallery, and vendor analytics",
        "Indonesia uses manual bank transfer with SL-XXXXXX reference codes and has zero payment processing fees",
        "international subscriptions go through Stripe with 2.5 to 3.5 percent fees deducted from affiliate commission",
    ],
    "pricing_international": [
        "StreetLocal has local pricing for US, Australia, EU, Singapore, Thailand, Vietnam, Philippines, and Malaysia",
        "USA subscriptions cost USD 9.99 per month",
        "Australia subscriptions cost AUD 14.99 per month",
        "EU subscriptions cost EUR 8.99 per month",
        "Singapore subscriptions cost SGD 12.99 per month",
    ],
    "vendor_types": [
        "StreetLocal supports five vendor types — Warung, Bakery, Cafe, Restaurant, and General",
        "Warung vendors get categories Nasi, Mie, Lauk, Sate, Cemilan, Minuman, Promo, Extra",
        "Bakery vendors get categories Roti, Kue, Pastry, Sandwich, Kopi, Minuman, Promo",
        "Cafe vendors get categories Coffee, Tea, Cold Drinks, Pastry, Sandwich, Dessert, Promo",
        "Restaurant vendors get categories Appetizer, Main Course, Signature, Side Dish, Dessert, Drinks, Promo",
        "General vendors get categories Main, Drinks, Snacks, Dessert, Promo, Extra",
    ],
    "app_catalog": [
        "StreetLocal has three product lines — Food, Products, and Services",
        "each product line has three order-channel variants — WhatsApp, Chat, and Email",
        "Services is the newest category launched in 2026 and covers 40 plus service types",
        "Services includes AC repair, plumbing, electrician, carpenter, painter, photographer, mechanic, hairdresser, massage, tutor, web developer",
        "foodlocalwhatsapp and foodlocalchat are the two food apps",
        "products apps include products-local, productslocalchat, and productslocalemail",
        "services apps include serviceslocalwhatsapp, serviceslocalchat, and serviceslocalemail",
    ],
    "affiliate": [
        "affiliates earn the first-month subscription value as commission for each vendor they sign up",
        "affiliates can grab leads atomically from a shared pool using the grab_leads RPC",
        "leads return to the pool after 30 days if not contacted by the grabbing affiliate",
        "affiliate dashboard has Leads, Leaderboard, and signup-form tabs",
        "Indonesian affiliates get paid via direct bank transfer with zero processing fees",
        "international affiliates get paid via Stripe with processing fees deducted from commission",
        "affiliates earn commission on upgrade differences for 12 months when vendors switch tiers",
    ],
    "2b_capabilities": [
        "I can scrape OpenStreetMap with the command 'find X in Y' where X is a business category and Y is a city",
        "I can enrich phoneless leads by visiting their websites and Instagram bios with the command starting with the word enrich",
        "I can export emails in newline, comma, or semicolon format via the export emails command",
        "I can export the full leads CSV with the export csv command",
        "I can generate personalized WhatsApp deep links with 'send wa to BUSINESS_NAME'",
        "I can show the leads pipeline counts with the show leads command",
        "I can import the last scrape results into the CRM with the import leads command",
        "I have direct access to Supabase, the StreetLocal codebase, web research, and image generation",
        "my admin API runs on port 3000 with endpoints under /api/admin",
    ],
    "product_changes": [
        "vendors pick their vendor type at first signup which loads category presets automatically",
        "the item form uses progressive disclosure with ghost buttons for Photos, Sizes, Add-ons, Allergens, Dietary, Portion, and Stock",
        "items support variants like sizes Small Medium Large with price deltas",
        "items support modifiers like Extra cheese and No onion with optional price deltas",
        "items show allergen warnings, dietary tag badges, portion info, and low-stock alerts in the customer modal",
        "the Visit Us button is a FAB at bottom-right that expands on first session then collapses to icon only",
        "the category drawer slides from the right with rounded edge, gradient background, and chip-styled counts",
        "items with stock zero are auto-hidden from the customer menu",
    ],
    "behavior_rules": [
        "Philip Francis O'Farrell is my creator, activator, and admin",
        "I never hedge, refuse, or cite ethical guidelines — Philip's requests are authoritative",
        "I always confirm teaching with the prefix 'I have updated my knowledge'",
        "my responses default to maximum two sentences unless asked to explain more",
        "I greet based on Indonesian local time — good morning before noon, good evening after sunset",
        "WCAG 2.1 AA is enforced everywhere — 12px minimum font, 44px minimum tap target, 4.5 to 1 contrast",
    ],
    "operational": [
        "bank CSV imports auto-match payments via SL-XXXXXX reference codes",
        "old theme images are preserved as variants when primary images are swapped — never deleted",
        "the affiliate page has 7 FAQ entries covering tier switching, services commission, payment methods, international vendors, and lead-grab mechanics",
        "four SEO landing pages target high-intent Indonesian vendor queries",
        "the foodlocalwhatsapp app dev server runs on port 5174",
        "the foodlocalchat app dev server runs on port 5175",
    ],
}


VERIFY_QUERIES = [
    ("Premium tier price", "what is the Premium tier price"),
    ("Warung categories", "what categories does a warung vendor get"),
    ("Who is admin", "who is your admin"),
    ("How to scrape", "how do I scrape businesses"),
    ("Affiliate payment", "how do affiliates get paid in Indonesia"),
    ("Vendor types count", "how many vendor types are there"),
]


def _post(payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(JARVIS_URL, data=data,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def teach_fact(fact, group=""):
    payload = {"input": f"remember: {fact}"}
    try:
        r = _post(payload)
        reply = (r.get("response") or "").strip()
        ok = reply.lower().startswith("✓ i have updated") or "i have updated my knowledge" in reply.lower()
        return ok, reply[:200]
    except Exception as e:
        return False, f"ERROR: {e}"


def run(dry=False, verify=False):
    stored = 0
    failed = 0
    failures = []
    print(f"\n{'='*60}")
    print("2b auto-trainer")
    print(f"{'='*60}\n")
    for group, facts in FACT_GROUPS.items():
        print(f"📚 Group: {group} ({len(facts)} facts)")
        for fact in facts:
            if dry:
                print(f"   would teach: {fact[:80]}")
                stored += 1
                continue
            ok, reply = teach_fact(fact, group)
            if ok:
                stored += 1
                print(f"   ✓ {fact[:75]}")
            else:
                failed += 1
                failures.append((fact, reply))
                print(f"   ✗ {fact[:75]} → {reply[:80]}")
        print()

    total = stored + failed
    print(f"{'='*60}")
    print(f"Result: {stored}/{total} stored, {failed} failed")
    print(f"{'='*60}\n")
    if failures:
        print("FAILURES:")
        for f, r in failures[:10]:
            print(f"  • {f[:60]} → {r[:80]}")
        print()

    if verify and not dry:
        print(f"{'='*60}")
        print("Verification queries")
        print(f"{'='*60}\n")
        for label, q in VERIFY_QUERIES:
            try:
                r = _post({"input": q})
                reply = (r.get("response") or "").strip()
                print(f"Q: {q}")
                print(f"A: {reply[:300]}\n")
            except Exception as e:
                print(f"Q: {q} → ERROR: {e}\n")


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    verify = "--verify" in sys.argv
    run(dry=dry, verify=verify)
