package com.learnassist.api.repository;

import com.learnassist.api.domain.SlideDeck;
import com.learnassist.api.domain.SlideDeckStatus;
import java.util.Collection;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.transaction.annotation.Transactional;

public interface SlideDeckRepository extends JpaRepository<SlideDeck, UUID> {

    Optional<SlideDeck> findByIdAndCreatedById(UUID id, UUID userId);

    Optional<SlideDeck> findFirstByDocumentIdAndCreatedByIdOrderByCreatedAtDesc(
            UUID documentId, UUID userId);

    /** For serving the built site: the token is the capability, there is no JWT. */
    Optional<SlideDeck> findByViewToken(String viewToken);

    @Modifying
    @Transactional
    @Query("update SlideDeck d set d.status = com.learnassist.api.domain.SlideDeckStatus.FAILED, "
            + "d.error = :error where d.status in :statuses")
    int failAll(Collection<SlideDeckStatus> statuses, String error);
}
