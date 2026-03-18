# AI-Powered Policy-Compliant Assistant

This project is an AI-powered compliance assistant that answers employee policy questions using a multi-agent backend grounded in NIST CSF 2.0 policy content. It combines retrieval from Milvus and Neo4j, LLM-based reasoning agents, guardrails, a FastAPI API, a React frontend, and a DeepEval-based evaluation flow.

## What the project does

- Accepts employee questions such as "Can I share customer data with another team?"
- Retrieves relevant NIST CSF policy chunks from a vector store and a knowledge graph
- Classifies the query as `INFO`, `ACTION`, or `INCIDENT`
- Produces:
  - an interpretation of the policy context
  - a compliance verdict
  - a risk assessment
  - recommended next steps
  - policy references
- Applies input and output guardrails, including off-topic checks, optional PII scrubbing, moderation, and response validation

## Repository structure

```text
.
|-- backend/
|   |-- agents/             # 5-agent pipeline + orchestrator
|   |-- api/                # FastAPI routes and Pydantic models
|   |-- data/               # Source policy PDF
|   |-- data_ingestion/     # PDF download, chunking, embedding, Milvus loading
|   |-- evaluation/         # Golden dataset + DeepEval runner
|   |-- graph/              # Neo4j graph build and query utilities
|   |-- guardrails/         # Input/output validation
|   |-- retrieval/          # Vector, BM25, hybrid search, reranking
|   |-- utils/              # Token/cost tracking helpers
|   |-- app.py              # FastAPI app entrypoint
|   `-- main.py             # End-to-end ingestion pipeline
|-- frontend/
|   |-- src/                # React UI
|   `-- vite.config.js      # Dev server + API proxy
`-- docker-compose.yml      # Milvus, Attu, Neo4j, etcd, MinIO
```

## Architecture overview

### Backend pipeline

The backend orchestrates five agents in sequence:

1. `retrieval_agent`
   Retrieves candidate policy chunks using:
   - Milvus semantic search
   - BM25 keyword search
   - Neo4j graph traversal based on detected NIST intent
   - a reranker that uses graph authority/context
2. `interpretation_agent`
   Classifies the question into `INFO`, `ACTION`, or `INCIDENT` and writes a grounded explanation from retrieved text.
3. `compliance_agent`
   Produces a compliance verdict and citations.
4. `risk_agent`
   Estimates the business/security risk of the action or incident.
5. `recommendation_agent`
   Converts the analysis into actionable next steps and escalation guidance.

### Retrieval design

- `Milvus` stores chunk text, metadata, and embeddings.
- `BM25` is built in memory from Milvus content for keyword retrieval.
- `Neo4j` stores the NIST function -> category -> subcategory -> policy graph.
- Final results merge Milvus/BM25 and Neo4j paths, then rerank the combined set.

### Guardrails

- Input guardrail:
  - validates length and topic relevance
  - optionally anonymizes PII with Presidio if installed
  - runs OpenAI moderation
- Output guardrail:
  - validates verdict/risk/recommendation structure
  - auto-forces escalation on high-risk results
  - optionally checks generated output for leaked PII

## Tech stack

### Backend

- Python
- FastAPI
- OpenAI API
- LangChain (`langchain-openai`, `langchain-core`)
- Milvus / PyMilvus
- Neo4j Python driver
- `rank-bm25`
- `pdfplumber`
- `python-dotenv`
- `requests`
- `deepeval`
- Optional: Microsoft Presidio

### Frontend

- React
- Vite

### Infrastructure

- Milvus
- Neo4j
- Attu

## Running the project

### 1. Start infrastructure

From the repository root:

```powershell
docker compose up -d
```

This starts:

- Milvus on `localhost:19530`
- Attu on `http://localhost:8080`
- Neo4j Browser on `http://localhost:7474`

### 2. Configure backend environment

Create `backend/.env` with the variables used by [`backend/config.py`](backend/config.py):

```env
OPENAI_API_KEY=your_openai_api_key
MILVUS_HOST=localhost
MILVUS_PORT=19530
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

Notes:

- The code defaults `NEO4J_PASSWORD` to `password`, but `docker-compose.yml` starts Neo4j with `password`, so set it explicitly in `.env`.
- Embeddings use `text-embedding-3-small`.
- The agents use `gpt-4o-mini` and the evaluation metrics use `gpt-4o`.

### 3. Install Python dependencies

Likely required packages based on the imports in `backend/`:

```powershell
pip install fastapi uvicorn python-dotenv openai langchain-openai langchain-core pymilvus neo4j rank-bm25 pdfplumber requests pydantic deepeval presidio-analyzer presidio-anonymizer
```

### 4. Run the ingestion pipeline

From `backend/`:

```powershell
python main.py
```

This pipeline:

1. downloads the policy PDF
2. chunks and cleans the text
3. generates embeddings
4. loads chunks into Milvus
5. builds the Neo4j graph

The source PDF currently lives at [`backend/data/nist_policy_guide.pdf`](backend/data/nist_policy_guide.pdf).

### 5. Start the backend API

From `backend/`:

```powershell
uvicorn app:app --reload --port 8001
```

The frontend Vite proxy is configured to send `/api` traffic to `http://localhost:8001`, so `8001` is the expected local API port.

Available docs:

- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

### 6. Start the frontend

From `frontend/`:

```powershell
npm install
npm run dev
```

The UI runs on `http://localhost:5173`.

## API endpoints

The main routes are defined in [`backend/api/routes.py`](backend/api/routes.py).

### `GET /api/v1/health`

Returns a simple health response.

### `POST /api/v1/query`

Runs the full 5-agent compliance pipeline.

Example request:

```json
{
  "query": "Can I share customer data with another internal team?",
  "top_k": 5
}
```

Example response shape:

```json
{
  "query": "Can I share customer data with another internal team?",
  "query_type": "ACTION",
  "interpretation": "...",
  "compliance": {
    "verdict": "NEEDS_REVIEW",
    "score": 62,
    "reason": "...",
    "citations": ["PR.AA-05"]
  },
  "risk": {
    "level": "MEDIUM",
    "reason": "...",
    "affected": ["PROTECT"],
    "potential_impact": "..."
  },
  "recommendation": {
    "steps": ["..."],
    "escalate": true,
    "escalate_to": "Information Security Team",
    "summary": "..."
  },
  "policy_references": ["Access Control Policy"]
}
```
## Evaluation

The project includes a golden dataset and a DeepEval runner:

- Dataset: [`backend/evaluation/golden_dataset.py`](backend/evaluation/golden_dataset.py)
- Runner: [`backend/evaluation/run_eval.py`](backend/evaluation/run_eval.py)

Run from `backend/`:

```powershell
python evaluation/run_eval.py
```

What it does:

- runs the live agent pipeline against the golden dataset
- evaluates answer relevancy, faithfulness, contextual precision, and contextual recall
- writes results to `backend/evaluation/eval_results.json`

Important:

- Evaluation requires working OpenAI credentials.
- It depends on the retrieval stores already being populated.
- The runner currently evaluates the first 10 dataset items.

## Frontend behavior

The frontend is a simple React app that:

- submits questions to `POST /api/v1/query`
- shows loading state and error handling
- renders verdict, risk, recommendations, and policy references
- includes example prompts for common policy/compliance questions

The API proxy is configured in [`frontend/vite.config.js`](frontend/vite.config.js).

## Key files

- [`backend/app.py`](backend/app.py): FastAPI app entrypoint
- [`backend/main.py`](backend/main.py): ingestion pipeline entrypoint
- [`backend/agents/orchestrator.py`](backend/agents/orchestrator.py): end-to-end agent orchestration
- [`backend/agents/retrieval_agent.py`](backend/agents/retrieval_agent.py): hybrid retrieval + graph search
- [`backend/graph/graph_builder.py`](backend/graph/graph_builder.py): Neo4j graph construction
- [`backend/retrieval/hybrid_search.py`](backend/retrieval/hybrid_search.py): retrieval-only API helper
- [`backend/guardrails/input_guardrail.py`](backend/guardrails/input_guardrail.py): query validation
- [`frontend/src/App.jsx`](frontend/src/App.jsx): root React app
