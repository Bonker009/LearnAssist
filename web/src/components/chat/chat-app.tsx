"use client";

import { IconLayoutSidebar, IconPaperclip } from "@tabler/icons-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { AiOrb, AiWaves, type OrbState } from "@/components/ai-orb";
import { useAuth } from "@/components/auth-provider";
import { SidebarDrawer } from "@/components/sidebar-drawer";
import type { NavigateHandler } from "@/components/citation";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type {
  ChatMessage,
  ConversationSummary,
  LectureDocument,
  SourceRef,
  SpeechLanguage,
} from "@/lib/types";
import { hasKhmer } from "@/lib/utils";
import { ChatSidebar } from "./chat-sidebar";
import { Composer, type PendingUpload } from "./composer";
import { LibraryDialog } from "./library-dialog";
import { MessageList } from "./message-list";
import { ResourcePanel, type ResourcePanelHandle } from "./resource-panel";

const SUGGESTIONS = [
  "Summarise the key ideas",
  "Quiz me on the main concepts",
  "សូមពន្យល់ចំណុចសំខាន់ៗជាភាសាខ្មែរ",
];

/**
 * The whole chat screen: sidebar of chats, the conversation, and the resource panel.
 *
 * Switching chats updates the URL with the History API rather than a router
 * navigation. A navigation would remount this tree and drop in-flight uploads and
 * a recording in progress; Next.js keeps `useParams` in sync with pushState, so
 * reloads and shared links still land on the right chat.
 */
export function ChatApp({ initialConversationId }: { initialConversationId?: string }) {
  const { user, ready } = useAuth();
  const router = useRouter();

  const [conversationId, setConversationId] = React.useState<string | null>(
    initialConversationId ?? null,
  );
  const [conversations, setConversations] = React.useState<ConversationSummary[] | null>(null);
  const [title, setTitle] = React.useState<string>("");
  const [documents, setDocuments] = React.useState<LectureDocument[]>([]);
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [uploads, setUploads] = React.useState<PendingUpload[]>([]);
  const [loadingChat, setLoadingChat] = React.useState(Boolean(initialConversationId));
  const [sending, setSending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const [panelOpen, setPanelOpen] = React.useState(false);
  const [libraryOpen, setLibraryOpen] = React.useState(false);
  const [voiceState, setVoiceState] = React.useState<OrbState>("idle");
  const voiceLevel = React.useRef(0);
  const panel = React.useRef<ResourcePanelHandle>(null);

  // Creating a chat is shared by several actions that can race (drop two files at
  // once); one promise makes them all attach to the same new chat.
  const creating = React.useRef<Promise<string> | null>(null);
  const activeId = React.useRef<string | null>(conversationId);
  activeId.current = conversationId;

  React.useEffect(() => {
    if (ready && !user) router.replace("/sign-in");
  }, [ready, user, router]);

  const refreshList = React.useCallback(async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
      // The server names a chat from its first question; adopt its title.
      const active = list.find((c) => c.id === activeId.current);
      if (active) setTitle(active.title);
    } catch {
      setConversations((current) => current ?? []);
    }
  }, []);

  React.useEffect(() => {
    if (user) void refreshList();
  }, [user, refreshList]);

  const loadConversation = React.useCallback(async (id: string) => {
    setLoadingChat(true);
    setError(null);
    try {
      const conversation = await api.getConversation(id);
      if (activeId.current !== id) return;
      setTitle(conversation.title);
      setDocuments(conversation.documents);
      setMessages(conversation.messages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load this chat");
      setDocuments([]);
      setMessages([]);
    } finally {
      if (activeId.current === id) setLoadingChat(false);
    }
  }, []);

  React.useEffect(() => {
    if (user && initialConversationId) void loadConversation(initialConversationId);
  }, [user, initialConversationId, loadConversation]);

  const selectConversation = React.useCallback(
    (id: string | null) => {
      if (id === activeId.current) return;
      setConversationId(id);
      activeId.current = id;
      setUploads([]);
      setError(null);
      setSidebarOpen(false);
      window.history.pushState(null, "", id ? `/c/${id}` : "/");
      if (id) {
        void loadConversation(id);
      } else {
        setTitle("");
        setDocuments([]);
        setMessages([]);
        setLoadingChat(false);
      }
    },
    [loadConversation],
  );

  // Back/forward buttons.
  React.useEffect(() => {
    const onPop = () => {
      const match = window.location.pathname.match(/^\/c\/([^/]+)/);
      const id = match?.[1] ?? null;
      if (id === activeId.current) return;
      setConversationId(id);
      activeId.current = id;
      if (id) void loadConversation(id);
      else {
        setDocuments([]);
        setMessages([]);
        setTitle("");
      }
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [loadConversation]);

  const ensureConversation = React.useCallback(async (): Promise<string> => {
    if (activeId.current) return activeId.current;
    if (!creating.current) {
      creating.current = api
        .createConversation()
        .then((conversation) => {
          setConversationId(conversation.id);
          activeId.current = conversation.id;
          setTitle(conversation.title);
          // replaceState: the empty "/" screen was a draft of this chat, so Back
          // should not return to it.
          window.history.replaceState(null, "", `/c/${conversation.id}`);
          void refreshList();
          return conversation.id;
        })
        .finally(() => {
          creating.current = null;
        });
    }
    return creating.current;
  }, [refreshList]);

  // Poll while anything is processing, so progress moves and "ready" appears
  // without a reload. Idle chats are not polled.
  const processing = documents.some((d) => d.status === "PROCESSING" || d.status === "UPLOADED");
  React.useEffect(() => {
    if (!processing || !conversationId) return;
    const id = conversationId;
    const timer = window.setInterval(async () => {
      try {
        const conversation = await api.getConversation(id);
        if (activeId.current === id) setDocuments(conversation.documents);
      } catch {
        /* transient; the next tick retries */
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [processing, conversationId]);

  const addDocument = React.useCallback((document: LectureDocument) => {
    setDocuments((previous) =>
      previous.some((d) => d.id === document.id)
        ? previous.map((d) => (d.id === document.id ? document : d))
        : [...previous, document],
    );
  }, []);

  const attachFiles = React.useCallback(
    async (files: File[]) => {
      setError(null);
      let id: string;
      try {
        id = await ensureConversation();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not start a chat");
        return;
      }

      await Promise.all(
        files.map(async (file) => {
          const uploadId = `${file.name}-${crypto.randomUUID()}`;
          setUploads((previous) => [...previous, { id: uploadId, name: file.name, progress: 0 }]);
          try {
            const document = await api.upload(file, {
              conversationId: id,
              onProgress: (progress) =>
                setUploads((previous) =>
                  previous.map((u) => (u.id === uploadId ? { ...u, progress } : u)),
                ),
            });
            setUploads((previous) => previous.filter((u) => u.id !== uploadId));
            if (activeId.current === id) addDocument(document);
          } catch (err) {
            setUploads((previous) =>
              previous.map((u) =>
                u.id === uploadId
                  ? { ...u, error: err instanceof Error ? err.message : "Upload failed" }
                  : u,
              ),
            );
          }
        }),
      );
    },
    [ensureConversation, addDocument],
  );

  const addLink = React.useCallback(
    async (url: string) => {
      const id = await ensureConversation();
      addDocument(await api.addLink(url, id));
    },
    [ensureConversation, addDocument],
  );

  const addNote = React.useCallback(
    async (noteTitle: string, text: string) => {
      const id = await ensureConversation();
      addDocument(await api.uploadNote(noteTitle, text, id));
    },
    [ensureConversation, addDocument],
  );

  const attachFromLibrary = React.useCallback(
    async (documentIds: string[]) => {
      const id = await ensureConversation();
      let latest: LectureDocument[] = [];
      for (const documentId of documentIds) {
        latest = await api.attachDocument(id, documentId);
      }
      if (activeId.current === id) setDocuments(latest);
    },
    [ensureConversation],
  );

  const removeDocument = React.useCallback(async (documentId: string) => {
    const id = activeId.current;
    if (!id) return;
    const previous = documents;
    setDocuments((current) => current.filter((d) => d.id !== documentId));
    try {
      await api.detachDocument(id, documentId);
    } catch (err) {
      setDocuments(previous);
      setError(err instanceof Error ? err.message : "Couldn't remove that resource");
    }
  }, [documents]);

  const send = React.useCallback(
    async (text: string) => {
      const id = activeId.current;
      if (!id || sending) return;
      setError(null);
      setSending(true);

      // Show the student's own turn immediately; waiting for a slow local model
      // before echoing their question makes the app feel broken.
      setMessages((previous) => [
        ...previous,
        {
          id: `pending-${Date.now()}`,
          role: "USER",
          content: text,
          citations: [],
          createdAt: new Date().toISOString(),
        },
      ]);

      try {
        const answer = await api.sendMessage(id, text);
        if (activeId.current === id) setMessages((previous) => [...previous, answer]);
        // The first question names the chat; pick up the new title and ordering.
        void refreshList();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not get an answer");
      } finally {
        setSending(false);
      }
    },
    [sending, refreshList],
  );

  const transcribe = React.useCallback(async (clip: Blob, language: SpeechLanguage) => {
    return (await api.transcribe(clip, language)).text;
  }, []);

  const navigate: NavigateHandler = React.useCallback(
    (source: SourceRef, documentId?: string | null) => {
      const target = documentId ?? (documents.length === 1 ? documents[0].id : null);
      if (!target) return;
      setPanelOpen(true);
      // The panel may be mounting in this same render; defer to the next frame.
      requestAnimationFrame(() => panel.current?.show(target, source));
    },
    [documents],
  );

  const openDocument = React.useCallback((documentId: string) => {
    setPanelOpen(true);
    requestAnimationFrame(() => panel.current?.show(documentId));
  }, []);

  async function renameConversation(id: string, next: string) {
    setConversations((list) => list?.map((c) => (c.id === id ? { ...c, title: next } : c)) ?? null);
    if (id === activeId.current) setTitle(next);
    try {
      await api.renameConversation(id, next);
    } catch {
      void refreshList();
    }
  }

  async function deleteConversation(id: string) {
    setConversations((list) => list?.filter((c) => c.id !== id) ?? null);
    if (id === activeId.current) selectConversation(null);
    try {
      await api.deleteConversation(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't delete that chat");
      void refreshList();
    }
  }

  const documentNames = React.useMemo(
    () => new Map(documents.map((d) => [d.id, d.filename])),
    [documents],
  );

  if (!ready || !user) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <p className="text-sm text-text-muted">Loading…</p>
      </div>
    );
  }

  const empty = !loadingChat && messages.length === 0;

  const composer = (
    <Composer
      variant={empty ? "hero" : "docked"}
      documents={documents}
      uploads={uploads}
      sending={sending}
      onSend={send}
      onAttachFiles={attachFiles}
      onAddLink={addLink}
      onAddNote={addNote}
      onOpenLibrary={() => setLibraryOpen(true)}
      onOpenDocument={openDocument}
      onRemoveDocument={removeDocument}
      onDismissUpload={(uploadId) => setUploads((u) => u.filter((x) => x.id !== uploadId))}
      onTranscribe={transcribe}
      voiceLevelRef={voiceLevel}
      onVoiceStateChange={setVoiceState}
    />
  );

  // The orb listens while the student speaks and thinks while anything is working.
  const orbState: OrbState =
    voiceState === "listening" ? "listening" : voiceState === "thinking" || sending ? "thinking" : "idle";

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <a
        href="#chat-main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2"
      >
        Skip to chat
      </a>

      <SidebarDrawer open={sidebarOpen} onClose={() => setSidebarOpen(false)}>
        <ChatSidebar
          conversations={conversations}
          activeId={conversationId}
          onSelect={selectConversation}
          onNew={() => selectConversation(null)}
          onRename={renameConversation}
          onDelete={deleteConversation}
        />
      </SidebarDrawer>

      <main id="chat-main" className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 px-3">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open chats"
            onClick={() => setSidebarOpen(true)}
          >
            <IconLayoutSidebar size={18} />
          </Button>
          <h1
            className="min-w-0 flex-1 truncate text-sm font-medium"
            lang={hasKhmer(title) ? "km" : undefined}
          >
            {conversationId ? title : ""}
          </h1>
          {documents.length > 0 && (
            <Button
              variant={panelOpen ? "secondary" : "ghost"}
              size="sm"
              onClick={() => setPanelOpen((open) => !open)}
              aria-expanded={panelOpen}
            >
              <IconPaperclip size={15} />
              {documents.length} {documents.length === 1 ? "resource" : "resources"}
            </Button>
          )}
        </header>

        {empty ? (
          <div className="relative flex flex-1 flex-col items-center justify-center overflow-y-auto px-4 pb-16">
            <AiWaves
              state={orbState}
              levelRef={voiceLevel}
              className="absolute inset-x-0 bottom-0 h-32 sm:h-40"
            />
            <div className="relative flex w-full max-w-2xl flex-col gap-6">
              <AiOrb
                state={orbState}
                levelRef={voiceLevel}
                className="mx-auto size-28 sm:size-32"
              />
              <div className="-mt-2 text-center">
                {/* Bilingual title: Khmer display line, English subtitle in the accent. */}
                <h2 lang="km" className="font-display-km text-balance text-2xl text-foreground">
                  តើថ្ងៃនេះអ្នករៀនអ្វី?
                </h2>
                <p className="text-base font-semibold text-emphasis">
                  What are you studying today?
                </p>
              </div>
              {composer}
              {error && (
                <p role="alert" className="text-center text-sm text-danger">
                  {error}
                </p>
              )}
              {documents.some((d) => d.status === "READY") && (
                <div className="flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <Button
                      key={suggestion}
                      variant="outline"
                      size="sm"
                      lang={hasKhmer(suggestion) ? "km" : undefined}
                      onClick={() => void send(suggestion)}
                    >
                      {suggestion}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {loadingChat ? (
                <p className="p-8 text-center text-sm text-text-muted">Loading chat…</p>
              ) : (
                <MessageList
                  messages={messages}
                  thinking={sending}
                  documentNames={documentNames}
                  onNavigate={navigate}
                />
              )}
            </div>
            <div className="mx-auto w-full max-w-3xl px-4 pb-4">
              {error && (
                <p role="alert" className="mb-2 px-3 text-sm text-danger">
                  {error}
                </p>
              )}
              {composer}
            </div>
          </>
        )}
      </main>

      {panelOpen && (
        <>
          <button
            type="button"
            aria-label="Close resources"
            className="fixed inset-0 z-30 bg-black/30 lg:hidden"
            onClick={() => setPanelOpen(false)}
          />
          <div className="fixed inset-y-0 right-0 z-40 w-full max-w-md border-l border-border lg:static lg:z-auto lg:w-[28rem] lg:max-w-none">
            <ResourcePanel ref={panel} documents={documents} onClose={() => setPanelOpen(false)} />
          </div>
        </>
      )}

      <LibraryDialog
        open={libraryOpen}
        onOpenChange={setLibraryOpen}
        attachedIds={new Set(documents.map((d) => d.id))}
        onAttach={attachFromLibrary}
      />
    </div>
  );
}
