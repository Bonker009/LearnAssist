-- Chat-first interface: conversations that hold resources.
--
-- A conversation is the unit a student talks to; the files, links and notes attached
-- to it are what its answers may cite. The join table (rather than a
-- conversation_id on documents) lets one uploaded lecture be reused across several
-- chats without re-ingesting it.

CREATE TABLE conversations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id      UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    title         VARCHAR(200) NOT NULL DEFAULT 'New chat',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    -- Bumped on every message, so the sidebar can sort by recent activity.
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_conversations_owner ON conversations (owner_id, updated_at DESC);

CREATE TABLE conversation_documents (
    conversation_id UUID        NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    document_id     UUID        NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    added_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (conversation_id, document_id)
);
CREATE INDEX idx_conversation_documents_document ON conversation_documents (document_id);

-- Move existing per-document chat history into conversations. Each document that
-- has messages becomes one conversation with that document attached. Reusing the
-- document id as the conversation id makes the backfill a pair of plain INSERTs
-- with no temporary mapping table.
INSERT INTO conversations (id, owner_id, title, created_at, updated_at)
SELECT d.id, d.owner_id, LEFT(d.filename, 200), MIN(m.created_at), MAX(m.created_at)
FROM documents d
JOIN chat_messages m ON m.document_id = d.id
GROUP BY d.id, d.owner_id, d.filename;

INSERT INTO conversation_documents (conversation_id, document_id)
SELECT id, id FROM conversations;

ALTER TABLE chat_messages
    ADD COLUMN conversation_id UUID REFERENCES conversations (id) ON DELETE CASCADE;
UPDATE chat_messages SET conversation_id = document_id;
ALTER TABLE chat_messages ALTER COLUMN conversation_id SET NOT NULL;

DROP INDEX idx_chat_messages_document;
ALTER TABLE chat_messages DROP COLUMN document_id;
CREATE INDEX idx_chat_messages_conversation ON chat_messages (conversation_id, created_at);

-- Link resources (web pages, YouTube videos).
--
-- A YouTube video is never stored: the viewer embeds the original, and the audio is
-- only held in a temp file for transcription. A web page does get a storage key,
-- for the fetched HTML snapshot, so a citation still resolves after the live page
-- changes. Every document must be locatable one way or the other.
ALTER TABLE documents ALTER COLUMN storage_key DROP NOT NULL;
ALTER TABLE documents ADD COLUMN source_url VARCHAR(2048);
ALTER TABLE documents ADD CONSTRAINT ck_documents_location
    CHECK (storage_key IS NOT NULL OR source_url IS NOT NULL);
