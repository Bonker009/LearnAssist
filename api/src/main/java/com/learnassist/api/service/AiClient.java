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
                .requestFactory(factory)
                .build();
    }

    public record IngestRequest(UUID documentId, String storageKey, String filename,
            String contentType) {}

    public record QueryRequest(UUID documentId, String question) {}

    public record QueryResponse(String answer, List<Map<String, Object>> citations,
            boolean grounded) {}

    /** Fire-and-forget: the AI service runs ingestion as a background task and reports progress
     *  by updating {@code ingest_jobs}. */
    public void startIngest(IngestRequest request) {
        rest.post().uri("/ingest").body(request).retrieve().toBodilessEntity();
        log.debug("Ingest queued for document {}", request.documentId());
    }

    public QueryResponse query(QueryRequest request) {
        return rest.post().uri("/query").body(request).retrieve().body(QueryResponse.class);
    }
}
