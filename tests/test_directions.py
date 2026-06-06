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


def test_directions_hide_unnamed_sidewalk_connectors() -> None:
    steps = build_directions(
        [
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
                geometry=[(-121.999, 37.0), (-121.999, 37.001)],
                length_m=50.0,
                edge_type="footway",
                source_tags={"highway": "footway", "footway": "sidewalk"},
                display_name="Divisadero Street",
                name_source="inferred_reachable_street",
                base_time_s=40.0,
            ),
            Edge(
                edge_id=3,
                source=3,
                target=4,
                geometry=[(-121.999, 37.001), (-121.998, 37.001)],
                length_m=80.0,
                street_name="Divisadero Street",
                base_time_s=60.0,
            ),
        ],
        BALANCED,
    )

    assert len(steps) == 2
    assert steps[1].street_name == "Divisadero Street"
    assert "pedestrian path" not in steps[1].instruction
    assert steps[1].instruction.startswith("Turn left onto Divisadero Street")
    assert steps[1].distance_m == pytest.approx(130.0)


def test_directions_absorb_short_cross_street_between_same_street() -> None:
    steps = build_directions(
        [
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
                geometry=[(-121.999, 37.0), (-121.999, 37.00006)],
                length_m=7.0,
                edge_type="footway",
                display_name="Broderick Street",
                name_source="datasf_centerline",
                base_time_s=5.0,
            ),
            Edge(
                edge_id=3,
                source=3,
                target=4,
                geometry=[(-121.999, 37.00006), (-121.998, 37.00006)],
                length_m=80.0,
                street_name="Page Street",
                base_time_s=60.0,
            ),
        ],
        BALANCED,
    )

    assert len(steps) == 1
    assert steps[0].street_name == "Page Street"
    assert "Broderick Street" not in steps[0].instruction
    assert steps[0].distance_m == pytest.approx(167.0)


def test_directions_preserve_real_unnamed_paths_alleys_and_streets() -> None:
    steps = build_directions(
        [
            Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-122.0, 37.001)],
                length_m=50.0,
                edge_type="path",
                source_tags={"highway": "path"},
                base_time_s=40.0,
            ),
            Edge(
                edge_id=2,
                source=2,
                target=3,
                geometry=[(-122.0, 37.001), (-121.999, 37.001)],
                length_m=50.0,
                edge_type="service",
                source_tags={"highway": "service", "service": "alley"},
                base_time_s=40.0,
            ),
            Edge(
                edge_id=3,
                source=3,
                target=4,
                geometry=[(-121.999, 37.001), (-121.998, 37.001)],
                length_m=50.0,
                edge_type="residential",
                source_tags={"highway": "residential"},
                base_time_s=40.0,
            ),
        ],
        BALANCED,
    )

    assert "walking path" in steps[0].instruction
    assert "alley" in steps[1].instruction
    assert "unnamed street" in steps[2].instruction
