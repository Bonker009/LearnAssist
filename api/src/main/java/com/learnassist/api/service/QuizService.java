package com.learnassist.api.service;

import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.DocumentStatus;
import com.learnassist.api.domain.Quiz;
import com.learnassist.api.domain.QuizAttempt;
import com.learnassist.api.domain.QuizQuestion;
import com.learnassist.api.domain.User;
import com.learnassist.api.repository.QuizAttemptRepository;
import com.learnassist.api.repository.QuizRepository;
import com.learnassist.api.web.ApiException;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class QuizService {

    private final QuizRepository quizzes;
    private final QuizAttemptRepository attempts;
    private final DocumentService documents;
    private final AiClient ai;
    private final RateLimiter rateLimiter;

    private static final String QUIZ_BUCKET = "quiz";
    private static final int QUIZ_LIMIT = 20;
    private static final Duration QUIZ_WINDOW = Duration.ofHours(1);

    public QuizService(QuizRepository quizzes, QuizAttemptRepository attempts,
            DocumentService documents, AiClient ai, RateLimiter rateLimiter) {
        this.quizzes = quizzes;
        this.attempts = attempts;
        this.documents = documents;
        this.ai = ai;
        this.rateLimiter = rateLimiter;
    }

    @Transactional
    public Quiz generate(User user, UUID documentId, int count) {
        if (!rateLimiter.tryAcquire(QUIZ_BUCKET, user.getId(), QUIZ_LIMIT, QUIZ_WINDOW)) {
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,
                    "Too many quizzes generated in the last hour. Try again shortly.");
        }

        Document document = documents.requireOwned(user, documentId);
        if (document.getStatus() != DocumentStatus.READY) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "This document is still being processed");
        }

        List<AiClient.GeneratedQuestion> generated =
                ai.generateQuiz(new AiClient.QuizRequest(documentId, count));

        if (generated == null || generated.isEmpty()) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Could not generate questions from this document");
        }

        Quiz quiz = new Quiz(document, user);
        for (AiClient.GeneratedQuestion question : generated) {
            quiz.addQuestion(new QuizQuestion(
                    question.question(),
                    question.options(),
                    (short) question.correctIndex(),
                    question.explanation(),
                    question.source(),
                    question.sourceLabel(),
                    question.snippet()));
        }
        return quizzes.save(quiz);
    }

    @Transactional(readOnly = true)
    public Quiz requireOwned(User user, UUID quizId) {
        return quizzes.findByIdAndCreatedById(quizId, user.getId())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Quiz not found"));
    }

    public record GradedQuestion(
            UUID questionId,
            int position,
            boolean correct,
            int correctIndex,
            Integer chosenIndex,
            String explanation,
            Map<String, Object> source,
            String sourceLabel,
            String snippet) {}

    public record Grade(UUID attemptId, int score, int total, List<GradedQuestion> questions) {}

    /**
     * Grade a submission.
     *
     * <p>This is the only path that reveals the answer key, and it does so only after the
     * student has committed to their answers.
     *
     * @param answers question position -> chosen option index
     */
    @Transactional
    public Grade grade(User user, UUID quizId, Map<String, Integer> answers) {
        Quiz quiz = requireOwned(user, quizId);

        short score = 0;
        List<GradedQuestion> graded = new java.util.ArrayList<>();

        for (QuizQuestion question : quiz.getQuestions()) {
            Integer chosen = answers.get(String.valueOf(question.getPosition()));
            boolean correct = chosen != null && chosen == question.getCorrectIndex();
            if (correct) {
                score++;
            }
            graded.add(new GradedQuestion(
                    question.getId(),
                    question.getPosition(),
                    correct,
                    question.getCorrectIndex(),
                    chosen,
                    question.getExplanation(),
                    question.getSource(),
                    question.getSourceLabel(),
                    question.getSnippet()));
        }

        short total = (short) quiz.getQuestions().size();
        QuizAttempt attempt = attempts.save(
                new QuizAttempt(quiz, user, answers, score, total));

        return new Grade(attempt.getId(), score, total, graded);
    }
}
