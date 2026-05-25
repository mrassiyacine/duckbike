from datetime import datetime, timezone

import boto3

from config import CityEndpoint, OperatorConfig, settings
from extraction.gbfs_client import GBFSClient
from extraction.parser import parse_snapshot
from extraction.writer import write_snapshot
from utils.logger import get_logger
from utils.r2_storage import R2Storage

logger = get_logger(__name__)


def run_extraction(op: OperatorConfig, city: CityEndpoint, storage: R2Storage) -> None:
    """
    Execute a single GBFS extraction pipeline:
    fetch -> parse -> persist to R2
    """
    run_ts = datetime.now(timezone.utc)
    logger.info(f"extracting {op.name} / {city.city}")
    client = GBFSClient(city.base_url, timeout=settings.REQUEST_TIMEOUT_SEC)
    raw = client.fetch(city.vehicle_status_endpoint)
    rows = parse_snapshot(raw, op)
    write_snapshot(rows, op.name, city, storage)


def main():
    logger.info("starting GBFS ingestion pipeline")

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )

    storage = R2Storage(client, settings.R2_BUCKET)

    for op in settings.operators:
        for city in op.cities:
            try:
                run_extraction(op, city, storage)

            except Exception as e:
                logger.exception(
                    "extraction failed",
                    extra={
                        "operator": op.name,
                        "city": city.city,
                        "error": str(e),
                    },
                )

    logger.info("pipeline finished")


if __name__ == "__main__":
    main()
