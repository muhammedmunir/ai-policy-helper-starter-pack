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
  <img width="1919" height="996" alt="Screenshot 2026-03-18 210749" src="https://github.com/user-attachments/assets/6f9d1c96-c7a0-4445-abf7-d0546567a822" />

- Backend API: http://localhost:8000/docs
  <img width="2650" height="2098" alt="localhost_8000_docs" src="https://github.com/user-attachments/assets/a1a5f7cb-4e04-4815-8c03-142b44848b3c" />

- Qdrant UI: http://localhost:6333
  <img width="1919" height="260" alt="Screenshot 2026-03-18 210948" src="https://github.com/user-attachments/assets/b56a83ca-cc7a-49d2-8a44-0e220922fa41" />

3. Ingest dokumen polisi (dari Admin tab UI) atau:
```bash
curl -X POST http://localhost:8000/api/ingest
```

4. Tanya soalan:
```bash
curl -X POST http://localhost:8000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is the shipping SLA to East Malaysia for bulky items?"}'
