import os
import shutil
import subprocess
import tempfile
import zipfile
from bs4 import BeautifulSoup
import google.generativeai as genai
from azure.storage.blob import BlobServiceClient

# === Configurations ===
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
AZURE_CONN_STRING = os.getenv('AZURE_CONN_STRING')
AZURE_CONTAINER_NAME = "doxygen-html"
OUTPUT_FOLDER = "outputs"
DOC_FOLDER = os.path.join(OUTPUT_FOLDER, "html")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# === Configure Gemini ===
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# === Azure Helper ===
class AzureHelper:
    def __init__(self, conn_str, container_name):
        self.client = BlobServiceClient.from_connection_string(conn_str)
        self.container = self.client.get_container_client(container_name)
        try:
            self.container.create_container()
        except Exception:
            pass

    def upload_file(self, local_path, blob_name):
        with open(local_path, "rb") as data:
            self.container.upload_blob(name=blob_name, data=data, overwrite=True)
        return f"https://{self.client.account_name}.blob.core.windows.net/{self.container.container_name}/{blob_name}"

azure_helper = AzureHelper(AZURE_CONN_STRING, AZURE_CONTAINER_NAME)

# === Main Function ===
def generate_docs(repo_path):
    print("\n📁 Cloning repository and preparing source...")

    with tempfile.TemporaryDirectory() as work_dir:
        source_path = os.path.join(work_dir, "source")
        shutil.copytree(repo_path, source_path, dirs_exist_ok=True)

        html_output_dir = os.path.join(OUTPUT_FOLDER, "html")
        if os.path.exists(html_output_dir):
            shutil.rmtree(html_output_dir)

        doxyfile_path = os.path.join(work_dir, "Doxyfile")
        doxy_content = f"""
PROJECT_NAME = AutoDocs
OUTPUT_DIRECTORY = {OUTPUT_FOLDER}
INPUT = {source_path}
RECURSIVE = YES

HAVE_DOT = YES
DOT_PATH = /usr/local/bin/dot  # Specify the correct path for dot if necessary
CLASS_DIAGRAMS = YES
CALL_GRAPH = YES
CALLER_GRAPH = YES
COLLABORATION_GRAPH = YES
INCLUDE_GRAPH = YES
INCLUDED_BY_GRAPH = YES
GRAPHICAL_HIERARCHY = YES
DOT_IMAGE_FORMAT = svg
INTERACTIVE_SVG = YES
GENERATE_HTML = YES
EXTRACT_ALL = YES
"""

        with open(doxyfile_path, "w", encoding="utf-8") as f:
            f.write(doxy_content)

        print("\n🔧 Running Doxygen...")
        subprocess.run(["doxygen", doxyfile_path], check=True)

        index_path = os.path.join(html_output_dir, "index.html")
        if not os.path.exists(index_path):
            raise Exception("❌ Doxygen did not produce index.html")

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        print("\n🤖 Generating Gemini summary...")
        gemini_response = model.generate_content(f"Summarize this documentation:\n\n{html_content[:12000]}")

        zip_path = os.path.join(OUTPUT_FOLDER, "html_output.zip")
        shutil.make_archive(zip_path.replace(".zip", ""), 'zip', html_output_dir)

        print("\n☁️ Uploading to Azure Blob Storage...")
        blob_url = azure_helper.upload_file(zip_path, "html_output.zip")

        print("\n✅ Documentation generated and uploaded successfully!")
        print(f"🔗 Azure Blob URL: {blob_url}")
        print(f"\n🧠 Gemini Summary:\n{gemini_response.text}\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python generate_docs.py <path-to-local-repo>")
    else:
        generate_docs(sys.argv[1])
