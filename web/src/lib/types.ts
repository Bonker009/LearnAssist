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
  /** Which attached resource the citation points into. */
  document_id?: string | null;
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

export type DocType =
  | "PDF"
  | "PPTX"
  | "DOCX"
  | "AUDIO"
  | "VIDEO"
  | "IMAGE"
  | "TEXT"
  | "WEB"
  | "YOUTUBE";

export interface LectureDocument {
  id: string;
  filename: string;
  docType: DocType;
  status: DocumentStatus;
  /** Original URL for web page and YouTube resources. */
  sourceUrl: string | null;
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

// ---------- conversations ----------

export interface ConversationSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface Conversation extends ConversationSummary {
  documents: LectureDocument[];
  messages: ChatMessage[];
}

export type SpeechLanguage = "km" | "en" | "auto";

export interface Transcript {
  text: string;
  language: string;
  durationSec: number;
}

/** A section of extracted text, as written by the AI service's reader snapshot. */
export interface ReaderUnit {
  kind: SourceKind;
  page_no: number | null;
  slide_no: number | null;
  label: string;
  title: string | null;
  text: string;
  ocr: boolean;
}

export interface ReaderSnapshot {
  version: number;
  source_url: string | null;
  units: ReaderUnit[];
}

// ---------- dashboard ----------

export interface DashboardTotals {
  resources: number;
  ready: number;
  processing: number;
  failed: number;
  chats: number;
  questions: number;
  groundedAnswers: number;
  answers: number;
  quizzes: number;
  /** 0..1 */
  averageScore: number;
  streakDays: number;
}

export interface Dashboard {
  totals: DashboardTotals;
  resourceTypes: { docType: DocType; count: number }[];
  /** One row per day, oldest first; `day` is YYYY-MM-DD in the viewer's zone. */
  activity: { day: string; questions: number; quizzes: number; resources: number }[];
  quizTrend: { takenAt: string; score: number; total: number; filename: string }[];
  mostCited: { id: string; filename: string; docType: DocType; citations: number }[];
  recentChats: {
    id: string;
    title: string;
    updatedAt: string;
    questions: number;
    resources: number;
  }[];
  processing: {
    id: string;
    filename: string;
    docType: DocType;
    stage: IngestStage;
    progress: number;
  }[];
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

/** Human-readable name for a resource type. */
export const DOC_TYPE_LABELS: Record<DocType, string> = {
  PDF: "PDF",
  PPTX: "Slides",
  DOCX: "Word",
  TEXT: "Notes",
  IMAGE: "Image",
  AUDIO: "Audio",
  VIDEO: "Video",
  WEB: "Web page",
  YOUTUBE: "YouTube",
};

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
