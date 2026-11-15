"""
Module responsible handling counters for activities when generating titles and descriptions.

"""

import logging
import json
from const import COUNTERS_FILE

COUNTERS = {
    "total": 91,
    "lowerhutt": 86,
    "wellington": 2
    
}


def get_counters():
    """Returns the current counters."""
    if not COUNTERS_FILE.is_file():
        return dict()
    counters = {}
    with COUNTERS_FILE.open("r", encoding="utf8") as f:
        counters = json.load(f)
    return counters

def update_counters(counters: dict[str, int]) -> None:
    """Updates the counters file."""
    with COUNTERS_FILE.open("w", encoding="utf8") as f:
        json.dump(counters, f, indent=4)
