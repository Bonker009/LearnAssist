"""Database access.

This service is the ONLY writer for `chunks` and the pgvector index. Spring Boot
owns every other table via JPA. The schema itself is created by Flyway on the
Spring side — the table definitions here describe it for querying and must be
kept in step with `api/src/main/resources/db/migration`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

metadata = MetaData()

chunks = Table(
    "chunks",
    metadata,
    Column("id", PgUUID(as_uuid=True), primary_key=True),
    Column("document_id", PgUUID(as_uuid=True), nullable=False, index=True),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("section_title", Text, nullable=True),
    Column("source_kind", String(16), nullable=False),
    Column("slide_no", Integer, nullable=True),
    Column("page_no", Integer, nullable=True),
    Column("start_sec", Float, nullable=True),
    Column("end_sec", Float, nullable=True),
    Column("ocr", Boolean, nullable=False, server_default="false"),
    Column("embedding", Vector(get_settings().embed_dim), nullable=False),
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional session. Commits on success, rolls back on error."""
    get_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
