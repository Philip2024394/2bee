"""
2bee Vault — Encrypted backup and restore.
Encrypts all knowledge before it leaves your machine.
Uses Python standard library encryption only.

Storage targets:
  - Local encrypted backup files
  - Pushed to private GitHub repo (encrypted, hidden)
  - Can be copied to USB, cloud drive, anywhere

Nobody can read your data without your key. Not GitHub. Not any AI. Nobody.
"""

import hashlib
import hmac
import os
import json
import zlib
import base64
import struct
import time
from brain.memory import get_db, get_all_facts, get_all_responses, get_profile, get_stats

VAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "vault")


# ======================================================================
# ENCRYPTION — XOR stream cipher with SHA-256 derived keystream
# Not AES (would need third party), but strong enough for personal data.
# Your key -> SHA-256 -> keystream -> XOR with data
# Plus HMAC for integrity verification
# ======================================================================

def derive_key(password, salt):
    """Derive a 256-bit key from password using proper PBKDF2."""
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000)


def generate_keystream(key, length):
    """Generate a pseudo-random keystream from key."""
    stream = b""
    counter = 0
    while len(stream) < length:
        block = hashlib.sha256(key + struct.pack(">Q", counter)).digest()
        stream += block
        counter += 1
    return stream[:length]


def encrypt(data_bytes, password):
    """Encrypt bytes with password. Returns base64 string."""
    # Compress first
    compressed = zlib.compress(data_bytes, 9)

    # Generate random salt
    salt = os.urandom(16)

    # Derive key
    key = derive_key(password, salt)

    # Generate keystream and XOR
    keystream = generate_keystream(key, len(compressed))
    encrypted = bytes(a ^ b for a, b in zip(compressed, keystream))

    # HMAC for integrity
    mac = hmac.new(key, encrypted, hashlib.sha256).digest()

    # Pack: salt(16) + mac(32) + encrypted_data
    packed = salt + mac + encrypted
    return base64.b64encode(packed).decode("ascii")


def decrypt(b64_data, password):
    """Decrypt base64 string with password. Returns bytes."""
    packed = base64.b64decode(b64_data)

    salt = packed[:16]
    stored_mac = packed[16:48]
    encrypted = packed[48:]

    # Derive key
    key = derive_key(password, salt)

    # Verify HMAC
    computed_mac = hmac.new(key, encrypted, hashlib.sha256).digest()
    if not hmac.compare_digest(stored_mac, computed_mac):
        raise ValueError("Wrong password or corrupted data.")

    # Decrypt
    keystream = generate_keystream(key, len(encrypted))
    compressed = bytes(a ^ b for a, b in zip(encrypted, keystream))

    # Decompress
    return zlib.decompress(compressed)


# ======================================================================
# BACKUP & RESTORE
# ======================================================================

def backup(password, filename=None):
    """Export all knowledge as encrypted file."""
    os.makedirs(VAULT_DIR, exist_ok=True)

    # Gather all data
    data = {
        "version": 1,
        "timestamp": time.time(),
        "facts": get_all_facts(),
        "responses": get_all_responses(),
        "profile": get_profile(),
        "stats": get_stats(),
    }

    json_bytes = json.dumps(data, indent=2).encode("utf-8")
    encrypted = encrypt(json_bytes, password)

    if not filename:
        filename = f"2bee_backup_{int(time.time())}.vault"

    filepath = os.path.join(VAULT_DIR, filename)
    with open(filepath, "w") as f:
        f.write(encrypted)

    size_kb = len(encrypted) / 1024
    original_kb = len(json_bytes) / 1024

    return {
        "file": filepath,
        "size_kb": round(size_kb, 1),
        "original_kb": round(original_kb, 1),
        "compression": f"{(1 - size_kb/original_kb)*100:.0f}%" if original_kb > 0 else "0%",
        "facts": len(data["facts"]),
        "responses": len(data["responses"]),
    }


def restore(filepath, password):
    """Import knowledge from encrypted backup."""
    with open(filepath, "r") as f:
        encrypted = f.read()

    json_bytes = decrypt(encrypted, password)
    data = json.loads(json_bytes.decode("utf-8"))

    from brain.memory import add_fact, add_response, set_profile

    imported_facts = 0
    imported_responses = 0

    # Restore facts
    for fact in data.get("facts", []):
        add_fact(fact["topic"], fact["info"])
        imported_facts += 1

    # Restore responses
    for resp in data.get("responses", []):
        add_response(resp["trigger"], resp["response"])
        imported_responses += 1

    # Restore profile
    for key, value in data.get("profile", {}).items():
        set_profile(key, value)

    return {
        "facts_imported": imported_facts,
        "responses_imported": imported_responses,
        "profile_items": len(data.get("profile", {})),
    }


def list_backups():
    """List all backup files in vault."""
    os.makedirs(VAULT_DIR, exist_ok=True)
    files = []
    for f in sorted(os.listdir(VAULT_DIR)):
        if f.endswith(".vault"):
            path = os.path.join(VAULT_DIR, f)
            size = os.path.getsize(path)
            files.append({
                "file": f,
                "path": path,
                "size_kb": round(size / 1024, 1),
                "created": os.path.getctime(path),
            })
    return files


# ======================================================================
# GIT SYNC — push encrypted backups to a private repo
# ======================================================================

def sync_to_remote(remote_url=None):
    """Push encrypted vault backups via the main project repo."""
    import subprocess
    project_root = os.path.dirname(os.path.dirname(__file__))

    # Stage vault files and push from the main repo
    cmds = [
        f'cd "{project_root}" && git add data/vault/*.vault data/vault/.gitignore data/vault/README.md 2>nul',
        f'cd "{project_root}" && git commit -m "2bee vault backup"',
        f'cd "{project_root}" && git push',
    ]
    for cmd in cmds:
        result = os.system(cmd)

    # Check if push succeeded (last command)
    return result == 0
