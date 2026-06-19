import geopandas as gpd
import h3
import pandas as pd

from config import settings
from utils.logger import get_logger, setup_logging
from utils.zones import load_operator_zone

logger = get_logger(__name__)

PARQUET_PATH = "data/carreaux-200m-met-3035-2021.parquet"
ZONES_CSV = "transform/duckbike/seeds/dott_paris_operator_zones.csv"
OUTPUT_CSV = "transform/duckbike/seeds/filosofi_paris.csv"


def seed_filosofi(parquet_path: str, zones_csv: str, output_csv: str) -> None:
    logger.info("loading filosofi parquet")
    gdf = gpd.read_parquet(parquet_path).to_crs("EPSG:4326")
    logger.info(f"loaded {len(gdf)} rows")

    zone = load_operator_zone(zones_csv)
    logger.info("loaded operator zone")

    gdf = gdf[gdf.geometry.within(zone)]
    logger.info(f"{len(gdf)} rows within operator zone")

    df = pd.DataFrame(gdf)
    df["geometry"] = gdf.geometry.to_wkt()
    centroids = gdf.geometry.to_crs("EPSG:2154").centroid.to_crs("EPSG:4326")
    df["h3_index"] = [
        h3.latlng_to_cell(pt.y, pt.x, settings.H3_RESOLUTION) for pt in centroids
    ]
    df.to_csv(output_csv, index=False)
    logger.info(f"wrote seed to {output_csv}")


if __name__ == "__main__":
    setup_logging()
    seed_filosofi(PARQUET_PATH, ZONES_CSV, OUTPUT_CSV)
