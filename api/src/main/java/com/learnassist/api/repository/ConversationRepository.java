package com.learnassist.api.repository;

import com.learnassist.api.domain.Conversation;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ConversationRepository extends JpaRepository<Conversation, UUID> {

    /** Resolved through the owner, for the same reason as {@link DocumentRepository}. */
    Optional<Conversation> findByIdAndOwnerId(UUID id, UUID ownerId);

    List<Conversation> findByOwnerIdOrderByUpdatedAtDesc(UUID ownerId);
}
