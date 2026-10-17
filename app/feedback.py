from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from uuid import uuid4

_feedback_lock = Lock()


@dataclass(frozen=True, slots=True)
class SavedFeedback:
    feedback_id: str
    saved_at: str
    path: str
    duplicate: bool = False


def _existing_feedback(path: Path, idempotency_key: object) -> SavedFeedback | None:
    if not idempotency_key or not path.exists():
        return None
    with path.open("r", encoding="utf-8") as feedback_file:
        for line in feedback_file:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("idempotency_key") == idempotency_key:
                return SavedFeedback(
                    feedback_id=str(record["feedback_id"]),
                    saved_at=str(record["saved_at"]),
                    path=str(path),
                    duplicate=True,
                )
    return None


def append_route_feedback(payload: dict[str, object], path: Path) -> SavedFeedback:
    with _feedback_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = _existing_feedback(path, payload.get("idempotency_key"))
        if existing is not None:
            return existing
        saved = SavedFeedback(
            feedback_id=str(uuid4()),
            saved_at=datetime.now(UTC).isoformat(),
            path=str(path),
        )
        record = {
            "feedback_id": saved.feedback_id,
            "saved_at": saved.saved_at,
            **payload,
        }
        with path.open("a", encoding="utf-8") as feedback_file:
            feedback_file.write(json.dumps(record, sort_keys=True) + "\n")
        return saved
