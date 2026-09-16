package com.learnassist.api.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * One question in a quiz.
 *
 * <p>{@code correctIndex} and {@code explanation} are stored here but must never reach the
 * browser before the attempt is submitted. That is enforced by using a separate response DTO
 * rather than annotating this entity — an entity annotation is one deletion away from leaking
 * the answer key, whereas a DTO requires someone to add the field deliberately.
 */
@Entity
@Table(name = "quiz_questions")
public class QuizQuestion {

    @Id
    @GeneratedValue
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "quiz_id", nullable = false)
    private Quiz quiz;

    @Column(nullable = false)
    private int position;

    @Column(nullable = false, columnDefinition = "text")
    private String question;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private List<String> options;

    @Column(name = "correct_index", nullable = false)
    private short correctIndex;

    @Column(nullable = false, columnDefinition = "text")
    private String explanation = "";

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false, columnDefinition = "jsonb")
    private Map<String, Object> source = Map.of();

    @Column(name = "source_label", nullable = false, length = 64)
    private String sourceLabel = "";

    @Column(nullable = false, columnDefinition = "text")
    private String snippet = "";

    protected QuizQuestion() {
        // JPA
    }

    public QuizQuestion(String question, List<String> options, short correctIndex,
            String explanation, Map<String, Object> source, String sourceLabel, String snippet) {
        this.question = question;
        this.options = options;
        this.correctIndex = correctIndex;
        this.explanation = explanation == null ? "" : explanation;
        this.source = source == null ? Map.of() : source;
        this.sourceLabel = sourceLabel == null ? "" : sourceLabel;
        this.snippet = snippet == null ? "" : snippet;
    }

    void attachTo(Quiz quiz, int position) {
        this.quiz = quiz;
        this.position = position;
    }

    public UUID getId() {
        return id;
    }

    public int getPosition() {
        return position;
    }

    public String getQuestion() {
        return question;
    }

    public List<String> getOptions() {
        return options;
    }

    public short getCorrectIndex() {
        return correctIndex;
    }

    public String getExplanation() {
        return explanation;
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
}
