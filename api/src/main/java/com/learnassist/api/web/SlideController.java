package com.learnassist.api.web;

import com.learnassist.api.domain.SlideDeck;
import com.learnassist.api.domain.SlideDeckStatus;
import com.learnassist.api.domain.User;
import com.learnassist.api.security.CurrentUser;
import com.learnassist.api.service.SlideService;
import com.learnassist.api.service.StorageService;
import com.learnassist.api.web.dto.StudyDtos;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.io.InputStream;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SlideController {

    /** Each segment a plain file or directory name; this also rules out "." and "..". */
    private static final Pattern SAFE_PATH =
            Pattern.compile("(?:[A-Za-z0-9_-][A-Za-z0-9._-]*/)*[A-Za-z0-9_-][A-Za-z0-9._-]*");

    private final SlideService slides;
    private final StorageService storage;

    public SlideController(SlideService slides, StorageService storage) {
        this.slides = slides;
        this.storage = storage;
    }

    /** Starts generation and returns at once; poll {@code GET /api/slide-decks/{id}}. */
    @PostMapping("/api/documents/{documentId}/slides")
    public ResponseEntity<StudyDtos.SlideDeckResponse> generate(
            @PathVariable UUID documentId,
            @RequestParam(defaultValue = "8") int count) {
        User user = CurrentUser.require();
        SlideDeck deck = slides.start(user, documentId, Math.clamp(count, 3, 20));
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(toResponse(deck));
    }

    @GetMapping("/api/slide-decks/{deckId}")
    public StudyDtos.SlideDeckResponse get(@PathVariable UUID deckId) {
        return toResponse(slides.requireOwned(CurrentUser.require(), deckId));
    }

    @GetMapping("/api/documents/{documentId}/slides/latest")
    public StudyDtos.SlideDeckResponse latest(@PathVariable UUID documentId) {
        return slides.latest(CurrentUser.require(), documentId)
                .map(this::toResponse)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "No slides yet"));
    }

    private StudyDtos.SlideDeckResponse toResponse(SlideDeck deck) {
        String viewPath = deck.getStatus() == SlideDeckStatus.READY
                ? SlideService.VIEW_PATH + deck.getViewToken() + "/"
                : null;
        return StudyDtos.SlideDeckResponse.from(deck, viewPath,
                slides.pdfUrl(deck).orElse(null), slides.markdownUrl(deck).orElse(null));
    }

    /**
     * Serve the built Slidev site.
     *
     * <p>Unauthenticated by necessity (an iframe cannot send the JWT), so the unguessable view
     * token is the capability, and it is looked up rather than parsed: nothing outside a READY
     * deck's own {@code site/} prefix is reachable. See {@code SecurityConfig} for the framing
     * rules.
     */
    @GetMapping({"/api/slides/view/{token}", "/api/slides/view/{token}/**"})
    public void view(@PathVariable String token, HttpServletRequest request,
            HttpServletResponse response) throws IOException {
        String prefix = SlideService.VIEW_PATH + token;
        String uri = request.getRequestURI();
        if (uri.equals(prefix)) {
            // Slidev's asset URLs are absolute, but the router expects the trailing slash.
            response.sendRedirect(prefix + "/");
            return;
        }

        String path = URLDecoder.decode(uri.substring(prefix.length() + 1), StandardCharsets.UTF_8);
        if (path.isEmpty()) {
            path = "index.html";
        }
        if (!SAFE_PATH.matcher(path).matches()) {
            response.setStatus(HttpStatus.NOT_FOUND.value());
            return;
        }

        SlideDeck deck = slides.findReadyByViewToken(token).orElse(null);
        if (deck == null) {
            response.setStatus(HttpStatus.NOT_FOUND.value());
            return;
        }

        var object = storage.openObject(SlideService.prefix(deck) + "/site/" + path);
        if (object.isEmpty()) {
            response.setStatus(HttpStatus.NOT_FOUND.value());
            return;
        }
        try (InputStream in = object.get()) {
            var meta = object.get().response();
            response.setContentType(meta.contentType());
            if (meta.contentLength() != null) {
                response.setContentLengthLong(meta.contentLength());
            }
            // Vite fingerprints everything under assets/; the HTML must always be revalidated.
            response.setHeader("Cache-Control", path.startsWith("assets/")
                    ? "public, max-age=31536000, immutable"
                    : "no-cache");
            in.transferTo(response.getOutputStream());
        }
    }
}
