package com.learnassist.api.domain;

import java.util.Map;
import java.util.Set;

/** Input categories the ingestion pipeline understands. */
public enum DocType {
    PDF,
    PPTX,
    DOCX,
    AUDIO,
    VIDEO,
    /** A photo or screenshot, read with OCR. */
    IMAGE,
    /** Pasted notes or an uploaded .txt / .md file. */
    TEXT,
    /** A web page fetched from a link. Never produced from an upload. */
    WEB,
    /** A YouTube video, transcribed from its audio. Never produced from an upload. */
    YOUTUBE;

    private static final Map<String, DocType> BY_CONTENT_TYPE = Map.ofEntries(
            Map.entry("application/pdf", PDF),
            Map.entry(
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    PPTX),
            Map.entry(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    DOCX),
            Map.entry("text/plain", TEXT),
            Map.entry("text/markdown", TEXT));

    /**
     * Image formats Tesseract reads. Listed rather than matched by prefix: {@code image/heic} and
     * {@code image/svg+xml} are common uploads that would pass a prefix check and then fail
     * minutes later in OCR, which is a worse place to learn it.
     */
    private static final Set<String> IMAGE_TYPES = Set.of(
            "image/png", "image/jpeg", "image/webp", "image/gif", "image/bmp", "image/tiff");

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
        if (IMAGE_TYPES.contains(normalised)) {
            return IMAGE;
        }
        if (normalised.startsWith("audio/")) {
            return AUDIO;
        }
        if (normalised.startsWith("video/")) {
            return VIDEO;
        }
        if (normalised.startsWith("image/")) {
            throw new IllegalArgumentException(
                    "Unsupported image type: " + contentType + ". Use PNG, JPEG or WebP.");
        }
        throw new IllegalArgumentException("Unsupported file type: " + contentType);
    }
}
