package com.learnassist.api.web;

import com.learnassist.api.domain.User;
import com.learnassist.api.security.CurrentUser;
import com.learnassist.api.service.FlashcardService;
import com.learnassist.api.web.dto.StudyDtos;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class FlashcardController {

    private final FlashcardService flashcards;

    public FlashcardController(FlashcardService flashcards) {
        this.flashcards = flashcards;
    }

    @PostMapping("/api/documents/{documentId}/flashcards")
    public ResponseEntity<StudyDtos.FlashcardDeckResponse> generate(
            @PathVariable UUID documentId,
            @RequestParam(defaultValue = "10") int count) {
        User user = CurrentUser.require();
        var deck = flashcards.generate(user, documentId, Math.clamp(count, 1, 30));
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(StudyDtos.FlashcardDeckResponse.from(deck));
    }

    /** The newest deck for a document, so progress survives a reload. 404 if there is none. */
    @GetMapping("/api/documents/{documentId}/flashcards/latest")
    public StudyDtos.FlashcardDeckResponse latest(@PathVariable UUID documentId) {
        User user = CurrentUser.require();
        return flashcards.latest(user, documentId)
                .map(StudyDtos.FlashcardDeckResponse::from)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "No flashcards yet"));
    }

    @PostMapping("/api/flashcards/{cardId}/review")
    public ResponseEntity<Void> review(@PathVariable UUID cardId,
            @Valid @RequestBody StudyDtos.ReviewRequest request) {
        flashcards.review(CurrentUser.require(), cardId, request.known());
        return ResponseEntity.noContent().build();
    }
}
