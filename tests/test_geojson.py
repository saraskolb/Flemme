from __future__ import annotations

from app.core.alternatives import build_route_option
from app.core.costs import BALANCED
from app.core.geojson import route_to_geojson
from app.core.models import Edge, Graph, Node


def test_route_to_geojson_includes_route_and_edge_debug_features() -> None:
    graph = Graph(
        nodes={
            1: Node(1, lon=-122.0, lat=37.0),
            2: Node(2, lon=-121.999, lat=37.0),
        },
        edges={
            10: Edge(
                edge_id=10,
                source=1,
                target=2,
                geometry=[(-122.0, 37.0), (-121.999, 37.0)],
                length_m=88.0,
                street_name="Page Street",
                max_uphill_grade=0.07,
                base_time_s=66.0,
                osm_way_id=123,
                source_tags={"highway": "residential", "name": "Page Street"},
            )
        },
    )
    option = build_route_option(graph, [10], "recommended", BALANCED)

    collection = route_to_geojson(graph, option, start_node=1, goal_node=2)

    assert collection["type"] == "FeatureCollection"
    assert collection["features"][0]["properties"]["feature_type"] == "route"
    edge_feature = collection["features"][1]
    assert edge_feature["properties"]["feature_type"] == "edge"
    assert edge_feature["properties"]["edge_id"] == 10
    assert edge_feature["properties"]["osm_way_id"] == 123
    assert edge_feature["properties"]["source_tags"]["highway"] == "residential"
    assert collection["features"][2]["properties"]["role"] == "origin"
    assert collection["features"][3]["properties"]["role"] == "destination"
