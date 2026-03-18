# AI Policy Helper — Solution

## Setup

1. Copy env file dan isi API key:
```bash
cp .env.example .env
```

2. Jalankan semua services:
```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs
- Qdrant UI: http://localhost:6333

3. Ingest dokumen polisi (dari Admin tab UI) atau:
```bash
curl -X POST http://localhost:8000/api/ingest
```

4. Tanya soalan:
```bash
curl -X POST http://localhost:8000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is the shipping SLA to East Malaysia for bulky items?"}'
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                         │
│              Next.js 14 frontend (port 3000)                │
│         Chat UI  │  Admin Panel (ingest + metrics)          │
└──────────────────┬──────────────────────────────────────────┘
                   │ HTTP (REST)
┌──────────────────▼──────────────────────────────────────────┐
│              FastAPI backend (port 8000)                     │
│                                                             │
│  POST /api/ingest ──► load_documents() ──► chunk_text()     │
│                             │                               │
│                      LocalEmbedder (384-dim)                │
│                             │                               │
│  POST /api/ask  ──► retrieve() ──► generate() ──► mask_pii()│
│                       │                  │                  │
│               cosine similarity    LLM (stub /              │
│                       │           OpenRouter / Ollama)      │
└──────────────────┬────┴─────────────────────────────────────┘
                   │ HTTP (port 6333)
┌──────────────────▼──────────────────────────────────────────┐
│                  Qdrant vector DB                            │
│              persistent volume: qdrant_data                  │
└─────────────────────────────────────────────────────────────┘
```

**RAG flow:**

1. `POST /api/ingest` — baca fail `.md`/`.txt` dari `/data`, split ikut Markdown headings, chunk ikut token count (700 tokens, 80 overlap), embed dengan `LocalEmbedder`, simpan dalam Qdrant (fallback ke in-memory).
2. `POST /api/ask` — embed query, cari top-k chunks guna cosine similarity, hantar ke LLM, apply PDPA masking pada jawapan, return `answer + citations + chunks + metrics`.

## LLM Options

| Provider | Config | Notes |
| --- | --- | --- |
| **Stub** (default) | `LLM_PROVIDER=stub` | Deterministic, fully offline |
| **OpenRouter** | `LLM_PROVIDER=openrouter` + `OPENROUTER_API_KEY=...` | GPT-4o-mini default |
| **Ollama** | `LLM_PROVIDER=ollama` + `OLLAMA_HOST=http://ollama:11434` | Local LLM, e.g. llama3 |

## Run Tests

```bash
# Dalam Docker
docker compose run --rm backend pytest -q

# Local (perlu venv)
cd backend && pytest -q
```

Test coverage:

- Health endpoint
- Ingest: response shape, idempotency (deduplication)
- Ask: response shape, citations ada title, chunks ada text, parameter `k`, latency metrics, empty query
- Ask sebelum ingest (empty citations)
- Metrics: shape, nilai selepas ingest dan ask
- Policy-specific: query warranty / returns / delivery cite dokumen yang betul
- PDPA masking: IC number, email, nombor telefon di-redact

## Changes Made

| Fail | Perubahan |
| --- | --- |
| `docker-compose.yml` | Betulkan `OPENAI_API_KEY` → `OPENROUTER_API_KEY` |
| `backend/app/rag.py` | Tambah `OllamaLLM`, tambah `mask_pii()` untuk PDPA, error handling LLM timeout |
| `backend/app/ingest.py` | Error handling: directory not found, fail tak boleh baca, fail kosong |
| `backend/app/main.py` | HTTP request logging middleware, structured logging, error handling endpoints |
| `backend/app/tests/test_api.py` | Tambah 17 tests (dari 2 → 19) |
| `backend/app/tests/conftest.py` | Tambah fixture `client_fresh` |

## Trade-offs

| Keputusan | Approach | Alternatif |
| --- | --- | --- |
| Embeddings | Hash-based local embedder (offline, deterministic) | Sentence-transformer (lebih semantic) |
| Chunking | Token-count split dengan overlap | Sentence-aware / semantic chunking |
| Vector store | Qdrant (persistent) + in-memory fallback | Pure in-memory |
| LLM | Pluggable: stub / OpenRouter / Ollama | Single provider hardcoded |
| PII masking | Regex post-processing pada output LLM | Instruction dalam LLM prompt |
| Metrics | In-memory rolling average | Prometheus / persistent DB |

## What I'd Ship Next

1. **Real embeddings** — ganti `LocalEmbedder` dengan `sentence-transformers/all-MiniLM-L6-v2` untuk semantic retrieval yang lebih baik
2. **Streaming answers** — `StreamingResponse` pada `/api/ask` + `EventSource` pada frontend
3. **Reranking** — cross-encoder reranker atau MMR untuk diversity dalam retrieved chunks
4. **Persistent metrics** — simpan latency dan query logs ke Postgres
5. **Feedback loop** — thumbs up/down pada jawapan untuk fine-tune retrieval
6. **File upload** — drag-and-drop dokumen polisi via UI
7. **Auth** — API key middleware untuk protect admin endpoints
