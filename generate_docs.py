# generate_docs.py (Enhanced for versioning and GitHub commit)

import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
import google.generativeai as genai

# === Configuration ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
REPO_ROOT = Path(__file__).parent
OUTPUT_DIR = REPO_ROOT / "outputs" / "html"
DOCS_DIR = REPO_ROOT / "docs"
SUMMARY_MD = REPO_ROOT / "AUTODOCS_SUMMARY.md"
DOXYFILE_PATH = REPO_ROOT / "Doxyfile"
INPUT_DIR = REPO_ROOT / "source"

GITHUB_SHA = os.getenv("GITHUB_SHA", "dev")
VERSION_TAG = f"v-{GITHUB_SHA[:7]}"
LATEST_DIR = DOCS_DIR / "latest"
VERSIONED_DIR = DOCS_DIR / VERSION_TAG

# === Setup Gemini ===
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# === Generate Doxygen HTML ===
def run_doxygen():
    doxy_content = f"""
    PROJECT_NAME = AutoDocs
    OUTPUT_DIRECTORY = {OUTPUT_DIR.parent}
    INPUT = {INPUT_DIR}
    RECURSIVE = YES
    GENERATE_HTML = YES
    HAVE_DOT = YES
    CLASS_DIAGRAMS = YES
    CALL_GRAPH = YES
    CALLER_GRAPH = YES
    COLLABORATION_GRAPH = YES
    INCLUDE_GRAPH = YES
    INCLUDED_BY_GRAPH = YES
    GRAPHICAL_HIERARCHY = YES
    DOT_IMAGE_FORMAT = svg
    INTERACTIVE_SVG = YES
    """
    with open(DOXYFILE_PATH, "w") as f:
        f.write(doxy_content)

    subprocess.run(["doxygen", str(DOXYFILE_PATH)], check=True)

# === Extract and Summarize ===
def extract_text(folder):
    content = []
    for file in Path(folder).rglob("*.html"):
        with open(file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            content.append(soup.get_text())
    return "\n\n".join(content)[:12000]

# === Save HTML docs to /docs/version/ and /docs/latest ===
def save_docs():
    if LATEST_DIR.exists():
        shutil.rmtree(LATEST_DIR)
    shutil.copytree(OUTPUT_DIR, LATEST_DIR)

    if VERSIONED_DIR.exists():
        shutil.rmtree(VERSIONED_DIR)
    shutil.copytree(OUTPUT_DIR, VERSIONED_DIR)

# === Generate Markdown Summary ===
def generate_markdown(summary_text, classes_text, todos_text, legend_text):
    with open(SUMMARY_MD, "w", encoding="utf-8") as md:
        md.write(f"# AutoDocs Summary (via Gemini + Doxygen)\n\n")
        md.write(f"### 🔖 Version: `{VERSION_TAG}`\n\n")
        md.write(f"📂 [View HTML Docs](/docs/{VERSION_TAG}/index.html)\n\n")
        md.write("## 📄 Summary\n\n" + summary_text + "\n\n")
        md.write("## 📚 Classes & Interfaces\n\n" + classes_text + "\n\n")
        md.write("## ❗ TODOs & Undocumented Items\n\n" + todos_text + "\n\n")
        md.write("## 📊 Dependency Graph Overview\n\n" + legend_text + "\n")

# === Main Process ===
def main():
    run_doxygen()
    save_docs()
    html_text = extract_text(OUTPUT_DIR)

    summary = model.generate_content(f"Summarize this documentation:\n\n{html_text}").text
    todos = model.generate_content(f"Extract TODOs and undocumented parts:\n\n{html_text}").text
    classes = model.generate_content(f"List all classes and their brief roles:\n\n{html_text}").text

    # Graph Legend from Doxygen file if exists
    legend_path = OUTPUT_DIR / "graph_legend.html"
    legend_text = ""
    if legend_path.exists():
        with open(legend_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            legend_text = soup.get_text(strip=True)[:3000]

    generate_markdown(summary, classes, todos, legend_text)
    print("✅ Documentation generated and saved to repo.")

if __name__ == "__main__":
    main()
