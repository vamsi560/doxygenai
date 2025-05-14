import os
import subprocess
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from google.generativeai import GenerativeModel, configure

# === CONFIG ===
SRC_DIR = "repo"
OUTPUT_DIR = "outputs"
SUMMARY_MD = "AUTODOCS_SUMMARY.md"
DOT_SVG_DIR = os.path.join(OUTPUT_DIR, "xml")
IMG_DIR = os.path.join("docs", "images")

configure(api_key=os.environ["GEMINI_API_KEY"])
model = GenerativeModel("gemini-2.0-flash")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

# === Step 1: Run Doxygen with XML ===
doxyfile = f"""
PROJECT_NAME = AutoDocs
OUTPUT_DIRECTORY = {OUTPUT_DIR}
INPUT = {SRC_DIR}
RECURSIVE = YES
HAVE_DOT = YES
GENERATE_XML = YES
CALL_GRAPH = YES
CALLER_GRAPH = YES
CLASS_DIAGRAMS = YES
INCLUDE_GRAPH = YES
INCLUDED_BY_GRAPH = YES
GRAPHICAL_HIERARCHY = YES
GENERATE_HTML = NO
"""

with open("Doxyfile", "w") as f:
    f.write(doxyfile)

subprocess.run(["doxygen", "Doxyfile"], check=True)

# === Step 2: Convert SVGs to PNGs ===
DOT_DIR = os.path.join(OUTPUT_DIR, "xml")
for root, _, files in os.walk(DOT_DIR):
    for file in files:
        if file.endswith(".svg"):
            svg_path = os.path.join(root, file)
            png_path = os.path.join(IMG_DIR, file.replace(".svg", ".png"))
            subprocess.run(["rsvg-convert", "-o", png_path, svg_path], check=False)

# === Step 3: Parse XML summary ===
def parse_index_xml(xml_path):
    classes = []
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for compound in root.findall("compound"):        
        kind = compound.get("kind")
        name = compound.findtext("name")
        if kind in ["class", "struct"]:
            classes.append(name)
    return classes

index_path = os.path.join(OUTPUT_DIR, "xml", "index.xml")
classes = parse_index_xml(index_path)

# === Step 4: Gemini Insights ===
prompt = (
    f"""Analyze this list of C++/Python classes and generate a Markdown summary with:
    1. Top 5 important classes/functions
    2. Missing docs
    3. Improvements

    Classes:
    {classes[:30]}...
    """
)
response = model.generate_content(prompt)

# === Step 5: Write to .md ===
with open(SUMMARY_MD, "w", encoding="utf-8") as f:
    f.write("# ✨ AutoDocs Summary\n\n")
    f.write(response.text + "\n")
    f.write("## 🔹 Dependency Graphs\n")
    for png in sorted(os.listdir(IMG_DIR)):
        if png.endswith(".png"):
            f.write(f"![{png}](docs/images/{png})\n")

print("✅ AUTODOCS_SUMMARY.md generated with graphs and AI insights.")
