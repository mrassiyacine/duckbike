"""
Runs the full transform and publishes a slim, serving-ready DuckDB to R2
"""

import os
import subprocess
from pathlib import Path

import duckdb

from config import settings
from utils.logger import get_logger, setup_logging
from utils.r2_storage import R2Storage

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DBT_PROJECT_DIR = "transform/duckbike"


def run_dbt_build() -> None:
    """
    Build every dbt model into dev.duckdb
    """
    log.info("running dbt build")
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            [str(REPO_ROOT), os.environ.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep),
    }
    subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            DBT_PROJECT_DIR,
            "--profiles-dir",
            DBT_PROJECT_DIR,
        ],
        check=True,
        env=env,
    )


def assemble_serving_db(
    dev_db: str = settings.DEV_DB_PATH, serving_db: str = settings.SERVING_DB_PATH
) -> list[str]:
    """Copy every mart_* object from dev_db into a fresh marts-only serving DB (as tables)."""
    if os.path.exists(serving_db):
        os.remove(serving_db)

    con = duckdb.connect(serving_db)
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"ATTACH '{dev_db}' AS dev (READ_ONLY)")
    marts = [
        row[0]
        for row in con.execute(
            r"""
            SELECT table_name FROM information_schema.tables
            WHERE table_catalog = 'dev' AND table_name LIKE 'mart\_%' ESCAPE '\'
            ORDER BY table_name
            """
        ).fetchall()
    ]
    for mart in marts:
        con.execute(f'CREATE TABLE "{mart}" AS SELECT * FROM dev."{mart}"')
        log.info("copied %s", mart)
    con.execute("DETACH dev")
    con.close()
    log.info("assembled %s with %d marts", serving_db, len(marts))
    return marts


def publish_serving_db(
    serving_db: str = settings.SERVING_DB_PATH, key: str = settings.SERVING_DB_KEY
) -> None:
    """Upload the serving DB to the warehouse bucket, overwriting the published snapshot."""
    storage = R2Storage.for_bucket(settings.R2_WAREHOUSE_BUCKET)
    storage.upload_file(serving_db, key)
    log.info("uploaded %s to r2://%s/%s", serving_db, storage.bucket, key)


def main() -> None:
    setup_logging()
    run_dbt_build()
    assemble_serving_db()
    publish_serving_db()
    log.info("build-and-publish complete")


if __name__ == "__main__":
    main()
