"""
2B Plugin Loader — Ingests knowledge from downloaded GitHub repos.
Reads README files, markdown docs, and code examples.
Stores everything as searchable facts in 2B's memory.
"""

import os
import re
from brain.memory import add_fact, search_facts

PLUGINS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "plugins")


def read_markdown(filepath, max_len=2000):
    """Read and clean a markdown file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        # Strip HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Strip markdown image links
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        # Strip excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text[:max_len].strip()
    except Exception:
        return None


def ingest_repo(repo_dir, topic, max_files=20):
    """Ingest a GitHub repo into 2B's memory."""
    if not os.path.exists(repo_dir):
        return 0

    stored = 0

    # 1. Read README
    for readme_name in ["README.md", "readme.md", "Readme.md", "README.rst"]:
        readme_path = os.path.join(repo_dir, readme_name)
        if os.path.exists(readme_path):
            content = read_markdown(readme_path, 3000)
            if content:
                # Split into chunks
                chunks = content.split('\n\n')
                for chunk in chunks[:15]:
                    chunk = chunk.strip()
                    if len(chunk) > 30:
                        add_fact(topic, chunk, source="verified")
                        stored += 1
            break

    # 2. Read docs directory
    docs_dirs = ["docs", "doc", "documentation", "guides"]
    for dd in docs_dirs:
        docs_path = os.path.join(repo_dir, dd)
        if os.path.isdir(docs_path):
            files_read = 0
            for root, dirs, files in os.walk(docs_path):
                for f in sorted(files):
                    if files_read >= max_files:
                        break
                    if f.endswith(('.md', '.txt', '.rst')):
                        content = read_markdown(os.path.join(root, f), 1500)
                        if content and len(content) > 50:
                            # Store key paragraphs
                            paragraphs = content.split('\n\n')
                            for p in paragraphs[:5]:
                                p = p.strip()
                                if len(p) > 30:
                                    add_fact(topic, f"[{f}] {p}", source="verified")
                                    stored += 1
                            files_read += 1

    # 3. Read any Python scripts for capabilities
    py_files = []
    for root, dirs, files in os.walk(repo_dir):
        # Skip node_modules, .git, __pycache__
        dirs[:] = [d for d in dirs if d not in ('node_modules', '.git', '__pycache__', 'venv', '.venv')]
        for f in files:
            if f.endswith('.py') and not f.startswith('test'):
                py_files.append(os.path.join(root, f))

    for pyf in py_files[:10]:
        try:
            with open(pyf, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read(2000)
            # Extract docstrings and function names
            docstrings = re.findall(r'"""(.*?)"""', code, re.DOTALL)
            functions = re.findall(r'def (\w+)\(', code)
            if docstrings:
                for ds in docstrings[:3]:
                    ds = ds.strip()[:200]
                    if len(ds) > 20:
                        add_fact(topic, f"[Code] {ds}", source="verified")
                        stored += 1
            if functions:
                func_list = ", ".join(functions[:10])
                add_fact(topic, f"[Functions in {os.path.basename(pyf)}] {func_list}", source="verified")
                stored += 1
        except Exception:
            pass

    return stored


def load_all_plugins():
    """Load all downloaded plugins into 2B's memory."""
    if not os.path.exists(PLUGINS_DIR):
        print("[Plugins] No plugins directory found.")
        return 0

    total = 0
    repos = {
        "ai-marketing-skills": "marketing",
        "screenshot-to-code": "design_tools",
        "awesome-opensource-ai": "ai_tools",
        "awesome-ai-tools": "ai_tools",
        "no-cost-ai": "free_ai_services",
    }

    for repo_name, topic in repos.items():
        repo_path = os.path.join(PLUGINS_DIR, repo_name)
        if os.path.exists(repo_path):
            count = ingest_repo(repo_path, topic)
            total += count
            print(f"  [Plugin] {repo_name}: {count} facts loaded ({topic})")
        else:
            print(f"  [Plugin] {repo_name}: not found, skipping")

    return total


if __name__ == "__main__":
    from brain.memory import init
    init()
    total = load_all_plugins()
    print(f"\n[OK] Total: {total} facts loaded from plugins")
