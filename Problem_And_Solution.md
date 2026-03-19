# Issues & Fixes — ai-policy-helper-starter-pack

---

## 1. LocalEmbedder is not semantic at all

**File:** `backend/app/rag.py` line 28–36

**Problem:**
- The embedder uses SHA1 hash of the text to seed a random vector generator
- "what is the refund policy?" and "how do I return an item?" will get completely different vectors even though they mean the same thing
- The RAG search is essentially random — it will never find the right chunks reliably

**Fix:**
```python
# Replace LocalEmbedder with a real model
# pip install sentence-transformers
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

---

## 2. CORS misconfigured — browser will reject requests

**File:** `backend/app/main.py` line 31–37

**Problem:**
- `allow_origins=["*"]` and `allow_credentials=True` are set at the same time
- Browsers block this combination by spec — wildcard origin + credentials is not allowed
- Frontend calls to `/api/ask` will fail with a CORS error in the browser console

**Fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # exact frontend URL only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For multiple origins:
```python
allow_origins=["http://localhost:3000", "https://yourdomain.com"],
```

---

## 3. Qdrant URL is hardcoded in source code

**File:** `backend/app/rag.py` line 71

**Problem:**
- `QdrantClient(url="http://qdrant:6333")` is written directly in the code
- Changing the host or port requires editing source, not `.env`
- The `Settings` class exists but is not used for the Qdrant URL

**Fix:**

Add to `backend/app/settings.py`:
```python
qdrant_url: str = os.getenv("QDRANT_URL", "http://qdrant:6333")
```

Update `rag.py`:
```python
self.client = QdrantClient(url=settings.qdrant_url, timeout=10.0)
```

Add to `.env.example`:
```
QDRANT_URL=http://qdrant:6333
```

Add to `docker-compose.yml` under backend environment:
```yaml
- QDRANT_URL=${QDRANT_URL:-http://qdrant:6333}
```

---

## 4. `recreate_collection` is deprecated and removed

**File:** `backend/app/rag.py` line 85–88

**Problem:**
- `self.client.recreate_collection(...)` was removed in newer versions of qdrant-client
- Will crash with `AttributeError: 'QdrantClient' object has no attribute 'recreate_collection'`

**Fix:**
```python
def _ensure_collection(self):
    existing = [c.name for c in self.client.get_collections().collections]
    if self.collection not in existing:
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE)
        )
```

---

## 5. Document title shows raw filename instead of clean name

**File:** `backend/app/ingest.py` line 50

**Problem:**
- `"title": fname` — citations will show `Returns_and_Refunds.md` to the user
- Should show `Returns and Refunds` instead

**Fix:**
```python
clean_title = os.path.splitext(fname)[0].replace("_", " ").replace("-", " ")
docs.append({
    "title": clean_title,
    "section": section,
    "text": body
})
```

---

## 6. API error details are swallowed in the frontend

**File:** `frontend/lib/api.ts` line 9

**Problem:**
- When a request fails, the frontend throws a generic `Error('Ask failed')`
- The server sends back a useful error message in the response body but it gets ignored
- User sees nothing helpful in the UI

**Fix:**
```typescript
export async function apiAsk(query: string, k: number = 4) {
  const r = await fetch(`${API_BASE}/api/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, k })
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: 'Ask failed' }));
    throw new Error(err.detail || 'Ask failed');
  }
  return r.json();
}
```

Do the same for `apiIngest` and `apiMetrics`.

---

## 7. Frontend container starts before the backend is actually ready

**File:** `docker-compose.yml` line 34–35

**Problem:**
- `depends_on: backend` only waits for the container to start, not for FastAPI to finish booting
- Frontend may get `Connection refused` on first load

**Fix:**

Add a healthcheck to the backend service:
```yaml
backend:
  build: ./backend
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
    interval: 10s
    timeout: 5s
    retries: 5
  ...

frontend:
  ...
  depends_on:
    backend:
      condition: service_healthy
```

---

## 8. Metrics are lost on every container restart

**File:** `backend/app/rag.py` — `Metrics` class

**Problem:**
- All latency data is stored in a Python list in memory
- Every Docker restart wipes everything
- Useless for any real monitoring

**Fix — persist to file:**
```python
import json, pathlib

class Metrics:
    def __init__(self, path: str = "/app/data/metrics.json"):
        self._path = pathlib.Path(path)
        data = json.loads(self._path.read_text()) if self._path.exists() else {}
        self.t_retrieval = data.get("t_retrieval", [])
        self.t_generation = data.get("t_generation", [])

    def _save(self):
        self._path.write_text(json.dumps({
            "t_retrieval": self.t_retrieval[-500:],
            "t_generation": self.t_generation[-500:],
        }))

    def add_retrieval(self, ms: float):
        self.t_retrieval.append(ms)
        self._save()

    def add_generation(self, ms: float):
        self.t_generation.append(ms)
        self._save()
```

---

## 9. StubLLM output is confusing for new users

**File:** `backend/app/rag.py` line 109–119

**Problem:**
- Default provider is `stub` — a new user who clones this repo will get answers like `Answer (stub): Based on the following sources:`
- No clear indication in the UI that this is demo mode, not an error

**Fix:**
- In `.env`, set `LLM_PROVIDER=openrouter` and add your API key
- Or detect stub output in the frontend and show a warning banner:

```tsx
// in Chat.tsx after receiving answer
const isStub = res.answer.startsWith('Answer (stub):');
// show a "Demo Mode — no LLM configured" badge if isStub is true
```

---

## Priority Summary

| # | Issue | Critical? |
|---|-------|-----------|
| 1 | Embedder is not semantic | Yes — RAG does not work |
| 2 | CORS misconfigured | Yes — frontend is broken |
| 3 | Qdrant URL hardcoded | Medium |
| 4 | `recreate_collection` deprecated | Yes — crashes on deploy |
| 5 | Raw filename as document title | Low |
| 6 | Error details swallowed in frontend | Medium |
| 7 | Frontend starts before backend is ready | Medium |
| 8 | Metrics lost on restart | Low |
| 9 | StubLLM output confusing | Low |
