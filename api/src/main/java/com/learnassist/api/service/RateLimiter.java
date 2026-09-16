package com.learnassist.api.service;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;

/**
 * Per-user sliding-window rate limiter for expensive operations.
 *
 * <p>Ingesting a lecture recording occupies a Whisper worker for minutes and then makes
 * hundreds of embedding calls to a single local model. Without a limit, one user queuing ten
 * uploads starves everybody else on the instance.
 *
 * <p><b>In-memory, and therefore per-instance.</b> That is honest for a single-container
 * deployment and wrong for a horizontally scaled one — with two replicas a user gets twice the
 * budget. Moving the counter to Redis is the fix if this is ever scaled out; it is not done
 * now because it would add a failure mode to the upload path for no benefit at one replica.
 */
@Component
public class RateLimiter {

    private final Map<String, Deque<Instant>> windows = new ConcurrentHashMap<>();

    /**
     * Record an attempt and report whether it is allowed.
     *
     * @return true if the caller is within budget
     */
    public boolean tryAcquire(String bucket, UUID userId, int limit, Duration window) {
        String key = bucket + ":" + userId;
        Instant now = Instant.now();
        Instant cutoff = now.minus(window);

        Deque<Instant> timestamps = windows.computeIfAbsent(key, k -> new ArrayDeque<>());
        synchronized (timestamps) {
            while (!timestamps.isEmpty() && timestamps.peekFirst().isBefore(cutoff)) {
                timestamps.pollFirst();
            }
            if (timestamps.size() >= limit) {
                return false;
            }
            timestamps.addLast(now);
            return true;
        }
    }

    /** Seconds until the caller's oldest attempt falls out of the window. */
    public long retryAfterSeconds(String bucket, UUID userId, Duration window) {
        Deque<Instant> timestamps = windows.get(bucket + ":" + userId);
        if (timestamps == null) {
            return 0;
        }
        synchronized (timestamps) {
            Instant oldest = timestamps.peekFirst();
            if (oldest == null) {
                return 0;
            }
            long seconds = Duration.between(Instant.now(), oldest.plus(window)).toSeconds();
            return Math.max(seconds, 1);
        }
    }

    /**
     * Drop buckets that have fully expired.
     *
     * <p>Called opportunistically rather than on a schedule; the map is keyed by user and a
     * study app has few enough users that unbounded growth is slow, but leaving it entirely
     * unbounded would still be a leak.
     */
    public void evictExpired(Duration window) {
        Instant cutoff = Instant.now().minus(window);
        windows.entrySet().removeIf(entry -> {
            Deque<Instant> timestamps = entry.getValue();
            synchronized (timestamps) {
                return timestamps.isEmpty() || timestamps.peekLast().isBefore(cutoff);
            }
        });
    }
}
