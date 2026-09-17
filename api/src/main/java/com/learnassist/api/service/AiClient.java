package com.learnassist.api.service;

import com.learnassist.api.config.AppProperties;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

/**
 * Client for the Python AI service.
 *
 * <p>This is the only place Spring Boot talks to FastAPI. The AI service performs no ownership
 * checks of its own — every call made here has already been authorised against the JWT.
 */
@Service
public class AiClient {

    private static final Logger log = LoggerFactory.getLogger(AiClient.class);

    private final RestClient rest;

    public AiClient(AppProperties props) {
        var factory = new SimpleClientHttpRequestFactory();
        // Local 7B inference is slow. A default 30s timeout turns a working
        // pipeline into a stream of spurious "ingest failed" errors.
        factory.setConnectTimeout((int) java.time.Duration.ofSeconds(10).toMillis());
        factory.setReadTimeout((int) props.ai().timeout().toMillis());

        this.rest = RestClient.builder()
                .baseUrl(props.ai().baseUrl())
                .defaultHeader("X-Internal-Key", props.ai().internalKey())
                // Carry the caller's request id across the service boundary so one
                // user action is traceable through both logs.
                .requestInterceptor((request, body, execution) -> {
                    String requestId = org.slf4j.MDC.get(
                            com.learnassist.api.web.RequestIdFilter.MDC_KEY);
                    if (requestId != null) {
                        request.getHeaders().add(
                                com.learnassist.api.web.RequestIdFilter.HEADER, requestId);
                    }
                    return execution.execute(request, body);
                })
                .requestFactory(factory)
                .build();
    }

    /**
     * @param storageKey null for a YouTube link
     * @param sourceUrl  set for link resources; the AI service fetches it itself
     */
    public record IngestRequest(UUID documentId, String storageKey, String filename,
            String contentType, String docType, String sourceUrl) {}

    /** A document the answer may cite. The filename lets the model say which file it used. */
    public record DocumentRef(UUID id, String filename) {}

    /** An earlier turn, sent so a follow-up like "explain that again" can be resolved. */
    public record Turn(String role, String content) {}

    public record QueryRequest(List<DocumentRef> documents, String question, List<Turn> history) {}

    public record QueryResponse(String answer, List<Map<String, Object>> citations,
            boolean grounded) {}

    /** Fire-and-forget: the AI service runs ingestion as a background task and reports progress
     *  by updating {@code ingest_jobs}. */
    public void startIngest(IngestRequest request) {
        rest.post().uri("/ingest").body(request).retrieve().toBodilessEntity();
        log.debug("Ingest queued for document {}", request.documentId());
    }

    public record QuizRequest(UUID documentId, int count) {}

    /** One generated question, including the answer key. */
    public record GeneratedQuestion(
            String question,
            List<String> options,
            int correctIndex,
            String explanation,
            Map<String, Object> source,
            String sourceLabel,
            String snippet) {}

    public List<GeneratedQuestion> generateQuiz(QuizRequest request) {
        return rest.post()
                .uri("/quiz")
                .body(request)
                .retrieve()
                .body(new org.springframework.core.ParameterizedTypeReference<>() {});
    }

    public QueryResponse query(QueryRequest request) {
        return rest.post().uri("/query").body(request).retrieve().body(QueryResponse.class);
    }

    public record TranscriptResponse(String text, String language, double durationSec) {}

    /**
     * Transcribe a short dictation clip.
     *
     * @param language {@code km}, {@code en}, or {@code auto} to let Whisper detect it
     */
    public TranscriptResponse transcribe(byte[] audio, String filename, String contentType,
            String language) {
        var parts = new org.springframework.util.LinkedMultiValueMap<String, Object>();
        var headers = new org.springframework.http.HttpHeaders();
        headers.setContentType(org.springframework.http.MediaType.parseMediaType(contentType));
        parts.add("file", new org.springframework.http.HttpEntity<>(
                new org.springframework.core.io.ByteArrayResource(audio) {
                    // Without a filename the part is sent as a plain form field and
                    // FastAPI rejects it as "not a file".
                    @Override
                    public String getFilename() {
                        return filename;
                    }
                }, headers));
        parts.add("language", language);

        return rest.post()
                .uri("/transcribe")
                .contentType(org.springframework.http.MediaType.MULTIPART_FORM_DATA)
                .body(parts)
                .retrieve()
                .body(TranscriptResponse.class);
    }
}
