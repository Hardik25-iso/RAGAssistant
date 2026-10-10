"""File storage. S3 (SSE-KMS, private bucket) in production, local disk in development.

Keys are always users/{user_id}/{subject_id}/{uuid}.{ext}, so the IAM policy can
restrict the instance role to the users/* prefix and every student's files sit
under their own prefix.
"""
import logging
import uuid
from pathlib import Path

from app.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


def build_key(user_id: str, subject_id: str, file_type: str) -> str:
    return f"users/{user_id}/{subject_id}/{uuid.uuid4().hex}.{file_type}"


CONTENT_TYPES = {
    "pdf": "application/pdf",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class S3Storage:
    def __init__(self, bucket: str, region: str):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "adaptive"}),
        )

    def put(self, key: str, data: bytes, file_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=CONTENT_TYPES.get(file_type, "application/octet-stream"),
            ServerSideEncryption="aws:kms",
        )

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def presigned_url(self, key: str, filename: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=settings.PRESIGNED_URL_SECONDS,
        )


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root)):
            raise ValueError("invalid key")
        return p

    def put(self, key: str, data: bytes, file_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def presigned_url(self, key: str, filename: str) -> str | None:
        return None  # router streams the file directly in local mode


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        if settings.STORAGE_BACKEND == "s3":
            if not settings.S3_BUCKET:
                raise RuntimeError("S3_BUCKET must be set when STORAGE_BACKEND=s3")
            _storage = S3Storage(settings.S3_BUCKET, settings.AWS_REGION)
        else:
            _storage = LocalStorage(settings.LOCAL_STORAGE_DIR)
    return _storage
