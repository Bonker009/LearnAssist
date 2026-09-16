-- Phase 1 schema.
--
-- Ownership rule: Spring Boot (JPA) is the only writer for every table here
-- EXCEPT `chunks`, which is written solely by the FastAPI service. The
-- `embedding vector(768)` column is deliberately NOT mapped by any JPA entity —
-- Hibernate has no native pgvector type, and since Java never writes chunks the
-- problem never arises. Do not add a Chunk @Entity without revisiting this.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name  VARCHAR(120) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id      UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    filename      VARCHAR(512) NOT NULL,
    content_type  VARCHAR(128) NOT NULL,
    -- pdf | pptx | docx | audio | video
    doc_type      VARCHAR(16)  NOT NULL,
    storage_key   VARCHAR(1024) NOT NULL,
    size_bytes    BIGINT       NOT NULL DEFAULT 0,
    -- PENDING_UPLOAD | UPLOADED | PROCESSING | READY | FAILED
    status        VARCHAR(24)  NOT NULL DEFAULT 'PENDING_UPLOAD',
    -- Page/slide count for documents, duration for media. Populated by ingestion.
    unit_count    INTEGER,
    duration_sec  DOUBLE PRECISION,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_documents_owner ON documents (owner_id, created_at DESC);

CREATE TABLE ingest_jobs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID         NOT NULL UNIQUE REFERENCES documents (id) ON DELETE CASCADE,
    -- QUEUED | PARSING | TRANSCRIBING | OCR | CHUNKING | EMBEDDING | SUMMARIZING | DONE | FAILED
    stage         VARCHAR(24)  NOT NULL DEFAULT 'QUEUED',
    -- 0..100. Whisper and embedding both report real progress so the UI can show
    -- movement instead of an hour-long spinner.
    progress      SMALLINT     NOT NULL DEFAULT 0,
    error         TEXT,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID         NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    -- Stable order within the document; enables ordinal +/- 1 neighbour expansion.
    ordinal       INTEGER      NOT NULL,
    text          TEXT         NOT NULL,
    section_title TEXT,
    -- slide | page | timestamp
    source_kind   VARCHAR(16)  NOT NULL,
    slide_no      INTEGER,
    page_no       INTEGER,
    start_sec     DOUBLE PRECISION,
    end_sec       DOUBLE PRECISION,
    ocr           BOOLEAN      NOT NULL DEFAULT FALSE,
    embedding     VECTOR(768)  NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_chunks_document_ordinal UNIQUE (document_id, ordinal),
    -- A chunk is bound to exactly one addressing scheme. Enforcing this in the
    -- database keeps an ambiguous citation from ever being stored.
    CONSTRAINT ck_chunks_source CHECK (
        (source_kind = 'slide'     AND slide_no IS NOT NULL AND page_no IS NULL AND start_sec IS NULL)
     OR (source_kind = 'page'      AND page_no  IS NOT NULL AND slide_no IS NULL AND start_sec IS NULL)
     OR (source_kind = 'timestamp' AND start_sec IS NOT NULL AND slide_no IS NULL AND page_no IS NULL)
    )
);
CREATE INDEX idx_chunks_document_ordinal ON chunks (document_id, ordinal);

-- HNSW over IVFFlat: needs no training pass and stays correct as rows are
-- inserted incrementally, which matters because chunks arrive per-document.
CREATE INDEX idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE summaries (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID         NOT NULL UNIQUE REFERENCES documents (id) ON DELETE CASCADE,
    summary       TEXT         NOT NULL,
    -- [{"term": "...", "explanation": "..."}]
    key_concepts  JSONB        NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID         NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    user_id       UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role          VARCHAR(16)  NOT NULL,
    content       TEXT         NOT NULL,
    -- Resolved citations for assistant turns: [{"marker":1,"label":"Slide 4",...}]
    citations     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_messages_document ON chat_messages (document_id, created_at);
