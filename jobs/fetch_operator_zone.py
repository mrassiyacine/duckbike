import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from config import OperatorConfig, settings
from extraction.gbfs_client import GBFSClient
from utils.logger import get_logger, setup_logging

logger = get_logger(__name__)

_GEOFENCING_ENDPOINT = "geofencing_zones.json"
_SEEDS_DIR = Path("transform/duckbike/seeds")


def _zone_seed_path(operator: str, city: str) -> Path:
    """Seed path for one operator/city zone, e.g. seeds/dott_paris_operator_zones.csv."""
    return _SEEDS_DIR / f"{operator}_{city}_operator_zones.csv"


def _extract_zone(data: dict, city: str) -> dict:
    """Return the GeoJSON geometry of the geofencing zone whose name matches `city`."""
    features = data["data"]["geofencing_zones"]["features"]
    match = next(
        (
            f
            for f in features
            if f.get("properties", {}).get("name", "").lower() == city.lower()
        ),
        None,
    )
    if match is None:
        available = [f.get("properties", {}).get("name") for f in features]
        raise ValueError(
            f"no geofencing zone matching {city!r}; available: {available}"
        )
    return match["geometry"]


def fetch_operator_zones(op: OperatorConfig) -> None:
    """Fetch each configured city's operating zone for one operator and write its seed."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    for city in op.cities:
        logger.info("fetching geofencing zone for %s / %s", op.name, city.city)
        client = GBFSClient(city.base_url, timeout=settings.REQUEST_TIMEOUT_SEC)
        data = client.fetch(_GEOFENCING_ENDPOINT)

        path = _zone_seed_path(op.name, city.city)
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["city", "geometry", "fetched_at"])
            writer.writeheader()
            writer.writerow(
                {
                    "city": city.city,
                    "geometry": json.dumps(_extract_zone(data, city.city)),
                    "fetched_at": fetched_at,
                }
            )
        logger.info("wrote zone for %s / %s to %s", op.name, city.city, path)


def main() -> None:
    operators = settings.operators
    if not operators:
        raise ValueError("no operators configured in operators.yaml")
    for op in operators:
        fetch_operator_zones(op)


if __name__ == "__main__":
    setup_logging()
    main()
