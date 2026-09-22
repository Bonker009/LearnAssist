# CLAUDE.md — ai/ (FastAPI)

The ingest pipeline, RAG answering, quiz generation and dictation transcription. Only Spring Boot calls this service, and every endpoint except `/health*` needs the `X-Internal-Key` header. **This service does no ownership checks.** It trusts the document ids Spring sends, so never expose it to the browser. The repo-wide architecture is in `../CLAUDE.md`.

## Commands

Tests are not baked into the image, and Compose only mounts `app/`, so mount `tests/` when you run them (from the repo root):

```bash
docker compose run --rm -v ./ai/tests:/srv/tests ai sh -c "uv pip install --system -q pytest pytest-asyncio && python -m pytest tests -q"
#   one test:        ... python -m pytest tests/test_citations.py::test_name -q
# From Git Bash on Windows, prefix with MSYS_NO_PATHCONV=1, or the mount silently fails ("file or directory not found: tests").
#   skip slow ones:  ... python -m pytest tests -q -m 'not slow'   (slow = Whisper/Qwen inference / model downloads)
```

- The container has ffmpeg, tesseract (`eng+khm`) and the full dependency set. Running tests on the host needs those binaries too.
- The tests don't need Postgres, Redis or Ollama. `test_cache.py` covers the fail-open cache.
- Fixtures in `tests/fixtures/` (`lecture_sample.*`) come from the `make_*.py` scripts. Their text is known and differs on each page or slide, so tests can assert which source a phrase lands on. Regenerate them rather than hand-editing the binaries.
- Lint: `ruff check app tests` (rules E, F, I, UP, B; line length 100; py312).
- `app/` is hot-reloaded in the running container. Changes to `pyproject.toml` need `docker compose build ai`.

## Layout and flow

`main.py` defines the endpoints: `/ingest` (202, background task), `/query`, `/quiz`, `/transcribe` (synchronous, clip limit 25 MB) and `/health/ready`. The middleware binds the `X-Request-Id` that Spring forwards into every log line.

**Ingest** (`rag/ingest.py::run_ingest`):
1. Choose the source by `doc_type` or content type: `YOUTUBE` → `transcribe/youtube.py`; `WEB` → `fetch.py` + `parsers/web.py`; media → ffmpeg + speech-to-text (`transcribe/`: Qwen3-ASR for the languages it supports, Whisper for Khmer, the rest and language detection); images → OCR; otherwise the `_PARSERS` map (pdf, pptx, docx, text).
2. Parsers return a `ParseResult` of `ParsedUnit`s (`parsers/base.py`), one per page, slide, section or transcript window. PDF pages under `scanned_page_char_threshold` characters are flagged `needs_ocr` and re-read by `ocr/`.
3. A reader snapshot (JSON of the units) is uploaded next to the file so the UI's text reader can show sections.
4. `chunking/splitter.py::chunk_units` → `Chunk`s. Units are split by token count (tiktoken), with overlap *within* a unit only. Khmer text is split on ។/៕ and never mid-cluster.
5. Old chunks are deleted, then the new ones are embedded (bounded by `embed_concurrency`/`embed_batch_size`, since local Ollama handles requests one at a time) and stored (`rag/retrieve.py`). The cache generation is bumped.
6. The summary is generated and inserted.

Progress is written straight to Spring-owned `ingest_jobs`/`documents` rows with raw SQL (`_set_stage`, `_fail`). That, plus inserting `summaries`, is the only case where this service writes Spring's tables. Don't create or delete those rows from here.

**Query** (`rag/answer.py`): check the cache (first question only) → embed a retrieval query (the previous user turn prepended, with no LLM rewrite) → `retrieve` top-k across the chat's documents, expanded by ±`neighbour_window` ordinals → a numbered-block prompt (`rag/prompts.py`) → `rag/citations.py` maps each `[n]` to a `Citation` and **drops markers that don't match a supplied block**. When the model says the material doesn't cover the question, the answer is `grounded=False`. The refusal is emitted in English and localised in code (`not_covered_message`), and reply language comes from the question's script (`lang.py`).

**Guardrails** (`guard.py`): `answer_question` asks the `guard` service (repo-root `guard/`, LLM Guard) about the question before the cache and retrieval, and about the answer before it is cached. Tests leave `guard_url` empty, which disables the checks.

**Quiz** (`quiz/`): take a stratified sample of chunks across the document, generate with `complete_json`, then validate. The response includes the answer key, and Spring must never forward it to the browser before the student submits.

**Flashcards and slides** (`study/`): the same pattern as quizzes, using `quiz.generate.load_document_chunks` and `stratified_sample`. `/flashcards` returns cards bound to their `SourceRef`, deduplicated by front. `/slides` returns the cited outline plus Slidev markdown from `render_slidev`, which is pure and unit-tested (`tests/test_study.py`). Never let the model write the markdown, and keep all model text going through `_text()` (escape, entities, `v-pre`).

## Conventions

- Every DB access goes through `async with session_scope()` (`db.py`, asyncpg). There's no ORM mapping for chunks. Queries are raw `sqlalchemy.text`.
- Everything outside this module depends on `EmbeddingProvider` / `LLMProvider` (`embeddings/base.py`, `llm/base.py`) through `get_embedding_provider()` / `get_llm_provider()`, never on Ollama directly. `embed_query` and `embed_documents` stay separate because asymmetric models use different prefixes. `complete_json` parses defensively and retries once.
- Pydantic models that Spring posts extend `ServiceRequest` (camelCase aliases, and snake_case still accepted, which is what tests use). Responses sent back to Java also use camelCase aliases.
- `SourceRef.kind` is `slide | page | timestamp`. Sections (Word headings, web and notes sections) use `kind="page"` with `label_override`. A new format means a new parser that returns `ParsedUnit`s. Nothing downstream should need changing.
- Settings live in `config.py` (pydantic-settings, env vars). `embed_dim` must match `VECTOR(1024)` in the Flyway schema.
- `cache.py` is fail-open: if Redis is missing or down, the answer is just slower, never an error. Keep new cache code that way.
- Never fetch a URL except through `fetch.fetch_public_page`, which is the SSRF guard: it pins the resolved public IP, uses SNI, and re-checks every redirect.
