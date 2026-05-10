"""
Bank statement → payment auto-match.

Parses CSV exports from Indonesian banks (BCA, Mandiri, BRI, BNI etc.),
finds reference codes (SL-XXXXXX) in transfer descriptions, validates the
amount matches the expected price from app_registrations, and auto-approves
matched payments.

The bank_transactions table de-duplicates rows by `bank_txn_ref` so the same
CSV pasted twice won't double-approve anything.
"""

import re
import csv
import io
import json
from datetime import datetime
from brain import supabase_connector as sb

# Reference code in transfer description. Tolerates lower-case input.
REF_PATTERN = re.compile(r'\bSL[-\s]?([A-Z0-9]{4,8})\b', re.IGNORECASE)

# Header aliases — banks vary in column names + language. Lower-case keys.
DATE_HEADERS = {"date", "tanggal", "transaction date", "transaksi", "value date", "tgl"}
DESC_HEADERS = {"description", "keterangan", "deskripsi", "remark", "narasi", "transaction details", "details", "narrative", "detail"}
AMOUNT_HEADERS = {"amount", "jumlah", "credit", "kredit", "amount (idr)", "credit amount", "incoming", "deposit", "in", "penerimaan"}
DEBIT_HEADERS = {"debit", "debet", "withdrawal", "outgoing", "out", "pengeluaran"}


def _norm_amount(s):
    """Strip currency symbols, thousand separators. Returns int or None."""
    if s is None or s == "":
        return None
    txt = str(s).strip()
    if not txt:
        return None
    # Remove currency, spaces, then handle Indonesian thousand separators (.) vs decimal
    txt = re.sub(r'[Rr][Pp\.]?\s*', '', txt)
    txt = txt.replace(" ", "")
    # Indonesian format: 35.000,50 (dot=thousands, comma=decimal). Drop decimals, drop thousands.
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").split(",")[0]
    elif "," in txt:
        # Could be "1,234,567" (US thousands) or "35,50" (decimal). If only 2 digits after comma → decimal.
        parts = txt.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            txt = parts[0]
        else:
            txt = txt.replace(",", "")
    elif "." in txt:
        # Could be "35.000" (Indonesian thousands) or "35.50" (decimal). 3-digit groups = thousands.
        parts = txt.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            txt = "".join(parts)
        else:
            txt = parts[0]
    txt = re.sub(r'[^0-9-]', '', txt)
    try:
        return int(txt) if txt and txt != "-" else None
    except ValueError:
        return None


def _norm_date(s):
    """Try a handful of common bank date formats. Returns ISO date string or None."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d %B %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _detect_dialect(sample):
    """Detect CSV separator (comma vs semicolon) — Indonesian Excel often uses ;."""
    try:
        return csv.Sniffer().sniff(sample[:4096], delimiters=",;\t|")
    except csv.Error:
        return csv.excel  # default to comma


def parse_csv(csv_text):
    """Parse a CSV string into normalized transaction dicts.

    Each returned dict has: txn_ref, date, description, amount, raw.
    Skips rows that are clearly non-transactions (headers, blank, outgoing).
    """
    if not csv_text or not csv_text.strip():
        return []
    dialect = _detect_dialect(csv_text)
    reader = csv.reader(io.StringIO(csv_text), dialect=dialect)

    # Find header row — first row with any recognized column.
    header = None
    rows = []
    for row in reader:
        if header is None:
            lowered = [c.strip().lower() for c in row]
            if any(h in DATE_HEADERS or h in DESC_HEADERS or h in AMOUNT_HEADERS for h in lowered):
                header = lowered
                continue
            # No header on first row → fall back to positional (date, desc, amount)
            if len(row) >= 3:
                header = ["date", "description", "amount"] + ["col_" + str(i) for i in range(len(row) - 3)]
                rows.append(row)
            continue
        if any(c.strip() for c in row):
            rows.append(row)

    if header is None:
        return []

    # Resolve column indices.
    def col_idx(aliases):
        for i, h in enumerate(header):
            if h in aliases:
                return i
        return None

    date_i = col_idx(DATE_HEADERS)
    desc_i = col_idx(DESC_HEADERS)
    amt_i = col_idx(AMOUNT_HEADERS)
    debit_i = col_idx(DEBIT_HEADERS)

    out = []
    for r in rows:
        # Pad to header length so index access is safe.
        if len(r) < len(header):
            r = r + [""] * (len(header) - len(r))
        date = _norm_date(r[date_i]) if date_i is not None else None
        desc = (r[desc_i] if desc_i is not None else "").strip()
        amt = _norm_amount(r[amt_i]) if amt_i is not None else None
        debit = _norm_amount(r[debit_i]) if debit_i is not None else None

        # Skip outgoing transactions (debits) and rows without an incoming amount.
        if amt is None or amt <= 0:
            continue
        if debit is not None and debit > 0:
            continue

        # Build a stable txn_ref so re-imports dedupe. Use a hash of date+amount+desc.
        ref_basis = f"{date}|{amt}|{desc}"
        import hashlib
        txn_ref = "bank_" + hashlib.sha1(ref_basis.encode("utf-8")).hexdigest()[:16]

        out.append({
            "txn_ref": txn_ref,
            "date": date,
            "description": desc,
            "amount": amt,
            "raw": dict(zip(header, r[:len(header)])),
        })
    return out


def find_reference(text):
    """Pull the SL-XXXXXX reference from a transfer description, normalised."""
    if not text:
        return None
    m = REF_PATTERN.search(text)
    if not m:
        return None
    return ("SL-" + m.group(1).upper()).replace("SL- ", "SL-").replace("SL-SL-", "SL-")


def _record_transaction(txn, ref, status, registration_id=None):
    """Insert into bank_transactions. Returns True if newly inserted, False if dupe."""
    raw_json = json.dumps(txn["raw"]).replace("'", "''")
    desc = (txn["description"] or "").replace("'", "''")
    ref_part = f"'{ref}'" if ref else "NULL"
    reg_part = f"'{registration_id}'" if registration_id else "NULL"
    matched_at_part = "NOW()" if status == "matched" else "NULL"
    date_part = f"'{txn['date']}'" if txn.get("date") else "NULL"
    sql = f"""
    INSERT INTO bank_transactions (bank_txn_ref, amount, description, transaction_date, detected_reference, matched_registration_id, matched_at, status, raw_row)
    VALUES ('{txn['txn_ref']}', {txn['amount']}, '{desc}', {date_part}, {ref_part}, {reg_part}, {matched_at_part}, '{status}', '{raw_json}'::jsonb)
    ON CONFLICT (bank_txn_ref) DO NOTHING
    RETURNING id;
    """
    result = sb._management_query(sql)
    return bool(result)


def process_csv(csv_text):
    """Parse + match + record + auto-approve. Returns a result dict suitable for chat display."""
    txns = parse_csv(csv_text)
    if not txns:
        return {"parsed": 0, "approved": [], "review": [], "no_ref": [], "duplicate": [], "error": "No incoming transactions detected. Check the CSV format."}

    approved = []
    review = []
    no_ref = []
    duplicates = []
    errors = []

    for txn in txns:
        ref = find_reference(txn["description"])
        if not ref:
            inserted = _record_transaction(txn, None, "no_ref")
            if inserted:
                no_ref.append({"amount": txn["amount"], "description": txn["description"][:60]})
            else:
                duplicates.append(txn["txn_ref"])
            continue

        # Look up registration by reference.
        try:
            reg = sb.find_by_reference(ref)
        except Exception as e:
            errors.append({"ref": ref, "error": str(e)})
            continue

        if not reg:
            inserted = _record_transaction(txn, ref, "no_ref")
            if inserted:
                no_ref.append({"amount": txn["amount"], "description": txn["description"][:60], "ref": ref, "note": "ref code not found"})
            continue

        # Validate amount matches the expected price.
        expected = sb._parse_price(reg.get("price"))
        if expected and txn["amount"] != expected:
            inserted = _record_transaction(txn, ref, "amount_mismatch", reg["id"])
            if inserted:
                review.append({"ref": ref, "expected": expected, "received": txn["amount"], "business": reg.get("business_name", "?"), "reason": "amount mismatch"})
            else:
                duplicates.append(ref)
            continue

        # Status check — only auto-approve if currently pending_verification.
        if reg.get("status") != "pending_verification":
            inserted = _record_transaction(txn, ref, "manual_review", reg["id"])
            if inserted:
                review.append({"ref": ref, "business": reg.get("business_name", "?"), "reason": f"status is '{reg.get('status')}', not pending_verification"})
            else:
                duplicates.append(ref)
            continue

        # All good — record and approve.
        inserted = _record_transaction(txn, ref, "matched", reg["id"])
        if not inserted:
            duplicates.append(ref)
            continue
        try:
            sb.approve_payment(ref)
            approved.append({"ref": ref, "business": reg.get("business_name", "?"), "amount": txn["amount"], "tier": reg.get("app_tier", "?"), "cycle": reg.get("billing_cycle", "monthly")})
        except Exception as e:
            errors.append({"ref": ref, "error": str(e)})

    return {
        "parsed": len(txns),
        "approved": approved,
        "review": review,
        "no_ref": no_ref,
        "duplicate": duplicates,
        "errors": errors,
    }


def format_result(r):
    """Pretty-print the process_csv result for a chat response."""
    if r.get("error"):
        return f"⚠️ {r['error']}"

    lines = [f"📥 Processed {r['parsed']} incoming transaction(s)"]

    if r["approved"]:
        lines.append("")
        lines.append(f"✓ Auto-approved {len(r['approved'])}:")
        for a in r["approved"]:
            lines.append(f"  • {a['ref']} — {a['business']} ({a['tier']} {a['cycle']}, Rp {a['amount']:,})")

    if r["review"]:
        lines.append("")
        lines.append(f"⚠️ {len(r['review'])} need manual review:")
        for v in r["review"]:
            if "expected" in v:
                lines.append(f"  • {v['ref']} — {v['business']} expected Rp {v['expected']:,} but got Rp {v['received']:,}")
            else:
                lines.append(f"  • {v['ref']} — {v['business']} ({v['reason']})")

    if r["no_ref"]:
        lines.append("")
        lines.append(f"❓ {len(r['no_ref'])} couldn't auto-match (no SL- code or unknown ref):")
        for n in r["no_ref"][:5]:
            note = f" [{n.get('note','no SL- code')}]" if n.get("note") else ""
            lines.append(f"  • Rp {n['amount']:,} — {n['description']}{note}")
        if len(r["no_ref"]) > 5:
            lines.append(f"  … and {len(r['no_ref']) - 5} more")

    if r["duplicate"]:
        lines.append("")
        lines.append(f"⏩ Skipped {len(r['duplicate'])} already-processed transaction(s)")

    if r["errors"]:
        lines.append("")
        lines.append(f"❌ {len(r['errors'])} errors:")
        for e in r["errors"][:3]:
            lines.append(f"  • {e.get('ref','?')}: {e.get('error','?')}")

    if not r["approved"] and not r["review"] and not r["no_ref"]:
        lines.append("")
        lines.append("(All transactions were already processed in a previous import.)")

    return "\n".join(lines)
