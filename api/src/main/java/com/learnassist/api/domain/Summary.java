package com.learnassist.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "summaries")
public class Summary {

    @Id
    @GeneratedValue
    private UUID id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "document_id", nullable = false, unique = true)
    private Document document;

    @Column(nullable = false, columnDefinition = "text")
    private String summary;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "key_concepts", nullable = false, columnDefinition = "jsonb")
    private List<KeyConcept> keyConcepts = List.of();

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    public record KeyConcept(String term, String explanation) {}

    protected Summary() {
        // JPA
    }

    public Summary(Document document, String summary, List<KeyConcept> keyConcepts) {
        this.document = document;
        this.summary = summary;
        this.keyConcepts = keyConcepts;
    }

    public UUID getId() {
        return id;
    }

    public Document getDocument() {
        return document;
    }

    public String getSummary() {
        return summary;
    }

    public List<KeyConcept> getKeyConcepts() {
        return keyConcepts;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
