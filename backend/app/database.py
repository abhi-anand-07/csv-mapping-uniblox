import uuid
import json
from typing import Dict, Optional
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SESSIONS: Dict[str, dict] = {}


def create_session() -> str:
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {"status": "created", "data": {}}
    return session_id


def get_session(session_id: str) -> Optional[dict]:
    return SESSIONS.get(session_id)


def update_session(session_id: str, data: dict):
    if session_id not in SESSIONS:
        raise ValueError(f"Session {session_id} not found")
    SESSIONS[session_id]["data"].update(data)


def set_session_status(session_id: str, status: str):
    if session_id not in SESSIONS:
        raise ValueError(f"Session {session_id} not found")
    SESSIONS[session_id]["status"] = status


def save_csv(session_id: str, content: bytes) -> Path:
    csv_path = DATA_DIR / f"{session_id}_input.csv"
    csv_path.write_bytes(content)
    return csv_path


def get_csv_path(session_id: str) -> Optional[Path]:
    csv_path = DATA_DIR / f"{session_id}_input.csv"
    return csv_path if csv_path.exists() else None


def save_published_csv(session_id: str, content: bytes) -> Path:
    csv_path = DATA_DIR / f"{session_id}_published.csv"
    csv_path.write_bytes(content)
    return csv_path


def get_published_csv_path(session_id: str) -> Optional[Path]:
    csv_path = DATA_DIR / f"{session_id}_published.csv"
    return csv_path if csv_path.exists() else None
