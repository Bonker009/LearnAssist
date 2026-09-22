package com.learnassist.api.repository;

import com.learnassist.api.domain.FlashcardDeck;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

/** Resolved through the creator, as with quizzes: another student's deck is simply not found. */
public interface FlashcardDeckRepository extends JpaRepository<FlashcardDeck, UUID> {

    @EntityGraph(attributePaths = "cards")
    Optional<FlashcardDeck> findFirstByDocumentIdAndCreatedByIdOrderByCreatedAtDesc(
            UUID documentId, UUID userId);
}
