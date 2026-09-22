"""Runtime configuration, loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://learnassist:learnassist@localhost:55432/learnassist"

    # RustFS / S3
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "rustfsadmin"
    s3_secret_key: str = "rustfsadmin"
    s3_bucket: str = "lecture-uploads"
    s3_region: str = "us-east-1"

    # Ollama (host-native)
    ollama_base_url: str = "http://172.168.5.2:11434"
    ollama_chat_model: str = "qwen2.5:32b-instruct"
    ollama_embed_model: str = "bge-m3"
    embed_dim: int = 1024

    # Shared secret for Spring Boot -> FastAPI calls.
    internal_api_key: str = "dev-internal-key-change-me"

    # --- Chunking ---
    # A chunk never spans two SourceRefs; these only govern splitting *within* one.
    max_chunk_tokens: int = 1000
    chunk_overlap_tokens: int = 150
    # A PDF page yielding fewer characters than this is assumed to be scanned.
    scanned_page_char_threshold: int = 50

    # --- Retrieval ---
    retrieval_top_k: int = 8
    # Each hit is expanded to its ordinal +/- this many neighbours for context.
    neighbour_window: int = 1
    max_context_tokens: int = 6000

    # --- Speech ---
    # "qwen": Qwen3-ASR for every language it supports, Whisper for the rest (Khmer
    # included) and for language detection. "whisper": Whisper only.
    speech_backend: str = "qwen"
    qwen_asr_model: str = "Qwen/Qwen3-ASR-0.6B"
    # "cpu", or "cuda:0" if the container has a GPU (and a CUDA build of torch).
    qwen_asr_device: str = "cpu"
    # Audio windows (~30 s each) transcribed per call. Larger helps on a GPU only.
    qwen_asr_batch_size: int = 4
    # A Khmer fine-tune of Whisper in CTranslate2 format. Used for dictation in Khmer
    # and for any recording Whisper's base model detects as Khmer, because the stock
    # multilingual checkpoints transcribe Khmer poorly. Empty disables the swap.
    whisper_model_km: str = "PhanithLIM/whisper-small-khmer-ct2"
    # A dictation clip is a question, not a lecture; anything longer is a mistake.
    dictation_max_seconds: float = 120.0
    # Voice messages can be in any language, but Whisper is unreliable on Khmer: it
    # recognises most languages at 0.92+ yet ranks Khmer speech as Vietnamese, Thai
    # or English at 0.3-0.87. A detected language is trusted only at this confidence;
    # below it the clip is treated as Khmer. Lower it if other languages land as Khmer.
    dictation_detect_min_prob: float = 0.9

    # --- Guardrails (the guard service, LLM Guard) ---
    # Every chat question is checked before it is answered and every answer before it
    # is returned. Empty disables the checks (the test suite, a bare local run).
    guard_url: str = ""
    # The first scan after the guard starts can wait on its models loading.
    guard_timeout_seconds: float = 30.0
    # If the guard is down: True answers anyway (logged), False refuses every
    # question until it is back. Open by default so an outage degrades to unguarded
    # rather than to a chat that cannot answer at all; set False where the checks
    # are a requirement.
    guard_fail_open: bool = True

    # --- OCR ---
    # Tesseract language packs, joined with '+'. Khmer is included so photos of Khmer
    # notes and scanned Khmer handouts are readable.
    ocr_languages: str = "eng+khm"

    # --- Link resources ---
    web_max_bytes: int = 5 * 1024 * 1024
    web_timeout_seconds: float = 20.0
    # Sites such as Wikipedia refuse clients whose User-Agent carries no contact URL.
    # Set this to a URL or address for your deployment.
    web_user_agent: str = (
        "Mozilla/5.0 (compatible; LearnAssist/0.1; +https://github.com/learnassist)"
    )
    # Bounds Whisper time for one link; a 10-hour livestream would occupy the
    # transcription worker for most of a day.
    youtube_max_duration_seconds: int = 4 * 60 * 60

    # Local Ollama serialises requests; unbounded fan-out stalls the whole pipeline.
    embed_concurrency: int = 4
    embed_batch_size: int = 16


@lru_cache
def get_settings() -> Settings:
    return Settings()
