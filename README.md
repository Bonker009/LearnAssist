# LearnAssist — AI-Powered Learning Assistant

Turn lecture slides, documents and recordings into summaries, grounded answers and
practice quizzes — where **every AI answer cites the exact slide, page or timestamp
it came from**.

An uncited answer from a language model is indistinguishable from a hallucination,
and a student cannot verify it against the lecture. Source attribution is therefore
not a feature bolted on at the end; it is the constraint the whole architecture is
built around.

---

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Compose stack, scaffolding | **Done** |
| 1 | PDF → summary → cited Q&A | **Done** (needs Ollama to run end to end) |
| 1b | Design system, citation UI | **Done** |
| 2 | PowerPoint and Word parsers | **Done** |
| 3 | Audio/video via Whisper + FFmpeg | **Done** |
| 4 | OCR fallback for scanned pages | **Done** |
| 5 | Quiz generation | **Done** |
| 6 | Caching, rate limiting, hardening | **Done** |

---

## Architecture

```
Next.js 16 (host :3000)
      │  JWT
      ▼
Spring Boot 4.1 :8081 ───────► Postgres 16 + pgvector :55432
  auth, files, quizzes,        users, documents, chunks(vector),
  job status, proxy            summaries, chat_messages
      │  internal REST               ▲
      ▼                              │
FastAPI :8000 ───────────────────────┘
  ingest pipeline, RAG
      │                    │
      ▼                    ▼
  RustFS :9000       Ollama (host :11434)
  raw uploads        chat + embeddings
  console :9001
  Redis :6381
  answer cache
```

**Service boundary.** Spring Boot owns users, documents, jobs and chat, via JPA, and
is the only service the browser talks to. FastAPI owns `chunks` and the vector index.
The browser never calls FastAPI; Spring Boot proxies after enforcing ownership.

**Why `chunks` has no JPA entity.** Hibernate has no native pgvector type. Because
Java never writes chunks, the column is simply left unmapped — Flyway creates it and
SQLAlchemy reads it. Adding a `Chunk` @Entity later would reintroduce the problem.

### The one abstraction that matters

Every parser — PDF, PowerPoint, Word, Whisper transcript — emits the same `Chunk`,
carrying exactly one `SourceRef` (`slide`, `page` or `timestamp`). That is what lets
one retrieval path and one UI component serve all input types. **A chunk never spans
two source references**, enforced both in the splitter and by a `CHECK` constraint in
the database, because a chunk drawn from two slides cannot be cited unambiguously.

---

## Host prerequisites

- **Docker Desktop**
- **Ollama, running natively on the host** (not in Compose — GPU passthrough via
  Docker Desktop is unreliable). Then pull the models:

  ```bash
  ollama pull qwen2.5:32b-instruct   # chat: summaries, Q&A, quizzes
  ollama pull bge-m3                 # embeddings, 1024-dim
  ```

  Running Ollama on a different machine? Set `OLLAMA_BASE_URL` in `.env` and start
  Ollama with `OLLAMA_HOST=0.0.0.0`.

  > **The embedding dimension is fixed in the schema** (`VECTOR(1024)` in
  > `V1__init.sql`). `bge-m3` matches it. A different embedding model needs a
  > migration *and* a full re-index; the provider fails loudly on a mismatch rather
  > than storing unusable vectors.

- **Node 20+** for the frontend.

---

## Running it

```bash
cp .env.example .env          # defaults work for local development
docker compose up -d          # postgres, rustfs, ai, api
cd web && npm install && npm run dev
```

Then open <http://localhost:3000>.

Check every dependency at once:

```bash
curl localhost:8000/health/ready
```

It reports Postgres, RustFS and Ollama **separately** and names any missing model,
rather than collapsing them into one unhelpful boolean.

### Non-default ports

Two ports were moved to avoid colliding with software already on the development
machine. Container-internal ports are unchanged.

| Service | Host port | Why not the default |
|---|---|---|
| Postgres | **55432** | A native `postgresql-x64-18` service owns 5432 and wins over Docker's mapping |
| Spring Boot | **8081** | Another project's container publishes on 8080 |

---

## Testing

```bash
# AI service: parsers, chunking, citation validation
docker compose run --rm ai sh -c "uv pip install --system -q pytest pytest-asyncio && python -m pytest tests -q"

# API
cd api && ./gradlew test

# Frontend
cd web && npm run build
```

The AI suite covers the three things that would silently break the product:

1. **Page attribution** — a known phrase must resolve to the page it is actually on.
2. **Chunk/source binding** — no chunk may span two `SourceRef`s, and two short
   slides must never be merged.
3. **Fabricated citations** — a `[9]` the model invented must be stripped before it
   reaches the UI, because a citation chip implies the claim was verified.

Media is covered end to end: FFmpeg extraction is asserted against real generated
audio and video (mono, 16 kHz, temp files cleaned up), and one `slow` test
synthesises speech with `espeak-ng`, transcribes it with Whisper and asserts the
spoken terms come back with usable timestamps. Skip the heavy ones with
`-m 'not slow'`.

Whisper is configured by `WHISPER_MODEL` / `WHISPER_DEVICE` / `WHISPER_COMPUTE`.
`tiny` makes local iteration much faster; `small` + `int8` is the CPU default.

---

## Layout

```
db/init/            pgvector extension, run once at first container init
api/                Spring Boot 4.1, Java 25, JPA + Flyway
  .../domain        entities; Flyway owns the schema, ddl-auto=validate
  .../service       StorageService (presigned URLs), AiClient, DocumentService
  .../web           controllers, DTOs, error handling
ai/                 FastAPI, Python 3.12
  app/parsers       one parser per input format -> ParsedUnit
  app/transcribe    ffmpeg extraction, Whisper, transcript windowing
  app/ocr           fallback for pages with no text layer
  app/chunking      splitter; never crosses a source boundary
  app/embeddings    EmbeddingProvider interface + Ollama impl
  app/llm           LLMProvider interface + Ollama impl
  app/rag           ingest, retrieve, prompts, citation resolution
  app/quiz          stratified sampling, generation, validation
web/                Next.js 16, Tailwind v4
  src/app/globals.css           three-layer design tokens
  src/components/citation.tsx   the signature UI primitive
```

---

## Design system

Tokens are three-layer, in `web/src/app/globals.css`:

**primitive** (raw scales, no meaning) → **semantic** (`--color-surface`,
`--color-citation`) → **component** (`--control-radius`).

Components reference *semantic* tokens only. Dark mode redefines the same semantic
names under `.dark`, so no `dark:` variants are scattered through the markup and a
theme change stays a one-file edit.

`<Citation>` is the product's signature element: one component renders a slide, page
or timestamp chip from a `SourceRef` and drives the source viewer (jumping a PDF to
the page, seeking a recording to the second). Every surface that shows a source uses
it, so adding a new source kind is a change in one file.

---

## Things worth knowing before changing something

- **Presigned URLs are signed against a different endpoint than server-side calls.**
  The browser cannot resolve `rustfs`, and an S3 signature covers the Host header, so
  presigning uses `APP_S3_PUBLIC_ENDPOINT` while the S3 client uses `APP_S3_ENDPOINT`.
  Collapsing these into one client breaks uploads with `SignatureDoesNotMatch`.
- **Path-style S3 addressing is mandatory.** RustFS is not AWS; virtual-host style
  requests do not resolve.
- **Jackson serialises camelCase; Pydantic expects snake_case.** The FastAPI request
  models accept camelCase aliases at the boundary. A new cross-service model must
  extend `ServiceRequest`, or it will 422.
- **Re-ingesting deletes the document's chunks first.** Without that, a retry silently
  doubles every chunk in the index.
- **The answer cache is keyed by a per-document generation counter.** A re-ingest
  bumps it, retiring every cached answer for that document at once. Without it, a
  cached answer would go on citing chunks that no longer exist.
- **The rate limiter is in-memory, so it is per-instance.** Correct at one replica,
  wrong at two — a user would get double the budget. Move the counter to Redis
  before scaling out.
- **The quiz answer key lives only in `GradeResponse`.** `QuestionResponse` has no
  `correctIndex` or `explanation` field at all. That omission is the control:
  suppressing the fields with `@JsonIgnore` on the entity would leave the answer key
  one deleted annotation away from the browser.
