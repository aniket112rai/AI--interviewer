# AI Interviewer

Resume-based voice interview practice app.

## Prerequisites

- Python 3.11 or newer
- Node.js and npm
- A hosted PostgreSQL database and its connection URL
- Self-hosted `livekit-server` available on `PATH`
- OpenAI API access and Deepgram API access

Copy `.env.example` to `.env`, then set your API keys, AI Credits base URL, and hosted PostgreSQL `DATABASE_URL`. The app uses that URL directly; it does not create or connect to a local database.

## Run locally (four processes)

```bash
livekit-server --dev
cd backend && uvicorn api.main:app --reload --port 8000
cd backend && python -m agent.main dev
cd web && npm run dev
```

The API is at `http://localhost:8000`; the web app is at `http://localhost:5173`.
