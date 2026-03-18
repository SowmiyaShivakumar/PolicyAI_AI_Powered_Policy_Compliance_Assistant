import time
from typing import List, Dict
from openai import OpenAI
from config import OPENAI_API_KEY, EMBEDDING_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

BATCH_SIZE = 50  # OpenAI allows up to 2048 inputs per call; 50 is safe & observable


def embed_chunks(chunks: List[Dict]) -> List[Dict]:
    """
    Add an 'embedding' field to each chunk dict.
    Processes in batches to stay within API limits.
    """
    print(f"[embedder] Embedding {len(chunks)} chunks in batches of {BATCH_SIZE}...")
    texts = [c["text"] for c in chunks]

    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]
        print(f"[embedder] Batch {i // BATCH_SIZE + 1} / {-(-len(texts) // BATCH_SIZE)}")

        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=batch,
        )
        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

        time.sleep(0.3)  # small delay to respect rate limits

    for chunk, emb in zip(chunks, all_embeddings):
        chunk["embedding"] = emb

    print("[embedder] Done.")
    return chunks