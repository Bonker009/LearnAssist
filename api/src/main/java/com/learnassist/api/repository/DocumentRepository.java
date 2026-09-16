package com.learnassist.api.repository;

import com.learnassist.api.domain.Document;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface DocumentRepository extends JpaRepository<Document, UUID> {

    /**
     * Resolve a document <em>through</em> its owner.
     *
     * <p>There is deliberately no plain {@code findById} usage in the service layer: fetching first
     * and comparing the owner afterwards is a check a future caller can forget, and forgetting it
     * leaks another student's lecture. Making the owner part of the lookup means an unauthorised
     * request simply finds nothing.
     */
    Optional<Document> findByIdAndOwnerId(UUID id, UUID ownerId);

    List<Document> findByOwnerIdOrderByCreatedAtDesc(UUID ownerId);
}
