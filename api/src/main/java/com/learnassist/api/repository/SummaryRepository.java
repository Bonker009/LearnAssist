package com.learnassist.api.repository;

import com.learnassist.api.domain.Summary;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface SummaryRepository extends JpaRepository<Summary, UUID> {

    Optional<Summary> findByDocumentId(UUID documentId);
}
