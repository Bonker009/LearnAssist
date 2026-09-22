package com.learnassist.api.repository;

import com.learnassist.api.domain.Flashcard;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface FlashcardRepository extends JpaRepository<Flashcard, UUID> {

    /** A card, only if its deck belongs to {@code userId}. */
    Optional<Flashcard> findByIdAndDeckCreatedById(UUID id, UUID userId);
}
