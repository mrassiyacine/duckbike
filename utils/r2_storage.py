import io

import pyarrow as pa
import pyarrow.parquet as pq


class R2Storage:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

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
