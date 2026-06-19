import os

import boto3
import duckdb
import streamlit as st

# The serving DB is published to R2 by transform/build_and_publish.py. We download it to
# the container's local disk once, then query that local copy read-only. Credentials come
# from st.secrets on Streamlit Community Cloud, falling back to env vars for local runs.
_LOCAL_PATH = "/tmp/serving.duckdb"


def _secret(key: str, default: str | None = None) -> str:
    """Read an R2 setting from st.secrets, falling back to the environment."""
    try:
        return st.secrets[key]
    except Exception:
        pass
    value = os.environ.get(key, default)
    if value is None:
        raise KeyError(
            f"missing R2 setting {key!r}: set it in st.secrets or the environment"
        )
    return value


@st.cache_resource(ttl=3600)
def _serving_db_path() -> str:
    """Download the published serving DB from R2 once per container (re-checked hourly)."""
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{_secret('S3_ENDPOINT')}",
        aws_access_key_id=_secret("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_secret("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )
    bucket = _secret("R2_WAREHOUSE_BUCKET", "duckbike-warehouse")
    key = _secret("SERVING_DB_KEY", "serving.duckdb")
    client.download_file(bucket, key, _LOCAL_PATH)
    return _LOCAL_PATH


@st.cache_resource
def _ensure_spatial_installed() -> bool:
    """INSTALL the spatial extension once per container. It persists to DuckDB's
    extension directory on local disk, so the per-connection LOAD below is a fast,
    network-free read rather than a fresh download on every query."""
    duckdb.execute("INSTALL spatial;")
    return True


def get_connection():
    _ensure_spatial_installed()
    con = duckdb.connect(_serving_db_path(), read_only=True)
    con.execute("LOAD spatial;")
    return con
