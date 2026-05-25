import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from utils.logger import get_logger

logger = get_logger(__name__)


class GBFSClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def fetch(self, endpoint: str) -> dict:
        url = f"{self.base_url}/{endpoint}"
        logger.info(f"Start fetching {url}")
        response = httpx.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
