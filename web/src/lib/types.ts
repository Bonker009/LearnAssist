/**
 * Shapes returned by the Spring Boot API.
 *
 * `SourceRef` mirrors the Python model of the same name: exactly one addressing
 * scheme is populated, matching `kind`.
 */

export type SourceKind = "slide" | "page" | "timestamp";

export interface SourceRef {
  kind: SourceKind;
  slide_no?: number | null;
  page_no?: number | null;
  start_sec?: number | null;
  end_sec?: number | null;
}

export interface Citation {
  marker: number;
  source: SourceRef;
  label: string;
  snippet: string;
  ocr?: boolean;
}

export type DocumentStatus =
  | "PENDING_UPLOAD"
  | "UPLOADED"
  | "PROCESSING"
  | "READY"
  | "FAILED";

export type IngestStage =
  | "QUEUED"
  | "PARSING"
  | "TRANSCRIBING"
  | "OCR"
  | "CHUNKING"
  | "EMBEDDING"
  | "SUMMARIZING"
  | "DONE"
  | "FAILED";

export interface IngestJob {
  stage: IngestStage;
  progress: number;
  error: string | null;
}

export interface KeyConcept {
  term: string;
  explanation: string;
}

export interface Summary {
  summary: string;
  keyConcepts: KeyConcept[];
}

export interface LectureDocument {
  id: string;
  filename: string;
  docType: "PDF" | "PPTX" | "DOCX" | "AUDIO" | "VIDEO";
  status: DocumentStatus;
  unitCount: number | null;
  durationSec: number | null;
  sizeBytes: number;
  createdAt: string;
  job: IngestJob | null;
  summary: Summary | null;
}

export interface ChatMessage {
  id: string;
  role: "USER" | "ASSISTANT";
  content: string;
  citations: Citation[];
  createdAt: string;
}

export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

/** Human-readable label for a pipeline stage. */
export const STAGE_LABELS: Record<IngestStage, string> = {
  QUEUED: "Queued",
  PARSING: "Reading the file",
  TRANSCRIBING: "Transcribing audio",
  OCR: "Reading scanned pages",
  CHUNKING: "Splitting into sections",
  EMBEDDING: "Building the search index",
  SUMMARIZING: "Writing the summary",
  DONE: "Ready",
  FAILED: "Failed",
};

// ---------- quizzes ----------

/** A question as served before submission: deliberately no answer key. */
export interface QuizQuestion {
  id: string;
  position: number;
  question: string;
  options: string[];
  sourceLabel: string;
}

export interface Quiz {
  id: string;
  documentId: string;
  createdAt: string;
  questions: QuizQuestion[];
}

/** A question after grading, with the answer and its source revealed. */
export interface GradedQuestion {
  questionId: string;
  position: number;
  correct: boolean;
  correctIndex: number;
  chosenIndex: number | null;
  explanation: string;
  source: SourceRef;
  sourceLabel: string;
  snippet: string;
}

export interface Grade {
  attemptId: string;
  score: number;
  total: number;
  questions: GradedQuestion[];
}
