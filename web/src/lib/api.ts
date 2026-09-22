"use client";

import type {
  AuthResponse,
  ChatMessage,
  Conversation,
  Dashboard,
  ConversationSummary,
  FlashcardDeck,
  Grade,
  LectureDocument,
  Quiz,
  ReaderSnapshot,
  SlideDeck,
  SpeechLanguage,
  Transcript,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8081";
const TOKEN_KEY = "learnassist.token";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    // Private-window or blocked storage: treat as signed out rather than crashing.
    return null;
  }
}

export function setToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* non-fatal */
  }
}

async function parseError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  try {
    const body = await response.json();
    if (body?.message) message = body.message;
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(response.status, message);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const isForm = init.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        // A FormData body must set its own multipart boundary header.
        ...(isForm ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    // fetch only rejects when no response arrived at all: the server is down,
    // unreachable, or refused the CORS preflight. The browser's own message
    // ("Failed to fetch") says none of that.
    throw new ApiError(
      0,
      `Can't reach the LearnAssist server at ${BASE_URL}. Check that it is running (docker compose up -d).`,
    );
  }

  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function orNullOn404<T>(pending: Promise<T>): Promise<T | null> {
  try {
    return await pending;
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/** Absolute URL of a path on the API, for things the browser loads itself (iframes). */
export function apiUrl(path: string): string {
  return `${BASE_URL}${path}`;
}

/**
 * Browsers report an empty type for many files (.md almost always), and the API
 * rejects an unknown type. Fill it in from the extension rather than failing an
 * upload the pipeline can actually read.
 */
export function contentTypeOf(file: File): string {
  if (file.type) return file.type;
  const extension = file.name.split(".").pop()?.toLowerCase();
  const byExtension: Record<string, string> = {
    md: "text/markdown",
    markdown: "text/markdown",
    txt: "text/plain",
    pdf: "application/pdf",
    pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    m4a: "audio/mp4",
    webp: "image/webp",
  };
  return (extension && byExtension[extension]) || "application/octet-stream";
}

export const api = {
  register: (email: string, password: string, displayName: string) =>
    request<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, displayName }),
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  // ---------- library ----------

  listDocuments: () => request<LectureDocument[]>("/api/documents"),

  getDocument: (id: string) => request<LectureDocument>(`/api/documents/${id}`),

  getFileUrl: (id: string) =>
    request<{ url: string }>(`/api/documents/${id}/file`),

  getReader: (id: string) => request<ReaderSnapshot>(`/api/documents/${id}/reader`),

  addLink: (url: string, conversationId?: string) =>
    request<LectureDocument>("/api/documents/links", {
      method: "POST",
      body: JSON.stringify({ url, conversationId }),
    }),

  // ---------- quizzes ----------

  generateQuiz: (documentId: string, count = 5) =>
    request<Quiz>(`/api/documents/${documentId}/quiz?count=${count}`, { method: "POST" }),

  getQuiz: (quizId: string) => request<Quiz>(`/api/quizzes/${quizId}`),

  submitQuiz: (quizId: string, answers: Record<string, number>) =>
    request<Grade>(`/api/quizzes/${quizId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  // ---------- flashcards ----------

  generateFlashcards: (documentId: string, count = 10) =>
    request<FlashcardDeck>(`/api/documents/${documentId}/flashcards?count=${count}`, {
      method: "POST",
    }),

  /** Resolves to null when the document has no deck yet. */
  latestFlashcards: (documentId: string) =>
    orNullOn404(request<FlashcardDeck>(`/api/documents/${documentId}/flashcards/latest`)),

  reviewFlashcard: (cardId: string, known: boolean) =>
    request<void>(`/api/flashcards/${cardId}/review`, {
      method: "POST",
      body: JSON.stringify({ known }),
    }),

  // ---------- slides ----------

  /** Starts generation; poll `getSlideDeck` until READY or FAILED. */
  generateSlides: (documentId: string, count = 8) =>
    request<SlideDeck>(`/api/documents/${documentId}/slides?count=${count}`, { method: "POST" }),

  getSlideDeck: (deckId: string) => request<SlideDeck>(`/api/slide-decks/${deckId}`),

  latestSlides: (documentId: string) =>
    orNullOn404(request<SlideDeck>(`/api/documents/${documentId}/slides/latest`)),

  // ---------- conversations ----------

  listConversations: () => request<ConversationSummary[]>("/api/conversations"),

  createConversation: (title?: string) =>
    request<Conversation>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),

  getConversation: (id: string) => request<Conversation>(`/api/conversations/${id}`),

  renameConversation: (id: string, title: string) =>
    request<ConversationSummary>(`/api/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),

  deleteConversation: (id: string) =>
    request<void>(`/api/conversations/${id}`, { method: "DELETE" }),

  attachDocument: (conversationId: string, documentId: string) =>
    request<LectureDocument[]>(`/api/conversations/${conversationId}/documents`, {
      method: "POST",
      body: JSON.stringify({ documentId }),
    }),

  detachDocument: (conversationId: string, documentId: string) =>
    request<void>(`/api/conversations/${conversationId}/documents/${documentId}`, {
      method: "DELETE",
    }),

  sendMessage: (conversationId: string, question: string) =>
    request<ChatMessage>(`/api/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  // ---------- dashboard ----------

  getDashboard: () => {
    // Days are bucketed in the viewer's own zone, so "today" means their today.
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    return request<Dashboard>(`/api/dashboard?tz=${encodeURIComponent(tz)}`);
  },

  // ---------- speech ----------

  transcribe: (audio: Blob, language: SpeechLanguage) => {
    const form = new FormData();
    const extension = audio.type.includes("mp4") ? "m4a" : audio.type.includes("ogg") ? "ogg" : "webm";
    form.append("file", audio, `voice.${extension}`);
    form.append("language", language);
    return request<Transcript>("/api/speech/transcribe", { method: "POST", body: form });
  },

  /**
   * Upload in three steps: reserve a row and get a presigned URL, PUT the bytes
   * straight to object storage, then tell the API to start ingestion.
   *
   * The bytes never pass through the API server, which is what makes a 500MB
   * lecture recording viable.
   */
  async upload(
    file: File,
    options: { conversationId?: string; onProgress?: (percent: number) => void } = {},
  ): Promise<LectureDocument> {
    const contentType = contentTypeOf(file);
    const ticket = await request<{ documentId: string; uploadUrl: string }>(
      "/api/documents",
      {
        method: "POST",
        body: JSON.stringify({
          filename: file.name,
          contentType,
          sizeBytes: file.size,
          conversationId: options.conversationId,
        }),
      },
    );

    await new Promise<void>((resolve, reject) => {
      // XHR rather than fetch: fetch still cannot report upload progress, and a
      // multi-hundred-megabyte upload with no progress bar feels broken.
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", ticket.uploadUrl);
      xhr.setRequestHeader("Content-Type", contentType);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && options.onProgress) {
          options.onProgress(Math.round((event.loaded / event.total) * 100));
        }
      };
      xhr.onload = () =>
        xhr.status >= 200 && xhr.status < 300
          ? resolve()
          : reject(new ApiError(xhr.status, "Upload to storage failed"));
      xhr.onerror = () => reject(new ApiError(0, "Upload to storage failed"));
      xhr.send(file);
    });

    return request<LectureDocument>(`/api/documents/${ticket.documentId}/ingest`, {
      method: "POST",
    });
  },

  /** Pasted notes become a Markdown file and go through the normal upload path. */
  uploadNote(title: string, text: string, conversationId?: string) {
    const safe = (title.trim() || "Notes").replace(/[\\/:*?"<>|]+/g, " ").slice(0, 120);
    const file = new File([text], `${safe}.md`, { type: "text/markdown" });
    return api.upload(file, { conversationId });
  },
};

export const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/markdown",
  ".md",
  ".txt",
  "image/png",
  "image/jpeg",
  "image/webp",
  "audio/*",
  "video/*",
].join(",");
