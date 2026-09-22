-- Flashcards and slide decks: study material generated from one document.
--
-- Like quiz questions, every card and every slide carries the SourceRef it was
-- drawn from, so a student can always get back to the lecture.

CREATE TABLE flashcard_decks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID        NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    created_by    UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_flashcard_decks_document ON flashcard_decks (document_id, created_by, created_at DESC);

CREATE TABLE flashcards (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deck_id       UUID         NOT NULL REFERENCES flashcard_decks (id) ON DELETE CASCADE,
    position      INTEGER      NOT NULL,
    front         TEXT         NOT NULL,
    back          TEXT         NOT NULL,
    source        JSONB        NOT NULL DEFAULT '{}'::jsonb,
    source_label  VARCHAR(255) NOT NULL DEFAULT '',
    snippet       TEXT         NOT NULL DEFAULT '',
    -- The student's latest self-grade: TRUE "knew it", FALSE "again", NULL not yet studied.
    known         BOOLEAN,
    reviewed_at   TIMESTAMPTZ,
    CONSTRAINT uq_flashcards_position UNIQUE (deck_id, position)
);

-- A deck is generated asynchronously: the outline comes from the AI service (GENERATING),
-- then the slides service builds the Slidev site and PDF into RustFS (RENDERING).
CREATE TABLE slide_decks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID         NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    created_by    UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status        VARCHAR(16)  NOT NULL DEFAULT 'GENERATING',
    title         VARCHAR(200) NOT NULL DEFAULT '',
    -- [{title, bullets, notes, sources: [{source, sourceLabel}]}], for the in-app outline.
    outline       JSONB        NOT NULL DEFAULT '[]'::jsonb,
    -- The built site is served at /api/slides/view/{view_token}/ without a JWT, because an
    -- iframe cannot send one. A separate random token, never the deck id, is that capability.
    view_token    VARCHAR(64)  NOT NULL UNIQUE,
    has_pdf       BOOLEAN      NOT NULL DEFAULT FALSE,
    error         TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_slide_decks_status
        CHECK (status IN ('GENERATING', 'RENDERING', 'READY', 'FAILED'))
);
CREATE INDEX idx_slide_decks_document ON slide_decks (document_id, created_by, created_at DESC);
