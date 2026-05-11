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


# ─── Admin-dashboard data feeds ─────────────────────────────────────────

def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def list_recent_signups(days=7, limit=50):
    """Registrations created within the last N days, newest first."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
    return _rest_get("app_registrations", {
        "select": "id,business_name,whatsapp,app_type,app_tier,billing_cycle,price,status,payment_reference,payment_proof_url,created_at",
        "created_at": f"gte.{cutoff}",
        "order": "created_at.desc",
        "limit": str(limit),
    })


def list_payment_due(days_ahead=7, include_expired=True, limit=100):
    """Active subscriptions with expires_at within the next N days (or already
    expired if include_expired=True)."""
    now = datetime.utcnow()
    soon = (now + timedelta(days=days_ahead)).isoformat() + "Z"
    rows = _rest_get("app_registrations", {
        "select": "id,business_name,whatsapp,app_type,app_tier,billing_cycle,price,status,expires_at,payment_reference,verified_at",
        "status": "eq.active",
        "expires_at": f"lte.{soon}",
        "order": "expires_at.asc.nullslast",
        "limit": str(limit),
    })
    if not include_expired:
        now_iso = now.isoformat() + "Z"
        rows = [r for r in rows if (r.get("expires_at") or "") >= now_iso]
    return rows


def get_country_breakdown():
    """Aggregate registrations by country (derived from WhatsApp prefix).
    Returns list of {country, total, active, pending, deactivated, revenue}.
    """
    rows = _rest_get("app_registrations", {
        "select": "id,status,billing_cycle,price,whatsapp",
    })
    buckets = {}
    for r in rows:
        country = _country_from_whatsapp(r.get("whatsapp"))
        b = buckets.setdefault(country, {"country": country, "total": 0, "active": 0, "pending": 0, "deactivated": 0, "revenue": 0})
        b["total"] += 1
        status = r.get("status")
        if status == "active":
            b["active"] += 1
            b["revenue"] += _parse_price(r.get("price"))
        elif status == "pending_verification":
            b["pending"] += 1
        elif status == "deactivated":
            b["deactivated"] += 1
    return sorted(buckets.values(), key=lambda x: x["total"], reverse=True)


def get_app_type_breakdown():
    """How registrations split across food/basic/pro/products/services apps."""
    rows = _rest_get("app_registrations", {"select": "app_type,status"})
    buckets = {}
    for r in rows:
        app_type = r.get("app_type") or "unknown"
        b = buckets.setdefault(app_type, {"app_type": app_type, "total": 0, "active": 0, "pending": 0})
        b["total"] += 1
        if r.get("status") == "active":
            b["active"] += 1
        elif r.get("status") == "pending_verification":
            b["pending"] += 1
    return sorted(buckets.values(), key=lambda x: x["total"], reverse=True)


def get_theme_popularity(window_hours=24, limit=15):
    """Popular themes within the last N hours. Requires a theme_views table —
    if it doesn't exist or is empty, returns an empty list with a note so the
    UI can display 'no tracking data yet'."""
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=window_hours)).isoformat() + "Z"
        rows = _rest_get("theme_views", {
            "select": "theme_id,country",
            "viewed_at": f"gte.{cutoff}",
            "limit": "5000",
        })
        counts = {}
        for r in rows:
            tid = r.get("theme_id") or "unknown"
            counts[tid] = counts.get(tid, 0) + 1
        return sorted(
            [{"theme_id": k, "views": v} for k, v in counts.items()],
            key=lambda x: x["views"], reverse=True,
        )[:limit]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"_note": "theme_views table not created yet — popularity tracking pending"}
        raise


def get_session_duration_stats(days=7):
    """Average + median session length. Requires a sessions table — same
    graceful-degrade behaviour as get_theme_popularity."""
    try:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
        rows = _rest_get("sessions", {
            "select": "duration_seconds,app",
            "started_at": f"gte.{cutoff}",
            "limit": "10000",
        })
        durations = [r["duration_seconds"] for r in rows if r.get("duration_seconds")]
        if not durations:
            return {"_note": "no session data in window"}
        durations.sort()
        avg = sum(durations) / len(durations)
        median = durations[len(durations) // 2]
        by_app = {}
        for r in rows:
            app = r.get("app", "unknown")
            by_app.setdefault(app, []).append(r.get("duration_seconds") or 0)
        return {
            "count": len(durations),
            "avg_seconds": int(avg),
            "median_seconds": int(median),
            "by_app": {a: int(sum(v) / len(v)) for a, v in by_app.items() if v},
        }
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"_note": "sessions table not created yet — duration tracking pending"}
        raise


def generate_suggestions():
    """Pattern analysis over live data → actionable text suggestions for admin.
    No external AI; pure rule-based reasoning over the health snapshot, country
    breakdown, and app-type breakdown."""
    h = get_health_snapshot()
    countries = get_country_breakdown()
    apps = get_app_type_breakdown()
    suggestions = []

    # Pending pile-up
    if h["pending_with_proof"] >= 5:
        suggestions.append({"priority": "high", "area": "Operations", "text": f"{h['pending_with_proof']} customer payments have proof uploaded but aren't approved yet. Review the queue in the next 30 minutes — every hour of delay costs you a customer's trust."})
    if h["pending_no_proof"] >= 10:
        suggestions.append({"priority": "medium", "area": "Conversion", "text": f"{h['pending_no_proof']} registrations are sitting without payment proof. Consider a WhatsApp follow-up template: 'Hi, your account is reserved — when can you complete payment?'"})

    # Churn
    if h["churn_rate"] > 15:
        suggestions.append({"priority": "high", "area": "Retention", "text": f"Churn rate is {h['churn_rate']}% — above the 15% danger line. Pull the last 5 deactivated accounts and call them; ask what broke."})
    elif h["churn_rate"] > 8:
        suggestions.append({"priority": "medium", "area": "Retention", "text": f"Churn rate is {h['churn_rate']}%. Healthy is <8%. Watch the trend over the next week."})

    # Renewal pipeline
    if h["expired"] > 0:
        suggestions.append({"priority": "high", "area": "Revenue", "text": f"{h['expired']} active subscription(s) have already expired — they're still active in the data but renewal is overdue. Send a renewal nudge today."})
    if h["expiring_in_7d"] >= 3:
        suggestions.append({"priority": "medium", "area": "Revenue", "text": f"{h['expiring_in_7d']} subscriptions expire within 7 days. Auto-send renewal reminders 3 days before expiry to reduce drop-off."})

    # Country imbalance — Indonesia heavy?
    total = sum(c["total"] for c in countries)
    if total >= 10:
        top = countries[0]
        if top["total"] / total > 0.85:
            suggestions.append({"priority": "low", "area": "Growth", "text": f"{int(top['total']/total*100)}% of customers are in {top['country']}. To diversify revenue, pick one secondary country (your next-biggest is {countries[1]['country'] if len(countries) > 1 else 'unknown'}) and run a localised promo there."})

    # App-type imbalance
    if apps:
        top_app = apps[0]
        if sum(a["total"] for a in apps) > 5 and top_app["total"] > 0:
            other_total = sum(a["total"] for a in apps[1:])
            if other_total == 0 and len(apps) == 1:
                suggestions.append({"priority": "low", "area": "Product", "text": f"All registrations are on '{top_app['app_type']}'. The other apps (food-pro, products, services) have zero traction yet — either pull them off the homepage or run a focused campaign for one."})

    # Empty state
    if not suggestions:
        suggestions.append({"priority": "info", "area": "Overall", "text": "Nothing urgent to flag right now. System is operating within healthy ranges. Keep monitoring."})

    return suggestions


def get_system_status():
    """One-shot snapshot for the login greeting — health + top alert + top suggestion."""
    h = get_health_snapshot()
    alerts = get_alerts()
    suggestions = generate_suggestions()
    # Bucket the system as ok / attention / critical based on signals.
    critical = sum(1 for a in alerts if a["severity"] == "warning")
    if critical >= 2:
        status = "critical"
    elif critical == 1 or len(alerts) >= 3:
        status = "attention"
    else:
        status = "ok"
    top_alert = next((a for a in alerts if a["severity"] == "warning"), alerts[0] if alerts else None)
    top_suggestion = next((s for s in suggestions if s["priority"] in ("high", "medium")), suggestions[0] if suggestions else None)
    return {
        "status": status,
        "snapshot": h,
        "alert_count": len(alerts),
        "top_alert": top_alert,
        "top_suggestion": top_suggestion,
    }
