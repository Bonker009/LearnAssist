"""RustFS (S3-compatible) object access.

Path-style addressing is mandatory: RustFS is not AWS, so a virtual-host style
request (`http://bucket.rustfs:9000/key`) does not resolve and every call 404s.
"""

from contextlib import asynccontextmanager

import aioboto3
from botocore.config import Config

from app.config import get_settings

_session = aioboto3.Session()


@asynccontextmanager
async def s3_client():
    settings = get_settings()
    async with _session.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
    ) as client:
        yield client


async def download_bytes(storage_key: str) -> bytes:
    """Fetch an uploaded lecture file whole.

    Parsers need random access (PyMuPDF seeks, python-pptx unzips), so streaming
    to a parser is not an option — the file is read into memory. Upload size is
    capped on the Spring Boot side to keep this bounded.
    """
    settings = get_settings()
    async with s3_client() as client:
        response = await client.get_object(Bucket=settings.s3_bucket, Key=storage_key)
        return await response["Body"].read()


async def ensure_bucket() -> None:
    """Create the uploads bucket if it does not exist. Idempotent."""
    settings = get_settings()
    async with s3_client() as client:
        try:
            await client.head_bucket(Bucket=settings.s3_bucket)
        except Exception:
            await client.create_bucket(Bucket=settings.s3_bucket)
