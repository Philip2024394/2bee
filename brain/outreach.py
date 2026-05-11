"""
Lead-gen + outreach CRM for StreetLocal.

Pulls businesses from OpenStreetMap via the Overpass API (free, no key, no
ToS issues — OSM data is CC-BY-SA) and stores them as leads in Supabase.
Generates pre-filled WhatsApp outreach links so the admin can message
one vendor at a time with a personalized message — no bulk spray.

Why OSM not Google Maps:
- Free, no API key, no quota
- CC-BY-SA — legal to use as long as we attribute (we do, in the lead record)
- Returns the same phone/website/address fields for Indonesian businesses
"""

import json
import urllib.request
import urllib.parse
from datetime import datetime
from brain import supabase_connector as sb


# Overpass API endpoint. Two public mirrors — fallback if one is down.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


# Category keyword → OSM tag mapping. OSM uses `amenity`, `shop`, `tourism`,
# `craft`, `office` etc. We translate common business types into these.
CATEGORY_MAP = {
    # Food
    "warung": ("amenity", "restaurant"),
    "restaurant": ("amenity", "restaurant"),
    "cafe": ("amenity", "cafe"),
    "coffee": ("amenity", "cafe"),
    "food": ("amenity", "restaurant"),
    "bakery": ("shop", "bakery"),
    "fast food": ("amenity", "fast_food"),
    "bar": ("amenity", "bar"),
    "ice cream": ("amenity", "ice_cream"),
    # Products
    "clothing": ("shop", "clothes"),
    "clothes": ("shop", "clothes"),
    "shoes": ("shop", "shoes"),
    "electronics": ("shop", "electronics"),
    "phone": ("shop", "mobile_phone"),
    "jewelry": ("shop", "jewelry"),
    "books": ("shop", "books"),
    "convenience": ("shop", "convenience"),
    "supermarket": ("shop", "supermarket"),
    "bicycle": ("shop", "bicycle"),
    "motorbike": ("shop", "motorcycle"),
    "florist": ("shop", "florist"),
    # Services
    "salon": ("shop", "hairdresser"),
    "hairdresser": ("shop", "hairdresser"),
    "barber": ("shop", "hairdresser"),
    "beauty": ("shop", "beauty"),
    "massage": ("shop", "massage"),
    "spa": ("leisure", "spa"),
    "tattoo": ("shop", "tattoo"),
    "cleaning": ("shop", "dry_cleaning"),
    "laundry": ("shop", "laundry"),
    "mechanic": ("shop", "car_repair"),
    "car repair": ("shop", "car_repair"),
    "car wash": ("amenity", "car_wash"),
    "carpenter": ("craft", "carpenter"),
    "tailor": ("shop", "tailor"),
    "photographer": ("shop", "photo"),
    "doctor": ("amenity", "doctor"),
    "dentist": ("amenity", "dentist"),
    "pharmacy": ("amenity", "pharmacy"),
    "school": ("amenity", "school"),
    "language school": ("amenity", "language_school"),
    "music": ("amenity", "music_school"),
    "gym": ("leisure", "fitness_centre"),
    "yoga": ("leisure", "fitness_centre"),
}


def _resolve_category(keyword):
    """Map a user-typed keyword to an OSM tag pair. Returns (tag, value) or None."""
    k = keyword.lower().strip()
    if k in CATEGORY_MAP:
        return CATEGORY_MAP[k]
    for key, tag in CATEGORY_MAP.items():
        if key in k or k in key:
            return tag
    return None


def _geocode_city(city, country=None):
    """Resolve 'Yogyakarta' (+ optional country) to a bounding box via Nominatim.
    Free, public, attribution-only. Returns (south, west, north, east) or None."""
    q = city
    if country:
        q = f"{city}, {country}"
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": q, "format": "json", "limit": 1,
    })
    req = urllib.request.Request(url, headers={"User-Agent": "2bee/1.0 (streetlocal lead-gen)"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=sb._SSL_CTX) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data:
            return None
        b = data[0].get("boundingbox")
        if not b or len(b) != 4:
            return None
        # Nominatim returns [south, north, west, east] as strings
        south, north, west, east = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        return (south, west, north, east)
    except Exception:
        return None


def find_businesses(keyword, city, country=None, limit=50):
    """Query Overpass for businesses matching `keyword` inside `city`.
    Returns a list of dicts with name, type, address, phone, website, source_id."""
    cat = _resolve_category(keyword)
    if not cat:
        return {"error": f"Unknown category '{keyword}'. Known: {', '.join(sorted(CATEGORY_MAP.keys())[:15])}..."}
    bbox = _geocode_city(city, country)
    if not bbox:
        return {"error": f"Could not locate '{city}'. Try a full name like 'Yogyakarta, Indonesia'."}
    south, west, north, east = bbox
    tag, value = cat
    # Overpass QL. Look for nodes + ways + relations with the tag inside the bbox.
    # Only fetch records that have a name (otherwise they're not useful as leads).
    query = f"""
    [out:json][timeout:25];
    (
      node["{tag}"="{value}"]["name"]({south},{west},{north},{east});
      way["{tag}"="{value}"]["name"]({south},{west},{north},{east});
      relation["{tag}"="{value}"]["name"]({south},{west},{north},{east});
    );
    out center {limit};
    """
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    last_err = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            req = urllib.request.Request(endpoint, data=body, headers={
                "User-Agent": "2bee/1.0 (streetlocal lead-gen)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=30, context=sb._SSL_CTX) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except Exception as e:
            last_err = e
            continue
    else:
        return {"error": f"Overpass API unreachable: {last_err}"}

    elements = data.get("elements", [])
    results = []
    for el in elements[:limit]:
        tags = el.get("tags") or {}
        name = tags.get("name", "").strip()
        if not name:
            continue
        phone = (tags.get("phone") or tags.get("contact:phone") or "").strip()
        whatsapp = (tags.get("contact:whatsapp") or tags.get("whatsapp") or "").strip()
        website = (tags.get("website") or tags.get("contact:website") or "").strip()
        # Address components
        addr_parts = []
        for k in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city", "addr:postcode"):
            v = tags.get(k)
            if v:
                addr_parts.append(v)
        address = ", ".join(addr_parts) if addr_parts else tags.get("addr:full", "")
        results.append({
            "source_id": f"{el.get('type','?')}/{el.get('id','?')}",
            "business_name": name,
            "business_type": value,
            "phone": phone,
            "whatsapp": whatsapp,
            "website": website,
            "address": address,
            "city": city,
            "country": country or "",
            "source": "osm",
            "source_url": f"https://www.openstreetmap.org/{el.get('type','node')}/{el.get('id','')}",
        })
    return {"results": results, "total": len(results), "category": f"{tag}={value}", "city": city}


def import_leads(results):
    """Insert OSM results into outreach_leads, skipping duplicates by phone or
    (source, source_id). Returns counts: inserted / skipped / error."""
    if not results:
        return {"inserted": 0, "skipped": 0, "errors": 0}
    inserted = 0
    skipped = 0
    errors = 0
    for r in results:
        # Build a single SQL INSERT with ON CONFLICT.
        def esc(s):
            return (s or "").replace("'", "''")
        sql = f"""
        INSERT INTO outreach_leads (business_name, business_type, country, city, address, phone, whatsapp, website, source, source_url, source_id, target_app)
        VALUES ('{esc(r['business_name'])}', '{esc(r['business_type'])}', '{esc(r['country'])}', '{esc(r['city'])}', '{esc(r['address'])}', NULLIF('{esc(r['phone'])}', ''), NULLIF('{esc(r['whatsapp'])}', ''), NULLIF('{esc(r['website'])}', ''), '{esc(r['source'])}', '{esc(r['source_url'])}', '{esc(r['source_id'])}', {f"'{_guess_target_app(r['business_type'])}'" if _guess_target_app(r['business_type']) else 'NULL'})
        ON CONFLICT DO NOTHING
        RETURNING id;
        """
        try:
            res = sb._management_query(sql)
            if res:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            errors += 1
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def _guess_target_app(business_type):
    """Suggest which StreetLocal app fits a given OSM business type."""
    food = {"restaurant", "cafe", "fast_food", "bar", "ice_cream", "bakery"}
    services = {"hairdresser", "beauty", "massage", "spa", "tattoo", "dry_cleaning", "laundry",
                "car_repair", "car_wash", "carpenter", "tailor", "photo", "doctor", "dentist",
                "language_school", "music_school", "fitness_centre"}
    products = {"clothes", "shoes", "electronics", "mobile_phone", "jewelry", "books",
                "convenience", "supermarket", "bicycle", "motorcycle", "florist"}
    if business_type in food:
        return "foodlocal"
    if business_type in services:
        return "serviceslocal"
    if business_type in products:
        return "productslocal"
    return None


# ─── CRM operations ──────────────────────────────────────────────────────

def list_leads(status=None, country=None, city=None, limit=200):
    """List leads with optional filters."""
    params = {
        "select": "id,business_name,business_type,country,city,phone,whatsapp,website,address,source,status,target_app,last_contacted_at,created_at",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if status:
        params["status"] = f"eq.{status}"
    if country:
        params["country"] = f"eq.{country}"
    if city:
        params["city"] = f"eq.{city}"
    return sb._rest_get("outreach_leads", params)


def get_lead_stats():
    """Lead pipeline counts by status."""
    rows = sb._rest_get("outreach_leads", {"select": "status"})
    counts = {}
    for r in rows:
        s = r.get("status") or "new"
        counts[s] = counts.get(s, 0) + 1
    return counts


def update_lead_status(lead_id, status, note=None):
    """Move a lead to a new status. Optionally log a note as an internal interaction."""
    sql = f"UPDATE outreach_leads SET status = '{status}', updated_at = NOW() WHERE id = '{lead_id}' RETURNING id, business_name, status;"
    res = sb._management_query(sql)
    if note:
        log_interaction(lead_id, "note", "internal", note)
    return res[0] if res else None


def log_interaction(lead_id, channel, direction, message, template_id=None):
    """Record an outreach event (sent WA, got reply, made a call, internal note)."""
    msg = (message or "").replace("'", "''")
    tpl = f"'{template_id}'" if template_id else "NULL"
    sql = f"""
    INSERT INTO outreach_interactions (lead_id, channel, direction, message, template_id, created_by)
    VALUES ('{lead_id}', '{channel}', '{direction}', '{msg}', {tpl}, 'admin')
    RETURNING id;
    """
    # Also bump last_contacted_at on the lead if direction is outbound
    if direction == "out":
        sb._management_query(f"UPDATE outreach_leads SET last_contacted_at = NOW(), status = CASE WHEN status = 'new' THEN 'contacted' ELSE status END WHERE id = '{lead_id}';")
    return sb._management_query(sql)


# ─── WhatsApp outreach templates ────────────────────────────────────────

WA_TEMPLATES = {
    "foodlocal_intro_id": (
        "Halo {name}! Saya dari StreetLocal — kami buat aplikasi pemesanan untuk warung & restoran. "
        "Tidak ada komisi seperti GoFood. Pelanggan pesan langsung lewat WhatsApp kamu. Hanya Rp 35.000/bulan. "
        "Mau lihat demonya? 🍜"
    ),
    "foodlocal_intro_en": (
        "Hi {name}! I'm from StreetLocal — we build branded ordering apps for restaurants and warung. "
        "Zero commission (unlike GoFood/GrabFood). Customers order straight to your WhatsApp. Rp 35,000/month flat. "
        "Want to see a demo?"
    ),
    "productslocal_intro_id": (
        "Halo {name}! Saya dari StreetLocal — kami buat aplikasi toko online untuk bisnis seperti kamu. "
        "Pelanggan order lewat WhatsApp, kamu simpan 100% pendapatan. Rp 35.000/bulan. Mau lihat demonya?"
    ),
    "serviceslocal_intro_id": (
        "Halo {name}! Saya dari StreetLocal — kami buat aplikasi booking untuk jasa seperti yang kamu tawarkan. "
        "Pelanggan booking via WhatsApp, kamu simpan 100% pendapatan. Rp 35.000/bulan. Mau lihat demonya?"
    ),
    "followup_id": (
        "Halo {name}, follow-up dari pesan sebelumnya. Tertarik untuk lihat aplikasi StreetLocal? "
        "Bisa diskusi via WA atau call kapan saja yang nyaman."
    ),
}


def build_whatsapp_link(lead, template_id=None):
    """Generate a wa.me URL with a personalized pre-filled message."""
    phone = (lead.get("whatsapp") or lead.get("phone") or "").strip()
    if not phone:
        return None
    # Strip non-digits and ensure Indonesian numbers have the country code.
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("0"):
        digits = "62" + digits[1:]  # Indonesia
    if not template_id:
        target = lead.get("target_app", "foodlocal")
        template_id = f"{target}_intro_id"
    template = WA_TEMPLATES.get(template_id) or WA_TEMPLATES["foodlocal_intro_id"]
    # Use first name only.
    name = (lead.get("business_name") or "").split()[0] if lead.get("business_name") else "Bapak/Ibu"
    text = template.format(name=name)
    return {
        "url": f"https://wa.me/{digits}?text={urllib.parse.quote(text)}",
        "phone": digits,
        "message_preview": text,
        "template_id": template_id,
    }


# ─── Display formatters (for 2bee chat) ─────────────────────────────────

def format_business_list(results):
    if isinstance(results, dict) and results.get("error"):
        return f"⚠️ {results['error']}"
    rows = results.get("results") if isinstance(results, dict) else results
    if not rows:
        return "No businesses found."
    lines = [f"📍 Found {len(rows)} businesses ({results.get('category','?')} in {results.get('city','?')}):"]
    for r in rows[:15]:
        bits = [r["business_name"]]
        if r.get("phone"):
            bits.append(f"📞 {r['phone']}")
        if r.get("website"):
            bits.append(f"🌐 {r['website']}")
        if r.get("address"):
            bits.append(f"📍 {r['address']}")
        lines.append("  • " + " · ".join(bits))
    if len(rows) > 15:
        lines.append(f"  … and {len(rows) - 15} more")
    return "\n".join(lines)


def format_import_summary(summary):
    return f"✓ Inserted {summary['inserted']} new leads. Skipped {summary['skipped']} duplicates. Errors: {summary['errors']}."
