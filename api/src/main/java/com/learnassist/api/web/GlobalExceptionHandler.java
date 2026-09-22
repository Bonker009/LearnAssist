package com.learnassist.api.web;

import jakarta.servlet.http.HttpServletRequest;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    private ResponseEntity<Map<String, Object>> body(HttpStatus status, String message,
            HttpServletRequest request) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("timestamp", Instant.now().toString());
        payload.put("status", status.value());
        payload.put("error", status.getReasonPhrase());
        payload.put("message", message);
        payload.put("path", request.getRequestURI());
        return ResponseEntity.status(status).body(payload);
    }

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Map<String, Object>> handleApi(ApiException e, HttpServletRequest req) {
        return body(e.getStatus(), e.getMessage(), req);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException e,
            HttpServletRequest req) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .collect(Collectors.joining("; "));
        return body(HttpStatus.BAD_REQUEST, message, req);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArgument(IllegalArgumentException e,
            HttpServletRequest req) {
        return body(HttpStatus.BAD_REQUEST, e.getMessage(), req);
    }

    /**
     * No controller matches. Without this, the catch-all below reports a mistyped or not yet
     * deployed route as a 500 "Unexpected error", which sends the reader to the server logs
     * for what is really a 404.
     */
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNoRoute(NoResourceFoundException e,
            HttpServletRequest req) {
        return body(HttpStatus.NOT_FOUND, "Not found", req);
    }

    /**
     * The AI service answered, but rejected the request.
     *
     * <p>Handled separately from a connection failure: reporting a 4xx contract mismatch as
     * "service unavailable" sends the reader to check whether the container is running, when
     * the container is running fine and the request shape is wrong.
     */
    @ExceptionHandler(RestClientResponseException.class)
    public ResponseEntity<Map<String, Object>> handleAiRejected(RestClientResponseException e,
            HttpServletRequest req) {
        log.error("AI service rejected the request: {} {}", e.getStatusCode(),
                e.getResponseBodyAsString());
        return body(HttpStatus.BAD_GATEWAY,
                "The AI service rejected the request (" + e.getStatusCode() + "). "
                        + "This usually means the two services disagree on the request format.",
                req);
    }

    @ExceptionHandler(RestClientException.class)
    public ResponseEntity<Map<String, Object>> handleAiDown(RestClientException e,
            HttpServletRequest req) {
        log.error("AI service call failed", e);
        // The AI service depends on Ollama running on the host, which is the most
        // common thing missing on a fresh machine. Say so rather than returning a
        // bare 500 that sends the reader into the wrong logs.
        return body(HttpStatus.SERVICE_UNAVAILABLE,
                "The AI service is unavailable. Check that it is running and that Ollama is "
                        + "reachable on the host.", req);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleUnexpected(Exception e,
            HttpServletRequest req) {
        log.error("Unhandled exception", e);
        return body(HttpStatus.INTERNAL_SERVER_ERROR, "Unexpected error", req);
    }
}
