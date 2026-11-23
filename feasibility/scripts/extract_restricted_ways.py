"""Pull the roads that matter for restriction checks out of a Singapore OSM extract.

    uv run --with osmium python scripts/extract_restricted_ways.py Singapore.osm.pbf data/

Keeps expressways and their slip roads, trunk roads, road tunnels and ways tagged
bicycle=no. Output: data/restricted_ways.geojson (OSM data, ODbL).
"""

import json
import sys
from pathlib import Path
from typing import Any

import osmium  # type: ignore[import-not-found]

ROADS = {"motorway", "motorway_link", "trunk", "trunk_link"}
FOOT_WAYS = {"footway", "path", "cycleway", "steps", "pedestrian", "corridor"}
KEPT_TAGS = ("highway", "name", "ref", "tunnel", "bridge", "bicycle", "foot", "layer")


class RestrictedWays(osmium.SimpleHandler):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__()
        self.features: list[dict[str, Any]] = []

    def way(self, way: Any) -> None:
        tags = dict(way.tags)
        highway = tags.get("highway")
        if highway is None:
            return
        road_tunnel = tags.get("tunnel") == "yes" and highway not in FOOT_WAYS
        if highway not in ROADS and tags.get("bicycle") != "no" and not road_tunnel:
            return
        try:
            coordinates = [[node.lon, node.lat] for node in way.nodes]
        except osmium.InvalidLocationError:
            return
        properties: dict[str, Any] = {}
        for key in KEPT_TAGS:
            if key in tags:
                properties[key] = tags[key]
        properties["osm_way_id"] = way.id
        geometry = {"type": "LineString", "coordinates": coordinates}
        self.features.append({"type": "Feature", "properties": properties, "geometry": geometry})


def main() -> None:
    pbf_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    handler = RestrictedWays()
    handler.apply_file(str(pbf_path), locations=True)
    collection = {"type": "FeatureCollection", "features": handler.features}
    (out_dir / "restricted_ways.geojson").write_text(json.dumps(collection))
    print(f"{len(handler.features)} ways -> {out_dir / 'restricted_ways.geojson'}")


if __name__ == "__main__":
    main()
