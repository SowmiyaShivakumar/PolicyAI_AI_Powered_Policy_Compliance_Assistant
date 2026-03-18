"""
Data Ingestion Pipeline
-----------------------
Run:  python main.py

Steps:
  1. Download the NIST policy PDF
  2. Extract + clean + chunk the text (section-based)
  3. Embed each chunk with OpenAI
  4. Load chunks into Milvus
"""

import sys
import os

# Allow imports from backend/ root
sys.path.insert(0, os.path.dirname(__file__))

from data_ingestion.downloader import download_pdf
from data_ingestion.chunker    import chunk_pdf
from data_ingestion.embedder   import embed_chunks
from data_ingestion.loader     import load_all
from graph.graph_builder import build_graph 

def run():
    print("=" * 55)
    print("  Policy Compliance — Data Ingestion Pipeline")
    print("=" * 55)

    # Step 1: Download
    pdf_path = download_pdf()

    # Step 2: Chunk
    chunks = chunk_pdf(pdf_path)
    # if not chunks:
    #     print("[main] No chunks produced. Exiting.")
    #     return

    # Step 3: Embed
    chunks = embed_chunks(chunks)

    # Step 4: Load into Milvus
    load_all(chunks)

    build_graph(chunks)

    print("\n✅ Ingestion completed in neo4j!")


if __name__ == "__main__":
    run()