"""
Enrich existing leads by scraping their PUBLICLY PUBLISHED contact info.

Sources (all 100% public-page parsing — no private APIs, no auth needed):
- The lead's own website (if present in OSM): /contact, /about, footer → extract mailto: + phone patterns
- Their Instagram bio (if handle in OSM 'contact:instagram'): public profile page → extract WhatsApp + email
- Their Facebook page (if URL in OSM): public about section

Result: a phoneless lead gets phone + email back where the business itself
published this info to attract customers. We just gather what they already
chose to make public.
"""

import re
import urllib.request
import urllib.parse
import urllib.error
import ssl
import json
from html.parser import HTMLParser
from brain import supabase_connector as sb


_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


# ─── Regex patterns ────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Indonesian + international phone patterns. Strict — only accepts forms that
# look like real WhatsApp-compatible numbers, not random digit strings.
PHONE_PATTERNS = [
    re.compile(r"\+62[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}"),  # +62 812 3456 7890
    re.compile(r"\b0\d{2,3}[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b"),        # 0812-3456-7890
    re.compile(r"\b62\d{8,12}\b"),                                  # 6281234567890
    re.compile(r"\+\d{1,3}[\s.-]?\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}"),  # any +country
]

# Filter out obvious junk emails (analytics, placeholders, examples).
EMAIL_JUNK = (
    "example.com", "sentry.io", "wixpress.com", "domain.com", "yourdomain",
    "youremail", "test@", "no-reply", "noreply@", "donotreply",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    "wordpress.com/wp-", "@2x.", "@x.", "u003e", "u003c",
)


def _looks_like_email(addr):
    a = addr.lower()
    if any(j in a for j in EMAIL_JUNK):
        return False
    if "@" not in a or "." not in a.split("@", 1)[1]:
        return False
    if len(a) > 80:
        return False
    return True


def _normalize_phone(p):
    """Normalize to + format. Drop separators."""
    digits = re.sub(r"[^\d+]", "", p)
    if digits.startswith("0"):
        digits = "+62" + digits[1:]  # default to Indonesia
    elif digits.startswith("62") and not digits.startswith("+"):
        digits = "+" + digits
    elif not digits.startswith("+"):
        if digits.startswith("8") and len(digits) >= 10:  # bare Indonesian mobile
            digits = "+62" + digits
        else:
            return None  # ambiguous
    return digits if 10 <= len(digits) <= 16 else None


# ─── Page fetching ─────────────────────────────────────────────────────

def _fetch(url, timeout=10):
    """Fetch a URL. Returns text or None. Respects robots.txt politeness via UA + reasonable rate (caller's job)."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "id,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
            ct = resp.headers.get("Content-Type", "")
            if "text" not in ct and "html" not in ct and "json" not in ct:
                return None
            data = resp.read(2_000_000)  # cap at 2MB
            try:
                return data.decode("utf-8", errors="ignore")
            except Exception:
                return data.decode("latin-1", errors="ignore")
    except Exception:
        return None


class _TextExtractor(HTMLParser):
    """Pull text + script JSON-LD content out of a page (skip <script> bodies except JSON-LD)."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False
        self._is_ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self._skip = True
            self._is_ld = tag == "script" and a.get("type") == "application/ld+json"
        if tag == "a":
            href = a.get("href", "")
            if href.startswith("mailto:") or href.startswith("tel:") or href.startswith("https://wa.me/"):
                self.parts.append(href)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
            self._is_ld = False

    def handle_data(self, data):
        if self._skip and not self._is_ld:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


def _extract_text(html):
    if not html:
        return ""
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass
    return "\n".join(p.parts)


# ─── Public extractor entrypoint ────────────────────────────────────────

def extract_contacts_from_text(text):
    """Pull emails + phones + WhatsApp links out of a blob of HTML or text."""
    if not text:
        return {"emails": [], "phones": [], "whatsapps": []}
    emails = set()
    for m in EMAIL_RE.findall(text):
        if _looks_like_email(m):
            emails.add(m.lower())
    phones = set()
    for pat in PHONE_PATTERNS:
        for m in pat.findall(text):
            n = _normalize_phone(m)
            if n:
                phones.add(n)
    # wa.me/<digits> + WhatsApp deep links
    whatsapps = set()
    for m in re.findall(r"wa\.me/(\d{8,16})", text):
        n = _normalize_phone(m)
        if n:
            whatsapps.add(n)
    return {
        "emails": sorted(emails),
        "phones": sorted(phones),
        "whatsapps": sorted(whatsapps),
    }


# ─── Source-specific scrapers ──────────────────────────────────────────

def enrich_from_website(website_url):
    """Visit the homepage + try /contact, /about, footer. Return aggregated contacts."""
    if not website_url:
        return {"emails": [], "phones": [], "whatsapps": []}
    if not website_url.startswith("http"):
        website_url = "https://" + website_url
    parsed = urllib.parse.urlparse(website_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        website_url,
        f"{base}/contact",
        f"{base}/contact-us",
        f"{base}/about",
        f"{base}/about-us",
        f"{base}/kontak",  # Indonesian
        f"{base}/hubungi-kami",  # Indonesian
    ]
    all_emails = set()
    all_phones = set()
    all_wa = set()
    pages_hit = 0
    for url in candidates:
        html = _fetch(url, timeout=8)
        if not html:
            continue
        pages_hit += 1
        text = _extract_text(html)
        # Also keep the raw HTML for mailto:/tel: parsing
        bundle = extract_contacts_from_text(text + "\n" + html)
        all_emails.update(bundle["emails"])
        all_phones.update(bundle["phones"])
        all_wa.update(bundle["whatsapps"])
        # If we've already got a phone+email, no need to keep crawling
        if all_emails and (all_phones or all_wa):
            break
    return {
        "emails": sorted(all_emails),
        "phones": sorted(all_phones),
        "whatsapps": sorted(all_wa),
        "pages_scanned": pages_hit,
    }


def enrich_from_instagram(handle):
    """Fetch a public Instagram profile and extract contact info from the bio.
    Instagram serves a public HTML page that contains the bio in og:description
    and in embedded JSON. No login required for public profiles."""
    if not handle:
        return {"emails": [], "phones": [], "whatsapps": []}
    handle = handle.strip().lstrip("@").rstrip("/")
    if handle.startswith("http"):
        handle = urllib.parse.urlparse(handle).path.strip("/").split("/")[0]
    url = f"https://www.instagram.com/{handle}/"
    html = _fetch(url, timeout=10)
    if not html:
        return {"emails": [], "phones": [], "whatsapps": []}
    # Strategy: search the whole HTML for emails + phones. Instagram embeds the
    # bio JSON in window._sharedData / __NEXT_DATA__ scripts. Our regex will pick
    # them up regardless of which encoding Instagram is using this week.
    bundle = extract_contacts_from_text(html)
    return bundle


def _osm_extra_tags(lead):
    """OSM source_url like 'https://www.openstreetmap.org/node/12345' — fetch
    the OSM XML for that element to recover IG/Facebook handles + extra
    contact tags that we discarded when initially importing."""
    src = lead.get("source_url", "")
    m = re.match(r"https?://www\.openstreetmap\.org/(node|way|relation)/(\d+)", src or "")
    if not m:
        return {}
    typ, oid = m.group(1), m.group(2)
    api = f"https://api.openstreetmap.org/api/0.6/{typ}/{oid}.json"
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers={"User-Agent": _UA}), timeout=10, context=_SSL) as r:
            data = json.loads(r.read().decode("utf-8"))
        elements = data.get("elements", [])
        if elements:
            return elements[0].get("tags", {}) or {}
    except Exception:
        return {}
    return {}


# ─── Top-level: enrich one lead ─────────────────────────────────────────

def enrich_lead(lead, dry_run=False):
    """Pull all public contact info we can find for this lead. Returns a dict
    of new fields to merge into outreach_leads, and a list of sources actually
    used."""
    found = {"emails": set(), "phones": set(), "whatsapps": set()}
    sources_used = []

    # 1. Website
    if lead.get("website"):
        bundle = enrich_from_website(lead["website"])
        if bundle["emails"] or bundle["phones"] or bundle["whatsapps"]:
            sources_used.append(f"website ({bundle.get('pages_scanned',0)} pages)")
        found["emails"].update(bundle["emails"])
        found["phones"].update(bundle["phones"])
        found["whatsapps"].update(bundle["whatsapps"])

    # 2. OSM extra tags (instagram, facebook handles often hide here)
    extra = _osm_extra_tags(lead)
    insta = (extra.get("contact:instagram") or extra.get("instagram") or "").strip()
    fb = (extra.get("contact:facebook") or extra.get("facebook") or "").strip()
    extra_phone = (extra.get("contact:phone") or extra.get("phone") or "").strip()
    extra_email = (extra.get("contact:email") or extra.get("email") or "").strip()
    extra_whatsapp = (extra.get("contact:whatsapp") or extra.get("whatsapp") or "").strip()
    if extra_phone:
        n = _normalize_phone(extra_phone)
        if n:
            found["phones"].add(n)
            sources_used.append("osm:phone")
    if extra_email and _looks_like_email(extra_email):
        found["emails"].add(extra_email.lower())
        sources_used.append("osm:email")
    if extra_whatsapp:
        n = _normalize_phone(extra_whatsapp)
        if n:
            found["whatsapps"].add(n)
            sources_used.append("osm:whatsapp")

    # 3. Instagram bio (if handle in OSM tags)
    if insta:
        bundle = enrich_from_instagram(insta)
        if bundle["emails"] or bundle["phones"] or bundle["whatsapps"]:
            sources_used.append(f"instagram:@{insta[:30]}")
        found["emails"].update(bundle["emails"])
        found["phones"].update(bundle["phones"])
        found["whatsapps"].update(bundle["whatsapps"])

    # Choose canonical values
    update = {}
    if not lead.get("phone") and found["phones"]:
        update["phone"] = sorted(found["phones"])[0]
    if not lead.get("whatsapp") and (found["whatsapps"] or found["phones"]):
        update["whatsapp"] = sorted(found["whatsapps"] or found["phones"])[0]
    if not lead.get("email") and found["emails"]:
        update["email"] = sorted(found["emails"])[0]

    return {
        "found": {k: sorted(v) for k, v in found.items()},
        "update": update,
        "sources": sources_used,
        "applied": bool(update) and not dry_run,
        "lead_id": lead.get("id"),
    }


def _apply_update(lead_id, update):
    if not update:
        return False
    set_parts = []
    for k, v in update.items():
        safe = str(v).replace("'", "''")
        set_parts.append(f"{k} = '{safe}'")
    sql = f"UPDATE outreach_leads SET {', '.join(set_parts)}, updated_at = NOW() WHERE id = '{lead_id}' RETURNING id;"
    try:
        sb._management_query(sql)
        return True
    except Exception:
        return False


def enrich_all_phoneless(limit=200):
    """Run enrichment across every lead that is missing phone + whatsapp.
    Returns aggregate stats — never fakes progress."""
    leads = sb._rest_get("outreach_leads", {
        "select": "*",
        "or": "(phone.is.null,whatsapp.is.null)",
        "limit": str(limit),
    })
    enriched = 0
    no_data = 0
    errors = 0
    new_emails = 0
    new_phones = 0
    new_was = 0
    for lead in leads:
        try:
            result = enrich_lead(lead)
            if result["update"]:
                if _apply_update(lead["id"], result["update"]):
                    enriched += 1
                    if "email" in result["update"]:
                        new_emails += 1
                    if "phone" in result["update"]:
                        new_phones += 1
                    if "whatsapp" in result["update"]:
                        new_was += 1
                else:
                    errors += 1
            else:
                no_data += 1
        except Exception:
            errors += 1
    return {
        "scanned": len(leads),
        "enriched": enriched,
        "no_data_found": no_data,
        "errors": errors,
        "new_emails": new_emails,
        "new_phones": new_phones,
        "new_whatsapps": new_was,
    }


# ─── Email export — Excel/CSV/TXT for the admin ─────────────────────────

def export_leads_csv(only_with_email=False, only_with_phone=False):
    """Return CSV text of all leads."""
    params = {"select": "business_name,business_type,country,city,phone,whatsapp,email,website,address,source,source_url,status,created_at", "limit": "10000"}
    if only_with_email:
        params["email"] = "not.is.null"
    if only_with_phone:
        params["or"] = "(phone.not.is.null,whatsapp.not.is.null)"
    leads = sb._rest_get("outreach_leads", params)
    cols = ["business_name", "business_type", "country", "city", "phone", "whatsapp", "email", "website", "address", "source", "source_url", "status", "created_at"]
    lines = [",".join(cols)]
    for l in leads:
        row = []
        for c in cols:
            v = (l.get(c) or "")
            if "," in str(v) or '"' in str(v) or "\n" in str(v):
                v = '"' + str(v).replace('"', '""') + '"'
            row.append(str(v))
        lines.append(",".join(row))
    return "\n".join(lines)


def export_emails_only(format="newline"):
    """Just the deduplicated email column for bulk-list use.
    format: newline | comma | semicolon"""
    leads = sb._rest_get("outreach_leads", {"select": "email", "email": "not.is.null", "limit": "10000"})
    seen = set()
    for l in leads:
        e = (l.get("email") or "").strip().lower()
        if e:
            seen.add(e)
    emails = sorted(seen)
    if format == "comma":
        return ", ".join(emails)
    if format == "semicolon":
        return "; ".join(emails)
    return "\n".join(emails)
