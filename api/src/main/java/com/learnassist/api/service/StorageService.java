package com.learnassist.api.service;

import com.learnassist.api.config.AppProperties;
import java.time.LocalDate;
import java.util.UUID;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.CreateBucketRequest;
import software.amazon.awssdk.services.s3.model.HeadBucketRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectRequest;
import software.amazon.awssdk.services.s3.model.HeadObjectResponse;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.PutObjectPresignRequest;
import jakarta.annotation.PostConstruct;

@Service
public class StorageService {

    private final S3Client client;
    private final S3Presigner presigner;
    private final AppProperties props;

    public StorageService(S3Client client, S3Presigner presigner, AppProperties props) {
        this.client = client;
        this.presigner = presigner;
        this.props = props;
    }

    @PostConstruct
    void ensureBucket() {
        String bucket = props.s3().bucket();
        try {
            client.headBucket(HeadBucketRequest.builder().bucket(bucket).build());
        } catch (S3Exception e) {
            client.createBucket(CreateBucketRequest.builder().bucket(bucket).build());
        }
    }

    /**
     * Build the object key for a new upload.
     *
     * <p>The owner id is the first path segment so a student's objects are contiguous in storage,
     * and the date prefix keeps any single directory listing manageable. The original filename is
     * never used in the key — it is untrusted input and would allow traversal or collisions.
     */
    public String newStorageKey(UUID ownerId, String filename) {
        String extension = "";
        int dot = filename.lastIndexOf('.');
        if (dot > -1 && dot < filename.length() - 1) {
            extension = "." + filename.substring(dot + 1).toLowerCase().replaceAll("[^a-z0-9]", "");
        }
        return "%s/%s/%s%s".formatted(ownerId, LocalDate.now(), UUID.randomUUID(), extension);
    }

    /**
     * Presign a PUT the browser uploads to directly.
     *
     * <p>Signed against the public endpoint (see {@link com.learnassist.api.config.StorageConfig}).
     * Uploading straight to storage keeps multi-hundred-megabyte lecture recordings from streaming
     * through the JVM heap.
     */
    public String presignUpload(String storageKey, String contentType) {
        PutObjectRequest put = PutObjectRequest.builder()
                .bucket(props.s3().bucket())
                .key(storageKey)
                .contentType(contentType)
                .build();

        return presigner.presignPutObject(PutObjectPresignRequest.builder()
                        .signatureDuration(props.s3().presignExpiry())
                        .putObjectRequest(put)
                        .build())
                .url()
                .toString();
    }

    /**
     * @return the uploaded object's size, or empty if the client never completed the PUT
     */
    public java.util.Optional<Long> uploadedSize(String storageKey) {
        try {
            HeadObjectResponse head = client.headObject(HeadObjectRequest.builder()
                    .bucket(props.s3().bucket())
                    .key(storageKey)
                    .build());
            return java.util.Optional.of(head.contentLength());
        } catch (S3Exception e) {
            // NoSuchKeyException is an S3Exception subclass; a 404 here just means the
            // client never completed the PUT, which is an expected state, not an error.
            return java.util.Optional.empty();
        }
    }
}
