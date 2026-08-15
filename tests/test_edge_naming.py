from __future__ import annotations

from app.core.edge_naming import (
    OfficialStreetName,
    apply_official_street_names,
    assign_edge_display_names,
    edge_label,
    format_street_name,
)
from app.core.models import Edge, Graph, Node


def test_format_street_name_humanizes_numbered_ordinal_streets() -> None:
    assert format_street_name("03RD ST") == "3rd Street"
    assert format_street_name("02ND AV") == "2nd Avenue"
    assert format_street_name("10TH ST") == "10th Street"


def test_edge_label_formats_raw_numbered_street_names_for_display() -> None:
    edge = Edge(
        edge_id=1,
        source=1,
        target=2,
        geometry=[(-122.0, 37.0), (-121.999, 37.0)],
        length_m=100.0,
        street_name="03RD Street",
        display_name="03RD Street",
    )

    assert edge_label(edge).text == "3rd Street"


def test_assign_edge_display_names_infers_sidewalk_names_from_adjacent_streets() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0),
            2: Node(2, lon=-121.999, lat=37.0),
            3: Node(3, lon=-121.999, lat=37.001),
            4: Node(4, lon=-121.999, lat=37.002),
            5: Node(5, lon=-121.999, lat=37.003),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-121.999, 37.0)],
                length_m=100.0,
                street_name="Page Street",
            ),
            2: Edge(
                edge_id=2,
                source=2,
                target=3,
                geometry=[(-121.999, 37.0), (-121.999, 37.001)],
                length_m=100.0,
                edge_type="footway",
                source_tags={"highway": "footway", "footway": "sidewalk"},
            ),
            3: Edge(
                edge_id=3,
                source=3,
                target=4,
                geometry=[(-121.999, 37.001), (-121.999, 37.002)],
                length_m=100.0,
                edge_type="footway",
                source_tags={"highway": "footway", "footway": "sidewalk"},
            ),
            4: Edge(
                edge_id=4,
                source=4,
                target=5,
                geometry=[(-121.999, 37.002), (-121.999, 37.003)],
                length_m=100.0,
                street_name="Divisadero Street",
            ),
        },
    )

    assign_edge_display_names(graph)

    assert graph.edges[1].display_name == "Page Street"
    assert graph.edges[1].name_source == "osm"
    assert graph.edges[2].display_name == "Divisadero Street"
    assert graph.edges[2].name_source == "inferred_reachable_street"
    assert graph.edges[3].display_name == "Divisadero Street"
    assert graph.edges[3].name_source == "inferred_reachable_street"


def test_assign_edge_display_names_preserves_real_unnamed_route_features() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0),
            2: Node(2, lon=-122.0, lat=37.001),
            3: Node(3, lon=-121.999, lat=37.001),
            4: Node(4, lon=-121.998, lat=37.001),
            5: Node(5, lon=-121.997, lat=37.001),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-122.0, 37.001)],
                length_m=50.0,
                edge_type="path",
                source_tags={"highway": "path"},
            ),
            2: Edge(
                edge_id=2,
                source=2,
                target=3,
                geometry=[(-122.0, 37.001), (-121.999, 37.001)],
                length_m=50.0,
                edge_type="service",
                source_tags={"highway": "service", "service": "alley"},
            ),
            3: Edge(
                edge_id=3,
                source=3,
                target=4,
                geometry=[(-121.999, 37.001), (-121.998, 37.001)],
                length_m=50.0,
                edge_type="residential",
                source_tags={"highway": "residential"},
            ),
            4: Edge(
                edge_id=4,
                source=4,
                target=5,
                geometry=[(-121.998, 37.001), (-121.997, 37.001)],
                length_m=50.0,
                edge_type="pedestrian",
                source_tags={"highway": "pedestrian"},
            ),
        },
    )

    assign_edge_display_names(graph)

    assert graph.edges[1].display_name == "walking path"
    assert graph.edges[2].display_name == "alley"
    assert graph.edges[3].display_name == "unnamed street"
    assert graph.edges[4].display_name == "pedestrian area"


def test_apply_official_street_names_matches_unnamed_sidewalk_to_datasf_centerline() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.00001, lat=37.0),
            2: Node(2, lon=-121.99901, lat=37.0),
        },
        edges={
            1: Edge(
                edge_id=1,
                source=1,
                target=2,
                geometry=[(-122.00001, 37.0), (-121.99901, 37.0)],
                length_m=88.0,
                edge_type="footway",
                source_tags={"highway": "footway", "footway": "sidewalk"},
            )
        },
    )
    centerlines = [
        OfficialStreetName(
            display_name="Page Street",
            source_dataset="datasf_streets_active_retired",
            source_feature_id="12345",
            geometry=[(-122.0, 37.0), (-121.999, 37.0)],
            active=True,
        )
    ]

    apply_official_street_names(graph, centerlines)

    edge = graph.edges[1]
    assert edge.display_name == "Page Street"
    assert edge.name_source == "datasf_centerline"
    assert edge.source_dataset == "datasf_streets_active_retired"
    assert edge.source_feature_id == "12345"
    assert edge.name_status == "official_street_name"
    assert edge.name_confidence > 0.8
