package com.learnassist.api.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Strongly-typed binding for the {@code app.*} configuration tree.
 */
@ConfigurationProperties(prefix = "app")
public record AppProperties(String corsOrigin, Jwt jwt, S3 s3, Ai ai, Slides slides) {

    public record Jwt(String secret, long expiryMinutes) {
        public Duration expiry() {
            return Duration.ofMinutes(expiryMinutes);
        }
    }

    /**
     * @param endpoint       reachable from inside the docker network; used for server-side calls
     * @param publicEndpoint reachable from the browser; presigned URLs MUST use this, because the
     *                       signature covers the Host header and the browser cannot resolve
     *                       {@code rustfs}
     */
    public record S3(
            String endpoint,
            String publicEndpoint,
            String accessKey,
            String secretKey,
            String bucket,
            String region,
            long presignExpiryMinutes,
            long maxUploadBytes) {

        public Duration presignExpiry() {
            return Duration.ofMinutes(presignExpiryMinutes);
        }
    }

    public record Ai(String baseUrl, String internalKey, long timeoutSeconds) {
        public Duration timeout() {
            return Duration.ofSeconds(timeoutSeconds);
        }
    }

    /**
     * The Slidev render service. It shares the AI service's internal key.
     *
     * @param timeoutSeconds covers {@code slidev build} and the PDF export, which runs a
     *                       headless Chromium over every slide
     */
    public record Slides(String baseUrl, long timeoutSeconds) {
        public Duration timeout() {
            return Duration.ofSeconds(timeoutSeconds);
        }
    }
}
