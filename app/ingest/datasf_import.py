from __future__ import annotations

from pathlib import Path
from typing import Any


def load_datasf_attributes(data_dir: Path) -> dict[str, Any]:
    """Load San Francisco pedestrian-quality and safety datasets.

    TODO:
    - Load sidewalk widths.
    - Load curb ramps and crossing metadata.
    - Load High Injury Network and crash layers where available.
    - Spatially join attributes to raw walking edges.
    """
    raise NotImplementedError("DataSF ingestion is intentionally stubbed in the first slice.")
