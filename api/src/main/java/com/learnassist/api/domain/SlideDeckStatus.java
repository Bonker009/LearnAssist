package com.learnassist.api.domain;

/** Mirrors {@code ck_slide_decks_status} in V5. */
public enum SlideDeckStatus {
    /** The AI service is writing the cited outline. */
    GENERATING,
    /** The slides service is building the Slidev site and exporting the PDF. */
    RENDERING,
    READY,
    FAILED;

    public boolean isFinished() {
        return this == READY || this == FAILED;
    }
}
