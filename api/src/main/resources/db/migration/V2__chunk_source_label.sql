-- The human-readable citation label, decided by the parser at parse time.
--
-- Needed because `source_kind` alone cannot produce an accurate label for every
-- format. Word has no page concept a parser can observe -- pagination is the
-- renderer's decision, not stored in the file -- so its units are addressed by
-- heading order. Storing them as kind='page' keeps retrieval and the UI uniform,
-- but rendering "Page 3" would tell the student something the file does not say.
--
-- NULL means "derive it from source_kind", which is correct for PDF and slides.
ALTER TABLE chunks ADD COLUMN source_label VARCHAR(64);
