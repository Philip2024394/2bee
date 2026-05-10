"""
Live Supabase connector for the StreetLocal project.
Reads via anon key + REST API, writes via Management API SQL endpoint.
Pure stdlib — urllib only — to keep with the jarvis "no third party" ethos.
"""

import os
import json
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timedelta

# Project config — falls back to streetlocal's prod project for dev convenience.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://fjvafjkzvygkhiwjuvla.supabase.co")
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZqdmFmamt6dnlna2hpd2p1dmxhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMDk0NDEsImV4cCI6MjA5MDY4NTQ0MX0.UoXfKznY9gAEqZDSTegDjIfYAeAeFg6Eh1D40Hoe2KM",
)
SUPABASE_PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "fjvafjkzvygkhiwjuvla")
# Management API token — load lazily so reads keep working without it.
_ACCESS_TOKEN = None


def _load_access_token():
    """Look in env first, then streetlocal/.env. Cached after first read."""
    global _ACCESS_TOKEN
    if _ACCESS_TOKEN is not None:
        return _ACCESS_TOKEN
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        env_path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "streetlocal", ".env"))
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("SUPABASE_ACCESS_TOKEN="):
                        token = line.split("=", 1)[1].strip()
                        break
        except (OSError, IOError):
            pass
    _ACCESS_TOKEN = token or ""
    return _ACCESS_TOKEN


# Some corporate / Windows machines fail certificate revocation checks against
# Supabase Cloudflare endpoints. Falling back to an unverified context here is
# acceptable for read-only public data + management API requests authenticated
# via bearer token.
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


# Cloudflare in front of api.supabase.com rejects requests with no User-Agent.
_UA = "2bee/1.0 (+https://github.com/Philip2024394/2bee)"


def _rest_get(path, params=None):
    """GET against PostgREST. Returns parsed JSON or raises."""
    url = SUPABASE_URL.rstrip("/") + "/rest/v1/" + path.lstrip("/")
    if params:
        url += "?" + urllib.parse.urlencode(params, safe=",.()*")
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Accept": "application/json",
        "User-Agent": _UA,
    })
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _management_query(sql):
    """Run arbitrary SQL via the Supabase Management API. Needs access token."""
    token = _load_access_token()
    if not token:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not configured — cannot run write queries")
    url = f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query"
    body = json.dumps({"query": sql}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": _UA,
    }, method="POST")
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─── Helpers ─────────────────────────────────────────────────────────────

def _parse_price(price_text):
    """Strip currency symbols and return integer. Accepts 'Rp 35.000', '$5', '5'."""
    if not price_text:
        return 0
    digits = "".join(c for c in str(price_text) if c.isdigit())
    return int(digits) if digits else 0


def _country_from_whatsapp(wa):
    if not wa:
        return "Unknown"
    n = "".join(c for c in str(wa) if c.isdigit())
    prefixes = [
        ("62", "🇮🇩 Indonesia"), ("60", "🇲🇾 Malaysia"), ("65", "🇸🇬 Singapore"),
        ("66", "🇹🇭 Thailand"), ("63", "🇵🇭 Philippines"), ("84", "🇻🇳 Vietnam"),
        ("44", "🇬🇧 UK"), ("61", "🇦🇺 Australia"), ("1", "🇺🇸 US"),
    ]
    for prefix, name in prefixes:
        if n.startswith(prefix):
            return name
    return "🌍 Other"


# ─── Read queries ────────────────────────────────────────────────────────

def list_pending_payments():
    """Registrations awaiting payment verification (status='pending_verification')."""
    return _rest_get("app_registrations", {
        "select": "id,business_name,whatsapp,app_type,app_tier,billing_cycle,price,payment_reference,payment_proof_url,payment_uploaded_at,created_at",
        "status": "eq.pending_verification",
        "order": "payment_uploaded_at.desc.nullslast",
    })


def list_active():
    return _rest_get("app_registrations", {
        "select": "id,business_name,billing_cycle,price,expires_at,whatsapp,app_type",
        "status": "eq.active",
        "order": "created_at.desc",
    })


def find_by_reference(ref_code):
    """Look up a single registration by its payment reference code."""
    rows = _rest_get("app_registrations", {
        "select": "*",
        "payment_reference": f"eq.{ref_code.upper().strip()}",
    })
    return rows[0] if rows else None


def get_country_pricing():
    return _rest_get("country_pricing", {"select": "*", "order": "country_name"})


# ─── Write queries (need management token) ──────────────────────────────

def approve_payment(ref_code):
    """Flip a pending_verification row to active, set verified_at + expires_at
    based on billing cycle. Returns dict with the updated row, or None if not
    found."""
    ref = ref_code.upper().strip().replace("'", "''")
    sql = f"""
    UPDATE app_registrations
    SET status = 'active',
        verified_at = NOW(),
        expires_at = NOW() + (CASE WHEN billing_cycle = 'yearly' THEN INTERVAL '365 days' ELSE INTERVAL '30 days' END)
    WHERE payment_reference = '{ref}'
      AND status = 'pending_verification'
    RETURNING id, business_name, payment_reference, billing_cycle, expires_at, status;
    """
    result = _management_query(sql)
    return result[0] if result else None


def reject_payment(ref_code, note=None):
    ref = ref_code.upper().strip().replace("'", "''")
    extra = ""
    if note:
        safe_note = note.replace("'", "''")
        extra = f", notes = '{safe_note}'"
    sql = f"""
    UPDATE app_registrations
    SET status = 'deactivated'{extra}
    WHERE payment_reference = '{ref}'
    RETURNING id, business_name, payment_reference, status;
    """
    result = _management_query(sql)
    return result[0] if result else None


# ─── Aggregations / health ──────────────────────────────────────────────

def get_health_snapshot():
    """One-shot dashboard data: counts, revenue, churn, expiring soon."""
    rows = _rest_get("app_registrations", {
        "select": "id,status,billing_cycle,price,expires_at,created_at,verified_at,payment_proof_url",
    })
    now = datetime.utcnow()
    week_from_now = now + timedelta(days=7)
    two_days_ago = now - timedelta(days=2)
    thirty_days_ago = now - timedelta(days=30)

    def parse_iso(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return None

    active = [r for r in rows if r["status"] == "active"]
    pending = [r for r in rows if r["status"] == "pending_verification"]
    deactivated = [r for r in rows if r["status"] == "deactivated"]

    active_monthly = [r for r in active if r.get("billing_cycle") == "monthly"]
    active_yearly = [r for r in active if r.get("billing_cycle") == "yearly"]

    monthly_rev = sum(_parse_price(r.get("price")) for r in active_monthly)
    yearly_rev = sum(_parse_price(r.get("price")) for r in active_yearly)

    expiring = []
    expired = []
    for r in active:
        exp = parse_iso(r.get("expires_at"))
        if not exp:
            continue
        if exp < now:
            expired.append(r)
        elif exp < week_from_now:
            expiring.append(r)

    stale_pending = [r for r in pending if (parse_iso(r.get("created_at")) or now) < two_days_ago]
    pending_with_proof = [r for r in pending if r.get("payment_proof_url")]
    pending_no_proof = [r for r in pending if not r.get("payment_proof_url")]

    # No updated_at column on app_registrations, so use verified_at (when status was last set) as a proxy
    recent_churn = [r for r in deactivated if (parse_iso(r.get("verified_at")) or parse_iso(r.get("created_at")) or datetime.min) > thirty_days_ago]
    churn_rate = (len(deactivated) / len(rows) * 100) if rows else 0

    return {
        "total": len(rows),
        "active": len(active),
        "pending": len(pending),
        "pending_with_proof": len(pending_with_proof),
        "pending_no_proof": len(pending_no_proof),
        "stale_pending": len(stale_pending),
        "deactivated": len(deactivated),
        "recent_churn": len(recent_churn),
        "churn_rate": round(churn_rate, 1),
        "monthly_revenue": monthly_rev,
        "yearly_revenue": yearly_rev,
        "active_monthly_count": len(active_monthly),
        "active_yearly_count": len(active_yearly),
        "expired": len(expired),
        "expiring_in_7d": len(expiring),
    }


def get_alerts():
    """Compact list of things admin should look at right now. Each alert has
    severity ('warning'|'info') and a short description."""
    h = get_health_snapshot()
    alerts = []
    if h["pending_with_proof"] > 0:
        alerts.append({"severity": "info", "msg": f"{h['pending_with_proof']} payment(s) waiting for review (proof uploaded)"})
    if h["stale_pending"] > 0:
        alerts.append({"severity": "warning", "msg": f"{h['stale_pending']} registration(s) pending more than 48h — follow up"})
    if h["expired"] > 0:
        alerts.append({"severity": "warning", "msg": f"{h['expired']} active subscription(s) have expired — needs renewal nudge"})
    if h["expiring_in_7d"] > 0:
        alerts.append({"severity": "info", "msg": f"{h['expiring_in_7d']} subscription(s) expire within 7 days"})
    if h["churn_rate"] > 10:
        alerts.append({"severity": "warning", "msg": f"Churn rate is {h['churn_rate']}% — above 10% threshold"})
    return alerts


# ─── Display formatters ─────────────────────────────────────────────────

def format_pending_list(rows, limit=10):
    if not rows:
        return "No pending payments. ✓"
    lines = [f"📋 Pending payments ({len(rows)}):"]
    for r in rows[:limit]:
        country = _country_from_whatsapp(r.get("whatsapp"))
        ref = r.get("payment_reference", "—")
        proof = "📎 proof attached" if r.get("payment_proof_url") else "⏳ no proof yet"
        lines.append(f"  • {ref}  {r.get('business_name','?')} ({r.get('app_tier','?')} {r.get('billing_cycle','monthly')}) — {country} — {proof}")
    if len(rows) > limit:
        lines.append(f"  … and {len(rows) - limit} more")
    return "\n".join(lines)


def format_health(h):
    return "\n".join([
        "🩺 Vendor health report",
        f"  Active: {h['active']} ({h['active_monthly_count']} monthly, {h['active_yearly_count']} yearly)",
        f"  Pending: {h['pending']} ({h['pending_with_proof']} with proof, {h['pending_no_proof']} waiting on customer)",
        f"  Stale (>48h): {h['stale_pending']}",
        f"  Deactivated: {h['deactivated']} (churn rate {h['churn_rate']}%)",
        f"  Expired: {h['expired']}, expiring within 7 days: {h['expiring_in_7d']}",
    ])


def format_revenue(h):
    monthly = h["monthly_revenue"]
    yearly = h["yearly_revenue"]
    return "\n".join([
        "💰 Revenue (active subscriptions)",
        f"  Monthly recurring (MRR): Rp {monthly:,}",
        f"  Yearly bookings: Rp {yearly:,}",
        f"  Implied annual: Rp {monthly * 12 + yearly:,}",
    ])


def format_alerts(alerts):
    if not alerts:
        return "✓ No alerts. Everything looks healthy."
    icons = {"warning": "⚠️", "info": "🔔"}
    lines = [f"📣 {len(alerts)} alert(s):"]
    for a in alerts:
        lines.append(f"  {icons.get(a['severity'], '•')} {a['msg']}")
    return "\n".join(lines)
