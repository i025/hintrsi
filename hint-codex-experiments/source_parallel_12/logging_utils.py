import logging
import os
from pathlib import Path
from typing import Optional
from tqdm import tqdm


class TqdmLoggingHandler(logging.Handler):
    def emit(self, record):
        try:
            tqdm.write(self.format(record))
            self.flush()
        except Exception:
            self.handleError(record)


_CONFIGURED_LOG_FILE: Optional[Path] = None

def setup_logging(log_file: str = "execution_volume.log"):
    global _CONFIGURED_LOG_FILE

    log_path = Path(log_file).expanduser()
    root_logger = logging.getLogger()
    if _CONFIGURED_LOG_FILE == log_path and root_logger.hasHandlers():
        return root_logger

    root_logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'
    )

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    tqdm_handler = TqdmLoggingHandler()
    tqdm_handler.setFormatter(formatter)
    root_logger.addHandler(tqdm_handler)

    for module in ["litellm", "urllib3", "docker", "httpcore", "httpx", "openai"]:
        logger = logging.getLogger(module)
        logger.setLevel(logging.ERROR)
        logger.propagate = False

    _CONFIGURED_LOG_FILE = log_path
    return root_logger

