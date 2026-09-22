package com.learnassist.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/** One card. Unlike a quiz question there is nothing to hide: the back is the point. */
@Entity
@Table(name = "flashcards")
public class Flashcard {

    private static final int LABEL_LENGTH = 255;

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "deck_id", nullable = false)
    private FlashcardDeck deck;

    @Column(nullable = false)
    private int position;

    @Column(nullable = false, columnDefinition = "text")
    private String front;

    @Column(nullable = false, columnDefinition = "text")
    private String back;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> source = Map.of();

    @Column(name = "source_label", nullable = false, length = LABEL_LENGTH)
    private String sourceLabel = "";

    @Column(nullable = false, columnDefinition = "text")
    private String snippet = "";

    /** TRUE "knew it", FALSE "again", null if never studied. */
    private Boolean known;

    @Column(name = "reviewed_at")
    private Instant reviewedAt;

    protected Flashcard() {
        // JPA
    }

    public Flashcard(String front, String back, Map<String, Object> source, String sourceLabel,
            String snippet) {
        this.front = front;
        this.back = back;
        this.source = source == null ? Map.of() : source;
        String label = sourceLabel == null ? "" : sourceLabel;
        // Section labels come from document headings, so their length is not ours to choose.
        this.sourceLabel = label.length() > LABEL_LENGTH ? label.substring(0, LABEL_LENGTH) : label;
        this.snippet = snippet == null ? "" : snippet;
    }

    void attachTo(FlashcardDeck deck, int position) {
        this.deck = deck;
        this.position = position;
    }

    public void review(boolean knewIt) {
        this.known = knewIt;
        this.reviewedAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public int getPosition() {
        return position;
    }

    public String getFront() {
        return front;
    }

    public String getBack() {
        return back;
    }

    public Map<String, Object> getSource() {
        return source;
    }

    public String getSourceLabel() {
        return sourceLabel;
    }

    public String getSnippet() {
        return snippet;
    }

    public Boolean getKnown() {
        return known;
    }
}
