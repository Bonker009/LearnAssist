package com.learnassist.api.repository;

import com.learnassist.api.domain.IngestJob;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface IngestJobRepository extends JpaRepository<IngestJob, UUID> {

    Optional<IngestJob> findByDocumentId(UUID documentId);
}
