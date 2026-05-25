from datetime import datetime, timezone

import h3
from pydantic import BaseModel, field_validator

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class Vehicle(BaseModel):
    bike_id: str
    lat: float
    lon: float
    current_fuel_percent: float
    current_range_meters: float
    is_disabled: bool
    is_reserved: bool
    last_reported: int
    vehicle_type_id: str
    pricing_plan_id: str | None

    @field_validator("bike_id")
    @classmethod
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("bike_id cannot be empty")
        return v


class SnapshotRow(BaseModel):
    bike_id: str
    last_reported: datetime
    lat: float
    lon: float
    battery_pct: float
    range_km: float
    is_disabled: bool
    is_reserved: bool
    h3_index: str
    snapshot_ts: datetime


def parse_snapshot(raw: dict) -> list[SnapshotRow]:
    snapshot_ts = datetime.now(tz=timezone.utc)
    rows = []
    for bike_raw in raw["data"]["bikes"]:
        try:
            bike = Vehicle(**bike_raw)
            rows.append(
                SnapshotRow(
                    bike_id=bike.bike_id,
                    lat=bike.lat,
                    lon=bike.lon,
                    battery_pct=bike.current_fuel_percent,
                    range_km=bike.current_range_meters / 1000,
                    is_disabled=bike.is_disabled,
                    is_reserved=bike.is_reserved,
                    last_reported=datetime.fromtimestamp(
                        bike.last_reported, tz=timezone.utc
                    ),
                    h3_index=h3.latlng_to_cell(
                        bike.lat, bike.lon, settings.H3_RESOLUTION
                    ),
                    snapshot_ts=snapshot_ts,
                )
            )
        except Exception as e:
            logger.warning(f"skipping bike {bike_raw.get('bike_id')}: {e}")

    logger.info(f"parsed {len(rows)} / {len(raw['data']['bikes'])} vehicles")
    return rows
