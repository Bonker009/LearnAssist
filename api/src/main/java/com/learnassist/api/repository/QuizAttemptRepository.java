package com.learnassist.api.repository;

import com.learnassist.api.domain.QuizAttempt;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface QuizAttemptRepository extends JpaRepository<QuizAttempt, UUID> {}
