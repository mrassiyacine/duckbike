"""Persist OSM graphs to R2 as gzipped GraphML.

GraphML is verbose XML but compresses ~5-6x and round-trips cleanly across osmnx /
networkx versions (unlike pickles), so it is the safe interchange format between the
standalone fetch job and the build steps that consume the graphs.
"""

import gzip
import os
import tempfile

import osmnx as ox

WALK_GRAPH_KEY = "reference/osm_walk.graphml.gz"
BIKE_GRAPH_KEY = "reference/osm_bike.graphml.gz"


def save_graph_to_r2(graph, storage, key: str) -> None:
    """Serialize a graph to gzipped GraphML and upload it to R2 under ``key``."""
    fd, tmp_path = tempfile.mkstemp(suffix=".graphml")
    os.close(fd)
    try:
        ox.save_graphml(graph, tmp_path)
        with open(tmp_path, "rb") as f:
            storage.write_bytes(key, gzip.compress(f.read()))
    finally:
        os.unlink(tmp_path)


def load_graph_from_r2(storage, key: str):
    """Download gzipped GraphML at ``key`` from R2 and return the networkx graph."""
    raw = gzip.decompress(storage.read_bytes(key))
    fd, tmp_path = tempfile.mkstemp(suffix=".graphml")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        return ox.load_graphml(tmp_path)
    finally:
        os.unlink(tmp_path)
