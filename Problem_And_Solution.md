# Issues & Fixes — ai-policy-helper-starter-pack

Focused on what the README acceptance checks and rubric actually require.

---

## 1. Hash-based embedder breaks all acceptance checks (most critical)

**File:** `backend/app/rag.py` line 28–36

**Problem:**
- `LocalEmbedder` seeds a random vector from a SHA1 hash — it is not semantic
- "Can a customer return a damaged blender after 20 days?" and "What's the shipping SLA?" will get random vectors with zero relation to what the words mean
- Acceptance check #3 requires `Returns_and_Refunds.md` AND `Warranty_Policy.md` to both be cited — this will never happen reliably
- Acceptance check #4 requires `Delivery_and_Shipping.md` — same problem
- The policy-specific tests in `test_api.py` lines 173–202 will all fail (`test_ask_warranty_returns_relevant_source`, `test_ask_returns_policy_returns_relevant_source`, `test_ask_delivery_returns_relevant_source`)

**Fix:**
```python
# Replace LocalEmbedder in rag.py
from sentence_transformers import SentenceTransformer

class LocalEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.dim = 384

    def embed(self, text: str):
        v = self.model.encode(text, normalize_embeddings=True)
        return v.astype("float32")
```

Add to `requirements.txt`:
```
sentence-transformers>=2.7.0
```

Update `settings.py` default:
```python
embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
```

---

## 2. Real LLM is required but stub is the default

**File:** `.env.example` line 3, `backend/app/rag.py` line 225

**Problem:**
- README line 142 explicitly says: *"You are required to demo with a real LLM, not stub."*
- Default in `.env.example` is `LLM_PROVIDER=stub`
- With stub, acceptance check answers look like: `Answer (stub): Based on the following sources:` — this will fail the demo

**Fix:**

In `.env`, change:
```
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<your-key-here>
LLM_MODEL=openai/gpt-4o-mini
```

Also update `docker-compose.yml` to pass `LLM_MODEL` (currently missing):
```yaml
- LLM_MODEL=${LLM_MODEL:-openai/gpt-4o-mini}
```

---

## 3. PII in citation chunks is not masked

**File:** `backend/app/rag.py` line 272, `frontend/components/Chat.tsx` line 47–51

**Problem:**
- `mask_pii()` is only called on the LLM-generated answer (line 272)
- The raw chunk text sent in `chunks[]` is NOT masked
- Acceptance check #5 says: "Expand a citation chip and see the underlying chunk text"
- If any document chunk contains an IC number, email, or phone, it will be visible to the user when they expand the citation popup — violates the PDPA requirement in this project

**Fix:**

In `main.py`, mask chunk text before returning:
```python
chunks = [
    Chunk(
        title=c.get("title"),
        section=c.get("section"),
        text=mask_pii(c.get("text", ""))
    )
    for c in ctx
]
```

Import `mask_pii` in `main.py`:
```python
from .rag import RAGEngine, build_chunks_from_docs, mask_pii
```

---

## 4. `docker-compose.yml` does not pass `LLM_MODEL` to backend

**File:** `docker-compose.yml` line 13–20

**Problem:**
- `LLM_MODEL` is in `settings.py` and `.env.example` but is not listed in the `environment:` block of docker-compose
- Setting it in `.env` will have no effect when running via Docker Compose
- Same issue for `DATA_DIR` — it has a default of `/app/data` which works, but it is not exposed for override either

**Fix:**
```yaml
environment:
  - EMBEDDING_MODEL=${EMBEDDING_MODEL:-local-384}
  - LLM_PROVIDER=${LLM_PROVIDER:-stub}
  - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
  - LLM_MODEL=${LLM_MODEL:-openai/gpt-4o-mini}
  - OLLAMA_HOST=${OLLAMA_HOST:-http://ollama:11434}
  - VECTOR_STORE=${VECTOR_STORE:-qdrant}
  - COLLECTION_NAME=${COLLECTION_NAME:-policy_helper}
  - CHUNK_SIZE=${CHUNK_SIZE:-700}
  - CHUNK_OVERLAP=${CHUNK_OVERLAP:-80}
  - DATA_DIR=${DATA_DIR:-/app/data}
```

---

## 5. No architecture diagram — rubric deduction

**File:** none (missing)

**Problem:**
- README constraints say: *"Provide small architecture diagram if you can (ASCII is fine)"*
- Rubric gives 15 pts for reproducibility & docs — missing diagram costs points
- Evaluators specifically look for this to understand the candidate's understanding of the system

**Fix — add to README:**
```
Request
  │
  ▼
Next.js Frontend (port 3000)
  │  POST /api/ask
  ▼
FastAPI Backend (port 8000)
  ├─ Ingest: load .md files → chunk → embed → upsert to Qdrant
  └─ Ask:    embed query → search Qdrant (top-k) → LLM generate → mask PII → return
       │                        │                        │
       ▼                        ▼                        ▼
  LocalEmbedder          Qdrant (port 6333)        OpenRouter / Ollama / Stub
  (all-MiniLM-L6-v2)    (vector store)             (LLM provider)
```

---

## 6. README is missing trade-offs and next steps — rubric deduction

**File:** `README.md` or `AI_Policy_Helper_README.md`

**Problem:**
- Rubric deliverable #2: *"README describing setup, architecture, trade-offs, and what you'd ship next"*
- Current README only has setup instructions, no trade-offs or next steps section
- This directly costs rubric points (15 pts for reproducibility & docs)

**Fix — add a section:**
```markdown
## Trade-offs
- Used all-MiniLM-L6-v2 (384-dim) for speed over accuracy; larger models like bge-large improve recall
- In-memory fallback means data is lost on restart — Qdrant is required for prod
- Chunk size 700 tokens is a balance; too small loses context, too large dilutes relevance

## What I'd ship next
- Streaming responses (Server-Sent Events) for better UX
- Re-ranking with a cross-encoder after initial retrieval
- Persistent metrics store (Prometheus or simple SQLite)
- Upload endpoint so users can add their own documents via the UI
- Evaluation harness using the acceptance check queries as ground-truth
```

---

## 7. Policy-specific retrieval tests will fail without fix #1

**File:** `backend/app/tests/test_api.py` line 173–202

**Problem:**
- Three tests check that specific policy docs appear in citations:
  - `test_ask_warranty_returns_relevant_source` — needs "Warranty" in titles
  - `test_ask_returns_policy_returns_relevant_source` — needs "Return" or "Refund" in titles
  - `test_ask_delivery_returns_relevant_source` — needs "Delivery" or "Shipping" in titles
- All three will fail with the hash-based embedder because retrieval is random
- `pytest -q` output shown to evaluators will have 3 failures

**Fix:** Fix #1 (replace embedder) resolves this automatically. No separate code change needed here.

---

## 8. API error details are swallowed in the frontend

**File:** `frontend/lib/api.ts` line 9, 15, 20

**Problem:**
- All three API functions throw a hardcoded generic error string (`'Ask failed'`, `'Ingest failed'`, `'Metrics failed'`)
- Server returns a `{"detail": "..."}` body on 4xx/5xx but it gets ignored
- Rubric gives 10 pts for UX & DX polish — unclear error messages cost points

**Fix:**
```typescript
async function handleResponse(r: Response, fallback: string) {
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: fallback }));
    throw new Error(err.detail || fallback);
  }
  return r.json();
}

export async function apiAsk(query: string, k: number = 4) {
  const r = await fetch(`${API_BASE}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, k })
  });
  return handleResponse(r, 'Ask failed');
}

export async function apiIngest() {
  const r = await fetch(`${API_BASE}/api/ingest`, { method: 'POST' });
  return handleResponse(r, 'Ingest failed');
}

export async function apiMetrics() {
  const r = await fetch(`${API_BASE}/api/metrics`);
  return handleResponse(r, 'Metrics failed');
}
```

---

## Priority Summary (against README rubric)

| # | Issue | Rubric impact | Must fix? |
|---|-------|--------------|-----------|
| 1 | Embedder not semantic | Acceptance checks #3 #4 fail, 3 tests fail | Yes |
| 2 | Stub LLM in demo | README requires real LLM | Yes |
| 3 | PII in citation chunks not masked | PDPA requirement in project | Yes |
| 4 | `LLM_MODEL` not in docker-compose env | Config won't apply via Docker | Yes |
| 5 | No architecture diagram | Rubric docs 15pts | Yes |
| 6 | README missing trade-offs/next steps | Rubric docs 15pts | Yes |
| 7 | 3 policy tests fail | Rubric testing 10pts | Fixed by #1 |
| 8 | Generic error messages in frontend | Rubric UX 10pts | Medium |
