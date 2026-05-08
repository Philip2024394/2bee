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

# Add project root to path
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from brain.memory import init as init_memory, get_stats
from brain.thinking import process
from brain import learner
from brain import vault

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

        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass


BANNER = """
       =============================================
        2 B E E
        To Be, Or Not To Be. I Chose To Be.
       =============================================

        100% Local | Zero Third Party | Zero Cost
        The Seed of AI - Yours Forever

        DEPENDENCIES: Python (that's it)
        ACCOUNTS NEEDED: None
        MONTHLY COST: $0
        KILL SWITCH: None
"""


def main():
    print(BANNER)

    # Initialize brain
    init_memory()
    stats = get_stats()
    print(f"  Brain loaded:")
    print(f"    {stats['facts']} facts | {stats['responses']} responses | {stats['markov_chains']} patterns")

    # Start background learner
    learner.start()
    print(f"  Background learner: ON (learning from Wikipedia, RSS, public APIs)")

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
