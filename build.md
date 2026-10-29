# AI Interviewer Build Log

## Status

| Phase | Status |
| --- | --- |
| Phase 0 | done |
| Phase 1 | blocked |
| Phase 2 | done |
| Phase 3 | done |
| Phase 4 | done |
| Phase 5 | done |
| Phase 6 | done |
| Phase 7 | done |
| Phase 8 | blocked |
| Phase 9 | not started |

## Deviations from PLAN

- Added `OPENAI_BASE_URL` to `.env.example` and typed settings so the OpenAI client can target the user's AI Credits API endpoint.
- Set the configurable Deepgram TTS example to `aura-2-thalia-en`, an Aura-2 English model listed in Deepgram's current docs.
- Configured both OpenAI model settings to `openai/gpt-4o-mini` and the documented AICredits OpenAI-compatible base URL, per the user's instruction.
- Per the user's clarification, the database is hosted and should be accessed through Prisma; this overrides the plan's local-only PostgreSQL prerequisite.
- Hosted database URL is the only database target. Any plan text suggesting a local database is superseded by the user's instruction.
- Phase 1 uses LiveKit Agents 1.8.10's nested `turn_handling` configuration and `max_completion_tokens`; this replaces the plan's conceptual flat option names and generic token limit.
- The installed multilingual turn-detector plugin is deprecated upstream, but remains the available self-hosted local multilingual detector in the pinned LiveKit version. Its model assets are downloaded during worker prewarm.
- The configured AICredits host (`aicredits.in`) returned HTTP 403. Updated `.env` and `.env.example` to the documented API host (`api.aicredits.in`); a minimal GPT-4o-mini chat completion returned HTTP 200.
- Per the user's Phase 2 request, database/schema work is proceeding while the Phase 1 live speech check remains pending; the Phase 1 status stays blocked until that manual check is completed.
- Replaced the exact `JWT_SECRET=change-me` template value in local `.env` with a randomly generated secret after HS256 warned that the template was too short; the secret value was not logged.
- Added resume `profile_path`/`error` and session `profile_snapshot` columns with idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements so the existing hosted schema receives the Phase 4 fields without Alembic.
- The installed PyMuPDF version deprecates `fitz`; resume parsing uses its `pymupdf` import and the same sorted text extraction API.
- LiveKit's current Python SDK supports explicit agent dispatch in the participant access token through `RoomConfiguration.agents`; used this documented token-based mechanism with JSON `session_id` metadata.
- Added `sessions.error` to retain a safe, user-facing planning failure message; applied idempotently to the hosted PostgreSQL schema.
- Defined a thin resume as fewer than two projects and under one year of experience so the one-fewer-topic rule is deterministic.
- Phase 6 follows the installed LiveKit Agents session events and React component hooks; categorical evaluation quality is stored separately from the numeric `quality` score.
- Replaced the deprecated Hugging Face multilingual detector with LiveKit's supported local `inference.TurnDetector(version="v1-mini")`; the former detector's cache had a broken model link and failed in the agent executor.
- The installed LiveKit transcript event does not expose STT confidence, so unclear transcripts are detected with short-response and text-shape heuristics.
- Worker disconnect handling keeps the active job available through the participant token's reconnect window, then finalizes the session if the candidate does not return.

## Build Log

### Phase 0: Foundation   [done]
- Built: root environment example, ignore rules, README, backend settings/async database engine/health API, and a minimal React + Vite + Tailwind landing page.
- How: added only the Phase 0 files and package manifests; installed dependencies, locked exact versions, and used the current Tailwind Vite plugin setup.
- Changes vs PLAN: added `OPENAI_BASE_URL` for AICredits and set both model roles to `openai/gpt-4o-mini`; selected Deepgram `aura-2-thalia-en` for the configurable Aura TTS model.
- Check result: frontend `npm run build` passed; hosted PostgreSQL connection succeeded through the app's async SQLAlchemy engine, and API startup completed with that connection. `GET /api/health` returned `{"ok":true}`. Prisma `db execute` also ran `SELECT 1` successfully; introspection found no tables, confirming the hosted database is empty. Python imports and `pip check` passed earlier. Initial AICredits check used a wrong host/route and returned HTTP 403; a later one-token GPT-4o-mini request to the documented gateway returned HTTP 200. Deepgram project authentication returned HTTP 200. `livekit-server` is not installed/on PATH.

### Phase 1: Voice loop spike   [blocked]
- Built: temporary fixed-room LiveKit token API, Deepgram/OpenAI interviewer worker, prewarmed Silero and multilingual turn detector, and browser room client with mic capture and remote audio playback.
- How: LiveKit Agents 1.8.10 APIs verified against installed source; OpenAI model/base URL and Deepgram models/keys come from settings. Added concise static interviewer instructions, recent-turn context trimming, interruption/resume settings, and per-turn latency logging.
- Changes vs PLAN: current SDK nests turn and interruption settings in `turn_handling`, caps via `max_completion_tokens`, and marks interrupted speech in its chat message. Turn detection uses LiveKit's supported local `v1-mini` implementation instead of the deprecated multilingual plugin; hosted DB URL is required, with no local fallback.
- Check result: Python compile/import passed; dev token endpoint returned a room-scoped token; frontend `npm run build` passed. A minimal GPT-4o-mini call through the corrected AICredits gateway returned HTTP 200. Voice latency, barge-in, backchannel filtering, and thinking pauses remain unverified because `livekit-server` is not installed/on `PATH`; live speech check is required before Phase 1 can be marked done.
- Open issues: `livekit-server` is now installed and starts locally; Phase 1's live room latency, interruption, backchannel, and thinking-pause checks still need a real interview run.

### Phase 2: Database and schemas   [done]
- Built: SQLAlchemy models for all seven tables, Pydantic schemas, atomic resume profile JSON storage, prompt skeletons, structured-output LLM helper, and `scripts/check_phase2.py`.
- How: uses async SQLAlchemy 2 style with PostgreSQL JSONB over the hosted `DATABASE_URL`; profile writes use a same-directory temporary file and `os.replace()`.
- Changes vs PLAN: uses the user's hosted database URL instead of any local database. Phase 2 was explicitly requested while Phase 1's manual voice check remains pending.
- Check result: Python compile passed; manual script created the schema on the hosted DB, inserted and read back user/resume/session/plan/turn/evaluation/usage/report rows, cleaned up its sample rows, and verified interrupted profile writes preserve the previous complete JSON.

### Phase 3: Auth   [done]
- Built: bcrypt signup/login, HS256 JWT authentication, current-user and daily-usage response, five-failure email rate limit, frontend auth context, protected routes, login/signup pages, dashboard stub, shared API fetch wrapper, and polling hook.
- How: all account data uses the hosted database; the frontend stores the JWT in `localStorage`, loads `/api/auth/me` on refresh, and clears credentials and redirects after protected API 401 responses.
- Changes vs PLAN: the fifth failed password attempt itself returns `429`, matching the phase check wording; omitted signup names default to the email prefix. Kept the Phase 1 voice spike at `/voice-loop` behind authentication.
- Check result: Python compile and Vite production build passed. `scripts/check_phase3.py` verified signup, login, protected `/me`, token reuse, and five failed attempts on the hosted DB; browser flow verified signup, logout, login, refresh persistence, and protected-route redirect. Temporary check accounts were removed.

### Phase 4: Resume upload and profile extraction   [done]
- Built: protected PDF/DOCX upload, file size/extension/magic validation, sorted PDF and table-aware DOCX text extraction, regex removal of contact details and labeled/street addresses, structured profile extraction, atomic JSON persistence, status/error polling endpoints, ownership checks, deletion, and startup recovery of stale parsing rows.
- How: uploaded bytes and extracted text stay in memory; only the sanitized `Profile` JSON is written under `data/resumes/`. The extraction uses `OPENAI_MODEL_STRONG` through the configured AICredits base URL, with one schema-validation retry. Dashboard lists status and summaries; upload page polls and displays summary, skills, and probe targets.
- Changes vs PLAN: added the explicitly required `profile_path`, `error`, and `sessions.profile_snapshot` fields to the existing schema via idempotent hosted PostgreSQL `ALTER TABLE` statements; enforced 3–6 `probe_targets` in the Profile schema. Uses `pymupdf` import for the installed PyMuPDF version.
- Check result: Python compile and Vite build passed. `scripts/check_phase4.py` successfully extracted real PDF and DOCX profiles through AICredits, confirmed contact details were absent and 3–6 probe targets were present, returned the exact friendly scanned-PDF error, enforced ownership, removed the JSON on deletion, and verified session snapshots survive resume deletion. Temporary DB rows and files were cleaned up.

### Phase 5: Plan generation and sessions   [done]
- Built: protected session create/list/detail/token endpoints, weighted resume-specific plan generation, quota and single-live-session checks, stale planning recovery, LiveKit token dispatch, `NewInterview`, session-based voice entry, and dashboard session history.
- How: snapshots the sanitized profile in the session row, generates one structured plan in a background task using the configured strong model (GPT‑4o‑mini via AICredits), computes thread budgets from duration and weights, and sends only topic names through the session detail API.
- Changes vs PLAN: adds a `sessions.error` column for safe planning failure feedback. Used the documented token-based dispatch option, with a deterministic thin-profile cutoff of <2 projects and <1 year of experience.
- Check result: Python compile and Vite production build passed. `scripts/check_phase5.py` generated 15/30/45-minute plans with 3/5/8 resume-specific topics through AICredits, confirmed topic-only session details, minted room-scoped LiveKit tokens, verified the Phase 1 dev token route is gone, and confirmed over-quota creation returns 429. Temporary check rows/files were cleaned up. Actual LiveKit room/agent connection remains unverified while `livekit-server` is unavailable.

### Phase 6: Adaptive interview   [done]
- Built: plan-driven agent directives and thread progression, resume keyterm hints, asynchronous answer evaluation and state updates, persisted turns/evaluations, internal session finalization, reconnect recovery, the mic-check/interview room UI, and local EOT model prewarm. Opening introductions are retained as unscored turns; evaluator jobs are tracked and drained before finalization.
- How: added an agent runtime over stored plan/live state, schedules strong-model evaluation outside speech generation, records interrupted assistant turns, and sends the end signal through the LiveKit data channel. Late evaluator results still merge their thread goal coverage; short interview-format questions bypass the unclear-transcript heuristic. The frontend checks actual microphone input and provides transcript, timer, mute, and end confirmation.
- Changes vs PLAN: the installed transcription event has no confidence value, so short or garbled text uses an explicit transcript heuristic. Disconnect finalization waits through the token reconnect window. Added hosted PostgreSQL columns for actual duration, end reason, and categorical evaluation quality.
- Changes vs PLAN: replaced the deprecated Hugging Face multilingual detector with LiveKit's supported local `v1-mini` detector. This stays on-device and avoids the broken model-cache path and a cloud detector service.
- Check result: Python compile/import and frontend production build passed. The user reports completing the manual Phase 6 verification; detailed latency readings and individual behavior/DB observations were not provided.
- Open issues: the SDK exposes no STT confidence, so the transcript heuristic is heuristic-based. `INTERNAL_SECRET` was still the template value at the last local inspection; replace it with a private value and restart API and agent together. Vite warns that its roughly 928 kB JavaScript bundle exceeds the 500 kB advisory threshold.

### Phase 7: Report generation   [done]
- Built: idempotent finalize/report endpoints, actual-minute quota accounting, structured report generation, early-interview conservatism, and the report UI with score bars, question details, strengths, gaps, next steps, and a failed state.
- How: finalization locks the session and adds usage only on the live-to-completed transition. It creates a pending report and schedules generation; a PostgreSQL advisory lock prevents concurrent duplicate model calls. The protected report endpoint handles stale live sessions and serves the saved report.
- Changes vs PLAN: uses a PostgreSQL advisory lock for cross-worker generation deduplication; report output contains `report` as specified. Estimated candidate content under three minutes uses scored answer word counts at 130 words/minute, excluding unscored turns.
- Check result: `scripts/check_phase7.py` passed against the hosted DB and configured AICredits endpoint using a temporary synthetic interview. It exercised the internal finalize and report route handlers, generated a schema-valid report, confirmed exactly three strengths/gaps and 3–5 next steps, and verified repeat finalize/report refresh did not change the saved report or daily usage. Temporary rows were deleted. Python compile, API route registration, and `npm run build` passed; Vite reports the existing ~934 kB bundle advisory.
- Follow-up: the completed session shown in the user's screenshot had no report row. The browser was receiving generic `404 Not Found` from an API process without the Phase 7 route. Started the current API on `127.0.0.1:8000`, confirmed health and route registration, then invoked the report endpoint for that completed session; report status is now `ready` with saved data. No interview turns were modified.
- Open issues: no real candidate interview was available in the hosted DB for a live transcript report check; the Phase 7 content match was checked with a synthetic transcript. The frontend production build passes, but its report screen was not manually browser-checked.

### Phase 8: Frontend completion   [blocked]
- Built: dashboard resume/session history with dates, scores and report links; current daily usage refresh; page-level loading/empty/error states; responsive navigation and page spacing; reconnect option after room loss; report pending/error states.
- How: added `report_status` to the session list API so dashboard polling can follow planning and report generation. Auth now reloads `/me` after signup/login, and the dashboard refreshes usage after return from an interview.
- Changes vs PLAN: session history exposes `report_status` for pending/failed report labels and polling.
- Check result: Python compile, API route/schema checks, and Vite production build passed. The requested new-user signup-to-report journey was not browser-verified: local browser use is disabled in this session, and completing it also requires a real voice interview.
- Open issues: run the full signup → resume upload → interview → report flow in a browser and verify mobile/desktop layout and reconnect behavior. Vite still reports a ~938 kB bundle-size advisory.

## Open issues

None outside the phase-specific issues listed under Phase 1 and Phase 6.

