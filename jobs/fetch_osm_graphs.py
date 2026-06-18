"""Download the OSM walk + bike networks for the operator zone and store them in R2.

On
"""

from config import settings
from utils.logger import get_logger, setup_logging
from utils.osm_graph import BIKE_GRAPH_KEY, WALK_GRAPH_KEY, save_graph_to_r2
from utils.r2_storage import R2Storage
from utils.zones import load_operator_zone_gdf

log = get_logger(__name__)

ZONES_CSV = "transform/duckbike/seeds/dott_paris_operator_zones.csv"
BUFFER_M = 500

GRAPHS = {"walk": WALK_GRAPH_KEY, "bike": BIKE_GRAPH_KEY}


def buffered_zone_geom(zones_csv: str, buffer_m: int):
    """Operator zone expanded by ``buffer_m`` metres, as a single EPSG:4326 polygon."""
    gdf = load_operator_zone_gdf(zones_csv)
    buffered = gdf.to_crs("EPSG:2154").buffer(buffer_m).to_crs("EPSG:4326")
    return buffered.union_all()


def fetch_osm_graphs(zones_csv: str = ZONES_CSV, buffer_m: int = BUFFER_M) -> None:
    geom = buffered_zone_geom(zones_csv, buffer_m)
    storage = R2Storage.for_bucket(settings.R2_WAREHOUSE_BUCKET)

    for network_type, key in GRAPHS.items():
        log.info("downloading %s network from OSM...", network_type)
        graph = ox.graph_from_polygon(geom, network_type=network_type, simplify=True)
        log.info(
            "%s graph: %d nodes, %d edges",
            network_type,
            graph.number_of_nodes(),
            graph.number_of_edges(),
        )
        save_graph_to_r2(graph, storage, key)
        log.info("uploaded %s graph to r2://%s/%s", network_type, storage.bucket, key)


import osmnx as ox

if __name__ == "__main__":
    setup_logging()
    fetch_osm_graphs()
