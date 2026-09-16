package com.learnassist.api.repository;

import com.learnassist.api.domain.Quiz;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

public interface QuizRepository extends JpaRepository<Quiz, UUID> {

    /**
     * Resolve a quiz through its creator, for the same reason documents are:
     * an unauthorised request must find nothing rather than depend on a check
     * a caller could forget.
     */
    @EntityGraph(attributePaths = "questions")
    Optional<Quiz> findByIdAndCreatedById(UUID id, UUID userId);
}
