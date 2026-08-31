"""Real-world statement format parsers.

Each parser turns one export file into a list of ``NormalizedTxn``. Use
``detect_and_parse(path, batch_id)`` to sniff the format and dispatch.
"""

from .detect import detect_and_parse, detect_format

__all__ = ["detect_and_parse", "detect_format"]
