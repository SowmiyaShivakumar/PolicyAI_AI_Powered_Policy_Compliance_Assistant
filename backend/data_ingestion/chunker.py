import re
import pdfplumber
from typing import List, Dict
from data_ingestion.cleaner import clean_text

# ── NIST CSF 2.0 subcategory ID pattern ───────────────────────────────────────
# Matches: GV.OC-01, ID.AM-1, PR.AA-01, DE.AE-02, RS.MA-01, RC.RP-01 etc.
SUBCATEGORY_RE = re.compile(
    r"\b([A-Z]{2}\.[A-Z]{2,3}-\d{1,2})\b"
)


def extract_full_text(pdf_path: str) -> str:
    """Extract all text page by page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)


def chunk_pdf(pdf_path: str) -> List[Dict]:
    """
    Parse the NIST PDF into one chunk per subcategory (e.g. GV.OC-01, ID.AM-1).

    Strategy:
      1. Extract full text
      2. Find every subcategory ID and its character position in the text
      3. Slice the text between consecutive IDs → each slice = one chunk
      4. Attach metadata: nist_function, category, policies referenced

    Result: ~49-60 chunks (one per subcategory) — maps cleanly to
    Neo4j nodes later: (Subcategory)-[:HAS_POLICY]->(Policy)
                       (Subcategory)-[:BELONGS_TO]->(Category)
                       (Category)-[:PART_OF]->(NistFunction)
    """
    print("[chunker] Extracting text from PDF...")
    raw = extract_full_text(pdf_path)
    text = clean_text(raw)

    print("[chunker] Finding subcategory boundaries...")
    all_matches = list(SUBCATEGORY_RE.finditer(text))

    if not all_matches:
        print("[chunker] WARNING: No subcategory IDs found. Falling back to full-text.")
        return [_make_chunk("Full Document", text, "GENERAL", "General", [], "Full Document")]

    # Deduplicate — keep only FIRST occurrence of each ID
    # The PDF TOC at the top causes duplicate hits (e.g. ID.AM-5 appears in TOC + content)
    seen = set()
    matches = []
    for m in all_matches:
        if m.group(1) not in seen:
            seen.add(m.group(1))
            matches.append(m)

    print(f"[chunker] Unique subcategory IDs: {len(matches)}")

    chunks = []
    for i, match in enumerate(matches):
        subcat_id = match.group(1)
        start     = match.start()
        end       = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        body = text[start:end].strip()

        # First line = "GV.OC-01  The organizational mission is..."
        first_line = body.split("\n")[0].strip()[:300]

        nist_fn   = _detect_nist_function(subcat_id)
        category  = _detect_category(subcat_id)
        policies  = _extract_policies(body)

        chunks.append(_make_chunk(
            title        = subcat_id,
            text         = body[:4000],       # Milvus VARCHAR(4096) guard
            nist_fn      = nist_fn,
            category     = category,
            policies     = policies,
            description  = first_line,
        ))

    print(f"[chunker] Total subcategory chunks: {len(chunks)}")
    return chunks


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_chunk(title: str, text: str, nist_fn: str,
                category: str, policies: List[str], description: str) -> Dict:
    return {
        # ── Milvus fields ──────────────────────────────────────────────────
        "title":         title,           # subcategory ID e.g. "GV.OC-01"
        "text":          text,            # full body → embedded
        "nist_function": nist_fn,         # "GOVERN" / "IDENTIFY" / ...
        "category":      category,        # "Organizational Context" / ...

        # ── Neo4j extra fields (passed through loader later) ───────────────
        "subcategory_id": title,
        "description":    description,    # first description line
        "policies":       " | ".join(policies),  # pipe-separated policy names
    }


def _extract_policies(text: str) -> List[str]:
    """
    Extract policy names from a subcategory block.

    PDF has bullet on its own line, policy name on the next line:
        •
        Information Security Policy
        •
        Access Control Policy
    """
    policies = []
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()

        # bullet alone on a line → policy name is next non-empty line
        if stripped == "•":
            for j in range(i + 1, min(i + 3, len(lines))):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith("•"):
                    # skip if it looks like a subcategory ID
                    if not re.match(r"^[A-Z]{2}\.[A-Z]{2,3}-\d", next_line):
                        policies.append(next_line)
                    break

        # inline bullet: "• Information Security Policy"
        elif stripped.startswith("•"):
            policy = stripped.lstrip("•").strip()
            if policy:
                policies.append(policy)

    return policies


def _detect_nist_function(subcategory_id: str) -> str:
    """Derive NIST CSF 2.0 function from the two-letter prefix."""
    prefix = subcategory_id.split(".")[0].upper()
    return {
        "GV": "GOVERN",
        "ID": "IDENTIFY",
        "PR": "PROTECT",
        "DE": "DETECT",
        "RS": "RESPOND",
        "RC": "RECOVER",
    }.get(prefix, "GENERAL")


def _detect_category(subcategory_id: str) -> str:
    """Derive category from the subcategory code (e.g. GV.OC → Organizational Context)."""
    try:
        cat_code = subcategory_id.split(".")[1].split("-")[0].upper()
    except IndexError:
        return "General"

    return {
        # GOVERN
        "OC": "Organizational Context",
        "RM": "Risk Management Strategy",
        "RR": "Roles and Responsibilities",
        "PO": "Policy",
        "OV": "Oversight",
        "SC": "Supply Chain Risk Management",
        # IDENTIFY
        "AM": "Asset Management",
        "RA": "Risk Assessment",
        "IM": "Improvement",
        # PROTECT
        "AA": "Identity and Access Control",
        "AT": "Awareness and Training",
        "DS": "Data Security",
        "PS": "Platform Security",
        "IR": "Infrastructure Resilience",
        # DETECT
        "AE": "Adverse Event Analysis",
        "CM": "Continuous Monitoring",
        # RESPOND
        "MA": "Incident Management",
        "CO": "Incident Communication",
        "AN": "Incident Analysis",
        "MI": "Incident Mitigation",
        # RECOVER
        "RP": "Recovery Plan Execution",
    }.get(cat_code, "General")