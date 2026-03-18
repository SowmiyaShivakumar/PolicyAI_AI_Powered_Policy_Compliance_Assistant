from typing import List, Dict
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
from config import MILVUS_HOST, MILVUS_PORT, COLLECTION_NAME, EMBEDDING_DIM

INSERT_BATCH = 100


def connect():
    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
    print(f"[loader] Connected to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")


def create_collection() -> Collection:
    if utility.has_collection(COLLECTION_NAME):
        print(f"[loader] Collection '{COLLECTION_NAME}' already exists.")
        col = Collection(COLLECTION_NAME)
        col.load()
        return col

    fields = [
        # Primary key
        FieldSchema(name="id",             dtype=DataType.INT64,        is_primary=True, auto_id=True),

        # Bridge key → used to JOIN with Neo4j after vector search
        FieldSchema(name="subcategory_id", dtype=DataType.VARCHAR,      max_length=32),

        # Text stored for context in responses
        FieldSchema(name="text",           dtype=DataType.VARCHAR,      max_length=4096),

        # Metadata filters — allow filtering by function or category before vector search
        FieldSchema(name="nist_function",  dtype=DataType.VARCHAR,      max_length=64),
        FieldSchema(name="category",       dtype=DataType.VARCHAR,      max_length=128),

        # The vector
        FieldSchema(name="embedding",      dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
    ]

    schema = CollectionSchema(fields, description="NIST CSF semantic search chunks")
    col = Collection(name=COLLECTION_NAME, schema=schema)
    print(f"[loader] Created collection '{COLLECTION_NAME}'.")

    # COSINE similarity — best for semantic text matching
    col.create_index(
        field_name="embedding",
        index_params={
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128},
        },
    )
    col.load()
    print("[loader] Index created and collection loaded.")
    return col


def insert_chunks(col: Collection, chunks: List[Dict]):
    print(f"[loader] Inserting {len(chunks)} chunks...")

    for i in range(0, len(chunks), INSERT_BATCH):
        batch = chunks[i: i + INSERT_BATCH]
        data = [
            [c.get("subcategory_id", c["title"])[:32]  for c in batch],  # bridge key
            [c["text"][:4000]                           for c in batch],
            [c["nist_function"]                         for c in batch],
            [c["category"]                              for c in batch],
            [c["embedding"]                             for c in batch],
        ]
        col.insert(data)
        print(f"[loader] Inserted batch {i // INSERT_BATCH + 1} ({len(batch)} rows)")

    col.flush()
    print(f"[loader] Done. Total entities: {col.num_entities}")


def load_all(chunks: List[Dict]):
    connect()
    col = create_collection()
    insert_chunks(col, chunks)