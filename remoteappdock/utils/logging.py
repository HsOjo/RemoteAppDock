"""日志配置。"""

import logging
import os


def configure_logging(level: int | None = None) -> None:
    if level is None:
        level_name = os.environ.get("RAD_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
