package com.learnassist.api.domain;

public enum DocumentStatus {
    /** Row exists and a presigned URL was issued, but the bytes are not in storage yet. */
    PENDING_UPLOAD,
    UPLOADED,
    PROCESSING,
    READY,
    FAILED
}
