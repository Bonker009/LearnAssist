package com.learnassist.api.web;

import com.learnassist.api.domain.Quiz;
import com.learnassist.api.domain.User;
import com.learnassist.api.security.CurrentUser;
import com.learnassist.api.service.QuizService;
import com.learnassist.api.web.dto.QuizDtos;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class QuizController {

    private final QuizService quizzes;

    public QuizController(QuizService quizzes) {
        this.quizzes = quizzes;
    }

    @PostMapping("/api/documents/{documentId}/quiz")
    public ResponseEntity<QuizDtos.QuizResponse> generate(
            @PathVariable UUID documentId,
            @RequestParam(defaultValue = "5") int count) {
        User user = CurrentUser.require();
        Quiz quiz = quizzes.generate(user, documentId, Math.clamp(count, 1, 20));
        return ResponseEntity.status(HttpStatus.CREATED).body(QuizDtos.QuizResponse.from(quiz));
    }

    /** Fetch a quiz to take. The response deliberately carries no answer key. */
    @GetMapping("/api/quizzes/{quizId}")
    public QuizDtos.QuizResponse get(@PathVariable UUID quizId) {
        User user = CurrentUser.require();
        return QuizDtos.QuizResponse.from(quizzes.requireOwned(user, quizId));
    }

    @PostMapping("/api/quizzes/{quizId}/submit")
    public QuizDtos.GradeResponse submit(@PathVariable UUID quizId,
            @Valid @RequestBody QuizDtos.SubmitRequest request) {
        User user = CurrentUser.require();
        return QuizDtos.GradeResponse.from(quizzes.grade(user, quizId, request.answers()));
    }
}
