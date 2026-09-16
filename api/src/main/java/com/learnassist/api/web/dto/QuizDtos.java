package com.learnassist.api.web.dto;

import com.learnassist.api.domain.Quiz;
import com.learnassist.api.service.QuizService;
import jakarta.validation.constraints.NotNull;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Quiz request and response shapes. */
public final class QuizDtos {

    private QuizDtos() {}

    /**
     * A question as sent to the browser before submission.
     *
     * <p>There is no {@code correctIndex}, {@code explanation} or {@code snippet} field here,
     * and that omission is the security control. Serialising the entity and suppressing those
     * fields with annotations would put the answer key one deleted annotation away from the
     * client; leaking it from this record requires someone to add the field by hand.
     */
    public record QuestionResponse(UUID id, int position, String question, List<String> options,
            String sourceLabel) {}

    public record QuizResponse(UUID id, UUID documentId, Instant createdAt,
            List<QuestionResponse> questions) {

        public static QuizResponse from(Quiz quiz) {
            return new QuizResponse(
                    quiz.getId(),
                    quiz.getDocument().getId(),
                    quiz.getCreatedAt(),
                    quiz.getQuestions().stream()
                            .map(q -> new QuestionResponse(
                                    q.getId(),
                                    q.getPosition(),
                                    q.getQuestion(),
                                    q.getOptions(),
                                    // The label alone is safe and useful: it tells the
                                    // student which part of the lecture to think about
                                    // without giving away the answer.
                                    q.getSourceLabel()))
                            .toList());
        }
    }

    /** @param answers question position (as a string key) -> chosen option index */
    public record SubmitRequest(@NotNull Map<String, Integer> answers) {}

    public record GradedQuestionResponse(UUID questionId, int position, boolean correct,
            int correctIndex, Integer chosenIndex, String explanation,
            Map<String, Object> source, String sourceLabel, String snippet) {}

    public record GradeResponse(UUID attemptId, int score, int total,
            List<GradedQuestionResponse> questions) {

        public static GradeResponse from(QuizService.Grade grade) {
            return new GradeResponse(
                    grade.attemptId(),
                    grade.score(),
                    grade.total(),
                    grade.questions().stream()
                            .map(q -> new GradedQuestionResponse(
                                    q.questionId(), q.position(), q.correct(), q.correctIndex(),
                                    q.chosenIndex(), q.explanation(), q.source(),
                                    q.sourceLabel(), q.snippet()))
                            .toList());
        }
    }
}
