# AI Interviewer

Practice resume-based interviews with a real-time voice interviewer and receive a feedback report when the session ends.

## Prerequisites

- macOS (commands below use the macOS Terminal and zsh)
- Python 3.11 or newer
- Node.js and npm
- `livekit-server` installed and available on your `PATH`
- A hosted PostgreSQL database and its connection URL
- An AI Credits API key and Deepgram API key

The app connects to the hosted database in `DATABASE_URL`. It does not need a local PostgreSQL server. The API creates/updates its SQLAlchemy tables on startup. Resume profiles are saved as JSON files under `data/`.

## First-time setup

Open Terminal and go to the project directory:

```bash
cd "/Users/aniketrai/Desktop/AI interviewer"
```

Create your local environment file, then edit it and fill in your real credentials:

```bash
cp .env.example .env
open -e .env
```

Set at least these values in `.env`:

- `OPENAI_API_KEY`: your AI Credits key
- `OPENAI_BASE_URL`: AI Credits OpenAI-compatible endpoint (the example is prefilled)
- `OPENAI_MODEL_FAST` and `OPENAI_MODEL_STRONG`: model names supported by your AI Credits account
- `DEEPGRAM_API_KEY`: your Deepgram key
- `DATABASE_URL`: your hosted PostgreSQL URL, in `postgresql+asyncpg://...` format
- `JWT_SECRET` and `INTERNAL_SECRET`: replace the example values with private random values

Keep the other example settings unless your local services use different addresses or ports. Do not commit `.env` or share its contents.

Install backend dependencies and create the virtual environment:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd ..
```

Install frontend dependencies:

```bash
cd web
npm install
cd ..
```

If `livekit-server` is not installed, install the self-hosted LiveKit server for macOS and verify it is on your `PATH`:

```bash
livekit-server --version
```

## Start the app

Run each command in its own Terminal tab or window. Keep all four processes running while using the app.

**Terminal 1 — LiveKit server**

```bash
cd "/Users/aniketrai/Desktop/AI interviewer"
livekit-server --dev
```

The development server uses `ws://localhost:7880` and the example development credentials (`devkey` / `secret`). Keep this terminal open. If it exits, the agent cannot connect and reports connection errors for `localhost:7880`.

**Terminal 2 — API**

```bash
cd "/Users/aniketrai/Desktop/AI interviewer/backend"
.venv/bin/uvicorn api.main:app --reload --port 8000
```

**Terminal 3 — interview agent**

```bash
cd "/Users/aniketrai/Desktop/AI interviewer/backend"
.venv/bin/python -m agent.main dev
```

**Terminal 4 — web app**

```bash
cd "/Users/aniketrai/Desktop/AI interviewer/web"
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser. The API health endpoint is [http://localhost:8000/api/health](http://localhost:8000/api/health) and should return `{"ok":true}`.

## Troubleshooting

- **`Address already in use` on port 8000:** an API process is already using that port. Use the existing API, or stop its process before starting another one.
- **Agent cannot connect to `localhost:7880`:** start or restart Terminal 1 with `livekit-server --dev`; then restart the agent in Terminal 3.
- **Database connection error:** verify the hosted database is reachable and `DATABASE_URL` is correct. The app does not fall back to a local database.
- **AI or transcription request errors:** verify the AI Credits base URL, API key and model names, plus the Deepgram API key, in `.env`.
- **Frontend dependency/build issues:** from `web/`, run `npm install`; use `npm run build` to check the production bundle.

## Project notes

- The app uses in-house email/password authentication.
- Uploaded resumes are parsed in memory and discarded. Only the extracted profile JSON is retained under `data/resumes/`.
- Application records (users, sessions, turns, evaluations and reports) live in the hosted PostgreSQL database.
- `build.md` is a development progress log; it is not needed to run the app.
