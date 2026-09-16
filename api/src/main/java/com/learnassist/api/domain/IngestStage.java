package com.learnassist.api.domain;

/** Pipeline stages, reported to the UI so a long ingest shows real movement. */
public enum IngestStage {
    QUEUED,
    PARSING,
    TRANSCRIBING,
    OCR,
    CHUNKING,
    EMBEDDING,
    SUMMARIZING,
    DONE,
    FAILED
}
