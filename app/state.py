from pathlib import Path
from typing import Any, Dict

from .utils import PROJECT_ROOT, load_json, save_json


STATE_PATH = PROJECT_ROOT / "data" / "state.json"


DEFAULT_STATE: Dict[str, Any] = {
    "current_index": 0,
    "download_root": "downloads/default",
    "language": "zh",
    "records": {},
    "skipped": []
}


def load_state() -> Dict[str, Any]:
    state = load_json(STATE_PATH, DEFAULT_STATE.copy())
    merged = DEFAULT_STATE.copy()
    merged.update(state)
    return merged


def save_state(state: Dict[str, Any]) -> None:
    save_json(STATE_PATH, state)


def set_current_index(state: Dict[str, Any], index: int, total: int) -> None:
    if total <= 0:
        state["current_index"] = 0
    else:
        state["current_index"] = max(0, min(index, total))


def record_download(state: Dict[str, Any], paper: Dict[str, str], category: str, file_path: Path) -> None:
    key = paper.get("detail_url") or paper.get("title", "")
    state.setdefault("records", {})[key] = {
        "title": paper.get("title", ""),
        "category": category,
        "file_path": str(file_path),
    }
