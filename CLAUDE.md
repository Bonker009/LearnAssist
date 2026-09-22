# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

LearnAssist: turns lecture files, recordings, links and notes into summaries, cited Q&A and quizzes. **Every AI answer must cite the exact slide, page, section or timestamp it came from**, and that rule shapes the whole architecture. `README.md` is detailed and current. Read its "Things worth knowing before changing something" section before you touch storage, fetching, caching, quizzes or cross-service models.

## Commands

```bash
cp .env.example .env
docker compose up -d                 # postgres(55432) rustfs(9000/9001) redis(6381) ai(8000) api(8081) web(3001)
cd web && npm install && npm run dev # dev frontend on :3000
curl localhost:8000/health/ready     # reports Postgres, RustFS, Ollama and missing models separately
```

Ollama runs **natively on the host**, not in Compose (`qwen2.5:32b-instruct` and `bge-m3`). Its address comes from `OLLAMA_BASE_URL`.

Each service also has its own CLAUDE.md with deeper detail: `ai/CLAUDE.md`, `api/CLAUDE.md` and `web/CLAUDE.md`.

**AI service (FastAPI, Python 3.12, uv, ruff line-length 100)**. Tests run inside the container. `tests/` is neither in the image nor mounted by Compose, so mount it:
```bash
docker compose run --rm -v ./ai/tests:/srv/tests ai sh -c "uv pip install --system -q pytest pytest-asyncio && python -m pytest tests -q"
# single file / test:     ... python -m pytest tests/test_chunking.py::test_name -q
# From Git Bash on Windows, prefix with MSYS_NO_PATHCONV=1, or the mount silently fails ("file or directory not found: tests").
# skip Whisper/model tests: ... python -m pytest tests -q -m 'not slow'
```
`ai/app` is bind-mounted and uvicorn runs with `--reload`, so Python edits apply without a rebuild. Changes to `pyproject.toml` or the Dockerfile need `docker compose build ai`. Set `WHISPER_MODEL=tiny` for faster local iteration.

**API (Spring Boot 4.1, Java 25, Gradle)**:
```bash
cd api && ./gradlew test
cd api && ./gradlew test --tests 'com.learnassist.api.service.StreakTest'
```
API code changes need `docker compose up -d --build api`.

**Web (Next.js 16, React 19, Tailwind v4, shadcn)**: `npm run build` (the frontend "test"), `npm run lint`.
- `web/CLAUDE.md` → `web/AGENTS.md`: this Next.js version has breaking changes. Before writing Next.js code, read the relevant guide in `web/node_modules/next/dist/docs/`.
- The API allows exactly one CORS origin (`APP_CORS_ORIGIN`). Compose sets it to `http://localhost:${WEB_PORT:-3001}`, so a `npm run dev` frontend on :3000 against the containerised API gets CORS errors until that value matches.

## Architecture

```
browser ──JWT──► Spring Boot (api/) ──internal REST + X-Internal-Key──► FastAPI (ai/)
                   │ owns users, documents, ingest_jobs,           │ owns chunks + pgvector index
                   │ summaries, conversations, chat, quizzes,      │ parsing, Whisper, OCR, RAG, quiz,
                   │ flashcards, slide decks                       │ flashcard + slide outline gen
                   ├──internal REST──► slides/ (Node, Slidev build + PDF export → RustFS)
                   └──────────────► Postgres + pgvector ◄──────────┘
                    RustFS (S3) for uploads + built decks · Redis for the answer cache · Ollama on the host
```

- **The browser only talks to Spring Boot.** Spring enforces ownership and then proxies to FastAPI through `service/AiClient.java`. FastAPI endpoints (`/ingest`, `/query`, `/quiz`, transcription) require the internal key.
- **Schema is owned by Flyway** (`api/src/main/resources/db/migration/V*.sql`) with `ddl-auto=validate`. Every schema change is a new migration, including changes to tables that only Python uses. `chunks` intentionally has **no JPA entity** because Hibernate has no pgvector type. Java never writes chunks, and SQLAlchemy reads and writes them directly.
- **Ingest is async.** `POST /ingest` returns 202 and runs `rag/ingest.run_ingest` as a background task. That task writes progress straight into Spring-owned `ingest_jobs` and `documents` rows (stages PARSING → TRANSCRIBING/OCR → CHUNKING → …). The frontend polls job status through the API. A re-ingest deletes the document's chunks first and bumps its generation counter, which retires its cached answers.
- **The core abstraction**: every parser (`ai/app/parsers/*`, `transcribe/*`, `ocr/*`) emits units that become `Chunk`s. Each chunk carries exactly **one** `SourceRef` (slide, page, section or timestamp). A chunk never spans two source refs. The splitter (`chunking/splitter.py`) and a DB `CHECK` constraint both enforce this, and one retrieval path plus one UI component (`web/src/components/citation.tsx`) serve every input type.
- **Guardrails.** `guard/` is a separate internal service running LLM Guard (it pins a transformers version Qwen3-ASR cannot share). `ai/app/guard.py` sends it every chat question (prompt injection, toxicity) before retrieval and every answer (toxicity) before caching; flagged messages get a localised refusal. The models are English-only: mostly-Khmer questions are injection-checked on their Latin words only, because the model flags ordinary Khmer as injection. `GUARD_URL` empty disables it; `guard_fail_open` decides what an outage does.
- **Citations are validated.** `rag/citations.py` strips citation markers the model invented before they reach the UI.
- **Pluggable providers**: `embeddings/base.py` and `llm/base.py` define the interfaces. Ollama is the implementation. The embedding dimension is fixed at `VECTOR(1024)` (bge-m3). Changing the embedding model needs a migration and a full re-index.
- **Cross-service models**: Jackson sends camelCase and Pydantic uses snake_case. New FastAPI request models must extend `ServiceRequest` in `ai/app/models.py` (camelCase aliases), or they will 422.
- **Quiz answer key**: `correctIndex`/`explanation` exist only in `GradeResponse`, never in `QuestionResponse`. Keep it that way.
- **Flashcards and slides** reuse the quiz pattern: sample chunks across the document, have the model cite numbered blocks, and bind each card or slide to its real `SourceRef` in code. For slides the model returns a JSON outline only, and `ai/app/study/slides.py` renders the Slidev markdown, escaping all model text (Slidev markdown is compiled to Vue templates). Slide decks are async: Spring's `SlideService` calls FastAPI `/slides`, then the `slides` service `/render`, which uploads `site/**`, `deck.pdf` and `slides.md` under `slides/{deckId}/`. The browser polls `GET /api/slide-decks/{id}`.
- **`/api/slides/view/{token}/**` is the one unauthenticated data route.** An iframe cannot send the JWT, so a random `view_token` (not the deck id) is the capability. It has its own `SecurityFilterChain` that allows framing by `APP_CORS_ORIGIN` only.

## Web conventions

- Design tokens are three layers in `web/src/app/globals.css`: primitive → semantic → component. Components use **semantic** tokens only. Dark mode redefines the semantic names under `.dark`, so don't add `dark:` variants. shadcn token names are aliases of the semantic layer.
- Base rules go inside `@layer base`. Unlayered rules override every Tailwind utility.
- Khmer text: set `lang="km"` (it picks up Kantumruy Pro automatically). Use `font-display-km` for display titles. Bilingual titles put the Khmer line first.
- The API client lives in `web/src/lib/api.ts` (`NEXT_PUBLIC_API_BASE_URL`, default `http://localhost:8081`). Uploads go straight to RustFS through presigned URLs.

## Gotchas

- `ai/app/fetch.py` is the SSRF guard for student-supplied URLs. Never replace it with a plain `httpx.get`. YouTube URLs are rebuilt from the video id before they are passed to yt-dlp.
- S3 needs two endpoints: `APP_S3_PUBLIC_ENDPOINT` for presigning (the browser-visible host) and `APP_S3_ENDPOINT` for server calls. If you merge them, uploads fail with `SignatureDoesNotMatch`. Path-style addressing is required because RustFS is not AWS.
- Only a chat's first question is answer-cached. The cache key covers the attached resource set at its current generations.
- The rate limiter (`api/.../service/RateLimiter.java`) is in-memory, so it only works with a single replica.
- Host ports are non-default: Postgres is on 55432 and the API on 8081.
