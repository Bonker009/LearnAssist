package com.learnassist.api.config;

import java.net.URI;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3Configuration;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * S3 clients pointed at RustFS.
 *
 * <p>Path-style addressing is mandatory: RustFS is not AWS, so a virtual-host style request
 * ({@code http://bucket.rustfs:9000/key}) does not resolve and every call fails.
 *
 * <p>Two beans, deliberately. The client performs server-side work over the docker network; the
 * presigner signs URLs the <em>browser</em> will open, so it must sign against the host-visible
 * endpoint or the browser gets SignatureDoesNotMatch.
 */
@Configuration
public class StorageConfig {

    private static final S3Configuration PATH_STYLE =
            S3Configuration.builder().pathStyleAccessEnabled(true).build();

    private StaticCredentialsProvider credentials(AppProperties props) {
        return StaticCredentialsProvider.create(
                AwsBasicCredentials.create(props.s3().accessKey(), props.s3().secretKey()));
    }

    @Bean
    public S3Client s3Client(AppProperties props) {
        return S3Client.builder()
                .endpointOverride(URI.create(props.s3().endpoint()))
                .credentialsProvider(credentials(props))
                .region(Region.of(props.s3().region()))
                .serviceConfiguration(PATH_STYLE)
                .build();
    }

    @Bean
    public S3Presigner s3Presigner(AppProperties props) {
        return S3Presigner.builder()
                .endpointOverride(URI.create(props.s3().publicEndpoint()))
                .credentialsProvider(credentials(props))
                .region(Region.of(props.s3().region()))
                .serviceConfiguration(PATH_STYLE)
                .build();
    }
}
