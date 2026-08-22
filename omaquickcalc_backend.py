#!/usr/bin/env python3
"""Structured, shell-free evaluator for OmaQuickCalc."""

from __future__ import annotations

import argparse
import colorsys
import json
import locale
import math
import os
import re
import resource
import selectors
import subprocess
import sys
import unicodedata
from calendar import monthrange
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
from time import monotonic
from zoneinfo import ZoneInfo, available_timezones

import omaquickcalc_tax as tax_engine


@dataclass
class Evaluation:
    ok: bool
    result: str = ""
    rawResult: str = ""
    error: str = ""
    kind: str = "math"
    normalizedExpression: str = ""
    swapExpression: str = ""
    dynamic: bool = False
    colorHex: str = ""
    formats: list[dict[str, str]] = field(default_factory=list)
    rateDate: str = ""
    rateSource: str = ""
    rateAgeDays: int = -1
    rateStale: bool = False
    note: str = ""
    pending: bool = False
    report: dict[str, object] = field(default_factory=dict)


EASTER_EGGS = {
    "quattro": ("4", "Fast by design."),
    "euler": ("2.718281828459045", "eⁱπ + 1 = 0"),
    "fibonacci": ("1, 1, 2, 3, 5, 8, 13, 21", "The pattern continues."),
    "gauss": ("5050", "Pair the ends."),
    "ramanujan": ("1729", "1³ + 12³ = 9³ + 10³"),
    "dhh": ("37", "Convention over configuration."),
}

DEFAULT_CLOCK_FORMAT = "12"

MAX_EXPRESSION_LENGTH = 4096
MAX_QALC_STDOUT_BYTES = 64 * 1024
MAX_QALC_STDERR_BYTES = 16 * 1024
MAX_QALC_MEMORY_BYTES = 256 * 1024 * 1024
MAX_RESULT_TEXT_BYTES = 16 * 1024
MAX_ERROR_TEXT_CHARS = 4096
MAX_FORMAT_VALUE_CHARS = 4096
MAX_INTEGER_FORMAT_DECIMAL_EXPONENT = 1000
MAX_FRACTION_DIGITS = 512
MAX_EVALUATION_JSON_BYTES = 128 * 1024
MAX_BATCH_JSON_BYTES = 512 * 1024


class QalcOutputLimitError(RuntimeError):
    """Raised after terminating qalc for exceeding a captured-stream limit."""


def _limit_qalc_address_space() -> None:
    """Apply a child-only address-space ceiling before qalc starts."""
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_AS)
    desired_limit = MAX_QALC_MEMORY_BYTES
    if hard_limit != resource.RLIM_INFINITY:
        desired_limit = min(desired_limit, hard_limit)
    if soft_limit == resource.RLIM_INFINITY or soft_limit > desired_limit:
        resource.setrlimit(resource.RLIMIT_AS, (desired_limit, hard_limit))


def _run_qalc_bounded(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """Run a direct argv command while bounding both captured pipes and child memory."""
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=_limit_qalc_address_space,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, (bytearray(), MAX_QALC_STDOUT_BYTES))
    selector.register(process.stderr, selectors.EVENT_READ, (bytearray(), MAX_QALC_STDERR_BYTES))
    buffers = {
        process.stdout: selector.get_key(process.stdout).data[0],
        process.stderr: selector.get_key(process.stderr).data[0],
    }
    deadline = monotonic() + timeout

    try:
        while selector.get_map():
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            events = selector.select(remaining)
            if not events:
                raise subprocess.TimeoutExpired(command, timeout)
            for key, _ in events:
                stream = key.fileobj
                buffer, byte_limit = key.data
                chunk = os.read(stream.fileno(), min(65_536, byte_limit - len(buffer) + 1))
                if not chunk:
                    selector.unregister(stream)
                    continue
                buffer.extend(chunk)
                if len(buffer) > byte_limit:
                    raise QalcOutputLimitError("qalc output exceeded its byte limit")

        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(command, timeout)
        return_code = process.wait(timeout=remaining)
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()

    return subprocess.CompletedProcess(
        command,
        return_code,
        buffers[process.stdout].decode("utf-8", errors="replace"),
        buffers[process.stderr].decode("utf-8", errors="replace"),
    )


ZONE_ALIASES = {
    "ldn": "Europe/London",
    "london": "Europe/London",
    "sf": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles",
    "la": "America/Los_Angeles",
    "los angeles": "America/Los_Angeles",
    "nyc": "America/New_York",
    "new york": "America/New_York",
    "jfk": "America/New_York",
    "tokyo": "Asia/Tokyo",
    "paris": "Europe/Paris",
    "berlin": "Europe/Berlin",
    "winnipeg": "America/Winnipeg",
    "chicago": "America/Chicago",
    "denver": "America/Denver",
    "vancouver": "America/Vancouver",
    "pacific": "America/Vancouver",
    "pacific time": "America/Vancouver",
    "pt": "America/Vancouver",
    "toronto": "America/Toronto",
    "sao paulo": "America/Sao_Paulo",
    "são paulo": "America/Sao_Paulo",
    "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne",
    "singapore": "Asia/Singapore",
    "hong kong": "Asia/Hong_Kong",
    "dubai": "Asia/Dubai",
    "utc": "UTC",
    "gmt": "UTC",
}

FIXED_ZONE_ALIASES = {
    "pdt": timezone(timedelta(hours=-7), "PDT"),
    "pst": timezone(timedelta(hours=-8), "PST"),
}

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

SUSPICIOUS_OUTPUT_TOKENS = ("bit", "Pa", "pg", "B²", "m⁴", "root()", "pow(", "rem(")
CURRENCY_CODES = {
    "AED", "AUD", "BGN", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR", "GBP", "HKD",
    "HUF", "IDR", "ILS", "INR", "ISK", "JPY", "KRW", "MXN", "MYR", "NOK",
    "NZD", "PHP", "PLN", "RON", "SEK", "SGD", "THB", "TRY", "USD", "ZAR",
    "BTC", "ETH",
}
DOLLAR_CURRENCIES = {"AUD", "CAD", "HKD", "NZD", "SGD", "USD"}
BARE_MATH_CONSTANTS = {"e", "pi", "phi", "tau"}
CURRENCY_ALIASES = {
    "a$": "AUD", "aussie": "AUD", "australian": "AUD",
    "real": "BRL", "reais": "BRL", "brazilian": "BRL",
    "c$": "CAD", "canadian": "CAD", "loonie": "CAD",
    "franc": "CHF", "francs": "CHF", "swiss": "CHF",
    "rmb": "CNY", "yuan": "CNY", "renminbi": "CNY", "chinese": "CNY",
    "koruna": "CZK", "czech": "CZK",
    "kr": "DKK", "kroner": "DKK", "krone": "DKK", "dkr": "DKK", "danish": "DKK",
    "€": "EUR", "euro": "EUR", "euros": "EUR",
    "£": "GBP", "pound": "GBP", "pounds": "GBP", "quid": "GBP", "sterling": "GBP", "british": "GBP",
    "hk$": "HKD", "forint": "HUF", "rupiah": "IDR",
    "₪": "ILS", "shekel": "ILS", "shekels": "ILS",
    "₹": "INR", "rupee": "INR", "rupees": "INR",
    "¥": "JPY", "yen": "JPY", "japanese": "JPY",
    "₩": "KRW", "won": "KRW", "korean": "KRW",
    "peso": "MXN", "pesos": "MXN", "mexican": "MXN",
    "ringgit": "MYR", "nkr": "NOK", "norwegian": "NOK",
    "kiwi": "NZD", "₱": "PHP", "philippine": "PHP",
    "zloty": "PLN", "zł": "PLN", "polish": "PLN",
    "leu": "RON", "lei": "RON", "romanian": "RON",
    "skr": "SEK", "swedish": "SEK", "s$": "SGD",
    "฿": "THB", "baht": "THB", "₺": "TRY", "lira": "TRY", "turkish": "TRY",
    "$": "USD", "dollar": "USD", "dollars": "USD", "buck": "USD", "bucks": "USD",
    "us dollar": "USD", "us dollars": "USD", "american": "USD",
    "rand": "ZAR", "bitcoin": "BTC", "ethereum": "ETH", "ether": "ETH",
}


def clean_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    return " ".join("".join(c for c in normalized if not unicodedata.combining(c)).replace("_", " ").split())


def easter_egg_evaluation(expression: str) -> Evaluation | None:
    name = clean_name(expression)
    egg = EASTER_EGGS.get(name)
    if egg is None:
        return None
    result, note = egg
    return Evaluation(True, result, result, kind="easter-egg",
                      normalizedExpression=name, note=note)


def local_zone() -> tzinfo:
    return datetime.now().astimezone().tzinfo


def resolve_zone(value: str) -> tzinfo | None:
    key = clean_name(value)
    if key in {"local", "local time", "here"}:
        return local_zone()
    fixed = FIXED_ZONE_ALIASES.get(key)
    if fixed:
        return fixed
    direct = ZONE_ALIASES.get(key)
    if direct:
        return ZoneInfo(direct)
    if value in available_timezones():
        return ZoneInfo(value)
    matches = [zone for zone in available_timezones() if clean_name(zone.rsplit("/", 1)[-1]) == key]
    if len(matches) == 1:
        return ZoneInfo(matches[0])
    return None


def format_number(value: float, precision: int = 10) -> str:
    if math.isclose(value, round(value), abs_tol=10 ** -(precision - 1)):
        return str(int(round(value)))
    return f"{value:.{precision}g}"


def uses_24_hour_clock(clock_format: str) -> bool:
    if clock_format == "24":
        return True
    if clock_format == "12":
        return False
    try:
        pattern = locale.nl_langinfo(locale.T_FMT)
        return "%H" in pattern or "%R" in pattern or "%T" in pattern
    except (AttributeError, ValueError):
        return False


def format_clock(value: datetime, clock_format: str) -> str:
    return value.strftime("%H:%M" if uses_24_hour_clock(clock_format) else "%-I:%M %p")


def format_datetime(value: datetime, clock_format: str = "auto") -> str:
    return f"{format_clock(value, clock_format)} · {value.strftime('%a, %b %-d')} · {value.strftime('%Z')}"


def format_timezone_conversion(source: datetime, target: datetime,
                               clock_format: str = "auto") -> str:
    clock = format_clock(target, clock_format)
    zone = target.strftime("%Z")
    if source.date() == target.date():
        return f"{clock} {zone}"
    return f"{clock} · {target.strftime('%a, %b %-d')} · {zone}"


def parse_clock(value: str) -> time | None:
    compact = value.strip().lower().replace(" ", "")
    for pattern in ("%I:%M%p", "%I%p", "%H:%M"):
        try:
            return datetime.strptime(compact, pattern).time()
        except ValueError:
            continue
    return None


def timezone_evaluation(expression: str, clock_format: str = "auto") -> Evaluation | None:
    text = expression.strip()

    match = re.fullmatch(r"time\s+in\s+([+-]?\d+(?:\.\d+)?)\s+hours?(?:\s+in\s+(.+))?", text, re.I)
    if match:
        hours = float(match.group(1))
        zone = resolve_zone(match.group(2)) if match.group(2) else datetime.now().astimezone().tzinfo
        if zone is None:
            return Evaluation(False, error=f"Unknown timezone: {match.group(2)}", kind="timezone")
        value = datetime.now(zone) + timedelta(hours=hours)
        return Evaluation(True, format_datetime(value, clock_format), value.isoformat(timespec="minutes"), kind="timezone", dynamic=True)

    match = re.fullmatch(r"(?:time\s+)?diff(?:erence)?\s+(.+)", text, re.I)
    if match:
        target = resolve_zone(match.group(1))
        if target is None:
            return Evaluation(False, error=f"Unknown timezone: {match.group(1)}", kind="timezone")
        now = datetime.now(timezone.utc)
        local = now.astimezone()
        there = now.astimezone(target)
        difference = (there.utcoffset() - local.utcoffset()).total_seconds() / 3600
        direction = "ahead" if difference >= 0 else "behind"
        hours = format_number(abs(difference))
        label = clean_name(match.group(1)).title()
        return Evaluation(True, f"{label} is {hours} hours {direction}", format_number(difference), kind="timezone", dynamic=True)

    match = re.fullmatch(r"time\s+in\s+(.+)", text, re.I)
    if match:
        zone = resolve_zone(match.group(1))
        if zone is None:
            return Evaluation(False, error=f"Unknown timezone: {match.group(1)}", kind="timezone")
        value = datetime.now(zone)
        return Evaluation(True, format_datetime(value, clock_format), value.strftime("%H:%M"), kind="timezone", dynamic=True)

    match = re.fullmatch(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})\s+(.+?)\s+in\s+(.+)", text, re.I)
    if match:
        clock = parse_clock(match.group(1))
        source = resolve_zone(match.group(2))
        target = resolve_zone(match.group(3))
        if clock is None or source is None or target is None:
            return Evaluation(False, error="Use a known source and destination timezone", kind="timezone")
        source_value = datetime.combine(datetime.now(source).date(), clock, source)
        value = source_value.astimezone(target)
        return Evaluation(True, format_timezone_conversion(source_value, value, clock_format),
                          value.strftime("%H:%M"), kind="timezone", dynamic=True)

    match = re.fullmatch(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})\s+(.+)", text, re.I)
    if match:
        clock = parse_clock(match.group(1))
        source = resolve_zone(match.group(2))
        if clock is not None and source is not None:
            target = local_zone()
            source_value = datetime.combine(datetime.now(source).date(), clock, source)
            value = source_value.astimezone(target)
            return Evaluation(True, format_timezone_conversion(source_value, value, clock_format),
                              value.strftime("%H:%M"), kind="timezone", dynamic=True)

    return None


def parse_month_day(value: str, today: date) -> date | None:
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)|([A-Za-z]+)\s+(\d{1,2})(?:,?\s+(\d{4}))?", value.strip())
    if not match:
        return None
    if match.group(1):
        day, month_name, year_text = int(match.group(1)), match.group(2), None
    else:
        month_name, day, year_text = match.group(3), int(match.group(4)), match.group(5)
    month = MONTHS.get(month_name.lower())
    if not month:
        return None
    year = int(year_text) if year_text else today.year
    try:
        result = date(year, month, day)
    except ValueError:
        return None
    if not year_text and result < today:
        result = result.replace(year=year + 1)
    return result


def date_evaluation(expression: str, clock_format: str = "auto") -> Evaluation | None:
    text = expression.strip()
    today = date.today()

    match = re.fullmatch(r"(" + "|".join(WEEKDAYS) + r")\s+in\s+(\d+)\s+weeks?", text, re.I)
    if match:
        target = WEEKDAYS[match.group(1).lower()]
        weeks = int(match.group(2))
        days_to_target = (target - today.weekday()) % 7
        if days_to_target == 0:
            days_to_target = 7
        result = today + timedelta(days=days_to_target + max(0, weeks - 1) * 7)
        return Evaluation(True, result.strftime("%A, %B %-d, %Y"), result.isoformat(), kind="date", dynamic=True)

    match = re.fullmatch(r"days\s+until\s+(.+)", text, re.I)
    if match:
        target = parse_month_day(match.group(1), today)
        if target is None:
            return Evaluation(False, error="Use a date such as 31 Mar", kind="date")
        days = (target - today).days
        return Evaluation(True, f"{days} days", str(days), kind="date", dynamic=True)

    match = re.fullmatch(r"(.+?)\s*\+\s*(\d+)\s*(?:days?)?", text, re.I)
    if match:
        base = parse_month_day(match.group(1), today)
        if base is not None:
            result = base + timedelta(days=int(match.group(2)))
            return Evaluation(True, result.strftime("%A, %B %-d, %Y"), result.isoformat(), kind="date")

    match = re.fullmatch(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})\s*\+\s*(\d+(?:\.\d+)?)", text, re.I)
    if match:
        clock = parse_clock(match.group(1))
        if clock:
            base = datetime.combine(today, clock).astimezone()
            result = base + timedelta(hours=float(match.group(2)))
            return Evaluation(True, format_clock(result, clock_format), result.strftime("%H:%M"), kind="time")

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?Z", text):
        try:
            parsed = datetime.fromisoformat(text[:-1] + "+00:00").astimezone()
            return Evaluation(True, format_datetime(parsed, clock_format), parsed.isoformat(timespec="seconds"), kind="timezone")
        except ValueError:
            return Evaluation(False, error="Invalid ISO 8601 timestamp", kind="date")

    return None


def design_evaluation(expression: str, rem_px: float, workday_hours: float) -> Evaluation | None:
    text = expression.strip()

    # Bare design units are intentionally opinionated. Qalculate otherwise
    # interprets `rem` as radiation dose and short partial suffixes as
    # scientific constants, which is surprising in a live design calculator.
    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*rem", text, re.I)
    if match:
        rem = float(match.group(1))
        pixels = rem * rem_px
        return Evaluation(True, f"{format_number(pixels)} px", format_number(pixels),
                          kind="design",
                          swapExpression=f"{format_number(pixels)} px in rem")

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*px", text, re.I)
    if match:
        pixels = float(match.group(1))
        rem = pixels / rem_px
        return Evaluation(True, f"{format_number(rem)} rem", format_number(rem),
                          kind="design",
                          swapExpression=f"{format_number(rem)} rem in px")

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*cm", text, re.I)
    if match:
        centimeters = float(match.group(1))
        inches = centimeters / 2.54
        return Evaluation(True, f"{format_number(inches)} in", format_number(inches),
                          kind="unit",
                          swapExpression=f"{format_number(inches)} in to cm")

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(?:in|inch|inches)", text, re.I)
    if match:
        inches = float(match.group(1))
        centimeters = inches * 2.54
        return Evaluation(True, f"{format_number(centimeters)} cm", format_number(centimeters),
                          kind="unit",
                          swapExpression=f"{format_number(centimeters)} cm to in")

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(?:in|inch|inches)\s+in\s+px(?:\s+at\s+([+-]?\d+(?:\.\d+)?)\s*ppi)?", text, re.I)
    if match:
        inches = float(match.group(1))
        ppi = float(match.group(2) or 96)
        pixels = inches * ppi
        result = f"{format_number(pixels)} px"
        swap = f"{format_number(pixels)} px in inches at {format_number(ppi)} ppi"
        return Evaluation(True, result, format_number(pixels), kind="design", swapExpression=swap)

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*px\s+in\s+(?:in|inch|inches)(?:\s+at\s+([+-]?\d+(?:\.\d+)?)\s*ppi)?", text, re.I)
    if match:
        pixels = float(match.group(1))
        ppi = float(match.group(2) or 96)
        inches = pixels / ppi
        result = f"{format_number(inches)} in"
        swap = f"{format_number(inches)} inches in px at {format_number(ppi)} ppi"
        return Evaluation(True, result, format_number(inches), kind="design", swapExpression=swap)

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*rem\s+(?:in|to)\s+px", text, re.I)
    if match:
        rem = float(match.group(1))
        pixels = rem * rem_px
        return Evaluation(True, f"{format_number(pixels)} px", format_number(pixels), kind="design",
                          swapExpression=f"{format_number(pixels)} px in rem")

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*px\s+(?:in|to)\s+rem", text, re.I)
    if match:
        pixels = float(match.group(1))
        rem = pixels / rem_px
        return Evaluation(True, f"{format_number(rem)} rem", format_number(rem), kind="design",
                          swapExpression=f"{format_number(rem)} rem in px")

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(?:min|mins|minute|minutes)\s+to\s+timespan", text, re.I)
    if match:
        minutes = round(float(match.group(1)))
        hours, remainder = divmod(minutes, 60)
        parts = []
        if hours:
            parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
        if remainder or not parts:
            parts.append(f"{remainder} {'minute' if remainder == 1 else 'minutes'}")
        return Evaluation(True, " ".join(parts), str(minutes), kind="duration")

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*h(?:ours?)?\s+in\s+workdays?", text, re.I)
    if match:
        hours = float(match.group(1))
        days = hours / workday_hours
        return Evaluation(True, f"{format_number(days)} workdays", format_number(days), kind="duration",
                          swapExpression=f"{format_number(days)} workdays in hours")

    match = re.fullmatch(r"workhours\s+in\s+(\d{4})", text, re.I)
    if match:
        year = int(match.group(1))
        weekdays = sum(1 for month in range(1, 13)
                       for day in range(1, monthrange(year, month)[1] + 1)
                       if date(year, month, day).weekday() < 5)
        hours = weekdays * workday_hours
        return Evaluation(True, f"{format_number(hours)} workhours", format_number(hours), kind="duration")

    return None


def clamp_channel(value: float) -> int:
    return round(max(0.0, min(1.0, value)) * 255)


def srgb_to_linear(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def linear_to_srgb(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return value * 12.92 if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055


def rgb_to_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (srgb_to_linear(c) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b)
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
    epsilon, kappa = 216 / 24389, 24389 / 27
    f = lambda t: t ** (1 / 3) if t > epsilon else (kappa * t + 16) / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def lab_to_rgb(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    lightness, a, b = lab
    fy = (lightness + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200
    epsilon, kappa = 216 / 24389, 24389 / 27
    inv = lambda t: t ** 3 if t ** 3 > epsilon else (116 * t - 16) / kappa
    x, y, z = 0.95047 * inv(fx), inv(fy), 1.08883 * inv(fz)
    r = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
    g = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
    blue = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z
    return linear_to_srgb(r), linear_to_srgb(g), linear_to_srgb(blue)


def rgb_to_oklch(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (srgb_to_linear(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = math.copysign(abs(l) ** (1 / 3), l), math.copysign(abs(m) ** (1 / 3), m), math.copysign(abs(s) ** (1 / 3), s)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_value = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    chroma = math.hypot(a, b_value)
    hue = math.degrees(math.atan2(b_value, a)) % 360
    return lightness, chroma, hue


def oklch_to_rgb(value: tuple[float, float, float]) -> tuple[float, float, float]:
    lightness, chroma, hue = value
    angle = math.radians(hue)
    a, b = chroma * math.cos(angle), chroma * math.sin(angle)
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    blue = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return linear_to_srgb(r), linear_to_srgb(g), linear_to_srgb(blue)


def color_formats(rgb: tuple[float, float, float], alpha: float = 1.0) -> Evaluation:
    channels = tuple(clamp_channel(c) for c in rgb)
    hex_value = "#" + "".join(f"{channel:02X}" for channel in channels)
    if alpha < 1:
        hex_value += f"{clamp_channel(alpha):02X}"
    hue, lightness, saturation = colorsys.rgb_to_hls(*rgb)
    lab = rgb_to_lab(rgb)
    oklch = rgb_to_oklch(rgb)
    formats = [
        {"label": "HEX", "value": hex_value},
        {"label": "RGB", "value": f"rgb({channels[0]}, {channels[1]}, {channels[2]})"},
        {"label": "HSL", "value": f"hsl({round(hue * 360)}, {round(saturation * 100)}%, {round(lightness * 100)}%)"},
        {"label": "OKLCH", "value": f"oklch({oklch[0]:.3f} {oklch[1]:.3f} {oklch[2]:.1f})"},
        {"label": "LAB", "value": f"lab({lab[0]:.2f}% {lab[1]:.2f} {lab[2]:.2f})"},
    ]
    return Evaluation(True, hex_value, hex_value, kind="color", colorHex=hex_value[:7], formats=formats)


def color_evaluation(expression: str) -> Evaluation | None:
    text = expression.strip()
    match = re.fullmatch(r"#?([0-9a-fA-F]{3,8})", text)
    if match and (text.startswith("#") or len(match.group(1)) in (6, 8)):
        value = match.group(1)
        if len(value) in (3, 4):
            value = "".join(c * 2 for c in value)
        if len(value) not in (6, 8):
            return Evaluation(False, error="Use a 3, 4, 6, or 8 digit hex color", kind="color")
        channels = tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))
        alpha = int(value[6:8], 16) / 255 if len(value) == 8 else 1.0
        return color_formats(channels, alpha)

    match = re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)", text, re.I)
    if match:
        values = [float(match.group(i)) for i in range(1, 4)]
        if any(value < 0 or value > 255 for value in values):
            return Evaluation(False, error="RGB channels must be between 0 and 255", kind="color")
        alpha = float(match.group(4)) if match.group(4) else 1.0
        if not 0 <= alpha <= 1:
            return Evaluation(False, error="Alpha must be between 0 and 1", kind="color")
        return color_formats(tuple(value / 255 for value in values), alpha)

    match = re.fullmatch(r"hsl\(\s*([\d.+-]+)(?:deg)?\s*,?\s*([\d.]+)%\s*,?\s*([\d.]+)%\s*\)", text, re.I)
    if match:
        hue, saturation, lightness = float(match.group(1)) % 360, float(match.group(2)), float(match.group(3))
        if not (0 <= saturation <= 100 and 0 <= lightness <= 100):
            return Evaluation(False, error="HSL percentages must be between 0 and 100", kind="color")
        return color_formats(colorsys.hls_to_rgb(hue / 360, lightness / 100, saturation / 100))

    match = re.fullmatch(r"oklch\(\s*([\d.]+)%?\s+([\d.]+)\s+([\d.+-]+)(?:deg)?\s*\)", text, re.I)
    if match:
        lightness = float(match.group(1))
        if "%" in text.split("(", 1)[1].split()[0]:
            lightness /= 100
        if not 0 <= lightness <= 1:
            return Evaluation(False, error="OKLCH lightness must be between 0 and 1 (or 0% and 100%)", kind="color")
        return color_formats(oklch_to_rgb((lightness, float(match.group(2)), float(match.group(3)))))

    match = re.fullmatch(r"lab\(\s*([\d.]+)%?\s+([\d.+-]+)\s+([\d.+-]+)\s*\)", text, re.I)
    if match:
        return color_formats(lab_to_rgb((float(match.group(1)), float(match.group(2)), float(match.group(3)))))

    return None


def resolve_currency(value: str) -> str:
    normalized = " ".join(value.lower().replace(".", "").strip(" .-=>→").split())
    if not normalized:
        return ""
    upper = normalized.upper()
    if upper in CURRENCY_CODES:
        return upper
    if normalized in CURRENCY_ALIASES:
        return CURRENCY_ALIASES[normalized]
    if normalized.endswith("s") and normalized[:-1] in CURRENCY_ALIASES:
        return CURRENCY_ALIASES[normalized[:-1]]
    return ""


def parse_localized_amount(value: str) -> Decimal | None:
    text = re.sub(r"[\s_']", "", value)
    if not text:
        return None
    multiplier = Decimal(1)
    if text[-1:].lower() in ("k", "m", "b"):
        multiplier = {"k": Decimal(1_000), "m": Decimal(1_000_000),
                      "b": Decimal(1_000_000_000)}[text[-1].lower()]
        text = text[:-1]
    last_dot, last_comma = text.rfind("."), text.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        if last_comma > last_dot:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif last_comma >= 0:
        parts = text.split(",")
        grouped = len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3
                                     and len(parts[0].lstrip("+-")) <= 3)
        text = text.replace(",", "") if grouped else text.replace(",", ".")
    elif last_dot >= 0 and text.count(".") > 1:
        text = text.replace(".", "")
    try:
        return Decimal(text) * multiplier
    except InvalidOperation:
        return None


def decimal_text(value: Decimal) -> str:
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized if normalized and normalized != "-0" else "0"


def split_currency_amount(value: str) -> tuple[Decimal | None, str]:
    match = re.search(r"[+-]?\d[\d.,\s_']*(?:[kmb]\b)?", value, re.I)
    if not match:
        return None, value.strip()
    amount = parse_localized_amount(match.group(0))
    remainder = " ".join((value[:match.start()] + " " + value[match.end():]).split())
    return amount, remainder


def normalize_currency_query(expression: str, default_from: str, default_to: str) -> str:
    text = " ".join(expression.strip().split())
    separator = re.search(r"\s*(?:->|=>|→|>)\s*|\s+\b(?:to|in|into|as)\b\s+", text, re.I)
    left, right = (text, "") if not separator else (
        text[:separator.start()].strip(), text[separator.end():].strip())
    amount, source_text = split_currency_amount(left)
    source = resolve_currency(source_text)
    target = ""
    if right:
        _, target_text = split_currency_amount(right)
        target = resolve_currency(target_text or right)
    if (target and not source and source_text
            and re.fullmatch(r"[\d\s.,_+'()*/%^+-]+", left)):
        # `500 * 0.5 in USD` means calculate first, then format the result as
        # USD. Attaching and converting the same currency prevents Qalculate
        # from converting the amount to its configured local currency.
        return f"({left}) {target} to {target}"
    if not source and not target:
        return ""
    if right and not target:
        return ""
    if amount is None:
        return ""
    fallback_from = resolve_currency(default_from) or "USD"
    fallback_to = resolve_currency(default_to) or "CAD"
    if not source:
        source = fallback_from
    if not target:
        target = fallback_from if source == fallback_to else fallback_to
    return f"{decimal_text(amount)} {source} to {target}"


def normalize_natural_language(expression: str, default_from: str = "USD",
                               default_to: str = "CAD") -> str:
    text = " ".join(expression.strip().split())

    currency = normalize_currency_query(text, default_from, default_to)
    if currency:
        return currency

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*%\s+off\s+(.+)", text, re.I)
    if match:
        return f"({match.group(2)}) * (1 - {match.group(1)}%)"

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*%\s+tip\s+on\s+(.+)", text, re.I)
    if match:
        return f"({match.group(2)}) * (1 + {match.group(1)}%)"

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*%\s+of\s+(.+)", text, re.I)
    if match:
        return f"{match.group(1)}% * ({match.group(2)})"

    match = re.fullmatch(r"ratio\s+of\s+(.+?)\s+to\s+(.+)", text, re.I)
    if match:
        return f"({match.group(1)}) / ({match.group(2)})"

    match = re.fullmatch(r"square\s+root\s+of\s+(.+)", text, re.I)
    if match:
        return f"sqrt({match.group(1)})"

    match = re.fullmatch(r"(.+?)\s+power\s+(.+)", text, re.I)
    if match:
        return f"({match.group(1)}) ^ ({match.group(2)})"

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*([KMB])", text, re.I)
    if match:
        factor = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[match.group(2).lower()]
        return f"{match.group(1)} * {factor}"

    match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*([A-Za-z°µμ]+)\s+in\s+([A-Za-z°µμ]+)", text)
    if match:
        return f"{match.group(1)} {match.group(2)} to {match.group(3)}"

    replacements = [
        (r"\bdivided\s+by\b", "/"),
        (r"\bmultiplied\s+by\b", "*"),
        (r"\btimes\b", "*"),
        (r"\bplus\b", "+"),
        (r"\bminus\b", "-"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return text


def plain_result(value: str, kind: str) -> str:
    result = value.strip().replace("−", "-").replace("×", "*").replace("÷", "/")
    result = re.sub(r"(?<=\d)[\u2009\u202f](?=\d)", "", result)
    if kind == "currency":
        match = re.search(r"[-+]?\d[\d.,]*(?:[Ee][-+]?\d+)?", result)
        if match:
            return match.group(0).replace(",", "")
    return result


def symbol_led_dollar_target(original: str, normalized: str) -> str:
    separator = re.search(
        r"\s*(?:->|=>|→|>)\s*|\s+\b(?:to|in|into|as)\b\s+", original, re.I
    )
    source_text = original if separator is None else original[:separator.start()]
    if "$" not in source_text:
        return ""
    match = re.search(r"\bto\s+([A-Z]{3})\s*$", normalized, re.I)
    target = match.group(1).upper() if match else ""
    return target if target in DOLLAR_CURRENCIES else ""


def currency_result(value: str, raw: str, original: str = "", normalized: str = "") -> str:
    """Round the primary money result while retaining raw calculator precision."""
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?(?:[Ee][-+]?\d+)?", value)
    if not match:
        return value
    try:
        amount = Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return value

    dollar_target = symbol_led_dollar_target(original, normalized)
    if dollar_target:
        sign = "-" if amount < 0 else ""
        return f"{dollar_target} {sign}${abs(amount):,.2f}"

    prefix = value[:match.start()]
    suffix = value[match.end():]
    sign_outside_number = amount < 0 and ("-" in prefix or "−" in prefix
                                          or "-" in suffix or "−" in suffix)
    display_amount = abs(amount) if sign_outside_number else amount
    formatted = f"{display_amount:,.2f}" if "," in match.group(0) else f"{display_amount:.2f}"
    return prefix + formatted + suffix


def numeric_formats(value: str, precision: int) -> list[dict[str, str]]:
    cleaned = value.strip().replace(",", "")
    if not re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?", cleaned):
        return []
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return []
    if not number.is_finite():
        return []

    digits = max(2, min(50, precision))
    output = []

    def append_format(label: str, formatted: str) -> None:
        if len(formatted) <= MAX_FORMAT_VALUE_CHARS:
            output.append({"label": label, "value": formatted})

    scientific = f"{number:.{digits - 1}E}"
    mantissa, exponent = scientific.split("E")
    scientific = mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
    if scientific.lower() != cleaned.lower():
        append_format("Scientific", scientific)

    if number:
        try:
            exponent_value = number.adjusted()
            engineering_exponent = exponent_value - exponent_value % 3
            engineering_mantissa = number.scaleb(-engineering_exponent)
            engineering = f"{engineering_mantissa:.{digits}g}e{engineering_exponent}"
            if (engineering_exponent != 0
                    and engineering.lower() not in (cleaned.lower(), scientific.lower())):
                append_format("Engineering", engineering)
        except (InvalidOperation, OverflowError, ValueError):
            pass

    decimal_tuple = number.as_tuple()
    if (len(decimal_tuple.digits) <= MAX_FRACTION_DIGITS
            and abs(number.adjusted()) <= MAX_FRACTION_DIGITS):
        fraction = Fraction(number).limit_denominator(1_000_000)
        if fraction.denominator != 1:
            approximation = Decimal(fraction.numerator) / Decimal(fraction.denominator)
            tolerance = Decimal(10) ** -(min(digits, 15) - 1)
            if abs(number - approximation) <= tolerance:
                append_format("Fraction", f"{fraction.numerator}/{fraction.denominator}")

    if (number == number.to_integral_value()
            and number.adjusted() <= MAX_INTEGER_FORMAT_DECIMAL_EXPONENT):
        integer = int(number)
        sign = "-" if integer < 0 else ""
        absolute = abs(integer)
        append_format("Binary", sign + "0b" + format(absolute, "b"))
        append_format("Octal", sign + "0o" + format(absolute, "o"))
        append_format("Hexadecimal", sign + "0x" + format(absolute, "X"))
    return output


def rate_metadata(stale_days: int) -> tuple[str, str, int, bool]:
    candidates = []
    override = os.environ.get("OMAQUICKCALC_QALCULATE_DATA_DIR", "")
    if override:
        candidates.append(Path(override))
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    candidates.extend([data_home / "qalculate", Path.home() / ".local/share/qalculate",
                       Path("/usr/share/qalculate")])

    dated_files: list[tuple[date, str]] = []
    seen = set()
    for directory in candidates:
        for filename in ("rates.json", "eurofxref-daily.xml"):
            path = directory / filename
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            try:
                content = path.read_text(encoding="utf-8", errors="replace")[:200_000]
                if filename == "rates.json":
                    match = re.search(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})"', content)
                else:
                    match = re.search(r"\btime=['\"](\d{4}-\d{2}-\d{2})['\"]", content)
                if match:
                    dated_files.append((date.fromisoformat(match.group(1)), "Qalculate cache"))
            except (OSError, ValueError):
                continue
    if not dated_files:
        return "", "", -1, False
    rate_date, source = max(dated_files, key=lambda item: item[0])
    age = max(0, (date.today() - rate_date).days)
    return rate_date.isoformat(), source, age, age > max(1, stale_days)


def infer_kind(expression: str) -> tuple[str, bool]:
    tokens = {token.upper() for token in re.findall(r"\b[A-Za-z]{3}\b", expression)}
    if tokens.intersection(CURRENCY_CODES) and re.search(r"\bto\b", expression, re.I):
        conversion = re.search(r"\b([A-Z]{3})\s+to\s+([A-Z]{3})\b", expression, re.I)
        return "currency", not conversion or conversion.group(1).upper() != conversion.group(2).upper()
    if re.search(r"\b(?:now|today|tomorrow)\b", expression, re.I):
        return "date", True
    if re.search(r"\bto\b", expression, re.I):
        return "unit", False
    return "math", False


def conversion_swap(expression: str, result: str, raw: str, kind: str) -> str:
    match = re.fullmatch(r"(.+?)\s+([A-Za-z°µμ]{1,12})\s+to\s+([A-Za-z°µμ]{1,12})", expression, re.I)
    if not match:
        return ""
    source, target = match.group(2), match.group(3)
    if source.upper() == target.upper():
        return ""
    if kind == "currency":
        numeric = raw
    else:
        numeric_match = re.search(r"[-+]?\d[\d.,]*(?:[Ee][-+]?\d+)?", result)
        numeric = numeric_match.group(0).replace(",", "") if numeric_match else ""
    if not numeric:
        return ""
    return f"{numeric} {target} to {source}"


def suspicious_result(original: str, normalized: str, output: str) -> bool:
    if any(token in output for token in SUSPICIOUS_OUTPUT_TOKENS):
        input_lower = original.lower()
        if not any(token.lower() in input_lower for token in SUSPICIOUS_OUTPUT_TOKENS):
            return True
    unresolved = re.search(r"\b(?:tip\s+on|ratio\s+of|square\s+root|power|timespan|workdays?|workhours?|days\s+until|time\s+(?:in|diff))\b", normalized, re.I)
    return unresolved is not None


def qalc_evaluation(expression: str, qalc: str, timeout_ms: int, unicode_output: bool,
                    digit_grouping: int, precision: int = 10,
                    default_from: str = "USD", default_to: str = "CAD",
                    rate_stale_days: int = 7) -> Evaluation:
    normalized = normalize_natural_language(expression, default_from, default_to)
    if suspicious_result(expression, normalized, ""):
        return Evaluation(False, error="Unsupported natural-language calculation", normalizedExpression=normalized)
    if (re.fullmatch(r"[+-]?\d+(?:\.\d+)?\s*[A-Za-z°µμ]{1,12}", normalized)
            or (re.fullmatch(r"[A-Za-z][A-Za-z\s]*", normalized)
                and normalized.strip().lower() not in BARE_MATH_CONSTANTS)):
        return Evaluation(False, pending=True,
                          normalizedExpression=normalized)

    command = [
        qalc, "--terse", "--time", str(timeout_ms), "+u8" if unicode_output else "-u8",
        "--set", "color off", "--set", "save config off", "--set", "save definitions off",
        "--set", f"digit grouping {digit_grouping}", "--set", f"precision {precision}",
        "--", normalized,
    ]
    try:
        process = _run_qalc_bounded(command, max(1.0, timeout_ms / 1000 + 0.75))
    except FileNotFoundError:
        return Evaluation(False, error="Calculator engine unavailable", normalizedExpression=normalized)
    except subprocess.TimeoutExpired:
        return Evaluation(False, error="Calculation timed out", normalizedExpression=normalized)
    except QalcOutputLimitError:
        return Evaluation(False, error="Calculation result is too large",
                          normalizedExpression=normalized)

    if len(process.stdout.encode("utf-8")) > MAX_RESULT_TEXT_BYTES:
        return Evaluation(False, error="Calculation result is too large",
                          normalizedExpression=normalized)
    output = process.stdout.replace("\x1b", "").strip()
    error = process.stderr.strip()
    resource_failure = process.returncode < 0 or re.search(
        r"bad_alloc|cannot allocate memory|out of memory|memory exhausted",
        error,
        re.I,
    )
    if resource_failure:
        return Evaluation(False, error="Calculation exceeded resource limit",
                          normalizedExpression=normalized)
    if process.returncode != 0 or not output:
        message = (error or output or "No result")[:MAX_ERROR_TEXT_CHARS]
        return Evaluation(False, error=message, normalizedExpression=normalized)
    if re.search(r"(^|\n)\s*(warning|error):", output + "\n" + error, re.I):
        return Evaluation(False, error=(error or output)[:MAX_ERROR_TEXT_CHARS],
                          normalizedExpression=normalized)
    if suspicious_result(expression, normalized, output):
        return Evaluation(False, error="That phrase was not understood. Try explicit operators or 'to' for conversions.",
                          normalizedExpression=normalized)

    if len(output) >= 2 and output[0] == output[-1] == '"':
        output = output[1:-1]
    kind, dynamic = infer_kind(normalized)
    raw = plain_result(output, kind)
    display = currency_result(output, raw, expression, normalized) if kind == "currency" else output
    formats = numeric_formats(raw, precision) if kind == "math" else []
    rate_date, rate_source, rate_age, rate_stale = ("", "", -1, False)
    if kind == "currency" and dynamic:
        rate_date, rate_source, rate_age, rate_stale = rate_metadata(rate_stale_days)
    return Evaluation(True, display, raw, kind=kind, normalizedExpression=normalized,
                      swapExpression=conversion_swap(normalized, display, raw, kind), dynamic=dynamic,
                      formats=formats, rateDate=rate_date, rateSource=rate_source,
                      rateAgeDays=rate_age, rateStale=rate_stale)


def tax_evaluation(expression: str, qalc: str, timeout_ms: int, unicode_output: bool,
                   digit_grouping: int, precision: int, default_from: str,
                   default_to: str, rate_stale_days: int,
                   tax_location: str = "auto", tax_custom_rate: float = 0) -> Evaluation | None:
    query = tax_engine.parse_tax_query(expression)
    if query is None:
        return None
    amount_expression = re.sub(r"(?<!\w)[$€£¥₹](?=\s*[+\-]?\d)", "",
                               query.amount_expression)
    if (re.search(r"[+\-*/^%]\s*$", amount_expression)
            or amount_expression.count("(") != amount_expression.count(")")):
        return Evaluation(False, kind="tax", pending=True,
                          normalizedExpression=expression)

    amount: Decimal | None = None
    if (re.fullmatch(r"[+\-\d\s_'.,]+", amount_expression)
            and re.search(r"\d", amount_expression)):
        amount = parse_localized_amount(amount_expression)

    if amount is None:
        base = qalc_evaluation(amount_expression, qalc, timeout_ms, unicode_output,
                               digit_grouping, precision, default_from, default_to,
                               rate_stale_days)
        if not base.ok:
            if base.pending and re.search(r"[A-Za-z°µμ]", amount_expression):
                return Evaluation(False, error="Tax requires a unitless numeric amount", kind="tax",
                                  normalizedExpression=expression)
            return Evaluation(False, error=base.error, kind="tax", pending=base.pending,
                              normalizedExpression=expression)
        if base.kind != "math" or not re.fullmatch(r"[+\-\d\s_'. ,Ee]+", base.rawResult):
            return Evaluation(False, error="Tax requires a unitless numeric amount", kind="tax",
                              normalizedExpression=expression)
        try:
            amount = Decimal(base.rawResult.replace(" ", "").replace(",", ""))
        except InvalidOperation:
            return Evaluation(False, error="Tax requires a unitless numeric amount", kind="tax",
                              normalizedExpression=expression)

    if not amount.is_finite() or amount.copy_abs() > Decimal("1e100"):
        return Evaluation(False, error="Tax amount is out of range", kind="tax",
                          normalizedExpression=expression)

    try:
        catalog = tax_engine.load_catalog()
        requested_location = query.location or tax_location
        custom_rate = Decimal(query.custom_rate) if query.custom_rate else Decimal(str(tax_custom_rate))
        if query.custom_rate or str(requested_location).lower() == "custom":
            if not custom_rate.is_finite() or custom_rate <= 0 or custom_rate > 100:
                return Evaluation(False, error="Set a custom tax rate in Preferences", kind="tax",
                                  normalizedExpression=expression)
            jurisdiction = {
                "id": "CUSTOM",
                "name": f"Custom {tax_engine.rate_text(custom_rate / 100)}",
                "countryCode": "",
                "currency": default_from.upper()
                if re.fullmatch(r"[A-Za-z]{3}", default_from) else "USD",
                "components": [{"code": "Tax", "rate": tax_engine.decimal_text(custom_rate / 100)}],
                "assumption": "Custom combined rate; actual taxability depends on the location and purchase",
                "sources": [],
            }
            inferred = False
            catalog = {**catalog, "reviewedOn": ""}
        else:
            jurisdiction, inferred = tax_engine.resolve_jurisdiction(requested_location, catalog)
        if jurisdiction is None:
            if query.location or str(tax_location).lower() not in {"", "auto"}:
                return Evaluation(False, error=f"Unsupported tax location: {requested_location}",
                                  kind="tax", normalizedExpression=expression)
            return Evaluation(False, error="Choose a tax location in Preferences", kind="tax",
                              normalizedExpression=expression)
        report = tax_engine.build_report(amount, jurisdiction, catalog, inferred)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return Evaluation(False, error="Tax scheme data is unavailable", kind="tax",
                          normalizedExpression=expression)

    location_note = str(report["locationName"])
    if report.get("locationInferred"):
        location_note += " · Auto"
    return Evaluation(
        True,
        str(report["result"]),
        str(report["rawResult"]),
        kind="tax",
        normalizedExpression=expression,
        dynamic=True,
        formats=list(report.get("formats", [])),
        note=location_note,
        report=report,
    )


def evaluate(expression: str, qalc: str = "qalc", timeout_ms: int = 250,
             unicode_output: bool = True, digit_grouping: int = 0,
             rem_px: float = 16, workday_hours: float = 8,
             clock_format: str = DEFAULT_CLOCK_FORMAT, precision: int = 10,
             default_from: str = "USD", default_to: str = "CAD",
             rate_stale_days: int = 7, tax_location: str = "auto",
             tax_custom_rate: float = 0) -> Evaluation:
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return Evaluation(False, error="Expression is too long")
    text = expression.strip()
    if not text:
        return Evaluation(False, error="No expression")
    precision = max(2, min(50, int(precision)))
    rate_stale_days = max(1, min(365, int(rate_stale_days)))

    tax_result = tax_evaluation(text, qalc, timeout_ms, unicode_output, digit_grouping,
                                precision, default_from, default_to, rate_stale_days,
                                tax_location, tax_custom_rate)
    if tax_result is not None:
        return tax_result

    for evaluator in (
        easter_egg_evaluation,
        color_evaluation,
        lambda value: timezone_evaluation(value, clock_format),
        lambda value: date_evaluation(value, clock_format),
        lambda value: design_evaluation(value, rem_px, workday_hours),
    ):
        try:
            result = evaluator(text)
        except (OverflowError, ValueError, ZeroDivisionError):
            return Evaluation(False, error="Calculation is out of range")
        if result is not None:
            result.normalizedExpression = text
            return result

    return qalc_evaluation(text, qalc, timeout_ms, unicode_output, digit_grouping,
                           precision, default_from, default_to, rate_stale_days)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("evaluate", "batch"), nargs="?", default="evaluate")
    parser.add_argument("--expression", default="")
    parser.add_argument("--expressions", default="[]")
    parser.add_argument("--qalc", default="qalc")
    parser.add_argument("--timeout-ms", type=int, default=250)
    parser.add_argument("--unicode", type=int, choices=(0, 1), default=1)
    parser.add_argument("--digit-grouping", type=int, choices=(0, 1, 2), default=0)
    parser.add_argument("--rem-px", type=float, default=16)
    parser.add_argument("--workday-hours", type=float, default=8)
    parser.add_argument("--clock-format", choices=("auto", "12", "24"),
                        default=DEFAULT_CLOCK_FORMAT)
    parser.add_argument("--precision", type=int, default=10)
    parser.add_argument("--default-from", default="USD")
    parser.add_argument("--default-to", default="CAD")
    parser.add_argument("--rate-stale-days", type=int, default=7)
    parser.add_argument("--tax-location", default="auto")
    parser.add_argument("--tax-custom-rate", type=float, default=0)
    return parser.parse_args()


def encode_json_payload(payload: object, byte_limit: int) -> str | None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > byte_limit:
        return None
    return encoded


def main() -> int:
    args = parse_arguments()
    if args.mode == "batch":
        try:
            expressions = json.loads(args.expressions)
        except json.JSONDecodeError:
            expressions = []
        payload = []
        for expression in expressions[:50]:
            result = evaluate(str(expression), args.qalc, args.timeout_ms, bool(args.unicode),
                              args.digit_grouping, args.rem_px, args.workday_hours,
                              args.clock_format, args.precision, args.default_from,
                              args.default_to, args.rate_stale_days, args.tax_location,
                              args.tax_custom_rate)
            payload.append({"expression": str(expression), **asdict(result)})
        encoded = encode_json_payload(payload, MAX_BATCH_JSON_BYTES)
        if encoded is None:
            print("[]")
            return 1
        print(encoded)
        return 0

    result = evaluate(args.expression, args.qalc, args.timeout_ms, bool(args.unicode),
                      args.digit_grouping, args.rem_px, args.workday_hours,
                      args.clock_format, args.precision, args.default_from,
                      args.default_to, args.rate_stale_days, args.tax_location,
                      args.tax_custom_rate)
    encoded = encode_json_payload(asdict(result), MAX_EVALUATION_JSON_BYTES)
    if encoded is None:
        result = Evaluation(False, error="Calculation result is too large")
        encoded = encode_json_payload(asdict(result), MAX_EVALUATION_JSON_BYTES)
        assert encoded is not None
    print(encoded)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
