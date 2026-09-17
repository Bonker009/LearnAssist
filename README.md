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
| 7 | Chat interface, links/images/notes, Khmer voice input | **Done** (needs Docker to run end to end) |

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
  src/components/chat/          chat screen: sidebar, composer, messages, resource panel
  src/hooks/use-voice-recorder  MediaRecorder capture for voice messages
```

---

## Design system

Tokens are three-layer, in `web/src/app/globals.css`:

**primitive** (raw scales, no meaning) → **semantic** (`--color-surface`,
`--color-citation`) → **component** (`--control-radius`).

Components reference *semantic* tokens only. Dark mode redefines the same semantic
names under `.dark`, so no `dark:` variants are scattered through the markup and a
theme change stays a one-file edit. shadcn's token names (`--background`,
`--muted-foreground`, …) are aliases of the semantic layer.

**Visual language**

- **Colour:** brand blue `#00518D` (`--color-primary`) for primary actions, links and
  key marks; accent red `#EA1D24` (`--color-emphasis`) for strong secondary emphasis
  such as the English line under a Khmer title. Cool blue-gray neutrals. Success is
  green and warning orange, so neither reads as brand or accent. `--color-chart-1…5`
  (blue, teal, amber, violet, rose) are for data.
- **Type:** Plus Jakarta Sans for Latin; Kantumruy Pro for Khmer text (applied
  automatically to anything with `lang="km"`); Dangrek for Khmer display titles
  (`font-display-km`). Bilingual titles put the Khmer line first and the English line
  smaller, in the accent.
- **Shape and size:** radius sm 6 / md 8 / lg 10 / xl 14 px; controls xs 24 / sm 32 /
  default 36 / lg 40 px. Only a single primary call to action (send) is fully round.
- **Surfaces:** canvas → cards (`shadow-sm`) → floating menus and dialogs
  (`shadow-lg`). Shadows are soft and low.
- **Motion and feedback:** 150–250 ms, ease-out, no bounce; skeletons pulse; focus is
  a soft ring in the theme's ring colour; invalid fields tint border and ring and
  carry an icon and message.
- **Micro-labels** (`micro-label`): uppercase, slightly tracked. Numbers in status
  lines use tabular figures.

**Components from community registries.** Besides official shadcn primitives: the
chat composer adapts blocks.so `ai-01`/`ai-04`; voice input uses ElevenLabs UI
`LiveWaveform` and `ShimmeringText` (installed from the raw GitHub registry JSON, since
ui.elevenlabs.io blocks CLI requests); the dashboard uses Magic UI `MagicCard`,
`NumberTicker` and `BorderBeam` with shadcn `chart` (Recharts).

**AI presence** (`components/ai-orb.tsx`, styles under "AI presence" in
`globals.css`): a soft glow in brand tints with a sparkle, plus flowing waves on the
welcome screen. It breathes when idle, swells with the microphone level while
listening, and turns faster while transcribing or answering. It is CSS only — an
earlier WebGL orb looked harsh and pulled in three.js — and it stops moving for
reduced-motion users.

`<Citation>` is the product's signature element: one component renders a slide, page
or timestamp chip from a `SourceRef` and drives the source viewer. It keeps its own
amber hue, distinct from both brand colours, so a source never reads as a button or
an alert.

> Base rules in `globals.css` live in `@layer base`. An unlayered rule beats every
> Tailwind utility, which is how `* { border-color }` once gave every ghost button a
> visible border. Global font stacks are written out rather than using
> `var(--font-sans)`, because `@theme inline` does not emit theme values as CSS
> variables.

---

## Chat interface

The app is a chat. Each chat holds **resources** (uploaded files, web pages, YouTube
videos, photos, pasted notes) and answers only from those, citing the file *and* the
page, slide, section or timestamp. A resource can be reused in other chats from the
library without being processed again.

| Resource | How it is read | Citation lands on |
|---|---|---|
| PDF | PyMuPDF, OCR fallback | the page, in the browser's PDF viewer |
| PowerPoint / Word | python-pptx / python-docx | the slide or section, in the text reader |
| Audio / video | FFmpeg + Whisper | the timestamp, in the player |
| YouTube link | yt-dlp (audio only, never stored) + Whisper | the timestamp, in the embedded video |
| Web page link | safe fetch + trafilatura, HTML snapshot kept | the section, in the text reader |
| Photo / screenshot | Tesseract (`eng+khm`) | the image and its OCR text |
| Pasted notes, .txt, .md | split by Markdown heading or paragraph | the section, in the text reader |

The composer is adapted from the blocks.so shadcn blocks `ai-04` (attachments, +
menu, drop zone) and `ai-01` (voice input), in `web/src/components/chat/composer.tsx`.
shadcn primitives live in `components/ui`; their token names (`--background`,
`--muted-foreground`, …) are aliases of the semantic layer in `globals.css`, so they
follow the design system and dark mode without a second palette.

### Dashboard

`/dashboard` shows study activity from `GET /api/dashboard?tz=<IANA zone>`: totals,
a 30-day activity chart, resource mix, quiz score trend, most-cited resources (read
from the stored citation JSON), recent chats, a study streak and anything still
processing. Days are bucketed in the student's time zone. Every query is scoped by
owner in its own `WHERE`, including the citation join, so an aggregate never counts
another student's rows.

### Khmer

- **Voice input.** The mic records in the browser and sends the clip to
  `POST /api/speech/transcribe`, which runs Whisper in the AI container. The composer
  has a ខ្មែរ / EN / Auto switch; with ខ្មែរ, `WHISPER_MODEL_KM`
  ([PhanithLIM/whisper-small-khmer-ct2](https://huggingface.co/PhanithLIM/whisper-small-khmer-ct2),
  ~8.9% CER on FLEURS) is used instead of the stock model, which handles Khmer poorly.
  The browser Web Speech API was not used: its Khmer support is Chrome-only and
  sends audio to Google.
- **Khmer recordings** are detected by the base model and re-transcribed with the
  Khmer model automatically.
- **Replies** come back in Khmer when the question is in Khmer (detected from the
  script, not a model). The refusal sentence is emitted in English by the model and
  localised in code, so "not covered" is still detected reliably.
  `qwen2.5:32b-instruct` writes serviceable but stiff Khmer; a stronger multilingual
  chat model can be swapped in with `OLLAMA_CHAT_MODEL`.
- **Chunking** splits Khmer on ។/៕ and never cuts inside a consonant cluster, since
  Khmer has no spaces between words.

The first Khmer voice message downloads the Khmer model (~250 MB) into the
`model-cache` volume, so it is slow once.

---

## Things worth knowing before changing something

- **Link fetching is an SSRF surface.** The AI service fetches student-supplied URLs
  from inside the compose network, one hop from Postgres, RustFS and host Ollama.
  `app/fetch.py` resolves the host, refuses any non-public address, connects to the
  *checked* IP (with SNI set to the hostname, so TLS still verifies), and re-checks
  every redirect. Don't replace it with a plain `httpx.get(url)`.
- **YouTube downloads rebuild the URL from the video id.** Passing the student's URL
  to yt-dlp would let its generic extractor fetch arbitrary hosts. If YouTube links
  start failing, upgrade `yt-dlp` — YouTube changes frequently.
- **Only a chat's first question is answer-cached.** With history, the same words
  can mean something else. The key covers the exact set of attached resources at
  their current generations.

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
