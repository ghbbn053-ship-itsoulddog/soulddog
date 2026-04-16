# AI Handover Guide

## Scope
This project is a campus education assistant with:
- `frontend/` (active Next.js app)
- `backend/` (active FastAPI app)
- Docker compose local/dev orchestration

Root `src/` exists but is legacy; prioritize `frontend/src/`.

## Current Critical Rules
- Package manager: `pnpm` only (frontend)
- Must keep user data isolated by student id (`username`)
- Never trust only client-side localStorage for isolation

## Known Fixed Issues (2026-04-16)
- Fixed: education data schema mismatch between scraper output and storage/vectorization.
  - `成绩信息` from scraper is `按学期`, not `成绩列表`.
  - `课表信息` is object with `课程列表`, not always list.
  - `考试安排` is object with `考试列表`, not always list.
  - Implemented normalization in `backend/app/services/data_processor.py`.
- Fixed: chat history endpoint now enforces per-username ownership.
  - `GET /api/chat/history/{id}` requires `username`.
- Fixed: chat endpoints enforce cookie/request username consistency.
  - `session_username` cookie is validated in chat APIs.
- Fixed: frontend stream parser now handles fragmented SSE chunks.
  - Implemented buffered SSE parsing in `frontend/src/app/chat/page.tsx`.
- Fixed: local conversation cache key is now per-username.
  - `current_conversation_id_<username>`

## Environment & Secret Strategy (for frequent key rotation)
1. Keep all keys in environment variables only.
2. Do not commit keys into:
   - `docker-compose.yml`
   - markdown docs
   - test scripts
3. Use `.env` or deployment platform secrets:
   - `QWEN_API_KEY`
   - `JWT_SECRET_KEY`
   - DB credentials
4. When rotating key:
   - Update env
   - restart backend container
   - verify `/api/health` then one chat request

## Recommended Runtime Checks
After pull/deploy, verify in this order:
1. Login works and returns `sync_status`.
2. `/api/sync-status?username=<id>` transitions to completed/failed.
3. Chat stream shows incremental tokens.
4. Refresh page: conversation history still visible.
5. Switch account: old account history must not be readable.

## Fast Debug Paths
- Backend logs: `docker logs backend --tail 80`
- Frontend logs: `docker logs frontend --tail 80`
- Critical files:
  - `backend/main.py`
  - `backend/app/api/chat.py`
  - `backend/app/services/data_processor.py`
  - `backend/app/services/qwen_service.py`
  - `frontend/src/app/chat/page.tsx`
  - `frontend/src/app/login/page.tsx`

## Next Priorities
1. Move hardcoded secrets out of tracked files.
2. Add DB migration tool (Alembic) and schema versioning.
3. Add integration tests for:
   - per-user isolation
   - SSE stream parse
   - data normalization pipeline
