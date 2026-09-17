package com.learnassist.api.service;

import com.learnassist.api.domain.ChatMessage;
import com.learnassist.api.domain.Conversation;
import com.learnassist.api.domain.Document;
import com.learnassist.api.domain.DocumentStatus;
import com.learnassist.api.domain.User;
import com.learnassist.api.repository.ChatMessageRepository;
import com.learnassist.api.repository.ConversationRepository;
import com.learnassist.api.web.ApiException;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ConversationService {

    /**
     * Earlier messages sent with each question. Enough to resolve "what about the second one?",
     * small enough that history never crowds retrieved lecture text out of a local model's context.
     */
    private static final int HISTORY_MESSAGES = 6;
    private static final int TITLE_LENGTH = 60;

    private final ConversationRepository conversations;
    private final ChatMessageRepository messages;
    private final DocumentService documents;
    private final AiClient ai;

    public ConversationService(ConversationRepository conversations,
            ChatMessageRepository messages, DocumentService documents, AiClient ai) {
        this.conversations = conversations;
        this.messages = messages;
        this.documents = documents;
        this.ai = ai;
    }

    /**
     * Everything the chat screen needs, fully loaded.
     *
     * <p>Built inside the transaction because open-in-view is off: handing the entity to a
     * controller and letting it walk the lazy document set would fail after the session closes.
     */
    public record ConversationView(Conversation conversation, List<Document> documents,
            List<ChatMessage> messages) {}

    @Transactional(readOnly = true)
    public List<Conversation> list(User owner) {
        return conversations.findByOwnerIdOrderByUpdatedAtDesc(owner.getId());
    }

    @Transactional
    public Conversation create(User owner, String title) {
        return conversations.save(new Conversation(owner, title));
    }

    @Transactional(readOnly = true)
    public Conversation requireOwned(User owner, UUID conversationId) {
        return conversations.findByIdAndOwnerId(conversationId, owner.getId())
                .orElseThrow(() -> new ApiException(HttpStatus.NOT_FOUND, "Chat not found"));
    }

    @Transactional(readOnly = true)
    public ConversationView view(User owner, UUID conversationId) {
        Conversation conversation = requireOwned(owner, conversationId);
        return new ConversationView(conversation, attached(conversation),
                messages.findByConversationIdOrderByCreatedAtAsc(conversationId));
    }

    @Transactional
    public Conversation rename(User owner, UUID conversationId, String title) {
        Conversation conversation = requireOwned(owner, conversationId);
        conversation.setTitle(title);
        return conversation;
    }

    /** Deletes the chat and its messages. Attached documents stay in the library. */
    @Transactional
    public void delete(User owner, UUID conversationId) {
        conversations.delete(requireOwned(owner, conversationId));
    }

    @Transactional
    public ConversationView attach(User owner, UUID conversationId, UUID documentId) {
        Conversation conversation = requireOwned(owner, conversationId);
        // Both lookups go through the owner: attaching someone else's document id
        // must fail exactly like attaching one that does not exist.
        Document document = documents.requireOwned(owner, documentId);
        conversation.getDocuments().add(document);
        conversation.touch();
        return new ConversationView(conversation, attached(conversation), List.of());
    }

    @Transactional
    public void detach(User owner, UUID conversationId, UUID documentId) {
        Conversation conversation = requireOwned(owner, conversationId);
        conversation.getDocuments().removeIf(d -> d.getId().equals(documentId));
        conversation.touch();
    }

    /** Ask a question across the chat's resources and persist both turns. */
    @Transactional
    public ChatMessage ask(User owner, UUID conversationId, String question) {
        Conversation conversation = requireOwned(owner, conversationId);
        List<Document> attached = attached(conversation);

        if (attached.isEmpty()) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "Add a file, link or note to this chat before asking about it.");
        }
        // Answer from whatever is ready rather than blocking on a recording that is
        // still transcribing; the UI shows which resources are still processing.
        List<AiClient.DocumentRef> ready = attached.stream()
                .filter(d -> d.getStatus() == DocumentStatus.READY)
                .map(d -> new AiClient.DocumentRef(d.getId(), d.getFilename()))
                .toList();
        if (ready.isEmpty()) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "Your resources are still being processed. Try again when one is ready.");
        }

        List<ChatMessage> previous = messages.findByConversationIdOrderByCreatedAtAsc(conversationId);
        List<AiClient.Turn> history = previous
                .subList(Math.max(previous.size() - HISTORY_MESSAGES, 0), previous.size())
                .stream()
                .map(m -> new AiClient.Turn(m.getRole().name(), m.getContent()))
                .toList();

        messages.save(new ChatMessage(conversation, owner, ChatMessage.Role.USER, question,
                List.of()));
        if (conversation.hasDefaultTitle()) {
            conversation.setTitle(titleFrom(question));
        }
        conversation.touch();

        AiClient.QueryResponse response =
                ai.query(new AiClient.QueryRequest(ready, question, history));

        return messages.save(new ChatMessage(conversation, owner, ChatMessage.Role.ASSISTANT,
                response.answer(), response.citations()));
    }

    private static List<Document> attached(Conversation conversation) {
        return conversation.getDocuments().stream()
                .sorted(Comparator.comparing(Document::getCreatedAt))
                .toList();
    }

    static String titleFrom(String question) {
        String collapsed = question.strip().replaceAll("\\s+", " ");
        if (collapsed.length() <= TITLE_LENGTH) {
            return collapsed;
        }
        // Cut on a grapheme boundary: Khmer text is full of combining marks and
        // subscript consonants, and a cut inside a cluster renders as a stray dotted circle.
        java.text.BreakIterator graphemes = java.text.BreakIterator.getCharacterInstance();
        graphemes.setText(collapsed);
        int end = graphemes.isBoundary(TITLE_LENGTH) ? TITLE_LENGTH
                : graphemes.preceding(TITLE_LENGTH);
        String cut = collapsed.substring(0, end);
        int space = cut.lastIndexOf(' ');
        return (space > TITLE_LENGTH / 2 ? cut.substring(0, space) : cut) + "…";
    }
}
