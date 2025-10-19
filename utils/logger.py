import logging
import os

def get_logger(name=__name__):
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(name)

    # Avoid duplicate handlers on cold start reuse
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
        ))
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger

__all__ = ["get_logger"]
