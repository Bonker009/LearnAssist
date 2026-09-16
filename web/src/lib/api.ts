"use client";

import type {
  AuthResponse,
  ChatMessage,
  LectureDocument,
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

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.message) message = body.message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
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

  listDocuments: () => request<LectureDocument[]>("/api/documents"),

  getDocument: (id: string) => request<LectureDocument>(`/api/documents/${id}`),

  getFileUrl: (id: string) =>
    request<{ url: string }>(`/api/documents/${id}/file`),

  getMessages: (id: string) => request<ChatMessage[]>(`/api/documents/${id}/messages`),

  ask: (id: string, question: string) =>
    request<ChatMessage>(`/api/documents/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  /**
   * Upload in three steps: reserve a row and get a presigned URL, PUT the bytes
   * straight to object storage, then tell the API to start ingestion.
   *
   * The bytes never pass through the API server, which is what makes a 500MB
   * lecture recording viable.
   */
  async upload(file: File, onProgress?: (percent: number) => void): Promise<LectureDocument> {
    const ticket = await request<{ documentId: string; uploadUrl: string }>(
      "/api/documents",
      {
        method: "POST",
        body: JSON.stringify({
          filename: file.name,
          contentType: file.type || "application/octet-stream",
          sizeBytes: file.size,
        }),
      },
    );

    await new Promise<void>((resolve, reject) => {
      // XHR rather than fetch: fetch still cannot report upload progress, and a
      // multi-hundred-megabyte upload with no progress bar feels broken.
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", ticket.uploadUrl);
      xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress(Math.round((event.loaded / event.total) * 100));
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
};

export const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "audio/*",
  "video/*",
].join(",");
