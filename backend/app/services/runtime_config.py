"""Runtime config - frontend hot-updatable, persisted to JSON file

Differs from Settings (env vars, requires restart):
- This module manages values that can be changed at runtime via API
- Persisted to backend/.runtime-config.json
- Excluded via .gitignore
- Typical use: LLM max_input/max_output_tokens per task type
"""
import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent / ".runtime-config.json"
_lock = threading.RLock()
_data: dict[str, Any] = {}


def _load_from_disk() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {}
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        logger.warning("Failed to load runtime config: %s", e)
        return {}


def _save_to_disk() -> None:
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to save runtime config: %s", e)


def get(key: str, default: Any = None) -> Any:
    """Read runtime config value. Returns default if not set."""
    with _lock:
        return _data.get(key, default)


def get_all() -> dict[str, Any]:
    """Return all runtime config (copy)."""
    with _lock:
        return dict(_data)


def set_value(key: str, value: Any) -> None:
    """Set a single value and persist immediately."""
    with _lock:
        _data[key] = value
        _save_to_disk()
        logger.info("Runtime config updated: %s = %r", key, value)


def update(updates: dict[str, Any]) -> dict[str, Any]:
    """Batch update, return full config after update."""
    with _lock:
        for k, v in updates.items():
            if v is None:
                _data.pop(k, None)
            else:
                _data[k] = v
        _save_to_disk()
        return dict(_data)


# Load from disk on module import
_data = _load_from_disk()
if _data:
    logger.info("Loaded %d runtime config keys from %s", len(_data), _CONFIG_PATH)