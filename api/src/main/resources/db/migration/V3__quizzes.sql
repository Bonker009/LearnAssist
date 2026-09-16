-- Quiz storage.
--
-- `correct_index` and `explanation` live here and are deliberately NEVER included
-- in the response DTO used before submission. Relying on @JsonIgnore on the entity
-- would make the answer key one forgotten annotation away from being served to the
-- browser; a separate DTO makes leaking it require writing the field by hand.

CREATE TABLE quizzes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID        NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    created_by    UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_quizzes_document ON quizzes (document_id, created_at DESC);

CREATE TABLE quiz_questions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id       UUID        NOT NULL REFERENCES quizzes (id) ON DELETE CASCADE,
    position      INTEGER     NOT NULL,
    question      TEXT        NOT NULL,
    -- ["option a", "option b", "option c", "option d"]
    options       JSONB       NOT NULL,
    correct_index SMALLINT    NOT NULL,
    explanation   TEXT        NOT NULL DEFAULT '',
    -- The SourceRef the question was drawn from, so review mode can show why.
    source        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    source_label  VARCHAR(64) NOT NULL DEFAULT '',
    snippet       TEXT        NOT NULL DEFAULT '',
    CONSTRAINT uq_quiz_questions_position UNIQUE (quiz_id, position),
    -- Four options, and an answer that actually points at one of them. The AI
    -- service validates this too; enforcing it here means a bug there can never
    -- persist an ungradeable question.
    CONSTRAINT ck_quiz_questions_options CHECK (jsonb_array_length(options) = 4),
    CONSTRAINT ck_quiz_questions_answer CHECK (correct_index BETWEEN 0 AND 3)
);

CREATE TABLE quiz_attempts (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id       UUID        NOT NULL REFERENCES quizzes (id) ON DELETE CASCADE,
    user_id       UUID        NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    -- Submitted answers, position -> chosen index.
    answers       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    score         SMALLINT    NOT NULL,
    total         SMALLINT    NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_quiz_attempts_user ON quiz_attempts (user_id, created_at DESC);
