package com.learnassist.api.web;

import com.learnassist.api.domain.User;
import com.learnassist.api.security.CurrentUser;
import com.learnassist.api.service.ConversationService;
import com.learnassist.api.web.dto.Dtos;
import jakarta.validation.Valid;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/conversations")
public class ConversationController {

    private final ConversationService conversations;
    private final DocumentViews views;

    public ConversationController(ConversationService conversations, DocumentViews views) {
        this.conversations = conversations;
        this.views = views;
    }

    @GetMapping
    public List<Dtos.ConversationSummaryResponse> list() {
        User user = CurrentUser.require();
        return conversations.list(user).stream()
                .map(Dtos.ConversationSummaryResponse::from)
                .toList();
    }

    @PostMapping
    public ResponseEntity<Dtos.ConversationResponse> create(
            @Valid @RequestBody(required = false) Dtos.CreateConversationRequest request) {
        User user = CurrentUser.require();
        var created = conversations.create(user, request == null ? null : request.title());
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(render(conversations.view(user, created.getId())));
    }

    @GetMapping("/{id}")
    public Dtos.ConversationResponse get(@PathVariable UUID id) {
        User user = CurrentUser.require();
        return render(conversations.view(user, id));
    }

    @PatchMapping("/{id}")
    public Dtos.ConversationSummaryResponse rename(@PathVariable UUID id,
            @Valid @RequestBody Dtos.RenameConversationRequest request) {
        User user = CurrentUser.require();
        return Dtos.ConversationSummaryResponse.from(
                conversations.rename(user, id, request.title()));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable UUID id) {
        User user = CurrentUser.require();
        conversations.delete(user, id);
        return ResponseEntity.noContent().build();
    }

    /** Attach a document already in the library, without re-ingesting it. */
    @PostMapping("/{id}/documents")
    public List<Dtos.DocumentResponse> attach(@PathVariable UUID id,
            @Valid @RequestBody Dtos.AttachDocumentRequest request) {
        User user = CurrentUser.require();
        return conversations.attach(user, id, request.documentId()).documents().stream()
                .map(views::of)
                .toList();
    }

    @DeleteMapping("/{id}/documents/{documentId}")
    public ResponseEntity<Void> detach(@PathVariable UUID id, @PathVariable UUID documentId) {
        User user = CurrentUser.require();
        conversations.detach(user, id, documentId);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{id}/messages")
    public Dtos.ChatMessageResponse ask(@PathVariable UUID id,
            @Valid @RequestBody Dtos.AskRequest request) {
        User user = CurrentUser.require();
        return Dtos.ChatMessageResponse.from(conversations.ask(user, id, request.question()));
    }

    private Dtos.ConversationResponse render(ConversationService.ConversationView view) {
        var conversation = view.conversation();
        return new Dtos.ConversationResponse(
                conversation.getId(),
                conversation.getTitle(),
                conversation.getCreatedAt(),
                conversation.getUpdatedAt(),
                view.documents().stream().map(views::of).toList(),
                view.messages().stream().map(Dtos.ChatMessageResponse::from).toList());
    }
}
