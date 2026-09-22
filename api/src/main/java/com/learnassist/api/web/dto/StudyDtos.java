package com.learnassist.api.web.dto;

import com.learnassist.api.domain.FlashcardDeck;
import com.learnassist.api.domain.SlideDeck;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Flashcard and slide deck shapes. */
public final class StudyDtos {

    private StudyDtos() {}

    public record FlashcardResponse(UUID id, int position, String front, String back,
            Map<String, Object> source, String sourceLabel, String snippet, Boolean known) {}

    public record FlashcardDeckResponse(UUID id, UUID documentId, Instant createdAt,
            List<FlashcardResponse> cards) {

        public static FlashcardDeckResponse from(FlashcardDeck deck) {
            return new FlashcardDeckResponse(
                    deck.getId(),
                    deck.getDocument().getId(),
                    deck.getCreatedAt(),
                    deck.getCards().stream()
                            .map(c -> new FlashcardResponse(c.getId(), c.getPosition(),
                                    c.getFront(), c.getBack(), c.getSource(), c.getSourceLabel(),
                                    c.getSnippet(), c.getKnown()))
                            .toList());
        }
    }

    public record ReviewRequest(@NotNull Boolean known) {}

    /**
     * @param viewPath path of the built deck on this API, e.g. {@code /api/slides/view/{token}/};
     *                 null until READY
     * @param pdfUrl   presigned, short-lived; null if not READY or the export failed
     */
    public record SlideDeckResponse(UUID id, UUID documentId, String status, String title,
            List<Map<String, Object>> slides, String error, String viewPath, String pdfUrl,
            String markdownUrl, Instant createdAt) {

        public static SlideDeckResponse from(SlideDeck deck, String viewPath, String pdfUrl,
                String markdownUrl) {
            return new SlideDeckResponse(deck.getId(), deck.getDocument().getId(),
                    deck.getStatus().name(), deck.getTitle(), deck.getOutline(), deck.getError(),
                    viewPath, pdfUrl, markdownUrl, deck.getCreatedAt());
        }
    }
}
