import re

def clean_text(text: str) -> str:
    """
    Clean raw PDF-extracted text:
    - Remove page headers/footers (page numbers, repeated titles)
    - Collapse excessive whitespace
    - Remove non-printable characters
    """
    # Remove page numbers (standalone numbers on a line)
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)

    # Remove common PDF header/footer noise (adjust patterns to your PDF)
    text = re.sub(r"CIS.*?NIST.*?\n", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Page \d+ of \d+", "", text, flags=re.IGNORECASE)

    # Remove non-printable / control characters BUT keep bullet point •  (ord 8226)
    text = re.sub(r"[^\x20-\x7E\n\u2022]", " ", text)

    # Collapse 3+ newlines into 2 (paragraph breaks)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple spaces into one
    text = re.sub(r" {2,}", " ", text)

    return text.strip()