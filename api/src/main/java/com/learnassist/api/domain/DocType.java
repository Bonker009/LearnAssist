package com.learnassist.api.domain;

import java.util.Map;

/** Input categories the ingestion pipeline understands. */
public enum DocType {
    PDF,
    PPTX,
    DOCX,
    AUDIO,
    VIDEO;

    private static final Map<String, DocType> BY_CONTENT_TYPE = Map.ofEntries(
            Map.entry("application/pdf", PDF),
            Map.entry(
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    PPTX),
            Map.entry(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    DOCX));

    /**
     * Resolve the declared content type to a pipeline category.
     *
     * <p>Audio and video are matched by prefix because browsers report a long tail of codec-specific
     * types ({@code audio/mp4}, {@code audio/x-m4a}, {@code video/quicktime}) that is not worth
     * enumerating.
     */
    public static DocType fromContentType(String contentType) {
        if (contentType == null) {
            throw new IllegalArgumentException("content type is required");
        }
        String normalised = contentType.toLowerCase().split(";")[0].trim();
        DocType exact = BY_CONTENT_TYPE.get(normalised);
        if (exact != null) {
            return exact;
        }
        if (normalised.startsWith("audio/")) {
            return AUDIO;
        }
        if (normalised.startsWith("video/")) {
            return VIDEO;
        }
        throw new IllegalArgumentException("Unsupported file type: " + contentType);
    }
}
