package com.learnassist.api.service;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.LocalDate;
import java.util.Set;
import org.junit.jupiter.api.Test;

class StreakTest {

    private static final LocalDate TODAY = LocalDate.of(2026, 9, 17);

    @Test
    void countsConsecutiveDaysEndingToday() {
        var days = Set.of(TODAY, TODAY.minusDays(1), TODAY.minusDays(2), TODAY.minusDays(4));
        assertEquals(3, DashboardService.streak(days, TODAY));
    }

    @Test
    void notBrokenBeforeStudyingToday() {
        var days = Set.of(TODAY.minusDays(1), TODAY.minusDays(2));
        assertEquals(2, DashboardService.streak(days, TODAY));
    }

    @Test
    void brokenAfterAMissedDay() {
        assertEquals(0, DashboardService.streak(Set.of(TODAY.minusDays(2)), TODAY));
        assertEquals(0, DashboardService.streak(Set.of(), TODAY));
    }
}
