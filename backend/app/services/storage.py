"""MinIO 对象存储服务"""
import io
from datetime import datetime, timedelta, timezone

from minio import Minio

from app.config import Settings


class StorageService:
    """MinIO 存储服务

    对象 key 格式: inspections/YYYY/MM/DD/{record_id}/{filename}
    """

    def __init__(self, client: Minio, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> "StorageService":
        """工厂方法: 从 Settings 创建"""
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        return cls(client=client, bucket=settings.minio_bucket)

    def ensure_bucket(self) -> None:
        """确保桶存在"""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def upload_file(
        self,
        file_bytes: bytes,
        filename: str,
        record_id: int,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传文件,返回 object_key"""
        now = datetime.now(timezone.utc)
        object_key = (
            f"inspections/{now.year:04d}/{now.month:02d}/{now.day:02d}/"
            f"{record_id}/{filename}"
        )
        self.client.put_object(
            bucket_name=self.bucket,
            object_name=object_key,
            data=io.BytesIO(file_bytes),
            length=len(file_bytes),
            content_type=content_type,
        )
        return object_key

    def get_file_url(self, object_key: str, expires_seconds: int = 900) -> str:
        """生成签名 URL (默认 15 分钟)"""
        url = self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_key,
            expires=timedelta(seconds=expires_seconds),
        )
        return url

    def download_file(self, object_key: str) -> bytes:
        """下载文件到内存 (小文件适用)"""
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
