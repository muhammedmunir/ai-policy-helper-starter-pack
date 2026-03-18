import pytest
from fastapi.testclient import TestClient
from app.main import app


# ── Existing tests ──────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ingest_and_ask(client):
    r = client.post("/api/ingest")
    assert r.status_code == 200
    # Ask a deterministic question
    r2 = client.post("/api/ask", json={"query": "What is the refund window for small appliances?"})
    assert r2.status_code == 200
    data = r2.json()
    assert "citations" in data and len(data["citations"]) > 0
    assert "answer" in data and isinstance(data["answer"], str)


# ── Ingest tests ─────────────────────────────────────────────────────────────

def test_ingest_returns_counts(client):
    r = client.post("/api/ingest")
    assert r.status_code == 200
    data = r.json()
    assert "indexed_docs" in data
    assert "indexed_chunks" in data
    assert isinstance(data["indexed_docs"], int)
    assert isinstance(data["indexed_chunks"], int)
    assert data["indexed_docs"] >= 0
    assert data["indexed_chunks"] >= 0


def test_ingest_idempotent(client):
    """Calling ingest twice should not double-count chunks (dedup by hash)."""
    r1 = client.post("/api/ingest")
    r2 = client.post("/api/ingest")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Second ingest should return 0 new docs/chunks (already indexed)
    data2 = r2.json()
    assert data2["indexed_docs"] == 0
    assert data2["indexed_chunks"] == 0


# ── Ask tests ────────────────────────────────────────────────────────────────

def test_ask_response_shape(client):
    """Response must contain all required fields with correct types."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": "What is the warranty period?"})
    assert r.status_code == 200
    data = r.json()

    assert "query" in data
    assert "answer" in data
    assert "citations" in data
    assert "chunks" in data
    assert "metrics" in data

    assert isinstance(data["query"], str)
    assert isinstance(data["answer"], str)
    assert isinstance(data["citations"], list)
    assert isinstance(data["chunks"], list)
    assert isinstance(data["metrics"], dict)


def test_ask_citations_have_title(client):
    """Every citation must have a non-empty title."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": "What is the return policy?"})
    assert r.status_code == 200
    data = r.json()
    for citation in data["citations"]:
        assert "title" in citation
        assert citation["title"] is not None
        assert len(citation["title"]) > 0


def test_ask_chunks_have_text(client):
    """Every chunk must have non-empty text."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": "What is the return policy?"})
    assert r.status_code == 200
    data = r.json()
    for chunk in data["chunks"]:
        assert "text" in chunk
        assert len(chunk["text"]) > 0


def test_ask_respects_k_parameter(client):
    """k parameter should control number of chunks/citations returned."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": "delivery time", "k": 2})
    assert r.status_code == 200
    data = r.json()
    assert len(data["chunks"]) <= 2
    assert len(data["citations"]) <= 2


def test_ask_metrics_present(client):
    """Metrics must contain retrieval and generation latency fields."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": "What products are available?"})
    assert r.status_code == 200
    metrics = r.json()["metrics"]
    assert "retrieval_ms" in metrics
    assert "generation_ms" in metrics
    assert isinstance(metrics["retrieval_ms"], (int, float))
    assert isinstance(metrics["generation_ms"], (int, float))


def test_ask_empty_query_returns_answer(client):
    """Even an empty query should return a valid (if unhelpful) response."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": ""})
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data


def test_ask_before_ingest_returns_empty_citations(client_fresh):
    """Asking before any ingest should return an answer with no citations."""
    r = client_fresh.post("/api/ask", json={"query": "Any question"})
    assert r.status_code == 200
    data = r.json()
    assert data["citations"] == []
    assert data["chunks"] == []


# ── Metrics endpoint tests ────────────────────────────────────────────────────

def test_metrics_shape(client):
    r = client.get("/api/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "total_docs" in data
    assert "total_chunks" in data
    assert "avg_retrieval_latency_ms" in data
    assert "avg_generation_latency_ms" in data
    assert "embedding_model" in data
    assert "llm_model" in data


def test_metrics_after_ingest(client):
    """After ingest, total_docs and total_chunks should be > 0."""
    client.post("/api/ingest")
    r = client.get("/api/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["total_docs"] > 0
    assert data["total_chunks"] > 0


def test_metrics_latency_after_ask(client):
    """After an ask, latency metrics should be non-zero."""
    client.post("/api/ingest")
    client.post("/api/ask", json={"query": "What is the warranty?"})
    r = client.get("/api/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["avg_retrieval_latency_ms"] > 0
    assert data["avg_generation_latency_ms"] > 0


# ── Policy-specific acceptance tests ─────────────────────────────────────────

def test_ask_warranty_returns_relevant_source(client):
    """Query about warranty should retrieve a chunk from the Warranty Policy doc."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": "What is covered under warranty?"})
    assert r.status_code == 200
    data = r.json()
    titles = [c["title"] for c in data["citations"]]
    assert any("Warranty" in t for t in titles), f"Expected warranty doc in citations, got: {titles}"


def test_ask_returns_policy_returns_relevant_source(client):
    """Query about returns should retrieve a chunk from the Returns doc."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": "How do I return a defective product?"})
    assert r.status_code == 200
    data = r.json()
    titles = [c["title"] for c in data["citations"]]
    assert any("Return" in t or "Refund" in t for t in titles), \
        f"Expected returns doc in citations, got: {titles}"


def test_ask_delivery_returns_relevant_source(client):
    """Query about delivery should retrieve a chunk from the Delivery doc."""
    client.post("/api/ingest")
    r = client.post("/api/ask", json={"query": "How long does delivery to East Malaysia take?"})
    assert r.status_code == 200
    data = r.json()
    titles = [c["title"] for c in data["citations"]]
    assert any("Delivery" in t or "Shipping" in t for t in titles), \
        f"Expected delivery doc in citations, got: {titles}"


# ── PDPA masking tests ────────────────────────────────────────────────────────

def test_pdpa_mask_ic_number():
    """IC numbers in answers must be redacted."""
    from app.rag import mask_pii
    text = "Customer IC: 901231-14-5678 submitted a claim."
    result = mask_pii(text)
    assert "901231-14-5678" not in result
    assert "[IC REDACTED]" in result


def test_pdpa_mask_email():
    """Email addresses in answers must be redacted."""
    from app.rag import mask_pii
    text = "Contact us at support@example.com for help."
    result = mask_pii(text)
    assert "support@example.com" not in result
    assert "[EMAIL REDACTED]" in result


def test_pdpa_mask_phone():
    """Phone numbers in answers must be redacted."""
    from app.rag import mask_pii
    text = "Call us at 012-3456789 or +60123456789."
    result = mask_pii(text)
    assert "012-3456789" not in result
    assert "[PHONE REDACTED]" in result


def test_pdpa_clean_text_unchanged():
    """Text without PII should pass through unchanged."""
    from app.rag import mask_pii
    text = "The warranty period is 12 months from date of purchase."
    assert mask_pii(text) == text
