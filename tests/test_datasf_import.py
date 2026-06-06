from __future__ import annotations

import json
from pathlib import Path

from app.ingest.datasf_import import load_datasf_street_centerlines


def test_load_datasf_street_centerlines_reads_geojson_features(tmp_path: Path) -> None:
    path = tmp_path / "streets.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-122.441, 37.771],
                                [-122.44, 37.771],
                            ],
                        },
                        "properties": {
                            "cnn": "98765",
                            "streetname": "PAGE ST",
                            "active": True,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    centerlines = load_datasf_street_centerlines(path)

    assert len(centerlines) == 1
    assert centerlines[0].display_name == "Page Street"
    assert centerlines[0].source_feature_id == "98765"
    assert centerlines[0].source_dataset == "datasf_streets_active_retired"
    assert centerlines[0].active is True
