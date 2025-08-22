import logging
from datetime import datetime


def setup_logging(level="INFO", output_dir="../logs"):
    """
    Set up logging configuration for the application.

    :param str level: The logging level to use. Acceptable values are "INFO", "DEBUG", "WARN", and "ERROR". Defaults to "INFO".
    :param str output_dir: Directory where log files will be saved. Defaults to "../logs".
    :raises ValueError: If an invalid logging level is provided.

    This function configures the root logger to write logs to a file in the specified output directory,
    with the filename based on the current date and time. The log format includes the timestamp,
    logger name, log level, and message.
    """
    import os

    level_map = {
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR
    }
    if level not in level_map:
        raise ValueError(f"Invalid logging level: {level}")

    os.makedirs(output_dir, exist_ok=True)
    log_filename = os.path.join(
        output_dir, f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    )
    logging.basicConfig(
        level=level_map[level],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=log_filename,
        filemode='x',
        force=True
    )
    logging.info("Logging initialized.")
