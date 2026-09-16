package com.learnassist.api.web.dto;

import com.learnassist.api.domain.ChatMessage;
import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.IngestJob;
import com.learnassist.api.domain.Summary;
import com.learnassist.api.domain.User;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Request and response shapes. Entities are never serialised directly. */
public final class Dtos {

    private Dtos() {}

    // ---------- auth ----------

    public record RegisterRequest(
            @Email @NotBlank String email,
            @NotBlank @Size(min = 8, max = 128, message = "must be at least 8 characters")
            String password,
            @NotBlank @Size(max = 120) String displayName) {}

    public record LoginRequest(@Email @NotBlank String email, @NotBlank String password) {}

    public record UserResponse(UUID id, String email, String displayName) {
        public static UserResponse from(User user) {
            return new UserResponse(user.getId(), user.getEmail(), user.getDisplayName());
        }
    }

    public record AuthResponse(String token, UserResponse user) {}

    // ---------- documents ----------

    public record CreateUploadRequest(
            @NotBlank @Size(max = 512) String filename,
            @NotBlank String contentType,
            @Positive long sizeBytes) {}

    public record CreateUploadResponse(UUID documentId, String uploadUrl, String storageKey) {}

    public record JobResponse(String stage, int progress, String error) {
        public static JobResponse from(IngestJob job) {
            return new JobResponse(job.getStage().name(), job.getProgress(), job.getError());
        }
    }

    public record KeyConceptResponse(String term, String explanation) {}

    public record SummaryResponse(String summary, List<KeyConceptResponse> keyConcepts) {
        public static SummaryResponse from(Summary summary) {
            return new SummaryResponse(summary.getSummary(),
                    summary.getKeyConcepts().stream()
                            .map(k -> new KeyConceptResponse(k.term(), k.explanation()))
                            .toList());
        }
    }

    public record DocumentResponse(
            UUID id,
            String filename,
            String docType,
            String status,
            Integer unitCount,
            Double durationSec,
            long sizeBytes,
            Instant createdAt,
            JobResponse job,
            SummaryResponse summary) {

        public static DocumentResponse from(Document document, IngestJob job, Summary summary) {
            return new DocumentResponse(
                    document.getId(),
                    document.getFilename(),
                    document.getDocType().name(),
                    document.getStatus().name(),
                    document.getUnitCount(),
                    document.getDurationSec(),
                    document.getSizeBytes(),
                    document.getCreatedAt(),
                    job == null ? null : JobResponse.from(job),
                    summary == null ? null : SummaryResponse.from(summary));
        }
    }

    // ---------- chat ----------

    public record AskRequest(@NotBlank @Size(max = 2000) String question) {}

    public record ChatMessageResponse(
            UUID id,
            String role,
            String content,
            List<Map<String, Object>> citations,
            Instant createdAt) {

        public static ChatMessageResponse from(ChatMessage message) {
            return new ChatMessageResponse(
                    message.getId(),
                    message.getRole().name(),
                    message.getContent(),
                    message.getCitations(),
                    message.getCreatedAt());
        }
    }
}
