from datetime import datetime

import pyarrow as pa
from pydantic import BaseModel

from config import CityEndpoint
from utils.logger import get_logger
from utils.r2_storage import R2Storage

logger = get_logger(__name__)


def _resolve_key(snapshot_ts: datetime, operator: str, city: CityEndpoint) -> str:
    """{operator}/{city}/2025/05/15/1748843869.parquet"""
    unix_ts = int(snapshot_ts.timestamp())

    return (
        f"{operator}/"
        f"{city.city}/"
        f"{snapshot_ts.year}/"
        f"{snapshot_ts.month:02d}/"
        f"{snapshot_ts.day:02d}/"
        f"{unix_ts}.parquet"
    )


def write_snapshot(
    rows: list[BaseModel],
    operator: str,
    city: CityEndpoint,
    storage: R2Storage,
) -> None:
    if not rows:
        logger.warning("no rows to write; skipping")
        return

    snapshot_ts = rows[0].snapshot_ts

    key = _resolve_key(snapshot_ts, operator, city)

    table = pa.Table.from_pylist([row.model_dump() for row in rows])

    storage.write_parquet(key, table)

    logger.info(f"wrote {len(rows)} rows to r2://{storage.bucket}/{key}")
