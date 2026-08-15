from __future__ import annotations

from app.core.alternatives import build_route_option
from app.core.costs import BALANCED
from app.core.graph_quality import (
    audit_edge_name_quality,
    audit_graph_integrity,
    audit_route_direction_quality,
)
from app.core.models import DirectionStep, Edge, Graph, Node


def test_audit_edge_name_quality_counts_sources_and_rates() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0),
            2: Node(2, lon=-121.999, lat=37.0),
            3: Node(3, lon=-121.998, lat=37.0),
            4: Node(4, lon=-121.997, lat=37.0),
            5: Node(5, lon=-121.996, lat=37.0),
            6: Node(6, lon=-121.995, lat=37.0),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-121.999, 37.0)],
                length_m=80.0,
                display_name="Page Street",
                name_source="datasf_centerline",
                name_confidence=0.9,
            ),
            2: Edge(
                edge_id=2,
                source=2,
                target=3,
                geometry=[(-121.999, 37.0), (-121.998, 37.0)],
                length_m=10.0,
                display_name="walkway",
                name_source="generic_connector",
            ),
            3: Edge(
                edge_id=3,
                source=3,
                target=4,
                geometry=[(-121.998, 37.0), (-121.997, 37.0)],
                length_m=40.0,
                edge_type="residential",
                display_name="unnamed street",
                name_source="generic_unnamed_street",
            ),
            4: Edge(
                edge_id=4,
                source=4,
                target=5,
                geometry=[(-121.997, 37.0), (-121.996, 37.0)],
                length_m=40.0,
                edge_type="pedestrian",
                display_name="unnamed street",
                name_source="generic_unnamed_street",
            ),
            5: Edge(
                edge_id=5,
                source=5,
                target=6,
                geometry=[(-121.996, 37.0), (-121.995, 37.0)],
                length_m=40.0,
                edge_type="unclassified",
                display_name="unnamed street",
                name_source="generic_unnamed_street",
            ),
        },
    )

    report = audit_edge_name_quality(graph)

    assert report.display_name_coverage == 1.0
    assert report.datasf_name_rate == 1 / 5
    assert report.generic_non_stairs_rate == 4 / 5
    assert report.generic_unnamed_major_road_edges == 1
    assert report.long_generic_unnamed_street_edges == 3


def test_audit_graph_integrity_flags_broken_edges() -> None:
    graph = Graph(
        nodes={1: Node(1, lon=-122.0, lat=37.0)},
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0)],
                length_m=0.0,
            )
        },
    )

    issues = audit_graph_integrity(graph)

    assert {issue.kind for issue in issues} == {
        "missing_target_node",
        "short_geometry",
        "nonpositive_length",
    }


def test_audit_route_direction_quality_flags_vague_and_tiny_turn_steps() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0),
            2: Node(2, lon=-121.999, lat=37.0),
            3: Node(3, lon=-121.999, lat=37.0001),
            4: Node(4, lon=-121.998, lat=37.0001),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-121.999, 37.0)],
                length_m=80.0,
                edge_type="path",
                display_name="walking path",
                name_source="generic_path",
                base_time_s=60.0,
            ),
            2: Edge(
                edge_id=2,
                source=2,
                target=3,
                geometry=[(-121.999, 37.0), (-121.999, 37.0001)],
                length_m=9.0,
                street_name="Noe Street",
                display_name="Noe Street",
                name_source="datasf_centerline",
                base_time_s=7.0,
            ),
            3: Edge(
                edge_id=3,
                source=3,
                target=4,
                geometry=[(-121.999, 37.0001), (-121.998, 37.0001)],
                length_m=80.0,
                street_name="Waller Street",
                display_name="Waller Street",
                name_source="datasf_centerline",
                base_time_s=60.0,
            ),
        },
    )
    route = build_route_option(graph, [1, 2, 3], "recommended", BALANCED)
    route.directions = [
        DirectionStep(
            instruction="Walk east on walking path for 80 m.",
            street_name="walking path",
            distance_m=80.0,
            time_s=60.0,
            gain_m=0.0,
            loss_m=0.0,
            max_uphill_grade=0.0,
            geometry=[],
        ),
        DirectionStep(
            instruction="Turn left onto Noe Street for 9 m.",
            street_name="Noe Street",
            distance_m=9.0,
            time_s=7.0,
            gain_m=0.0,
            loss_m=0.0,
            max_uphill_grade=0.0,
            geometry=[],
        ),
        DirectionStep(
            instruction="Turn right onto Waller Street for 80 m.",
            street_name="Waller Street",
            distance_m=80.0,
            time_s=60.0,
            gain_m=0.0,
            loss_m=0.0,
            max_uphill_grade=0.0,
            geometry=[],
        ),
    ]

    issues = audit_route_direction_quality([route])

    assert "vague_term:walking path" in {issue.reason for issue in issues}
    assert "short_turn_fragment" in {issue.reason for issue in issues}


def test_audit_route_direction_quality_allows_tiny_final_arrival_turn() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0),
            2: Node(2, lon=-121.999, lat=37.0),
            3: Node(3, lon=-121.999, lat=37.0001),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-121.999, 37.0)],
                length_m=80.0,
                street_name="Page Street",
                base_time_s=60.0,
            ),
            2: Edge(
                edge_id=2,
                source=2,
                target=3,
                geometry=[(-121.999, 37.0), (-121.999, 37.0001)],
                length_m=9.0,
                street_name="Noe Street",
                display_name="Noe Street",
                name_source="datasf_centerline",
                base_time_s=7.0,
            ),
        },
    )
    route = build_route_option(graph, [1, 2], "recommended", BALANCED)

    assert audit_route_direction_quality([route]) == []
