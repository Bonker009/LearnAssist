package com.learnassist.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UpdateTimestamp;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "slide_decks")
public class SlideDeck {

    private static final int TITLE_LENGTH = 200;

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "document_id", nullable = false)
    private Document document;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "created_by", nullable = false)
    private User createdBy;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private SlideDeckStatus status = SlideDeckStatus.GENERATING;

    @Column(nullable = false, length = TITLE_LENGTH)
    private String title = "";

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private List<Map<String, Object>> outline = List.of();

    @Column(name = "view_token", nullable = false, unique = true, length = 64)
    private String viewToken;

    @Column(name = "has_pdf", nullable = false)
    private boolean hasPdf;

    @Column(columnDefinition = "text")
    private String error;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected SlideDeck() {
        // JPA
    }

    public SlideDeck(Document document, User createdBy, String viewToken) {
        this.document = document;
        this.createdBy = createdBy;
        this.viewToken = viewToken;
    }

    public void outlined(String title, List<Map<String, Object>> outline) {
        String clean = title == null ? "" : title;
        this.title = clean.length() > TITLE_LENGTH ? clean.substring(0, TITLE_LENGTH) : clean;
        this.outline = outline == null ? List.of() : outline;
        this.status = SlideDeckStatus.RENDERING;
    }

    public void rendered(boolean hasPdf) {
        this.hasPdf = hasPdf;
        this.status = SlideDeckStatus.READY;
    }

    public void failed(String error) {
        this.error = error;
        this.status = SlideDeckStatus.FAILED;
    }

    public UUID getId() {
        return id;
    }

    public Document getDocument() {
        return document;
    }

    public User getCreatedBy() {
        return createdBy;
    }

    public SlideDeckStatus getStatus() {
        return status;
    }

    public String getTitle() {
        return title;
    }

    public List<Map<String, Object>> getOutline() {
        return outline;
    }

    public String getViewToken() {
        return viewToken;
    }

    public boolean hasPdf() {
        return hasPdf;
    }

    public String getError() {
        return error;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
