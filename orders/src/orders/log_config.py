from colorlog import ColoredFormatter
import logging


def setup_logger(name=__name__, log_level=logging.DEBUG):
    """
    Sets up a logger with color-coded output and optional file logging.
    :param name: Name of the logger.
    :param log_level: Logging level (default is DEBUG).
    :return: Configured logger.
    """
    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Define the log format
    LOG_FORMAT = "%(log_color)s%(levelname)-8s%(reset)s | %(message)s"
    LOG_COLORS = {
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    }

    # Create a color formatter
    color_formatter = ColoredFormatter(LOG_FORMAT, log_colors=LOG_COLORS)

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(color_formatter)

    # Add the console handler to the logger
    if not logger.hasHandlers():
        logger.addHandler(console_handler)

    return logger
