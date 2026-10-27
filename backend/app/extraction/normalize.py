"""Deterministic normalisation helpers: dates/times, durations, numbers and currencies.

These never guess silently: functions return ``None`` when a value cannot be interpreted.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for m in names
}
_MONTH_RE = r"(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"

_TIME_RE = re.compile(
    r"(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?\s*(?P<ampm>a\.?m\.?|p\.?m\.?)|(?P<h24>\d{1,2})[:.](?P<m24>\d{2})(?:\s*(?:hrs|hours|h))?|(?P<hhmm>\d{4})\s*(?:hrs|hours)",
    re.IGNORECASE,
)

DATE_PATTERNS = [
    # 14 November 2026 / 14th Nov, 2026
    re.compile(rf"\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\s+{_MONTH_RE}\.?,?\s+(?P<y>\d{{4}})\b", re.IGNORECASE),
    # November 14, 2026
    re.compile(rf"\b{_MONTH_RE}\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<y>\d{{4}})\b", re.IGNORECASE),
    # 2026-11-14
    re.compile(r"\b(?P<y>\d{4})-(?P<mo>\d{1,2})-(?P<d>\d{1,2})\b"),
    # 14/11/2026, 14-11-2026, 14.11.2026 (day first)
    re.compile(r"\b(?P<d>\d{1,2})[/.\-](?P<mo>\d{1,2})[/.\-](?P<y>\d{4})\b"),
]


def find_date(text: str) -> tuple[date, tuple[int, int]] | None:
    """Return the first date in ``text`` and its character span."""
    best: tuple[date, tuple[int, int]] | None = None
    for pattern in DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        groups = m.groupdict()
        if groups.get("mo"):
            month: int | None = int(groups["mo"])
        else:
            name = (groups.get("mon") or "").lower()
            month = MONTHS.get(name) or MONTHS.get(name[:3])
        if month is None:
            continue
        try:
            d = date(int(groups["y"]), month, int(groups["d"]))
        except (ValueError, KeyError, TypeError):
            continue
        if best is None or m.start() < best[1][0]:
            best = (d, m.span())
    return best


def find_time(text: str) -> tuple[int, int] | None:
    m = _TIME_RE.search(text)
    if not m:
        return None
    try:
        if m.group("ampm"):
            h = int(m.group("h"))
            minute = int(m.group("m") or 0)
            if not 1 <= h <= 12:
                return None
            pm = m.group("ampm").lower().startswith("p")
            h = (h % 12) + (12 if pm else 0)
        elif m.group("h24"):
            h, minute = int(m.group("h24")), int(m.group("m24"))
        else:
            hhmm = m.group("hhmm")
            h, minute = int(hhmm[:2]), int(hhmm[2:])
    except (TypeError, ValueError):
        return None
    if 0 <= h <= 23 and 0 <= minute <= 59:
        return h, minute
    return None


def normalize_datetime(text: str) -> str | None:
    """'14 November 2026, 11:00 AM' -> '2026-11-14T11:00'; date-only -> '2026-11-14'."""
    found = find_date(text)
    if not found:
        return None
    d, span = found
    rest = text[span[1] :]
    t = find_time(rest[:40]) or find_time(text[: span[0]][-25:])
    if t:
        return datetime(d.year, d.month, d.day, t[0], t[1]).strftime("%Y-%m-%dT%H:%M")
    return d.isoformat()


NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "forty-five": 45,
    "forty five": 45,
    "fifty": 50,
    "sixty": 60,
    "ninety": 90,
    "hundred": 100,
    "a": 1,
    "an": 1,
}
_DURATION_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty[- ]five|forty|fifty|sixty|ninety|a|an)"
    r"(?:\s*\(\s*\d+\s*\))?\s*(?:working\s+|calendar\s+|business\s+)?(?P<unit>days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def duration_days(text: str) -> int | None:
    """'Within 45 days of PO' -> 45; 'one (1) year' -> 365; returns None when no duration is present."""
    m = _DURATION_RE.search(text or "")
    if not m:
        return None
    raw = m.group("num").lower().replace("-", " ")
    try:
        num = float(raw) if raw[0].isdigit() else float(NUMBER_WORDS[raw])
    except (KeyError, ValueError):
        return None
    unit = m.group("unit").lower().rstrip("s")
    return int(round(num * _UNIT_DAYS[unit]))


_NUM_RE = re.compile(r"^[^\d\-]*?(-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)")


def parse_decimal(value: object) -> Decimal | None:
    """Parse '1,250.50', 'Rs. 4,500', '4500.0', 4500 -> Decimal. Returns None for non-numbers."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = str(value).strip()
    if not text:
        return None
    m = _NUM_RE.match(text)
    if not m:
        return None
    try:
        return Decimal(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None


_QTY_RE = re.compile(r"^\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([A-Za-z][A-Za-z.\- ]{0,20})?\s*$")


def parse_quantity(text: str) -> tuple[Decimal | None, str | None]:
    """'4' -> (4, None); '6 Boxes' -> (6, 'Boxes'); 'As required' -> (None, None)."""
    m = _QTY_RE.match(text or "")
    if not m:
        return None, None
    try:
        qty = Decimal(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None, None
    unit = m.group(2).strip() if m.group(2) else None
    return qty, unit


CURRENCY_WORDS = {
    "PKR": ("pkr", "pak rupee", "pakistani rupee", "pakistan rupee", "rs", "rupees"),
    "USD": ("usd", "us dollar", "u.s. dollar", "us$"),
    "EUR": ("eur", "euro"),
    "GBP": ("gbp", "pound sterling", "british pound"),
    "AED": ("aed", "dirham"),
    "SAR": ("sar", "saudi riyal"),
    "CNY": ("cny", "rmb", "yuan", "renminbi"),
    "INR": ("inr", "indian rupee"),
    "BHD": ("bhd", "bahraini dinar"),
    "QAR": ("qar", "qatari riyal"),
}

SUPPORTED_CURRENCIES = tuple(CURRENCY_WORDS.keys())


def detect_currency(text: str) -> str | None:
    t = f" {text.lower()} "
    # Prefer explicit ISO codes, then names. "rupees" alone is ambiguous (PKR/INR/...), so it maps to PKR
    # only when no other code is present; the user must still confirm the currency explicitly.
    for code in CURRENCY_WORDS:
        if re.search(rf"\b{code.lower()}\b", t):
            return code
    for code, words in CURRENCY_WORDS.items():
        for w in words:
            if len(w) > 3 and w in t:
                return code
    return None
