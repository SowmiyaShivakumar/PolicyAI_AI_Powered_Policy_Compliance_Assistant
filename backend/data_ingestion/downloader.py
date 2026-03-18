import os, requests

# PDF Source
PDF_URL = (
    "https://www.cisecurity.org/-/media/project/cisecurity/cisecurity/data/media/files/uploads/2024/08/cis-ms-isac-nist-cybersecurity-framework-policy-template-guide-2024.pdf"
)
PDF_PATH = "data/nist_policy_guide.pdf"

def download_pdf():
    """Download the NIST policy PDF if not already present."""
    os.makedirs(os.path.dirname(PDF_PATH), exist_ok=True)
 
    if os.path.exists(PDF_PATH):
        print(f"[downloader] PDF already exists at '{PDF_PATH}', skipping download.")
        return PDF_PATH
 
    print(f"[downloader] Downloading PDF from:\n  {PDF_URL}")
    response = requests.get(PDF_URL, timeout=60)
    response.raise_for_status()
 
    with open(PDF_PATH, "wb") as f:
        f.write(response.content)
 
    print(f"[downloader] Saved to '{PDF_PATH}' ({len(response.content) / 1024:.1f} KB)")
    return PDF_PATH