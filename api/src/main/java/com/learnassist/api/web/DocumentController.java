package com.learnassist.api.web;

import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.User;
import com.learnassist.api.security.CurrentUser;
import com.learnassist.api.service.ConversationService;
import com.learnassist.api.service.DocumentService;
import com.learnassist.api.web.dto.Dtos;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {

    private final DocumentService documents;
    private final ConversationService conversations;
    private final DocumentViews views;

    public DocumentController(DocumentService documents, ConversationService conversations,
            DocumentViews views) {
        this.documents = documents;
        this.conversations = conversations;
        this.views = views;
    }

    /** Step 1: reserve a document row and get a presigned upload URL. */
    @PostMapping
    public ResponseEntity<Dtos.CreateUploadResponse> createUpload(
            @Valid @RequestBody Dtos.CreateUploadRequest request) {
        User user = CurrentUser.require();
        // Check the chat first, so a bad id fails before an orphan document row exists.
        if (request.conversationId() != null) {
            conversations.requireOwned(user, request.conversationId());
        }
        var ticket = documents.createUpload(user, request.filename(), request.contentType(),
                request.sizeBytes());
        if (request.conversationId() != null) {
            conversations.attach(user, request.conversationId(), ticket.document().getId());
        }
        return ResponseEntity.status(HttpStatus.CREATED).body(new Dtos.CreateUploadResponse(
                ticket.document().getId(), ticket.uploadUrl(), ticket.document().getStorageKey()));
    }

    /** Step 2: the browser has finished the PUT; verify and start ingestion. */
    @PostMapping("/{id}/ingest")
    public Dtos.DocumentResponse ingest(@PathVariable UUID id) {
        User user = CurrentUser.require();
        return views.of(documents.confirmUploadAndIngest(user, id));
    }

    /** Add a web page or YouTube video by URL. Ingestion starts immediately. */
    @PostMapping("/links")
    public ResponseEntity<Dtos.DocumentResponse> addLink(
            @Valid @RequestBody Dtos.CreateLinkRequest request) {
        User user = CurrentUser.require();
        if (request.conversationId() != null) {
            conversations.requireOwned(user, request.conversationId());
        }
        Document document = documents.addLink(user, request.url());
        if (request.conversationId() != null) {
            conversations.attach(user, request.conversationId(), document.getId());
        }
        return ResponseEntity.status(HttpStatus.CREATED).body(views.of(document));
    }

    @GetMapping
    public List<Dtos.DocumentResponse> list() {
        User user = CurrentUser.require();
        return documents.listForOwner(user).stream().map(views::of).toList();
    }

    @GetMapping("/{id}")
    public Dtos.DocumentResponse get(@PathVariable UUID id) {
        User user = CurrentUser.require();
        return views.of(documents.requireOwned(user, id));
    }

    /** Presigned URL for the original file, so the viewer can show the cited page. */
    @GetMapping("/{id}/file")
    public java.util.Map<String, String> fileUrl(@PathVariable UUID id) {
        User user = CurrentUser.require();
        Document document = documents.requireOwned(user, id);
        return java.util.Map.of("url", documents.downloadUrl(document));
    }

    /**
     * The extracted text, section by section, for resources without a native viewer.
     *
     * <p>Proxied rather than presigned: it is a few kilobytes, and serving it from this origin
     * avoids depending on the object store's CORS configuration for a {@code fetch}.
     */
    @GetMapping(value = "/{id}/reader", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> reader(@PathVariable UUID id) {
        User user = CurrentUser.require();
        Document document = documents.requireOwned(user, id);
        return documents.readerSnapshot(document)
                .map(ResponseEntity::ok)
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND,
                        "No text preview is available for this resource"));
    }
}
