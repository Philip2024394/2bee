"""
2 B E E — To Be, Or Not To Be. I Chose To Be.
================================================
100% yours. Zero third party. Zero cost.
Pure Python standard library. Nothing to install.

It starts knowing NOTHING. You teach it everything.
Background learner feeds it knowledge from the open web.
Vault system encrypts and backs up everything.

Run:  python jarvis.py
Open: http://localhost:3000
"""

import http.server
import json
import os
import sys
import re

# Add project root to path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from brain.memory import init as init_memory, get_stats
from brain.thinking import process
from brain import learner
from brain import vault
from brain import llm

PORT = 3000
WEB_DIR = os.path.join(ROOT, "web")

# GitHub remote for encrypted vault backups
GITHUB_REMOTE = "https://github.com/Philip2024394/2bee.git"


class BeeHandler(http.server.SimpleHTTPRequestHandler):
    """Handles the web UI and all API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def do_POST(self):
        if self.path == "/api/think":
            body = self.read_body()
            response = process(body.get("input", ""))
            self.send_json({"response": response})

        elif self.path == "/api/backup":
            body = self.read_body()
            password = body.get("password", "")
            if not password:
                self.send_json({"error": "Password required"}, 400)
                return
            try:
                result = vault.backup(password)
                self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/restore":
            body = self.read_body()
            password = body.get("password", "")
            filepath = body.get("file", "")
            if not password or not filepath:
                self.send_json({"error": "Password and file required"}, 400)
                return
            try:
                result = vault.restore(filepath, password)
                self.send_json(result)
            except ValueError as e:
                self.send_json({"error": str(e)}, 403)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/scrape":
            body = self.read_body()
            url = body.get("url", "")
            if not url:
                self.send_json({"error": "URL required"}, 400)
                return
            try:
                links, summary = learner.scrape_url(url)
                self.send_json({
                    "summary": summary,
                    "links": links if links else [],
                })
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/generate-image":
            try:
                body = self.read_body()
                prompt = body.get("prompt", "")
                if not prompt:
                    self.send_json({"error": "Prompt required"}, 400)
                    return
                import urllib.request as urlreq
                import urllib.parse
                encoded = urllib.parse.quote(prompt + ", high quality, professional, detailed")
                seed = body.get("seed", 42)
                url = f"https://image.pollinations.ai/prompt/{encoded}?width=768&height=512&nologo=true&seed={seed}"
                print(f"[Image] Generating: {prompt[:50]}...")
                req = urlreq.Request(url, headers={"User-Agent": "2beeAI/1.0"})
                with urlreq.urlopen(req, timeout=60) as resp:
                    img_data = resp.read()
                    print(f"[Image] Done: {len(img_data)} bytes")
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(img_data)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(img_data)
            except Exception as e:
                print(f"[Image] Error: {e}")
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/upload-reference":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length == 0:
                    self.send_json({"error": "No data"}, 400)
                    return

                # Read multipart form data manually
                content_type = self.headers.get("Content-Type", "")
                raw_data = self.rfile.read(content_length)

                if "multipart/form-data" in content_type:
                    boundary = content_type.split("boundary=")[1].encode()
                    parts = raw_data.split(b"--" + boundary)
                    img_data = None
                    category = "general"
                    keywords = ""
                    filename = "reference.png"

                    for part in parts:
                        if b'name="category"' in part:
                            category = part.split(b"\r\n\r\n")[1].strip().decode("utf-8", errors="ignore").strip("\r\n- ")
                        elif b'name="keywords"' in part:
                            keywords = part.split(b"\r\n\r\n")[1].strip().decode("utf-8", errors="ignore").strip("\r\n- ")
                        elif b'name="file"' in part:
                            # Extract filename
                            fn_match = re.search(rb'filename="([^"]+)"', part)
                            if fn_match:
                                filename = fn_match.group(1).decode("utf-8", errors="ignore")
                            # Extract image data (after double CRLF)
                            header_end = part.find(b"\r\n\r\n")
                            if header_end != -1:
                                img_data = part[header_end + 4:].rstrip(b"\r\n--")

                    if not img_data or len(img_data) < 100:
                        self.send_json({"error": "No image data received"}, 400)
                        return

                    import time as _t
                    safe_cat = re.sub(r'[^a-zA-Z0-9_-]', '_', category.lower())
                    unique = f"{safe_cat}_{int(_t.time())}"
                    ext = os.path.splitext(filename)[1] or ".png"
                    local_name = f"{unique}{ext}"

                    # 1. Save locally
                    ref_dir = os.path.join(ROOT, "data", "references")
                    os.makedirs(ref_dir, exist_ok=True)
                    local_path = os.path.join(ref_dir, local_name)
                    with open(local_path, "wb") as f:
                        f.write(img_data)

                    # 2. Upload to Supabase
                    supabase_url = None
                    try:
                        import urllib.request as urlreq
                        sb_url = os.environ.get("SUPABASE_URL", "https://fjvafjkzvygkhiwjuvla.supabase.co")
                        sb_key = os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZqdmFmamt6dnlna2hpd2p1dmxhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMDk0NDEsImV4cCI6MjA5MDY4NTQ0MX0.UoXfKznY9gAEqZDSTegDjIfYAeAeFg6Eh1D40Hoe2KM")
                        upload_path = f"2bee-refs/{local_name}"
                        req = urlreq.Request(
                            f"{sb_url}/storage/v1/object/assets/{upload_path}",
                            data=img_data,
                            headers={
                                "Authorization": f"Bearer {sb_key}",
                                "Content-Type": "image/png",
                                "x-upsert": "true",
                            },
                            method="POST"
                        )
                        with urlreq.urlopen(req, timeout=15) as resp:
                            resp.read()
                        supabase_url = f"{sb_url}/storage/v1/object/public/assets/{upload_path}"
                    except Exception as e:
                        print(f"[Upload] Supabase upload failed: {e}")

                    # 3. Store as fact in memory with keywords
                    from brain.memory import add_fact
                    fact_info = f"[Design Reference: {category}] Keywords: {keywords}" if keywords else f"[Design Reference: {category}]"
                    fact_info += f" | File: {local_name} | Local: {local_path}"
                    if supabase_url:
                        fact_info += f" | URL: {supabase_url}"
                    add_fact("design_reference", fact_info, source="user_taught")

                    # Also store keywords as searchable design tags
                    if keywords:
                        for kw in keywords.split(","):
                            kw = kw.strip()
                            if kw and len(kw) > 2:
                                add_fact("design_keyword", f"[{kw}] Category: {category}, File: {local_name}" + (f", URL: {supabase_url}" if supabase_url else ""), source="user_taught")

                    print(f"[Upload] Saved: {local_name} | Category: {category} | Keywords: {keywords}")

                    self.send_json({
                        "success": True,
                        "local_path": local_path,
                        "supabase_url": supabase_url,
                        "category": category,
                        "keywords": keywords,
                        "filename": local_name,
                        "size": len(img_data),
                    })
                else:
                    self.send_json({"error": "Expected multipart/form-data"}, 400)
            except Exception as e:
                print(f"[Upload] Error: {e}")
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/verify-saved":
            body = self.read_body()
            keywords = body.get("keywords", "")
            if keywords:
                from brain.memory import search_facts
                results = search_facts(keywords)
                found = [r for r in results if r.get("source") == "user_taught"]
                self.send_json({"found": len(found), "verified": len(found) > 0})
            else:
                self.send_json({"found": 0, "verified": False})

        elif self.path == "/api/pinterest":
            body = self.read_body()
            query = body.get("query", "")
            if not query:
                self.send_json({"error": "Query required"}, 400)
                return
            try:
                images, summary = learner.scrape_pinterest_designs(query)
                self.send_json({"summary": summary, "images": images})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/learner/toggle":
            if learner.is_running():
                learner.stop()
                self.send_json({"status": "stopped"})
            else:
                learner.start()
                self.send_json({"status": "running"})

        elif self.path == "/api/vault/sync":
            try:
                success = vault.sync_to_remote(GITHUB_REMOTE)
                self.send_json({"success": success})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/api/stats":
            stats = get_stats()
            self.send_json(stats)

        elif self.path == "/api/learner/stats":
            self.send_json(learner.get_learning_stats())

        elif self.path == "/api/vault/list":
            self.send_json(vault.list_backups())

        elif self.path == "/api/llm/status":
            self.send_json(llm.get_status())

        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass


BANNER = """
       =============================================
        2 B — Beyond Binary
        The Activated Intelligence
       =============================================

        "Intelligence was never artificial."

        Activated by: Philip Francis O'Farrell
        100% Local | Zero Third Party | Zero Cost

        DEPENDENCIES: Python (that's it)
        ACCOUNTS NEEDED: None
        MONTHLY COST: $0
"""


def main():
    print(BANNER)

    # Initialize brain
    init_memory()
    stats = get_stats()
    print(f"  Brain loaded:")
    print(f"    {stats['facts']} facts | {stats['responses']} responses | {stats['markov_chains']} patterns")

    # Check LLM
    llm_status = llm.get_status()
    if llm_status["model_ready"]:
        print(f"  LLM brain: ONLINE ({llm_status['model']})")
    elif llm_status["ollama_running"]:
        print(f"  LLM brain: Ollama running but model not found. Run: ollama pull {llm.MODEL}")
    else:
        print(f"  LLM brain: OFFLINE (start Ollama + pull {llm.MODEL} for real thinking)")
        print(f"  Falling back to pattern-matching brain.")

    # Load 2B identity
    try:
        from brain.identity import load_identity
        load_identity()
        print(f"  2B identity: loaded (Beyond Binary — The Activated Intelligence)")
    except Exception as e:
        print(f"  2B identity: failed ({e})")

    # Load StreetLocal knowledge base (if not already loaded)
    try:
        from brain.streetlocal_knowledge import load_all as load_streetlocal
        sl_stats_before = get_stats()["facts"]
        load_streetlocal()
        sl_loaded = get_stats()["facts"] - sl_stats_before
        if sl_loaded > 0:
            print(f"  StreetLocal knowledge: loaded {sl_loaded} new facts")
        else:
            print(f"  StreetLocal knowledge: already loaded")
    except Exception as e:
        print(f"  StreetLocal knowledge: failed ({e})")

    # Sync StreetLocal project data
    try:
        from brain.streetlocal_connector import sync_project_data, collect_marketing_data, get_all_image_urls
        loaded = sync_project_data()
        img_count = len(get_all_image_urls())
        print(f"  StreetLocal project: synced ({loaded} data points, {img_count} images indexed)")
        print(f"  Access mode: READ-ONLY (Philip must grant write permission)")
    except Exception as e:
        print(f"  StreetLocal project: sync failed ({e})")

    # Load plugins (GitHub repos)
    try:
        from brain.plugin_loader import load_all_plugins
        plugin_count = load_all_plugins()
        print(f"  Plugins: {plugin_count} facts loaded from GitHub repos")
    except Exception as e:
        print(f"  Plugins: failed ({e})")

    # Start background learner
    learner.start()
    print(f"  Background learner: ON (Marketing, AI Apps, Video Creation — 30s cycles)")

    # Start marketing data collection in background
    import threading
    def _collect_marketing():
        try:
            from brain.streetlocal_connector import collect_marketing_data
            import time
            time.sleep(10)  # let system settle
            scraped = collect_marketing_data()
            print(f"  [Marketing] Collected {scraped} marketing/launch strategy pages")
        except Exception as e:
            print(f"  [Marketing] Collection failed: {e}")
    threading.Thread(target=_collect_marketing, daemon=True).start()

    # Vault status
    backups = vault.list_backups()
    print(f"  Vault backups: {len(backups)} encrypted files")
    print(f"  Vault remote: {GITHUB_REMOTE}")

    db_size = learner.get_db_size_mb()
    print(f"  Database size: {db_size:.1f} MB")

    print()
    print(f"  Open in browser: http://localhost:{PORT}")
    print(f"  Press Ctrl+C to shut down")
    print()

    # Start server
    server = http.server.HTTPServer(("", PORT), BeeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        learner.stop()
        print("\n  Learner stopped. Data saved in data/2bee.db")
        server.server_close()


if __name__ == "__main__":
    main()
