import logging
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List
from .models import IngestResponse, AskRequest, AskResponse, MetricsResponse, Citation, Chunk
from .settings import settings
from .ingest import load_documents
from .rag import RAGEngine, build_chunks_from_docs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("policy_helper")

app = FastAPI(title="AI Policy & Product Helper")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - t0) * 1000, 1)
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%s",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = RAGEngine()

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/metrics", response_model=MetricsResponse)
def metrics():
    s = engine.stats()
    return MetricsResponse(**s)

@app.post("/api/ingest", response_model=IngestResponse)
def ingest():
    logger.info("ingest started data_dir=%s", settings.data_dir)
    try:
        docs = load_documents(settings.data_dir)
    except FileNotFoundError as e:
        logger.error("ingest failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    if not docs:
        logger.warning("ingest found no valid documents in %s", settings.data_dir)
        raise HTTPException(status_code=422, detail="No valid documents found in data directory.")
    chunks = build_chunks_from_docs(docs, settings.chunk_size, settings.chunk_overlap)
    new_docs, new_chunks = engine.ingest_chunks(chunks)
    logger.info("ingest complete new_docs=%s new_chunks=%s", new_docs, new_chunks)
    return IngestResponse(indexed_docs=new_docs, indexed_chunks=new_chunks)

@app.post("/api/ask", response_model=AskResponse)
def ask(req: AskRequest):
    logger.info("ask query=%r k=%s", req.query, req.k)
    if not req.query or not req.query.strip():
        ctx = []
        answer = "Please provide a question."
    else:
        ctx = engine.retrieve(req.query, k=req.k or 4)
        try:
            answer = engine.generate(req.query, ctx)
        except RuntimeError as e:
            logger.error("generation failed: %s", e)
            raise HTTPException(status_code=503, detail=str(e))
    citations = [Citation(title=c.get("title"), section=c.get("section")) for c in ctx]
    chunks = [Chunk(title=c.get("title"), section=c.get("section"), text=c.get("text")) for c in ctx]
    stats = engine.stats()
    return AskResponse(
        query=req.query,
        answer=answer,
        citations=citations,
        chunks=chunks,
        metrics={
            "retrieval_ms": stats["avg_retrieval_latency_ms"],
            "generation_ms": stats["avg_generation_latency_ms"],
        }
    )
