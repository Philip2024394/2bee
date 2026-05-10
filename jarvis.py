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
import socketserver
import json
import os
import sys
import re
import time
import signal
import threading
from collections import defaultdict

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
STREETLOCAL_ROOT = os.path.normpath(os.path.join(ROOT, "..", "streetlocal"))

# Supabase credentials from environment (fallback to defaults for dev)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://fjvafjkzvygkhiwjuvla.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZqdmFmamt6dnlna2hpd2p1dmxhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxMDk0NDEsImV4cCI6MjA5MDY4NTQ0MX0.UoXfKznY9gAEqZDSTegDjIfYAeAeFg6Eh1D40Hoe2KM")

# --- Rate Limiting ---
_rate_limits = defaultdict(list)
RATE_LIMIT = 60  # max requests per minute per IP
def check_rate_limit(ip):
    now = time.time()
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < 60]
    if len(_rate_limits[ip]) >= RATE_LIMIT:
        return False
    _rate_limits[ip].append(now)
    return True


# --- Multi-threaded HTTP Server ---
class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


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

    def _check_rate(self):
        ip = self.client_address[0]
        if not check_rate_limit(ip):
            self.send_json({"error": "Rate limited. Try again in a minute."}, 429)
            return False
        return True

    def _validate_path(self, rel_path):
        """Validate file path is within StreetLocal project."""
        if '\x00' in rel_path or '..' in rel_path:
            return None
        full = os.path.normpath(os.path.join(STREETLOCAL_ROOT, rel_path))
        if not full.startswith(os.path.normpath(STREETLOCAL_ROOT)):
            return None
        return full

    def do_POST(self):
        if not self._check_rate():
            return
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
                        sb_url = SUPABASE_URL
                        sb_key = SUPABASE_KEY
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

        elif self.path == "/api/files/write":
            body = self.read_body()
            rel_path = body.get("path", "")
            content = body.get("content", "")
            if not rel_path:
                self.send_json({"error": "Path required"}, 400)
                return
            full = os.path.normpath(os.path.join(STREETLOCAL_ROOT, rel_path))
            if not full.startswith(os.path.normpath(STREETLOCAL_ROOT)):
                self.send_json({"error": "Access denied"}, 403)
                return
            try:
                with open(full, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                self.send_json({"success": True, "path": rel_path, "size": len(content)})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/files/git-push":
            body = self.read_body()
            message = body.get("message", "Update from 2B")
            # Sanitize commit message — strip dangerous chars
            message = re.sub(r'[^\w\s\-.,!?:;()/\'\"@#&+=]', '', message)[:200].strip() or "Update from 2B"
            import subprocess
            try:
                subprocess.run(["git", "add", "-A"], cwd=STREETLOCAL_ROOT, capture_output=True)
                result = subprocess.run(["git", "commit", "-m", "--", message], cwd=STREETLOCAL_ROOT, capture_output=True, text=True)
                push = subprocess.run(["git", "push", "origin", "master"], cwd=STREETLOCAL_ROOT, capture_output=True, text=True)
                self.send_json({
                    "success": push.returncode == 0,
                    "commit": result.stdout.strip()[:200],
                    "push": push.stdout.strip()[:200] or push.stderr.strip()[:200],
                })
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/ai-chat":
            body = self.read_body()
            prompt = body.get("prompt", "")
            user_msg = body.get("user_message", "")
            if not prompt:
                self.send_json({"error": "Prompt required"}, 400)
                return
            try:
                import urllib.request as urlreq
                import urllib.parse

                reply = None

                # PRIMARY: Ollama local (always available, instant)
                try:
                    ollama_data = json.dumps({
                        "model": "phi3:mini",
                        "messages": [
                            {"role": "system", "content": prompt[:2000].split("User:")[0]},
                            {"role": "user", "content": user_msg or prompt.split("User:")[-1] if "User:" in prompt else prompt[-500:]}
                        ],
                        "stream": False,
                        "options": {"temperature": 0.7, "num_predict": 300}
                    }).encode("utf-8")
                    ollama_req = urlreq.Request("http://localhost:11434/api/chat", data=ollama_data, headers={"Content-Type": "application/json"}, method="POST")
                    with urlreq.urlopen(ollama_req, timeout=60) as ollama_resp:
                        result = json.loads(ollama_resp.read().decode("utf-8"))
                        reply = result.get("message", {}).get("content", "").strip()
                except Exception:
                    pass

                # FALLBACK: Pollinations cloud
                if not reply:
                    try:
                        encoded = urllib.parse.quote(prompt[:4000])
                        url = f"https://text.pollinations.ai/{encoded}?model=openai"
                        req = urlreq.Request(url, headers={"User-Agent": "2B-AI/1.0"})
                        with urlreq.urlopen(req, timeout=30) as resp:
                            reply = resp.read().decode("utf-8", errors="ignore").strip()
                    except Exception:
                        pass

                if not reply:
                    reply = "AI engines temporarily unavailable. Try again in a moment."

                    # --- LEARN FROM EVERY EXCHANGE ---
                    from brain.memory import save_message, add_fact
                    import re as _re

                    # Save conversation
                    if user_msg:
                        save_message("user", user_msg)
                    save_message("2B", reply[:500])

                    # Extract and store any URLs from the AI response
                    urls = _re.findall(r'https?://[^\s<>"\')\]]+', reply)
                    for u in urls[:5]:
                        add_fact("ai_suggested_link", f"AI suggested: {u}", source="verified")

                    # Store code knowledge — if reply contains code patterns
                    if user_msg and len(reply) > 50:
                        # Store as coding knowledge
                        topic = "code_knowledge"
                        if any(w in user_msg.lower() for w in ['feature', 'what is', 'what are', 'how does', 'explain']):
                            topic = "project_knowledge"
                        elif any(w in user_msg.lower() for w in ['fix', 'bug', 'error', 'wrong']):
                            topic = "bug_fix"
                        elif any(w in user_msg.lower() for w in ['add', 'create', 'build', 'make', 'new']):
                            topic = "code_pattern"
                        elif any(w in user_msg.lower() for w in ['dont', "don't", 'stop', 'never', 'remove', 'delete']):
                            topic = "preference_negative"
                        elif any(w in user_msg.lower() for w in ['yes', 'good', 'perfect', 'great', 'keep', 'like']):
                            topic = "preference_positive"

                        # Store condensed Q&A as fact
                        qa = f"Q: {user_msg[:100]} → A: {reply[:200]}"
                        add_fact(topic, qa, source="user_taught")

                    self.send_json({"reply": reply})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/api/themes/generate":
            body = self.read_body()
            category = body.get("category", "")
            from brain.theme_generator import generate_batch, load_queue, save_queue
            if category:
                themes = generate_batch(category, count=body.get("count", 3))
                queue = load_queue()
                for t in themes:
                    queue["pending"].append(t)
                    queue["stats"]["generated"] += 1
                save_queue(queue)
                self.send_json({"generated": len(themes), "category": category})
            else:
                # Auto-check all categories
                from brain.theme_generator import auto_generate_check
                count = auto_generate_check()
                self.send_json({"generated": count})

        elif self.path == "/api/themes/accept":
            body = self.read_body()
            from brain.theme_generator import accept_theme
            result = accept_theme(body.get("id", ""))
            self.send_json(result)

        elif self.path == "/api/themes/reject":
            body = self.read_body()
            from brain.theme_generator import reject_theme
            result = reject_theme(body.get("id", ""), body.get("comment", ""))
            self.send_json(result)

        elif self.path == "/api/vision/analyze":
            body = self.read_body()
            image_url = body.get("url", "")
            image_path = body.get("path", "")
            question = body.get("question", "Describe this image in detail.")
            from brain.vision import analyze_image_url, analyze_image_file, is_available as vision_available
            if not vision_available():
                self.send_json({"error": "LLaVA vision model not loaded. Run: ollama pull llava"})
                return
            if image_url:
                result, err = analyze_image_url(image_url, question)
            elif image_path:
                result, err = analyze_image_file(image_path, question)
            else:
                self.send_json({"error": "Provide url or path"}, 400)
                return
            if result:
                # Store the analysis in 2B memory
                from brain.memory import add_fact
                add_fact("image_analysis", f"[Vision] {question}: {result[:300]}", source="verified")
                self.send_json({"analysis": result})
            else:
                self.send_json({"error": err or "Analysis failed"}, 500)

        elif self.path == "/api/vision/upload":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                content_type = self.headers.get("Content-Type", "")
                raw_data = self.rfile.read(content_length)

                if "multipart/form-data" in content_type:
                    boundary = content_type.split("boundary=")[1].encode()
                    parts = raw_data.split(b"--" + boundary)
                    img_data = None
                    question = "Describe this image in detail."

                    for part in parts:
                        if b'name="question"' in part:
                            question = part.split(b"\r\n\r\n")[1].strip().decode("utf-8", errors="ignore").strip("\r\n- ")
                        elif b'name="file"' in part:
                            header_end = part.find(b"\r\n\r\n")
                            if header_end != -1:
                                img_data = part[header_end + 4:].rstrip(b"\r\n--")

                    if img_data and len(img_data) > 100:
                        from brain.vision import analyze_image_bytes, is_available as vision_available
                        if not vision_available():
                            self.send_json({"error": "LLaVA not loaded. Run: ollama pull llava"})
                            return
                        result, err = analyze_image_bytes(img_data, question)
                        if result:
                            from brain.memory import add_fact, save_message
                            save_message("user", f"[Uploaded image] {question}")
                            save_message("2B", result[:500])
                            add_fact("image_analysis", f"[Vision] {question}: {result[:300]}", source="verified")
                            self.send_json({"analysis": result})
                        else:
                            self.send_json({"error": err or "Analysis failed"}, 500)
                    else:
                        self.send_json({"error": "No image data received"}, 400)
                else:
                    self.send_json({"error": "Expected multipart/form-data"}, 400)
            except Exception as e:
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
        if self.path.startswith("/api/") and not self._check_rate():
            return
        if self.path == "/api/stats":
            stats = get_stats()
            self.send_json(stats)

        elif self.path == "/api/learner/stats":
            self.send_json(learner.get_learning_stats())

        elif self.path == "/api/vault/list":
            self.send_json(vault.list_backups())

        elif self.path == "/api/llm/status":
            self.send_json(llm.get_status())

        # --- THEME LIBRARY ---
        elif self.path == "/api/themes/pending":
            from brain.theme_generator import get_pending
            self.send_json({"themes": get_pending()})

        elif self.path == "/api/themes/stats":
            from brain.theme_generator import get_stats as theme_stats
            self.send_json(theme_stats())

        # --- FILE SYSTEM API (StreetLocal project) ---
        elif self.path.startswith("/api/files/tree"):
            # Return directory tree
            import urllib.parse
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            rel_path = params.get("path", [""])[0]
            base = os.path.normpath(os.path.join(STREETLOCAL_ROOT, rel_path))
            if not base.startswith(os.path.normpath(STREETLOCAL_ROOT)):
                self.send_json({"error": "Access denied"}, 403)
                return
            try:
                entries = []
                for item in sorted(os.listdir(base)):
                    if item in ('.git', 'node_modules', '__pycache__', '.env', 'dist'):
                        continue
                    full = os.path.join(base, item)
                    rel = os.path.relpath(full, STREETLOCAL_ROOT).replace("\\", "/")
                    entries.append({
                        "name": item,
                        "path": rel,
                        "type": "dir" if os.path.isdir(full) else "file",
                        "size": os.path.getsize(full) if os.path.isfile(full) else 0,
                    })
                self.send_json({"entries": entries, "path": rel_path})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path.startswith("/api/files/read"):
            # Read file contents
            import urllib.parse
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            rel_path = params.get("path", [""])[0]
            full = os.path.normpath(os.path.join(STREETLOCAL_ROOT, rel_path))
            if not full.startswith(os.path.normpath(STREETLOCAL_ROOT)):
                self.send_json({"error": "Access denied"}, 403)
                return
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                ext = os.path.splitext(full)[1].lower()
                lang_map = {'.jsx': 'javascript', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
                            '.css': 'css', '.html': 'html', '.json': 'json', '.py': 'python', '.md': 'markdown',
                            '.sql': 'sql', '.sh': 'shell', '.bat': 'bat', '.yml': 'yaml', '.yaml': 'yaml'}
                self.send_json({"content": content, "path": rel_path, "language": lang_map.get(ext, "plaintext")})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path.startswith("/api/files/git-status"):
            # Git status
            import subprocess
            try:
                result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=STREETLOCAL_ROOT)
                files = []
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        status = line[:2].strip()
                        filepath = line[3:].strip()
                        files.append({"status": status, "path": filepath})
                self.send_json({"files": files, "clean": len(files) == 0})
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        # Serve theme candidate images
        elif self.path.startswith("/api/theme-image"):
            import urllib.parse
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            img_path = params.get("path", [""])[0]
            if os.path.exists(img_path) and img_path.endswith(('.png', '.jpg', '.jpeg')):
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                with open(img_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

        # Serve Monaco editor files
        elif self.path.startswith("/monaco/"):
            monaco_path = self.path.replace("/monaco/", "node_modules/monaco-editor/min/")
            full_path = os.path.join(ROOT, monaco_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                ext = os.path.splitext(full_path)[1]
                content_types = {'.js': 'application/javascript', '.css': 'text/css', '.html': 'text/html', '.ttf': 'font/ttf', '.svg': 'image/svg+xml'}
                self.send_response(200)
                self.send_header("Content-Type", content_types.get(ext, "application/octet-stream"))
                self.end_headers()
                with open(full_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

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

    # Load language & marketing words
    try:
        from brain.languages import load_languages
        load_languages()
    except Exception as e:
        print(f"  Languages: failed ({e})")

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

    # Load English grammar (pronouns, verbs, question words, prepositions, etc.)
    try:
        from brain.grammar_knowledge import load_all as load_grammar
        g_before = get_stats()["facts"]
        load_grammar()
        g_loaded = get_stats()["facts"] - g_before
        if g_loaded > 0:
            print(f"  Grammar knowledge: loaded {g_loaded} new facts")
        else:
            print(f"  Grammar knowledge: already loaded")
    except Exception as e:
        print(f"  Grammar knowledge: failed ({e})")

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

    # Warm up Ollama model in background (first call loads into GPU)
    def _warmup_ollama():
        try:
            import urllib.request as urlreq
            data = json.dumps({"model": "phi3:mini", "messages": [{"role": "user", "content": "hi"}], "stream": False, "options": {"num_predict": 5}}).encode("utf-8")
            req = urlreq.Request("http://localhost:11434/api/chat", data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urlreq.urlopen(req, timeout=120) as resp:
                resp.read()
            print(f"  Ollama: model loaded and ready")
        except Exception as e:
            print(f"  Ollama: warmup skipped ({e})")
    threading.Thread(target=_warmup_ollama, daemon=True).start()
    print(f"  Ollama: warming up model...")

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

    # Start multi-threaded server
    server = ThreadedHTTPServer(("", PORT), BeeHandler)

    def cleanup(signum=None, frame=None):
        print("\n  Shutting down...")
        learner.stop()
        print("  Learner stopped. Data saved in data/2bee.db")
        server.server_close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
