"""Locale-tolerant number and date parsing for statement files.

Statements arrive in whatever format the bank/country uses:
  US / IN : 1,234.56   dd/mm/yy or mm/dd/yyyy
  EU (DE) : 1.234,56   dd.mm.yyyy
"""

from __future__ import annotations

import re
from datetime import datetime

_NUM = re.compile(r"-?[\d.,\s]+")


def parse_amount(value) -> float:
    """Best-effort parse of a monetary string in any common locale."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(" ", " ").replace(" ", "")
    s = s.replace("₹", "").replace("$", "").replace("€", "").replace("£", "")
    s = s.replace("INR", "").replace("USD", "").replace("EUR", "").strip()
    if not s or s in ("-", "--"):
        return 0.0
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()-")

    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        # the rightmost separator is the decimal point
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "").replace(dec, ".")
    elif has_comma:
        # comma is decimal only if it looks like ...,dd  at the very end
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    # else: only dots or plain digits -> assume '.' is the decimal point
    try:
        n = float(s)
    except ValueError:
        return 0.0
    return -n if neg else n


_DATE_FORMATS = (
    "%d/%m/%y", "%d/%m/%Y", "%m/%d/%Y", "%m/%d/%y",
    "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d.%m.%y",
    "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d",
)


def parse_date(value, prefer: str = "dmy") -> datetime | None:
    """Parse a date string. `prefer` = 'dmy' or 'mdy' disambiguates 03/04/2026."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()[:10].strip()
    order = ("%d/%m/%Y", "%d/%m/%y") if prefer == "dmy" else ("%m/%d/%Y", "%m/%d/%y")
    for fmt in (*order, *[f for f in _DATE_FORMATS if f not in order]):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None
