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
