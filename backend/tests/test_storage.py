"""存储服务测试"""
from unittest.mock import MagicMock

from app.services.storage import StorageService


def _make_minio_mock() -> MagicMock:
    client = MagicMock()
    client.put_object = MagicMock()
    client.presigned_get_object = MagicMock(return_value="https://example.com/signed")
    client.bucket_exists = MagicMock(return_value=True)
    return client


def test_upload_file() -> None:
    """上传文件返回 object_key"""
    mock_minio = _make_minio_mock()
    service = StorageService(client=mock_minio, bucket="gevic")
    key = service.upload_file(
        file_bytes=b"hello world",
        filename="test.jpg",
        record_id=1024,
    )
    assert key.startswith("inspections/")
    assert "1024" in key
    assert key.endswith("test.jpg")
    assert mock_minio.put_object.called


def test_get_file_url() -> None:
    """生成签名 URL"""
    mock_minio = _make_minio_mock()
    service = StorageService(client=mock_minio, bucket="gevic")
    url = service.get_file_url("inspections/2026/07/01/1024/test.jpg")
    assert url == "https://example.com/signed"
    mock_minio.presigned_get_object.assert_called_once()


def test_ensure_bucket() -> None:
    """桶不存在则创建"""
    mock_minio = _make_minio_mock()
    mock_minio.bucket_exists.return_value = False
    service = StorageService(client=mock_minio, bucket="gevic")
    service.ensure_bucket()
    assert mock_minio.make_bucket.called


def test_ensure_bucket_existing() -> None:
    """桶已存在不创建"""
    mock_minio = _make_minio_mock()
    service = StorageService(client=mock_minio, bucket="gevic")
    service.ensure_bucket()
    assert not mock_minio.make_bucket.called
