"""
2B Vision — Analyze images using LLaVA via Ollama.
2B can now SEE images: describe layouts, read text, analyze colors, compare designs.
"""

import urllib.request
import json
import base64
import os


OLLAMA_URL = "http://localhost:11434"
VISION_MODEL = "llava"


def is_available():
    """Check if LLaVA vision model is loaded in Ollama."""
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m["name"] for m in data.get("models", [])]
            return any("llava" in m for m in models)
    except Exception:
        return False


def analyze_image_file(filepath, question="Describe this image in detail."):
    """Analyze a local image file using LLaVA."""
    if not os.path.exists(filepath):
        return None, "File not found"

    with open(filepath, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")

    return _call_llava(img_data, question)


def analyze_image_url(url, question="Describe this image in detail."):
    """Download and analyze an image from a URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "2B-AI/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            img_data = base64.b64encode(resp.read()).decode("utf-8")
        return _call_llava(img_data, question)
    except Exception as e:
        return None, f"Failed to download image: {e}"


def analyze_image_bytes(img_bytes, question="Describe this image in detail."):
    """Analyze image from raw bytes."""
    img_data = base64.b64encode(img_bytes).decode("utf-8")
    return _call_llava(img_data, question)


def _call_llava(img_base64, question):
    """Call Ollama LLaVA with an image."""
    try:
        payload = {
            "model": VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": question,
                    "images": [img_base64]
                }
            ],
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 500}
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            reply = result.get("message", {}).get("content", "").strip()
            return reply, None

    except Exception as e:
        return None, f"Vision analysis failed: {e}"


def analyze_theme(filepath_or_url, category=""):
    """Analyze a theme image specifically for design quality."""
    question = f"""Analyze this product theme image for a mobile app. Describe:
1. Layout: where are products positioned, text placement, header/footer areas
2. Colors: dominant colors, accent colors, background color, overall mood
3. Products: what products are shown, how many, how they're displayed
4. Text: any text visible, what language, what it says
5. Quality: is it professional, modern, clean? Rate 1-10
6. Suggestions: what could make this theme better for a {category or 'product'} store app
Keep response under 200 words."""

    if filepath_or_url.startswith("http"):
        return analyze_image_url(filepath_or_url, question)
    else:
        return analyze_image_file(filepath_or_url, question)
