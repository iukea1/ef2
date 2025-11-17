#!/usr/bin/env python3
"""
Logging configuration for EF2 data extraction and validation

Provides centralized logging setup with:
- File and console output
- Log rotation
- Different log levels
- Structured formatting
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime

# Log directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Log levels
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


def setup_logging(
    name: str,
    level: str = 'INFO',
    log_to_file: bool = True,
    log_to_console: bool = True,
    max_bytes: int = 10*1024*1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Setup logging with file and console handlers

    Args:
        name: Logger name (usually script name)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Enable file logging
        log_to_console: Enable console logging
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance
    """

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))

    # Remove existing handlers
    logger.handlers = []

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # File handler with rotation
    if log_to_file:
        log_file = LOG_DIR / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(logging.DEBUG)  # File gets all levels
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(LOG_LEVELS.get(level.upper(), logging.INFO))
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)

    # Add initial log entry
    logger.info(f"Logger initialized: {name} (level={level})")
    logger.debug(f"Log file: {log_file if log_to_file else 'None'}")

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get or create logger with default settings"""
    return logging.getLogger(name) or setup_logging(name)


# Performance logging decorator
def log_performance(func):
    """Decorator to log function execution time"""
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()

        logger.debug(f"Starting {func.__name__}")

        try:
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.info(f"Completed {func.__name__} in {elapsed_time:.2f}s")
            return result
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Failed {func.__name__} after {elapsed_time:.2f}s: {str(e)}")
            raise

    return wrapper


# Context manager for logging blocks
class LogBlock:
    """Context manager for logging a block of code"""

    def __init__(self, logger: logging.Logger, message: str, level: str = 'INFO'):
        self.logger = logger
        self.message = message
        self.level = level
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.now()
        log_func = getattr(self.logger, self.level.lower())
        log_func(f"Starting: {self.message}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()

        if exc_type is None:
            self.logger.info(f"Completed: {self.message} ({elapsed:.2f}s)")
        else:
            self.logger.error(f"Failed: {self.message} ({elapsed:.2f}s) - {exc_val}")

        return False  # Don't suppress exceptions


# Example usage
if __name__ == "__main__":
    # Setup logger
    logger = setup_logging("test_logging", level="DEBUG")

    # Test different log levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Test performance decorator
    @log_performance
    def slow_function():
        import time
        time.sleep(1)
        return "Done"

    slow_function()

    # Test log block
    with LogBlock(logger, "Processing data block"):
        logger.info("Doing some work...")
        # Simulate work
        pass

    print(f"\nLog file created in: {LOG_DIR}")
