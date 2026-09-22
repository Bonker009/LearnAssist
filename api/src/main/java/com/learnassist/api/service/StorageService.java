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
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;
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
     * Presign a GET so the browser can display the original file.
     *
     * <p>Needed for citation navigation: a "Page 4" chip is only useful if the reader can
     * actually be taken to page 4 of the source document.
     */
    public String presignDownload(String storageKey) {
        GetObjectRequest get = GetObjectRequest.builder()
                .bucket(props.s3().bucket())
                .key(storageKey)
                .build();

        return presigner.presignGetObject(GetObjectPresignRequest.builder()
                        .signatureDuration(props.s3().presignExpiry())
                        .getObjectRequest(get)
                        .build())
                .url()
                .toString();
    }

    /**
     * As {@link #presignDownload(String)}, but the browser saves the file as
     * {@code downloadName} instead of opening it or naming it after the storage key.
     */
    public String presignDownload(String storageKey, String downloadName) {
        GetObjectRequest get = GetObjectRequest.builder()
                .bucket(props.s3().bucket())
                .key(storageKey)
                .responseContentDisposition("attachment; filename=\"" + downloadName + "\"")
                .build();

        return presigner.presignGetObject(GetObjectPresignRequest.builder()
                        .signatureDuration(props.s3().presignExpiry())
                        .getObjectRequest(get)
                        .build())
                .url()
                .toString();
    }

    /**
     * Open an object for streaming, or empty if it does not exist. The caller must close it.
     *
     * <p>For the built slide sites, whose files are small but many: presigning each asset is
     * not possible, because the built HTML references them by fixed paths.
     */
    public java.util.Optional<software.amazon.awssdk.core.ResponseInputStream<
            software.amazon.awssdk.services.s3.model.GetObjectResponse>> openObject(
            String storageKey) {
        try {
            return java.util.Optional.of(client.getObject(GetObjectRequest.builder()
                    .bucket(props.s3().bucket())
                    .key(storageKey)
                    .build()));
        } catch (S3Exception e) {
            return java.util.Optional.empty();
        }
    }

    /**
     * Read a small object whole, or empty if it does not exist.
     *
     * <p>Only for derived artefacts measured in kilobytes (the reader snapshot). Lecture files are
     * always served by presigned URL so they never pass through the JVM.
     */
    public java.util.Optional<byte[]> readSmallObject(String storageKey) {
        try {
            return java.util.Optional.of(client.getObjectAsBytes(GetObjectRequest.builder()
                    .bucket(props.s3().bucket())
                    .key(storageKey)
                    .build()).asByteArray());
        } catch (S3Exception e) {
            return java.util.Optional.empty();
        }
    }

    /**
     * Key of the text snapshot the AI service writes beside a document.
     *
     * <p>Must match {@code reader_key} in the AI service's ingest module.
     */
    public static String readerKey(String storageKey) {
        return storageKey + ".reader.json";
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
