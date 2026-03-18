import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions
EMBEDDING_DIM = 1536

# Milvus
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.getenv("MILVUS_PORT", 19530))
COLLECTION_NAME = "nist_policy_chunks"

# Chunking
MAX_CHUNK_TOKENS = 400   # soft upper limit per chunk (in words, approximated)

# Neo4j
NEO4J_URI       = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER      = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD  = os.getenv("NEO4J_PASSWORD", "password")