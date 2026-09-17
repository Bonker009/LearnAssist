package com.learnassist.api.service;

import com.learnassist.api.config.AppProperties;
import com.learnassist.api.domain.DocType;
import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.DocumentStatus;
import com.learnassist.api.domain.IngestJob;
import com.learnassist.api.domain.Summary;
import com.learnassist.api.domain.User;
import com.learnassist.api.repository.DocumentRepository;
import com.learnassist.api.repository.IngestJobRepository;
import com.learnassist.api.repository.SummaryRepository;
import com.learnassist.api.web.ApiException;
import java.net.URI;
import java.net.URISyntaxException;
import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DocumentService {

    private final DocumentRepository documents;
    private final IngestJobRepository jobs;
    private final SummaryRepository summaries;
    private final StorageService storage;
    private final AiClient ai;
    private final RateLimiter rateLimiter;
    private final AppProperties props;

    /** Ingest is minutes of CPU per call, so the budget is deliberately small. */
    private static final String INGEST_BUCKET = "ingest";
    private static final int INGEST_LIMIT = 10;
    private static final Duration INGEST_WINDOW = Duration.ofHours(1);

    /**
     * Hosts treated as YouTube. Must stay in step with {@code YOUTUBE_HOSTS} in the AI service,
     * which re-validates: this check only decides which pipeline a link goes to.
     */
    private static final Set<String> YOUTUBE_HOSTS = Set.of(
            "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be");

    public DocumentService(DocumentRepository documents, IngestJobRepository jobs,
            SummaryRepository summaries, StorageService storage, AiClient ai,
            RateLimiter rateLimiter, AppProperties props) {
        this.documents = documents;
        this.jobs = jobs;
        this.summaries = summaries;
        this.storage = storage;
        this.ai = ai;
        this.rateLimiter = rateLimiter;
        this.props = props;
    }

    public record UploadTicket(Document document, String uploadUrl) {}

    /**
     * Step 1 of upload: record the document and hand back a presigned PUT.
     *
     * <p>The row is created in {@code PENDING_UPLOAD} before any bytes exist, so an abandoned
     * upload is visible and can be cleaned up rather than vanishing silently.
     */
    @Transactional
    public UploadTicket createUpload(User owner, String filename, String contentType,
            long declaredSize) {

        if (declaredSize > props.s3().maxUploadBytes()) {
            throw new ApiException(HttpStatus.PAYLOAD_TOO_LARGE,
                    "File exceeds the %d MB limit".formatted(
                            props.s3().maxUploadBytes() / (1024 * 1024)));
        }
        DocType docType = DocType.fromContentType(contentType);
        String key = storage.newStorageKey(owner.getId(), filename);

        Document document = documents.save(
                new Document(owner, filename, contentType, docType, key));
        return new UploadTicket(document, storage.presignUpload(key, contentType));
    }

    /**
     * Step 2: confirm the bytes landed, then queue ingestion.
     *
     * <p>The size is read back from storage rather than trusted from the client — the browser
     * uploads directly, so a client-reported size proves nothing.
     */
    @Transactional
    public Document confirmUploadAndIngest(User owner, UUID documentId) {
        Document document = requireOwned(owner, documentId);
        if (document.getSourceUrl() != null) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "Links are ingested when added");
        }

        long size = storage.uploadedSize(document.getStorageKey())
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST,
                        "No uploaded file found for this document"));
        document.setSizeBytes(size);

        queueIngest(owner, document);
        return document;
    }

    /**
     * Add a web page or YouTube video by URL and queue its ingestion.
     *
     * <p>Only the shape of the URL is checked here. Whether it is safe to fetch — that it does not
     * resolve to a private address inside the compose network — is decided by the AI service at
     * fetch time, because that is the only place the resolved address is actually known.
     */
    @Transactional
    public Document addLink(User owner, String rawUrl) {
        URI uri = parseLink(rawUrl);
        String host = uri.getHost().toLowerCase(Locale.ROOT);
        String url = uri.toString();

        Document document;
        if (YOUTUBE_HOSTS.contains(host)) {
            document = Document.fromLink(owner, url, "video/x-youtube", DocType.YOUTUBE, null);
        } else {
            // The fetched HTML is kept as a snapshot, so the page can be cited as it
            // was when it was read, not as it is after the author edits it.
            String key = storage.newStorageKey(owner.getId(), "page.html");
            document = Document.fromLink(owner, url, "text/html", DocType.WEB, key);
        }
        document = documents.save(document);
        queueIngest(owner, document);
        return document;
    }

    private static URI parseLink(String rawUrl) {
        String trimmed = rawUrl == null ? "" : rawUrl.strip();
        // Pasting "example.com/page" without a scheme is the common case, not an error.
        if (!trimmed.contains("://")) {
            trimmed = "https://" + trimmed;
        }
        try {
            URI uri = new URI(trimmed);
            String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.ROOT);
            if (!scheme.equals("http") && !scheme.equals("https")) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "Only http and https links work");
            }
            if (uri.getHost() == null || !uri.getHost().contains(".")) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "That doesn't look like a web link");
            }
            if (uri.getUserInfo() != null) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "Links with a username aren't supported");
            }
            return uri;
        } catch (URISyntaxException e) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "That doesn't look like a web link");
        }
    }

    private void queueIngest(User owner, Document document) {
        if (!rateLimiter.tryAcquire(INGEST_BUCKET, owner.getId(), INGEST_LIMIT, INGEST_WINDOW)) {
            long retryAfter =
                    rateLimiter.retryAfterSeconds(INGEST_BUCKET, owner.getId(), INGEST_WINDOW);
            throw new ApiException(HttpStatus.TOO_MANY_REQUESTS,
                    "You have added %d resources in the last hour. Try again in %d minute(s)."
                            .formatted(INGEST_LIMIT, Math.max(retryAfter / 60, 1)));
        }
        rateLimiter.evictExpired(INGEST_WINDOW);

        jobs.findByDocumentId(document.getId()).ifPresentOrElse(
                existing -> {
                    throw new ApiException(HttpStatus.CONFLICT,
                            "This document is already being processed");
                },
                () -> jobs.save(new IngestJob(document)));

        document.setStatus(DocumentStatus.PROCESSING);
        ai.startIngest(new AiClient.IngestRequest(document.getId(), document.getStorageKey(),
                document.getFilename(), document.getContentType(), document.getDocType().name(),
                document.getSourceUrl()));
    }

    @Transactional(readOnly = true)
    public List<Document> listForOwner(User owner) {
        return documents.findByOwnerIdOrderByCreatedAtDesc(owner.getId());
    }

    @Transactional(readOnly = true)
    public Document requireOwned(User owner, UUID documentId) {
        // Resolved through the owner, never fetched-then-compared: an unauthorised
        // request finds nothing rather than relying on a check a caller might omit.
        return documents.findByIdAndOwnerId(documentId, owner.getId())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Document not found"));
    }

    public String downloadUrl(Document document) {
        if (document.getStorageKey() == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "This resource has no stored file");
        }
        return storage.presignDownload(document.getStorageKey());
    }

    /**
     * The extracted text of a document, section by section, for the in-app reader.
     *
     * <p>Word, PowerPoint, web pages, notes and images have no native browser viewer that can
     * jump to "Section 3". The snapshot lets a citation to one still land on the cited text.
     */
    public Optional<byte[]> readerSnapshot(Document document) {
        if (document.getStorageKey() == null) {
            return Optional.empty();
        }
        return storage.readSmallObject(StorageService.readerKey(document.getStorageKey()));
    }

    @Transactional(readOnly = true)
    public Optional<IngestJob> job(UUID documentId) {
        return jobs.findByDocumentId(documentId);
    }

    @Transactional(readOnly = true)
    public Optional<Summary> summary(UUID documentId) {
        return summaries.findByDocumentId(documentId);
    }
}
