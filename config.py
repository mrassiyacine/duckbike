from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class CityEndpoint(BaseModel):
    city: str
    base_url: str
    vehicle_status_endpoint: str


class OperatorConfig(BaseModel):
    name: str
    parser: str
    cities: list[CityEndpoint]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Polling
    POLL_INTERVAL_SEC: int = 80
    REQUEST_TIMEOUT_SEC: int = 10
    MAX_RETRIES: int = 3

    # storage
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    S3_ENDPOINT: str
    R2_BUCKET: str = "gbfs-raw-data"
    R2_WAREHOUSE_BUCKET: str = "duckbike-warehouse"

    H3_RESOLUTION: int = 9

    DEV_DB_PATH: str = "dev.duckdb"
    SERVING_DB_PATH: str = "serving.duckdb"
    SERVING_DB_KEY: str = "serving.duckdb"

    OPERATORS_FILE: str = "operators.yaml"

    @property
    def operators(self) -> list[OperatorConfig]:
        path = Path(self.OPERATORS_FILE)
        if not path.exists():
            return []
        with open(path) as f:
            data = yaml.safe_load(f)
        return [OperatorConfig(**op) for op in data.get("operators", [])]


settings = Settings()
