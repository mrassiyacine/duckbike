import csv
import json

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry


def load_operator_zone(zones_csv: str) -> BaseGeometry:
    """Load the operator operating-zone polygon from a seed CSV.

    The CSV holds a single row with a GeoJSON ``geometry`` column (EPSG:4326).

    Args:
        zones_csv: Path to the operator-zone seed CSV.

    Returns:
        The zone polygon as a Shapely geometry (EPSG:4326).
    """
    with open(zones_csv) as f:
        for row in csv.DictReader(f):
            return shape(json.loads(row["geometry"]))
    raise ValueError(f"no operator zone found in {zones_csv}")


def load_operator_zone_gdf(zones_csv: str):
    """Load the operator zone as a single-row GeoDataFrame in EPSG:4326.

    Args:
        zones_csv: Path to the operator-zone seed CSV.

    Returns:
        Single-row GeoDataFrame with the zone geometry (EPSG:4326).
    """
    return gpd.GeoDataFrame(geometry=[load_operator_zone(zones_csv)], crs="EPSG:4326")


import geopandas as gpd
