package com.learnassist.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import org.hibernate.annotations.UpdateTimestamp;

/**
 * Progress record for one document's ingestion.
 *
 * <p>Written by Spring Boot when the job is queued, and updated by the AI service as it advances,
 * so the UI can show a real progress bar rather than an indefinite spinner — which matters when a
 * one-hour lecture recording takes many minutes to transcribe.
 */
@Entity
@Table(name = "ingest_jobs")
public class IngestJob {

    @Id
    @GeneratedValue
    private UUID id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "document_id", nullable = false, unique = true)
    private Document document;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 24)
    private IngestStage stage = IngestStage.QUEUED;

    @Column(nullable = false)
    private short progress;

    @Column
    private String error;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected IngestJob() {
        // JPA
    }

    public IngestJob(Document document) {
        this.document = document;
        this.startedAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public Document getDocument() {
        return document;
    }

    public IngestStage getStage() {
        return stage;
    }

    public void setStage(IngestStage stage) {
        this.stage = stage;
    }

    public short getProgress() {
        return progress;
    }

    public void setProgress(short progress) {
        this.progress = progress;
    }

    public String getError() {
        return error;
    }

    public void fail(String error) {
        this.stage = IngestStage.FAILED;
        // Job errors surface in the UI; a multi-kilobyte stack trace is useless there
        // and would bloat every status poll.
        this.error = error != null && error.length() > 2000 ? error.substring(0, 2000) : error;
        this.finishedAt = Instant.now();
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public Instant getFinishedAt() {
        return finishedAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
