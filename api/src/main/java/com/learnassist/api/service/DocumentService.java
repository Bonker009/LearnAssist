package com.learnassist.api.service;

import com.learnassist.api.config.AppProperties;
import com.learnassist.api.domain.ChatMessage;
import com.learnassist.api.domain.DocType;
import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.DocumentStatus;
import com.learnassist.api.domain.IngestJob;
import com.learnassist.api.domain.Summary;
import com.learnassist.api.domain.User;
import com.learnassist.api.repository.ChatMessageRepository;
import com.learnassist.api.repository.DocumentRepository;
import com.learnassist.api.repository.IngestJobRepository;
import com.learnassist.api.repository.SummaryRepository;
import com.learnassist.api.web.ApiException;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class DocumentService {

    private final DocumentRepository documents;
    private final IngestJobRepository jobs;
    private final SummaryRepository summaries;
    private final ChatMessageRepository chats;
    private final StorageService storage;
    private final AiClient ai;
    private final AppProperties props;

    public DocumentService(DocumentRepository documents, IngestJobRepository jobs,
            SummaryRepository summaries, ChatMessageRepository chats, StorageService storage,
            AiClient ai, AppProperties props) {
        this.documents = documents;
        this.jobs = jobs;
        this.summaries = summaries;
        this.chats = chats;
        this.storage = storage;
        this.ai = ai;
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

        long size = storage.uploadedSize(document.getStorageKey())
                .orElseThrow(() -> new ApiException(HttpStatus.BAD_REQUEST,
                        "No uploaded file found for this document"));

        document.setSizeBytes(size);
        document.setStatus(DocumentStatus.PROCESSING);

        jobs.findByDocumentId(documentId).ifPresentOrElse(
                existing -> {
                    throw new ApiException(HttpStatus.CONFLICT,
                            "This document is already being processed");
                },
                () -> jobs.save(new IngestJob(document)));

        ai.startIngest(new AiClient.IngestRequest(document.getId(), document.getStorageKey(),
                document.getFilename(), document.getContentType()));
        return document;
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

    @Transactional(readOnly = true)
    public Optional<IngestJob> job(UUID documentId) {
        return jobs.findByDocumentId(documentId);
    }

    @Transactional(readOnly = true)
    public Optional<Summary> summary(UUID documentId) {
        return summaries.findByDocumentId(documentId);
    }

    @Transactional(readOnly = true)
    public List<ChatMessage> history(UUID documentId) {
        return chats.findByDocumentIdOrderByCreatedAtAsc(documentId);
    }

    /** Ask a question about a document and persist both turns of the exchange. */
    @Transactional
    public ChatMessage ask(User owner, UUID documentId, String question) {
        Document document = requireOwned(owner, documentId);
        if (document.getStatus() != DocumentStatus.READY) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "This document is still being processed");
        }

        chats.save(new ChatMessage(document, owner, ChatMessage.Role.USER, question, List.of()));

        AiClient.QueryResponse response =
                ai.query(new AiClient.QueryRequest(documentId, question));

        return chats.save(new ChatMessage(document, owner, ChatMessage.Role.ASSISTANT,
                response.answer(), response.citations()));
    }
}
