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
    ollama_base_url: str = "http://host.docker.internal:11434"
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
    # A Khmer fine-tune of Whisper in CTranslate2 format. Used for dictation in Khmer
    # and for any recording Whisper's base model detects as Khmer, because the stock
    # multilingual checkpoints transcribe Khmer poorly. Empty disables the swap.
    whisper_model_km: str = "PhanithLIM/whisper-small-khmer-ct2"
    # A dictation clip is a question, not a lecture; anything longer is a mistake.
    dictation_max_seconds: float = 120.0

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
