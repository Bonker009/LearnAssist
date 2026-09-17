package com.learnassist.api.service;

import com.learnassist.api.domain.User;
import java.sql.Date;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Read-only study statistics for the dashboard.
 *
 * <p>Plain SQL rather than JPA: these are aggregates across five tables (including the
 * citations JSON), and expressing them as entity graphs would load whole histories into memory
 * to count them. Every query is scoped by owner in its own WHERE clause, for the same reason
 * lookups elsewhere go through the owner: an aggregate is still a leak if it counts someone
 * else's rows.
 */
@Service
public class DashboardService {

    static final int ACTIVITY_DAYS = 30;

    private final NamedParameterJdbcTemplate jdbc;

    public DashboardService(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public record Totals(long resources, long ready, long processing, long failed, long chats,
            long questions, long groundedAnswers, long answers, long quizzes,
            double averageScore, int streakDays) {}

    public record TypeCount(String docType, long count) {}

    public record ActivityDay(LocalDate day, long questions, long quizzes, long resources) {}

    public record QuizPoint(Instant takenAt, int score, int total, String filename) {}

    public record CitedResource(UUID id, String filename, String docType, long citations) {}

    public record RecentChat(UUID id, String title, Instant updatedAt, long questions,
            long resources) {}

    public record Processing(UUID id, String filename, String docType, String stage,
            int progress) {}

    public record Dashboard(Totals totals, List<TypeCount> resourceTypes,
            List<ActivityDay> activity, List<QuizPoint> quizTrend,
            List<CitedResource> mostCited, List<RecentChat> recentChats,
            List<Processing> processing) {}

    @Transactional(readOnly = true)
    public Dashboard build(User owner, ZoneId zone) {
        var params = new MapSqlParameterSource()
                .addValue("owner", owner.getId())
                // Day buckets follow the student's clock, not the server's: a question
                // asked at 11pm in Phnom Penh belongs to that evening.
                .addValue("tz", zone.getId())
                .addValue("days", ACTIVITY_DAYS - 1);

        Map<String, Long> byStatus = new LinkedHashMap<>();
        Map<String, Long> byType = new LinkedHashMap<>();
        jdbc.query("""
                SELECT doc_type, status, count(*) AS n
                FROM documents
                WHERE owner_id = :owner AND status <> 'PENDING_UPLOAD'
                GROUP BY doc_type, status
                """, params, rs -> {
                    long n = rs.getLong("n");
                    byStatus.merge(rs.getString("status"), n, Long::sum);
                    byType.merge(rs.getString("doc_type"), n, Long::sum);
                });

        long chats = count("SELECT count(*) FROM conversations WHERE owner_id = :owner", params);
        long questions = count("""
                SELECT count(*) FROM chat_messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.owner_id = :owner AND m.role = 'USER'
                """, params);

        long[] answers = jdbc.queryForObject("""
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE jsonb_array_length(m.citations) > 0) AS grounded
                FROM chat_messages m
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.owner_id = :owner AND m.role = 'ASSISTANT'
                """, params, (rs, i) -> new long[] {rs.getLong("total"), rs.getLong("grounded")});

        Object[] quiz = jdbc.queryForObject("""
                SELECT count(*) AS n,
                       coalesce(avg(score::float / nullif(total, 0)), 0) AS average
                FROM quiz_attempts WHERE user_id = :owner
                """, params, (rs, i) -> new Object[] {rs.getLong("n"), rs.getDouble("average")});

        List<ActivityDay> activity = jdbc.query("""
                WITH days AS (
                    SELECT generate_series(
                        (now() AT TIME ZONE :tz)::date - :days,
                        (now() AT TIME ZONE :tz)::date,
                        interval '1 day')::date AS day
                )
                SELECT d.day,
                  (SELECT count(*) FROM chat_messages m
                     JOIN conversations c ON c.id = m.conversation_id
                    WHERE c.owner_id = :owner AND m.role = 'USER'
                      AND (m.created_at AT TIME ZONE :tz)::date = d.day) AS questions,
                  (SELECT count(*) FROM quiz_attempts a
                    WHERE a.user_id = :owner
                      AND (a.created_at AT TIME ZONE :tz)::date = d.day) AS quizzes,
                  (SELECT count(*) FROM documents x
                    WHERE x.owner_id = :owner AND x.status <> 'PENDING_UPLOAD'
                      AND (x.created_at AT TIME ZONE :tz)::date = d.day) AS resources
                FROM days d
                ORDER BY d.day
                """, params, (rs, i) -> new ActivityDay(rs.getDate("day").toLocalDate(),
                        rs.getLong("questions"), rs.getLong("quizzes"), rs.getLong("resources")));

        // A year of active days, so a streak longer than the chart window still counts.
        Set<LocalDate> activeDays = new HashSet<>(jdbc.query("""
                SELECT DISTINCT day FROM (
                  SELECT (m.created_at AT TIME ZONE :tz)::date AS day
                    FROM chat_messages m JOIN conversations c ON c.id = m.conversation_id
                   WHERE c.owner_id = :owner AND m.role = 'USER'
                     AND m.created_at > now() - interval '366 days'
                  UNION
                  SELECT (a.created_at AT TIME ZONE :tz)::date
                    FROM quiz_attempts a
                   WHERE a.user_id = :owner AND a.created_at > now() - interval '366 days'
                ) active
                """, params, (rs, i) -> ((Date) rs.getDate("day")).toLocalDate()));

        List<QuizPoint> quizTrend = new ArrayList<>(jdbc.query("""
                SELECT a.created_at, a.score, a.total, d.filename
                FROM quiz_attempts a
                JOIN quizzes q ON q.id = a.quiz_id
                JOIN documents d ON d.id = q.document_id
                WHERE a.user_id = :owner
                ORDER BY a.created_at DESC
                LIMIT 12
                """, params, (rs, i) -> new QuizPoint(rs.getTimestamp("created_at").toInstant(),
                        rs.getInt("score"), rs.getInt("total"), rs.getString("filename"))));
        Collections.reverse(quizTrend);

        List<CitedResource> mostCited = jdbc.query("""
                SELECT d.id, d.filename, d.doc_type, count(*) AS citations
                FROM chat_messages m
                JOIN conversations c ON c.id = m.conversation_id
                CROSS JOIN LATERAL jsonb_array_elements(m.citations) AS cit
                JOIN documents d ON d.id::text = cit ->> 'document_id'
                WHERE c.owner_id = :owner AND d.owner_id = :owner AND m.role = 'ASSISTANT'
                GROUP BY d.id, d.filename, d.doc_type
                ORDER BY citations DESC, d.filename
                LIMIT 5
                """, params, (rs, i) -> new CitedResource(rs.getObject("id", UUID.class),
                        rs.getString("filename"), rs.getString("doc_type"),
                        rs.getLong("citations")));

        List<RecentChat> recentChats = jdbc.query("""
                SELECT c.id, c.title, c.updated_at,
                  (SELECT count(*) FROM chat_messages m
                    WHERE m.conversation_id = c.id AND m.role = 'USER') AS questions,
                  (SELECT count(*) FROM conversation_documents cd
                    WHERE cd.conversation_id = c.id) AS resources
                FROM conversations c
                WHERE c.owner_id = :owner
                ORDER BY c.updated_at DESC
                LIMIT 5
                """, params, (rs, i) -> new RecentChat(rs.getObject("id", UUID.class),
                        rs.getString("title"), rs.getTimestamp("updated_at").toInstant(),
                        rs.getLong("questions"), rs.getLong("resources")));

        List<Processing> processing = jdbc.query("""
                SELECT d.id, d.filename, d.doc_type, j.stage, j.progress
                FROM documents d
                JOIN ingest_jobs j ON j.document_id = d.id
                WHERE d.owner_id = :owner AND d.status = 'PROCESSING'
                ORDER BY d.created_at DESC
                LIMIT 5
                """, params, (rs, i) -> new Processing(rs.getObject("id", UUID.class),
                        rs.getString("filename"), rs.getString("doc_type"),
                        rs.getString("stage"), rs.getInt("progress")));

        long resources = byStatus.values().stream().mapToLong(Long::longValue).sum();
        var totals = new Totals(
                resources,
                byStatus.getOrDefault("READY", 0L),
                byStatus.getOrDefault("PROCESSING", 0L) + byStatus.getOrDefault("UPLOADED", 0L),
                byStatus.getOrDefault("FAILED", 0L),
                chats,
                questions,
                answers[1],
                answers[0],
                (long) quiz[0],
                (double) quiz[1],
                streak(activeDays, LocalDate.now(zone)));

        List<TypeCount> types = byType.entrySet().stream()
                .map(e -> new TypeCount(e.getKey(), e.getValue()))
                .sorted((a, b) -> Long.compare(b.count(), a.count()))
                .toList();

        return new Dashboard(totals, types, activity, quizTrend, mostCited, recentChats,
                processing);
    }

    private long count(String sql, MapSqlParameterSource params) {
        Long n = jdbc.queryForObject(sql, params, Long.class);
        return n == null ? 0 : n;
    }

    /**
     * Consecutive active days ending today — or yesterday, so a streak is not shown as broken
     * in the morning before the student has studied.
     */
    static int streak(Set<LocalDate> activeDays, LocalDate today) {
        LocalDate day = activeDays.contains(today) ? today : today.minusDays(1);
        int streak = 0;
        while (activeDays.contains(day)) {
            streak++;
            day = day.minusDays(1);
        }
        return streak;
    }
}
