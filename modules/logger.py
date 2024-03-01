"""Logger module

A custom logger for the application
"""

import logging

# region Module info

__all__ = ["get_logger"]
__version__ = "1.0"
__author__ = "Davide Tarpini"


# endregion


# region Module functions

def get_logger(name: str, filename: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s "
                                  "- %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(filename)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# endregion
