from collections import Counter

import pandas as pd

MIN_TRIP_KM = 0.1

OUTPUT_COLUMNS = ["u", "v", "name", "length_m", "n_trips", "geometry_wkt"]


def _load_bike_graph():
    """Load the pre-fetched bike graph (jobs/fetch_osm_graphs.py) from R2."""
    storage = R2Storage.for_bucket(settings.R2_WAREHOUSE_BUCKET)
    return load_graph_from_r2(storage, BIKE_GRAPH_KEY)


def model(dbt, session):
    dbt.config(materialized="table")

    trips = dbt.ref("mart_matched_trips").df()
    trips = trips[
        (trips["match_type"] == "User Trip") & (trips["dist_km"] >= MIN_TRIP_KM)
    ]
    if trips.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    g = _load_bike_graph()

    u = ox.distance.nearest_nodes(
        g, trips["start_lon"].to_numpy(), trips["start_lat"].to_numpy()
    )
    v = ox.distance.nearest_nodes(
        g, trips["end_lon"].to_numpy(), trips["end_lat"].to_numpy()
    )

    pairs = pd.DataFrame({"u": u, "v": v})
    pairs = pairs[pairs["u"] != pairs["v"]]
    pair_counts = pairs.groupby(["u", "v"]).size().reset_index(name="n_trips")
    if pair_counts.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    routes = ox.routing.shortest_path(
        g,
        pair_counts["u"].tolist(),
        pair_counts["v"].tolist(),
        weight="length",
    )
    paths_by_pair = {
        (uu, vv): (list(p) if p else None)
        for uu, vv, p in zip(pair_counts["u"], pair_counts["v"], routes)
    }

    segment_trips = Counter()
    for row in pair_counts.itertuples(index=False):
        path = paths_by_pair.get((row.u, row.v))
        if not path:
            continue
        for a, b in zip(path[:-1], path[1:]):
            key = (a, b) if a < b else (b, a)
            segment_trips[key] += int(row.n_trips)

    rows = []
    for (a, b), n in segment_trips.items():
        data = g.get_edge_data(a, b) or g.get_edge_data(b, a)
        edge = min(data.values(), key=lambda e: e.get("length", float("inf")))
        geom = edge.get("geometry")
        if geom is None:
            geom = LineString(
                [
                    (g.nodes[a]["x"], g.nodes[a]["y"]),
                    (g.nodes[b]["x"], g.nodes[b]["y"]),
                ]
            )
        rows.append(
            {
                "u": a,
                "v": b,
                "name": edge.get("name"),
                "length_m": float(edge.get("length", 0.0)),
                "n_trips": n,
                "geometry_wkt": geom.wkt,
            }
        )

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


import osmnx as ox
from shapely.geometry import LineString

from config import settings
from utils.osm_graph import BIKE_GRAPH_KEY, load_graph_from_r2
from utils.r2_storage import R2Storage
