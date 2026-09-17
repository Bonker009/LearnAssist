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
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

@Entity
@Table(name = "documents")
public class Document {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "owner_id", nullable = false)
    private User owner;

    @Column(nullable = false)
    private String filename;

    @Column(name = "content_type", nullable = false)
    private String contentType;

    @Enumerated(EnumType.STRING)
    @Column(name = "doc_type", nullable = false, length = 16)
    private DocType docType;

    /** Null only for YouTube links, whose media is embedded rather than stored. */
    @Column(name = "storage_key")
    private String storageKey;

    /** The original URL for a web page or YouTube resource; null for uploads. */
    @Column(name = "source_url", length = 2048)
    private String sourceUrl;

    @Column(name = "size_bytes", nullable = false)
    private long sizeBytes;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 24)
    private DocumentStatus status = DocumentStatus.PENDING_UPLOAD;

    /** Page or slide count for documents; null until ingestion determines it. */
    @Column(name = "unit_count")
    private Integer unitCount;

    @Column(name = "duration_sec")
    private Double durationSec;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected Document() {
        // JPA
    }

    public Document(User owner, String filename, String contentType, DocType docType,
            String storageKey) {
        this.owner = owner;
        this.filename = filename;
        this.contentType = contentType;
        this.docType = docType;
        this.storageKey = storageKey;
    }

    /** A resource added by link rather than by upload. */
    public static Document fromLink(User owner, String sourceUrl, String contentType,
            DocType docType, String storageKey) {
        // The URL stands in as the name until ingestion reads the page or video title.
        String name = sourceUrl.length() > 512 ? sourceUrl.substring(0, 512) : sourceUrl;
        Document document = new Document(owner, name, contentType, docType, storageKey);
        document.sourceUrl = sourceUrl;
        return document;
    }

    public UUID getId() {
        return id;
    }

    public User getOwner() {
        return owner;
    }

    public String getFilename() {
        return filename;
    }

    public String getContentType() {
        return contentType;
    }

    public DocType getDocType() {
        return docType;
    }

    public String getStorageKey() {
        return storageKey;
    }

    public String getSourceUrl() {
        return sourceUrl;
    }

    public long getSizeBytes() {
        return sizeBytes;
    }

    public void setSizeBytes(long sizeBytes) {
        this.sizeBytes = sizeBytes;
    }

    public DocumentStatus getStatus() {
        return status;
    }

    public void setStatus(DocumentStatus status) {
        this.status = status;
    }

    public Integer getUnitCount() {
        return unitCount;
    }

    public void setUnitCount(Integer unitCount) {
        this.unitCount = unitCount;
    }

    public Double getDurationSec() {
        return durationSec;
    }

    public void setDurationSec(Double durationSec) {
        this.durationSec = durationSec;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
