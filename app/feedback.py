from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class SavedFeedback:
    feedback_id: str
    saved_at: str
    path: str


def append_route_feedback(payload: dict[str, object], path: Path) -> SavedFeedback:
    path.parent.mkdir(parents=True, exist_ok=True)
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
