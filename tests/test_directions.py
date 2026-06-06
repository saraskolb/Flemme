from __future__ import annotations

import pytest

from app.core.costs import BALANCED
from app.core.directions import build_directions
from app.core.models import Edge


def test_directions_group_edges_by_street_and_add_turns() -> None:
    edges = [
        Edge(
            edge_id=1,
            source=1,
            target=2,
            geometry=[(-122.0, 37.0), (-121.999, 37.0)],
            length_m=80.0,
            street_name="Page Street",
            base_time_s=60.0,
        ),
        Edge(
            edge_id=2,
            source=2,
            target=3,
            geometry=[(-121.999, 37.0), (-121.998, 37.0)],
            length_m=85.0,
            street_name="Page Street",
            base_time_s=64.0,
        ),
        Edge(
            edge_id=3,
            source=3,
            target=4,
            geometry=[(-121.998, 37.0), (-121.998, 36.999)],
            length_m=100.0,
            street_name="Noe Street",
            base_time_s=75.0,
            gain_m=7.0,
            max_uphill_grade=0.07,
        ),
    ]

    steps = build_directions(edges, BALANCED)

    assert len(steps) == 2
    assert steps[0].instruction.startswith("Walk east on Page Street")
    assert steps[0].distance_m == pytest.approx(165.0)
    assert steps[1].instruction.startswith("Turn right onto Noe Street")
    assert "uphill up to 7%" in steps[1].instruction


def test_directions_use_pedestrian_path_for_unnamed_footways() -> None:
    steps = build_directions(
        [
            Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-122.0, 37.001)],
                length_m=50.0,
                edge_type="footway",
                base_time_s=40.0,
            )
        ],
        BALANCED,
    )

    assert steps[0].street_name == "pedestrian path"
    assert "pedestrian path" in steps[0].instruction
