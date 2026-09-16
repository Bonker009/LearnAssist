package com.learnassist.api.domain;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.hibernate.annotations.CreationTimestamp;

@Entity
@Table(name = "quizzes")
public class Quiz {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "document_id", nullable = false)
    private Document document;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "created_by", nullable = false)
    private User createdBy;

    @OneToMany(mappedBy = "quiz", cascade = CascadeType.ALL, orphanRemoval = true,
            fetch = FetchType.LAZY)
    @OrderBy("position ASC")
    private List<QuizQuestion> questions = new ArrayList<>();

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected Quiz() {
        // JPA
    }

    public Quiz(Document document, User createdBy) {
        this.document = document;
        this.createdBy = createdBy;
    }

    public void addQuestion(QuizQuestion question) {
        question.attachTo(this, questions.size());
        questions.add(question);
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

    public List<QuizQuestion> getQuestions() {
        return questions;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
