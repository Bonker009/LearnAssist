package com.learnassist.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinTable;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

/**
 * A chat, and the resources its answers are allowed to draw on.
 *
 * <p>Retrieval is scoped to exactly the attached documents. That is the conversation-level
 * version of the rule the per-document chat enforced: a question asked in the biology chat must
 * never be answered from the history lecture that happens to be in the same library.
 */
@Entity
@Table(name = "conversations")
public class Conversation {

    public static final String DEFAULT_TITLE = "New chat";

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "owner_id", nullable = false)
    private User owner;

    @Column(nullable = false, length = 200)
    private String title = DEFAULT_TITLE;

    @ManyToMany(fetch = FetchType.LAZY)
    @JoinTable(
            name = "conversation_documents",
            joinColumns = @JoinColumn(name = "conversation_id"),
            inverseJoinColumns = @JoinColumn(name = "document_id"))
    private Set<Document> documents = new LinkedHashSet<>();

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    /**
     * Set explicitly rather than by {@code @UpdateTimestamp}: adding a message does not dirty this
     * row, so an automatic timestamp would never move and the sidebar would sort by creation.
     */
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt = Instant.now();

    protected Conversation() {
        // JPA
    }

    public Conversation(User owner, String title) {
        this.owner = owner;
        if (title != null && !title.isBlank()) {
            this.title = title.strip();
        }
    }

    public UUID getId() {
        return id;
    }

    public User getOwner() {
        return owner;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title.strip();
    }

    public boolean hasDefaultTitle() {
        return DEFAULT_TITLE.equals(title);
    }

    public Set<Document> getDocuments() {
        return documents;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }

    public void touch() {
        this.updatedAt = Instant.now();
    }
}
