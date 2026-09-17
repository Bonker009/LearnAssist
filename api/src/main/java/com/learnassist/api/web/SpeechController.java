package com.learnassist.api.web;

import com.learnassist.api.domain.User;
import com.learnassist.api.security.CurrentUser;
import com.learnassist.api.service.AiClient;
import com.learnassist.api.service.RateLimiter;
import com.learnassist.api.web.dto.Dtos;
import java.io.IOException;
import java.time.Duration;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

/**
 * Voice input for the chat composer.
 *
 * <p>Unlike lecture uploads, a dictation clip goes through this server rather than straight to
 * object storage: it is a few hundred kilobytes, it is never kept, and the student is waiting
 * on the text, so a presign-then-ingest round trip would only add latency.
 */
@RestController
public class SpeechController {

    /** Two minutes of Opus is well under 2 MB; this bound only stops abuse. */
    private static final long MAX_CLIP_BYTES = 25L * 1024 * 1024;
    private static final Set<String> LANGUAGES = Set.of("auto", "km", "en");

    private static final String BUCKET = "speech";
    private static final int LIMIT = 120;
    private static final Duration WINDOW = Duration.ofHours(1);

    private final AiClient ai;
    private final RateLimiter rateLimiter;

    public SpeechController(AiClient ai, RateLimiter rateLimiter) {
        this.ai = ai;
        this.rateLimiter = rateLimiter;
    }

    @PostMapping("/api/speech/transcribe")
    public Dtos.TranscriptResponse transcribe(
            @RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue = "auto") String language) throws IOException {
        User user = CurrentUser.require();

        if (!LANGUAGES.contains(language)) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "language must be auto, km or en");
        }
        if (file.isEmpty()) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "The recording was empty");
        }
        if (file.getSize() > MAX_CLIP_BYTES) {
            throw new ApiException(HttpStatus.CONTENT_TOO_LARGE, "The recording is too long");
        }
        if (!rateLimiter.tryAcquire(BUCKET, user.getId(), LIMIT, WINDOW)) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,
                    "Too many voice messages in the last hour. Try again shortly.");
        }

        String contentType = file.getContentType() == null
                ? "application/octet-stream" : file.getContentType();
        var result = ai.transcribe(file.getBytes(),
                file.getOriginalFilename() == null ? "clip.webm" : file.getOriginalFilename(),
                contentType, language);
        return new Dtos.TranscriptResponse(result.text(), result.language(), result.durationSec());
    }
}
