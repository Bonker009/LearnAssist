# learnassist-ai

FastAPI service: document/media ingestion, RAG retrieval, and quiz generation.
Owns the `chunks` table and the pgvector index. Never called directly by the browser —
Spring Boot proxies every request after enforcing ownership.
