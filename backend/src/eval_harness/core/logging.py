from __future__ import annotations

import logging

from rich.logging import RichHandler


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s", handlers=[RichHandler(show_path=False)], force=True)
    for noisy in ("httpx", "httpcore", "urllib3", "langsmith"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
