package com.learnassist.api.web;

import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.User;
import com.learnassist.api.security.CurrentUser;
import com.learnassist.api.service.DocumentService;
import com.learnassist.api.web.dto.Dtos;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
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

    public DocumentController(DocumentService documents) {
        this.documents = documents;
    }

    /** Step 1: reserve a document row and get a presigned upload URL. */
    @PostMapping
    public ResponseEntity<Dtos.CreateUploadResponse> createUpload(
            @Valid @RequestBody Dtos.CreateUploadRequest request) {
        User user = CurrentUser.require();
        var ticket = documents.createUpload(user, request.filename(), request.contentType(),
                request.sizeBytes());
        return ResponseEntity.status(HttpStatus.CREATED).body(new Dtos.CreateUploadResponse(
                ticket.document().getId(), ticket.uploadUrl(), ticket.document().getStorageKey()));
    }

    /** Step 2: the browser has finished the PUT; verify and start ingestion. */
    @PostMapping("/{id}/ingest")
    public Dtos.DocumentResponse ingest(@PathVariable UUID id) {
        User user = CurrentUser.require();
        Document document = documents.confirmUploadAndIngest(user, id);
        return detail(document);
    }

    @GetMapping
    public List<Dtos.DocumentResponse> list() {
        User user = CurrentUser.require();
        return documents.listForOwner(user).stream().map(this::detail).toList();
    }

    @GetMapping("/{id}")
    public Dtos.DocumentResponse get(@PathVariable UUID id) {
        User user = CurrentUser.require();
        return detail(documents.requireOwned(user, id));
    }

    /** Presigned URL for the original file, so the viewer can show the cited page. */
    @GetMapping("/{id}/file")
    public java.util.Map<String, String> fileUrl(@PathVariable UUID id) {
        User user = CurrentUser.require();
        Document document = documents.requireOwned(user, id);
        return java.util.Map.of("url", documents.downloadUrl(document));
    }

    @GetMapping("/{id}/messages")
    public List<Dtos.ChatMessageResponse> messages(@PathVariable UUID id) {
        User user = CurrentUser.require();
        documents.requireOwned(user, id);
        return documents.history(id).stream().map(Dtos.ChatMessageResponse::from).toList();
    }

    @PostMapping("/{id}/chat")
    public Dtos.ChatMessageResponse ask(@PathVariable UUID id,
            @Valid @RequestBody Dtos.AskRequest request) {
        User user = CurrentUser.require();
        return Dtos.ChatMessageResponse.from(documents.ask(user, id, request.question()));
    }

    private Dtos.DocumentResponse detail(Document document) {
        return Dtos.DocumentResponse.from(
                document,
                documents.job(document.getId()).orElse(null),
                documents.summary(document.getId()).orElse(null));
    }
}
