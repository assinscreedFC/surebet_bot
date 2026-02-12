# Logging avec rotation quotidienne

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import sys

def setup_logger(log_file: Path, level: int = logging.INFO) -> logging.Logger:
    """Configure le logger avec rotation quotidienne."""
    
    logger = logging.getLogger("surebet_bot")
    logger.setLevel(level)
    
    # Format
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Handler fichier avec rotation quotidienne
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,  # Garde 30 jours
        encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Ajouter les handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Logger global
_logger = None

def get_logger() -> logging.Logger:
    """Retourne le logger global."""
    global _logger
    if _logger is None:
        from config import LOG_FILE
        _logger = setup_logger(LOG_FILE)
    return _logger
