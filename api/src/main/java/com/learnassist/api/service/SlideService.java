package com.learnassist.api.service;

import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.DocumentStatus;
import com.learnassist.api.domain.SlideDeck;
import com.learnassist.api.domain.SlideDeckStatus;
import com.learnassist.api.domain.User;
import com.learnassist.api.repository.SlideDeckRepository;
import com.learnassist.api.web.ApiException;
import jakarta.annotation.PreDestroy;
import java.security.SecureRandom;
import java.time.Duration;
import java.util.Base64;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClientException;

/**
 * Slide decks: an outline from the AI service, rendered by Slidev in the slides service.
 *
 * <p>Generation takes minutes (a local LLM, then a Vite build and a Chromium PDF export), so
 * it runs in the background and the browser polls the deck, as it polls ingest jobs.
 */
@Service
public class SlideService {

    private static final Logger log = LoggerFactory.getLogger(SlideService.class);

    private static final String BUCKET = "slides";
    private static final int LIMIT = 5;
    private static final Duration WINDOW = Duration.ofHours(1);
    /** Must match the view route in {@code SlideController}. */
    public static final String VIEW_PATH = "/api/slides/view/";

    private final SlideDeckRepository decks;
    private final DocumentService documents;
    private final AiClient ai;
    private final SlidesClient slides;
    private final StorageService storage;
    private final RateLimiter rateLimiter;
    private final SecureRandom random = new SecureRandom();
    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();

    public SlideService(SlideDeckRepository decks, DocumentService documents, AiClient ai,
            SlidesClient slides, StorageService storage, RateLimiter rateLimiter) {
        this.decks = decks;
        this.documents = documents;
        this.ai = ai;
        this.slides = slides;
        this.storage = storage;
        this.rateLimiter = rateLimiter;
    }

    /**
     * A generation runs on this JVM's executor, so a restart abandons it. Without this, a deck
     * interrupted mid-render would say "generating" forever. Single replica only, like the rate
     * limiter.
     */
    @EventListener(ApplicationReadyEvent.class)
    void failInterrupted() {
        int count = decks.failAll(
                List.of(SlideDeckStatus.GENERATING, SlideDeckStatus.RENDERING),
                "Interrupted by a server restart. Generate the slides again.");
        if (count > 0) {
            log.warn("Marked {} interrupted slide deck(s) as failed", count);
        }
    }

    @PreDestroy
    void shutdown() {
        executor.shutdownNow();
    }

    /**
     * Storage prefix of one deck's rendered files. Keyed by deck id alone, so building it never
     * touches the lazy owner association outside a session.
     */
    public static String prefix(SlideDeck deck) {
        return "slides/" + deck.getId();
    }

    /** Create the deck and start generating it. Not transactional: the row must be committed
     *  before the background task looks it up. */
    public SlideDeck start(User user, UUID documentId, int count) {
        if (!rateLimiter.tryAcquire(BUCKET, user.getId(), LIMIT, WINDOW)) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,
                    "Too many slide decks generated in the last hour. Try again shortly.");
        }

        Document document = documents.requireOwned(user, documentId);
        if (document.getStatus() != DocumentStatus.READY) {
            throw new ApiException(HttpStatus.CONFLICT, "This document is still being processed");
        }

        SlideDeck deck = decks.save(new SlideDeck(document, user, newViewToken()));
        String filename = document.getFilename();
        String requestId = MDC.get(com.learnassist.api.web.RequestIdFilter.MDC_KEY);

        executor.submit(() -> {
            if (requestId != null) {
                MDC.put(com.learnassist.api.web.RequestIdFilter.MDC_KEY, requestId);
            }
            try {
                generate(deck.getId(), documentId, filename, count);
            } finally {
                MDC.clear();
            }
        });
        return deck;
    }

    private void generate(UUID deckId, UUID documentId, String filename, int count) {
        try {
            AiClient.GeneratedSlides outline =
                    ai.generateSlides(new AiClient.SlidesRequest(documentId, filename, count));
            if (outline == null || outline.slides() == null || outline.slides().isEmpty()) {
                throw new IllegalStateException("empty outline");
            }

            SlideDeck deck = update(deckId, d -> d.outlined(outline.title(), outline.slides()));

            SlidesClient.RenderResult result = slides.render(new SlidesClient.RenderRequest(
                    outline.markdown(), VIEW_PATH + deck.getViewToken() + "/", prefix(deck)));

            update(deckId, d -> d.rendered(result.pdf()));
            log.info("Slide deck {} ready: {} files, pdf={}", deckId, result.files(), result.pdf());
        } catch (Exception e) {
            log.error("Slide deck {} failed", deckId, e);
            update(deckId, d -> d.failed(describe(e)));
        }
    }

    private static String describe(Exception e) {
        if (e instanceof HttpClientErrorException.UnprocessableEntity) {
            return "Could not write slides from this document.";
        }
        if (e instanceof RestClientException) {
            return "The slide service or AI service is unavailable. Try again shortly.";
        }
        return "Something went wrong while generating the slides.";
    }

    private SlideDeck update(UUID deckId, java.util.function.Consumer<SlideDeck> change) {
        SlideDeck deck = decks.findById(deckId).orElseThrow();
        change.accept(deck);
        return decks.save(deck);
    }

    @Transactional(readOnly = true)
    public SlideDeck requireOwned(User user, UUID deckId) {
        return decks.findByIdAndCreatedById(deckId, user.getId())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Slides not found"));
    }

    @Transactional(readOnly = true)
    public Optional<SlideDeck> latest(User user, UUID documentId) {
        documents.requireOwned(user, documentId);
        return decks.findFirstByDocumentIdAndCreatedByIdOrderByCreatedAtDesc(
                documentId, user.getId());
    }

    @Transactional(readOnly = true)
    public Optional<SlideDeck> findReadyByViewToken(String token) {
        return decks.findByViewToken(token).filter(d -> d.getStatus() == SlideDeckStatus.READY);
    }

    public Optional<String> pdfUrl(SlideDeck deck) {
        if (deck.getStatus() != SlideDeckStatus.READY || !deck.hasPdf()) {
            return Optional.empty();
        }
        return Optional.of(storage.presignDownload(prefix(deck) + "/deck.pdf", "slides.pdf"));
    }

    public Optional<String> markdownUrl(SlideDeck deck) {
        if (deck.getStatus() != SlideDeckStatus.READY) {
            return Optional.empty();
        }
        return Optional.of(storage.presignDownload(prefix(deck) + "/slides.md", "slides.md"));
    }

    private String newViewToken() {
        byte[] bytes = new byte[32];
        random.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
