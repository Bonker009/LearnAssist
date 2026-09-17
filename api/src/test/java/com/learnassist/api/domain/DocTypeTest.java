package com.learnassist.api.domain;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

class DocTypeTest {

    @Test
    void newResourceTypesResolve() {
        assertEquals(DocType.TEXT, DocType.fromContentType("text/plain; charset=utf-8"));
        assertEquals(DocType.TEXT, DocType.fromContentType("text/markdown"));
        assertEquals(DocType.IMAGE, DocType.fromContentType("image/jpeg"));
        assertEquals(DocType.AUDIO, DocType.fromContentType("audio/webm"));
    }

    @Test
    void imagesTesseractCannotReadAreRejectedUpFront() {
        assertThrows(IllegalArgumentException.class, () -> DocType.fromContentType("image/heic"));
        assertThrows(IllegalArgumentException.class, () -> DocType.fromContentType("image/svg+xml"));
    }

    @Test
    void htmlIsNotAnUploadType() {
        // Web pages arrive as links; an uploaded .html has no URL to cite.
        assertThrows(IllegalArgumentException.class, () -> DocType.fromContentType("text/html"));
    }
}
