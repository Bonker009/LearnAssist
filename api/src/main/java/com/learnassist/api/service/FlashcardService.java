package com.learnassist.api.service;

import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.DocumentStatus;
import com.learnassist.api.domain.Flashcard;
import com.learnassist.api.domain.FlashcardDeck;
import com.learnassist.api.domain.User;
import com.learnassist.api.repository.FlashcardDeckRepository;
import com.learnassist.api.repository.FlashcardRepository;
import com.learnassist.api.web.ApiException;
import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.HttpClientErrorException;

@Service
public class FlashcardService {

    private static final String BUCKET = "flashcards";
    private static final int LIMIT = 20;
    private static final Duration WINDOW = Duration.ofHours(1);

    private final FlashcardDeckRepository decks;
    private final FlashcardRepository cards;
    private final DocumentService documents;
    private final AiClient ai;
    private final RateLimiter rateLimiter;

    public FlashcardService(FlashcardDeckRepository decks, FlashcardRepository cards,
            DocumentService documents, AiClient ai, RateLimiter rateLimiter) {
        this.decks = decks;
        this.cards = cards;
        this.documents = documents;
        this.ai = ai;
        this.rateLimiter = rateLimiter;
    }

    @Transactional
    public FlashcardDeck generate(User user, UUID documentId, int count) {
        if (!rateLimiter.tryAcquire(BUCKET, user.getId(), LIMIT, WINDOW)) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,
                    "Too many flashcard decks generated in the last hour. Try again shortly.");
        }

        Document document = documents.requireOwned(user, documentId);
        if (document.getStatus() != DocumentStatus.READY) {
            throw new ApiException(HttpStatus.CONFLICT, "This document is still being processed");
        }

        List<AiClient.GeneratedCard> generated;
        try {
            generated = ai.generateFlashcards(new AiClient.FlashcardRequest(documentId, count));
        } catch (HttpClientErrorException.UnprocessableEntity e) {
            // The AI service's 422 means "nothing usable came back", not a contract mismatch.
            generated = List.of();
        }
        if (generated == null || generated.isEmpty()) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Could not generate flashcards from this document");
        }

        FlashcardDeck deck = new FlashcardDeck(document, user);
        for (AiClient.GeneratedCard card : generated) {
            deck.addCard(new Flashcard(card.front(), card.back(), card.source(),
                    card.sourceLabel(), card.snippet()));
        }
        return decks.save(deck);
    }

    @Transactional(readOnly = true)
    public Optional<FlashcardDeck> latest(User user, UUID documentId) {
        documents.requireOwned(user, documentId);
        return decks.findFirstByDocumentIdAndCreatedByIdOrderByCreatedAtDesc(
                documentId, user.getId());
    }

    @Transactional
    public void review(User user, UUID cardId, boolean knewIt) {
        cards.findByIdAndDeckCreatedById(cardId, user.getId())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Card not found"))
                .review(knewIt);
    }
}
