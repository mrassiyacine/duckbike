from collections import defaultdict

import geopandas as gpd
import h3
import networkx as nx
import osmnx as ox
import pandas as pd
import pyarrow as pa

from config import settings
from utils.logger import get_logger, setup_logging
from utils.osm_graph import WALK_GRAPH_KEY, load_graph_from_r2
from utils.r2_storage import R2Storage
from utils.zones import load_operator_zone_gdf

ZONES_CSV = "transform/duckbike/seeds/dott_paris_operator_zones.csv"
WALK_MATRIX_KEY = "reference/walk_time_matrix.parquet"
BUFFER_M = 500
WALKING_SPEED = 1.5  # m/s
TIME_CAP_MIN = 20

log = get_logger(__name__)


def buffer_zone(zone_gdf: gpd.GeoDataFrame, buffer_m: int) -> gpd.GeoSeries:
    """Expand the zone geometry by a fixed distance.

    Args:
        zone_gdf: Zone GeoDataFrame in EPSG:4326.
        buffer_m: Buffer distance in metres (projected via EPSG:2154).

    Returns:
        GeoSeries of the buffered geometry in EPSG:4326.
    """
    zone_buffered = zone_gdf.to_crs("EPSG:2154").buffer(buffer_m).to_crs("EPSG:4326")
    area_km2 = zone_gdf.to_crs("EPSG:2154").area.loc[0] / 1e6
    buffered_km2 = zone_buffered.to_crs("EPSG:2154").area.iloc[0] / 1e6
    log.info(
        "Buffered area: %.1f km² (+%.1f km²)", buffered_km2, buffered_km2 - area_km2
    )
    return zone_buffered


def build_h3_grid(
    buffered_geom, resolution: int
) -> tuple[list[str], dict[str, tuple[float, float]]]:
    """Fill a polygon with H3 cells and compute their centroids.

    Args:
        buffered_geom: Shapely Polygon covering the area of interest (EPSG:4326).
        resolution: H3 resolution level (e.g. 9 ≈ 0.1 km² per cell).

    Returns:
        Tuple of (h3_cells, centroids) where centroids maps cell → (lat, lng).
    """
    exterior_coords = [(lat, lon) for lon, lat in buffered_geom.exterior.coords]
    h3_poly = h3.LatLngPoly(exterior_coords)
    h3_cells = list(h3.polygon_to_cells(h3_poly, resolution))
    centroids = {cell: h3.cell_to_latlng(cell) for cell in h3_cells}
    log.info("H3 resolution: %d  cells: %d", resolution, len(h3_cells))
    return h3_cells, centroids


def load_walk_graph(walking_speed: float) -> nx.Graph:
    """Load the pre-fetched walk network from R2 and annotate edges with travel time.

    The graph is downloaded once by jobs/fetch_osm_graphs.py; here we just read it.

    Args:
        walking_speed: Walking speed in m/s used to compute edge travel_time.

    Returns:
        Undirected NetworkX graph with a 'travel_time' attribute on every edge (seconds).
    """
    storage = R2Storage.for_bucket(settings.R2_WAREHOUSE_BUCKET)
    log.info("Loading walk graph from r2://%s/%s", storage.bucket, WALK_GRAPH_KEY)
    G = load_graph_from_r2(storage, WALK_GRAPH_KEY).to_undirected()
    for _, _, data in G.edges(data=True):
        data["travel_time"] = data["length"] / walking_speed
    log.info("Graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
    return G


def snap_to_graph(
    G: nx.Graph, h3_cells: list[str], centroids: dict[str, tuple[float, float]]
) -> dict[int, list[str]]:
    """Map each H3 cell to its nearest OSM graph node.

    Args:
        G: Walking graph (nodes must have 'x'/'y' attributes as set by osmnx).
        h3_cells: List of H3 cell IDs to snap.
        centroids: Dict mapping cell ID → (lat, lng).

    Returns:
        Dict mapping graph node ID → list of H3 cell IDs snapped to that node.
    """
    h3_lats = [centroids[c][0] for c in h3_cells]
    h3_lons = [centroids[c][1] for c in h3_cells]
    nearest_nodes = ox.distance.nearest_nodes(G, X=h3_lons, Y=h3_lats)
    cell_to_node = dict(zip(h3_cells, nearest_nodes))
    node_to_cells: dict[int, list[str]] = defaultdict(list)
    for cell, node in cell_to_node.items():
        node_to_cells[node].append(cell)
    log.info("Unique snap nodes: %d", len(node_to_cells))
    return node_to_cells


def compute_matrix(
    G: nx.Graph, node_to_cells: dict[int, list[str]], time_cap_min: float
) -> pd.DataFrame:
    """Compute pairwise walk times between all H3 cells within a time cap.

    Runs Dijkstra from each unique snap node and expands results back to H3 cells.

    Args:
        G: Walking graph with 'travel_time' edge weights (seconds).
        node_to_cells: Dict mapping graph node ID → list of H3 cell IDs.
        time_cap_min: Maximum walk time to include in the output (minutes).

    Returns:
        DataFrame with columns [origin_h3, destination_h3, walk_minutes].
    """
    cap_seconds = time_cap_min * 60
    rows = []
    unique_origin_nodes = list(node_to_cells.keys())
    n = len(unique_origin_nodes)
    for i, origin_node in enumerate(unique_origin_nodes):
        if i % 100 == 0:
            log.info("  %d / %d origins processed", i, n)
        lengths = nx.single_source_dijkstra_path_length(
            G, origin_node, cutoff=cap_seconds, weight="travel_time"
        )
        for origin_cell in node_to_cells[origin_node]:
            for dest_node, t_seconds in lengths.items():
                if dest_node not in node_to_cells:
                    continue
                for dest_cell in node_to_cells[dest_node]:
                    rows.append((origin_cell, dest_cell, t_seconds / 60.0))
    df = pd.DataFrame(rows, columns=["origin_h3", "destination_h3", "walk_minutes"])
    log.info("Matrix rows: %d", len(df))
    return df


def write_matrix_to_r2(df: pd.DataFrame, key: str = WALK_MATRIX_KEY) -> None:
    """Write the walk-time matrix to R2 as Parquet, replacing any existing object.

    Args:
        df: Walk-time matrix with columns [origin_h3, destination_h3, walk_minutes].
        key: Object key under the warehouse bucket.
    """
    storage = R2Storage.for_bucket(settings.R2_WAREHOUSE_BUCKET)
    storage.write_parquet(key, pa.Table.from_pandas(df, preserve_index=False))
    log.info("Wrote %d rows to r2://%s/%s", len(df), storage.bucket, key)


def build_walk_time_matrix(
    zones_csv: str = ZONES_CSV,
    buffer_m: int = BUFFER_M,
    walking_speed: float = WALKING_SPEED,
    time_cap_min: float = TIME_CAP_MIN,
    h3_resolution: int = settings.H3_RESOLUTION,
) -> pd.DataFrame:
    """Run the full pipeline: load zone → H3 grid → OSM graph → walk-time matrix → R2.

    Args:
        zones_csv: Path to the operator zones CSV seed file.
        buffer_m: Buffer around the zone in metres before downloading the OSM graph.
        walking_speed: Assumed walking speed in m/s.
        time_cap_min: Pairs with walk time above this cap are excluded.
        h3_resolution: H3 resolution level for the spatial grid.

    Returns:
        DataFrame with columns [origin_h3, destination_h3, walk_minutes].
    """
    zone_gdf = load_operator_zone_gdf(zones_csv)
    area_km2 = zone_gdf.to_crs("EPSG:2154").area.iloc[0] / 1e6
    log.info("Zone type: %s  area: %.1f km²", zone_gdf.geom_type.iloc[0], area_km2)
    zone_buffered = buffer_zone(zone_gdf, buffer_m)
    buffered_geom = zone_buffered.union_all()

    h3_cells, centroids = build_h3_grid(buffered_geom, h3_resolution)
    G = load_walk_graph(walking_speed)
    node_to_cells = snap_to_graph(G, h3_cells, centroids)
    df = compute_matrix(G, node_to_cells, time_cap_min)

    write_matrix_to_r2(df)

    return df


if __name__ == "__main__":
    setup_logging()
    build_walk_time_matrix()
