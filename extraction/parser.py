import importlib

from pydantic import BaseModel

from config import OperatorConfig
from utils.logger import get_logger

logger = get_logger(__name__)


def parse_snapshot(raw: dict, op: OperatorConfig) -> list[BaseModel]:
    module = importlib.import_module(f"extraction.operators.{op.parser}")
    return module.parse_snapshot(raw)
