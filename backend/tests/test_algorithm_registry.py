"""算法注册表测试"""
import pytest

from app.services.algorithm_registry import AlgorithmRegistry


def test_registry_empty_initially() -> None:
    """新注册表为空"""
    reg = AlgorithmRegistry()
    assert len(reg) == 0
    assert reg.get("nonexistent") is None


def test_registry_get_required_raises() -> None:
    """get_required 找不到抛 KeyError"""
    reg = AlgorithmRegistry()
    with pytest.raises(KeyError):
        reg.get_required("nonexistent")


def test_registry_membership() -> None:
    """__contains__ 行为"""
    reg = AlgorithmRegistry()
    reg._cache["test"] = None  # type: ignore[assignment]
    assert "test" in reg
    assert "other" not in reg
    assert len(reg) == 1
    assert len(reg.all()) == 1
    assert reg.loaded_at is None  # 还没真正 load


def test_to_dict_masks_secrets() -> None:
    """to_dict 脱敏 secret/key 字段"""
    from app.services.algorithm_registry import to_dict

    class FakeAlgo:
        code = "test"
        name = "Test"
        category = "cat"
        description = "desc"
        engine_type = "cloud_api"
        is_active = True
        version = 1
        engine_config = {
            "provider": "aliyun",
            "access_key_id": "should_be_hidden",
            "access_key_secret": "should_be_hidden",
        }
        request_schema = None

    d = to_dict(FakeAlgo())  # type: ignore[arg-type]
    assert "access_key_id" not in d["engine_config"]
    assert "access_key_secret" not in d["engine_config"]
    assert d["engine_config"]["provider"] == "aliyun"
