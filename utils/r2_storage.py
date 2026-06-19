import io

import boto3
import pyarrow as pa
import pyarrow.parquet as pq

from config import settings


def make_r2_client():
    """Build an S3 client pointed at the Cloudflare R2 endpoint from settings."""
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.S3_ENDPOINT}",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


class R2Storage:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    @classmethod
    def for_bucket(cls, bucket: str) -> "R2Storage":
        """Construct an R2Storage with a fresh client for the given bucket."""
        return cls(make_r2_client(), bucket)

    def write_parquet(self, key: str, table: pa.Table):
        """
        Write a PyArrow table to R2 as a compressed Parquet file.

        The data is serialized in-memory and uploaded directly to R2.

        Args:
            key (str): Object key (path inside the bucket, e.g.
                "dott/paris/2025/05/15/1748843869.parquet")
            table (pa.Table): PyArrow table containing structured data.
        """
        buffer = io.BytesIO()
        pq.write_table(
            table,
            buffer,
            compression="zstd",
        )

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=buffer.getvalue(),
        )

    def write_bytes(self, key: str, data: bytes):
        """Upload raw bytes to R2 under ``key``."""
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def read_bytes(self, key: str) -> bytes:
        """Download the object at ``key`` from R2 and return its bytes."""
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def upload_file(self, path: str, key: str):
        """Upload a local file to R2 under ``key`` (multipart for large files)."""
        self.client.upload_file(path, self.bucket, key)
