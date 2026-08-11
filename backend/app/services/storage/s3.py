"""S3-compatible object storage client (MinIO locally, S3/R2 in prod —
see docs/ARCHITECTURE.md §5)."""
import json
import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

settings = get_settings()

# Only `slides/*` needs to be publicly fetchable — by the Instagram Graph
# API when it fetches image_url server-side to build a media container
# (docs/API_REQUIREMENTS.md §1), and by the dashboard's <img> tags. Every
# other prefix (raw reel video, archived source full-text) stays private:
# it's only ever read back server-side via get_bytes(), and reel video in
# particular may be copyrighted/sensitive with no reason to expose it
# beyond what publishing actually requires.
_PUBLIC_READ_PREFIX = "slides/*"


class StorageClient:
    def __init__(self):
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = settings.S3_BUCKET

    def ensure_bucket(self) -> None:
        existing = self._client.list_buckets().get("Buckets", [])
        if not any(b["Name"] == self._bucket for b in existing):
            self._client.create_bucket(Bucket=self._bucket)

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self._bucket}/{_PUBLIC_READ_PREFIX}"],
                }
            ],
        }
        try:
            self._client.put_bucket_policy(Bucket=self._bucket, Policy=json.dumps(policy))
        except ClientError as exc:
            # Some managed S3-compatible providers (notably Cloudflare R2)
            # don't support bucket policies and expect public access to be
            # configured via their own dashboard/API instead — surface
            # this rather than failing bootstrap silently.
            raise RuntimeError(
                f"Could not set a public-read policy on bucket '{self._bucket}' for "
                f"'{_PUBLIC_READ_PREFIX}'. If this provider doesn't support bucket "
                f"policies (e.g. Cloudflare R2), configure public read access for that "
                f"prefix manually. Underlying error: {exc}"
            ) from exc

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def get_bytes(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    def public_url(self, key: str) -> str:
        return f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}"

    @staticmethod
    def generate_key(prefix: str, extension: str) -> str:
        return f"{prefix}/{uuid.uuid4()}.{extension.lstrip('.')}"


_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    global _client
    if _client is None:
        _client = StorageClient()
    return _client
