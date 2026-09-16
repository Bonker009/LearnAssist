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
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "quiz_attempts")
public class QuizAttempt {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "quiz_id", nullable = false)
    private Quiz quiz;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    /** Submitted answers as position -> chosen option index. */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String, Integer> answers = Map.of();

    @Column(nullable = false)
    private short score;

    @Column(nullable = false)
    private short total;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected QuizAttempt() {
        // JPA
    }

    public QuizAttempt(Quiz quiz, User user, Map<String, Integer> answers, short score,
            short total) {
        this.quiz = quiz;
        this.user = user;
        this.answers = answers;
        this.score = score;
        this.total = total;
    }

    public UUID getId() {
        return id;
    }

    public short getScore() {
        return score;
    }

    public short getTotal() {
        return total;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
