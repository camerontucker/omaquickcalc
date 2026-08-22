#!/usr/bin/env python3
"""Local, data-driven consumption-tax reports for OmaQuickCalc."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).with_name("data") / "tax_schemes.json"
CENT = Decimal("0.01")
CURRENCY_MINOR_UNITS = {"JPY": 0}


@dataclass(frozen=True)
class TaxQuery:
    amount_expression: str
    location: str = ""
    custom_rate: str = ""


CANADIAN_TIMEZONES = {
    "America/St_Johns": "CA-NL",
    "America/Goose_Bay": "CA-NL",
    "America/Halifax": "CA-NS",
    "America/Glace_Bay": "CA-NS",
    "America/Moncton": "CA-NB",
    "America/Toronto": "CA-ON",
    "America/Thunder_Bay": "CA-ON",
    "America/Nipigon": "CA-ON",
    "America/Atikokan": "CA-ON",
    "America/Montreal": "CA-QC",
    "America/Blanc-Sablon": "CA-QC",
    "America/Winnipeg": "CA-MB",
    "America/Regina": "CA-SK",
    "America/Swift_Current": "CA-SK",
    "America/Edmonton": "CA-AB",
    "America/Vancouver": "CA-BC",
    "America/Dawson_Creek": "CA-BC",
    "America/Fort_Nelson": "CA-BC",
    "America/Creston": "CA-BC",
    "America/Yellowknife": "CA-NT",
    "America/Inuvik": "CA-NT",
    "America/Iqaluit": "CA-NU",
    "America/Rankin_Inlet": "CA-NU",
    "America/Cambridge_Bay": "CA-NU",
    "America/Whitehorse": "CA-YT",
    "America/Dawson": "CA-YT",
}


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    plain = "".join(character for character in decomposed
                    if not unicodedata.combining(character))
    return " ".join(plain.replace("_", " ").replace(".", "").split())


def parse_tax_query(expression: str) -> TaxQuery | None:
    text = " ".join(str(expression or "").strip().split())
    match = re.fullmatch(
        r"(?P<amount>.+?)\s+(?:sales\s+)?tax"
        r"(?:\s+at\s+(?P<rate>\d+(?:[.,]\d+)?)\s*%|\s+in\s+(?P<location>.+))?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    amount = match.group("amount").strip()
    if not amount:
        return None
    return TaxQuery(amount, (match.group("location") or "").strip(),
                    (match.group("rate") or "").replace(",", "."))


def load_catalog(path: Path = DATA_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    if catalog.get("schemaVersion") != 1 or not isinstance(catalog.get("jurisdictions"), list):
        raise ValueError("Unsupported tax data schema")
    return catalog


def jurisdiction_maps(catalog: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    jurisdictions: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for jurisdiction in catalog["jurisdictions"]:
        identifier = str(jurisdiction.get("id", "")).upper()
        if not re.fullmatch(r"[A-Z]{2}(?:-[A-Z0-9]{1,3})?", identifier):
            raise ValueError(f"Invalid tax jurisdiction: {identifier}")
        if identifier in jurisdictions:
            raise ValueError(f"Duplicate tax jurisdiction: {identifier}")
        jurisdictions[identifier] = jurisdiction
        for alias in [identifier, jurisdiction.get("name", ""), *jurisdiction.get("aliases", [])]:
            key = normalize_name(str(alias))
            if key and key not in aliases:
                aliases[key] = identifier
    return jurisdictions, aliases


def system_timezone() -> str:
    configured = os.environ.get("TZ", "").lstrip(":")
    if configured:
        return configured
    try:
        resolved = str(Path("/etc/localtime").resolve())
        marker = "/zoneinfo/"
        if marker in resolved:
            return resolved.split(marker, 1)[1]
    except OSError:
        pass
    try:
        return Path("/etc/timezone").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def timezone_country(timezone_name: str,
                     zone_table: Path = Path("/usr/share/zoneinfo/zone.tab")) -> str:
    if not timezone_name:
        return ""
    try:
        lines = zone_table.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 3 and fields[2] == timezone_name:
            countries = fields[0].split(",")
            return countries[0] if len(countries) == 1 else ""
    return ""


def resolve_jurisdiction(location: str, catalog: dict[str, Any],
                         timezone_name: str = "") -> tuple[dict[str, Any] | None, bool]:
    jurisdictions, aliases = jurisdiction_maps(catalog)
    requested = str(location or "auto").strip()
    inferred = normalize_name(requested) in {"", "auto"}
    if not inferred:
        identifier = aliases.get(normalize_name(requested), requested.upper())
        return jurisdictions.get(identifier), False

    zone = timezone_name or system_timezone()
    identifier = CANADIAN_TIMEZONES.get(zone, "")
    if identifier:
        return jurisdictions.get(identifier), True

    zone_country = timezone_country(zone)
    country_matches = [item for item in jurisdictions.values()
                       if item.get("countryCode") == zone_country]
    if len(country_matches) == 1:
        return country_matches[0], True

    for variable in ("LC_ADDRESS", "LC_ALL", "LANG"):
        match = re.search(r"(?:^|[_-])([A-Za-z]{2})(?:[.@-]|$)", os.environ.get(variable, ""))
        if not match:
            continue
        country = match.group(1).upper()
        country_matches = [item for item in jurisdictions.values()
                           if item.get("countryCode") == country]
        if len(country_matches) == 1:
            return country_matches[0], True
    return None, True


def money_quantum(currency: str) -> Decimal:
    return Decimal(1).scaleb(-CURRENCY_MINOR_UNITS.get(currency, 2))


def money_round(value: Decimal, currency: str = "") -> Decimal:
    return value.quantize(money_quantum(currency) if currency else CENT,
                          rounding=ROUND_HALF_UP)


def decimal_text(value: Decimal) -> str:
    normalized = format(value, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized if normalized and normalized != "-0" else "0"


def rate_text(rate: Decimal) -> str:
    return decimal_text(rate * 100) + "%"


def money_text(value: Decimal, currency: str) -> str:
    symbol = {"CAD": "$", "USD": "$", "AUD": "$", "NZD": "$", "EUR": "€",
              "GBP": "£", "JPY": "¥", "CNY": "¥", "INR": "₹", "MXN": "$",
              "SGD": "$", "ZAR": "R", "SAR": "SAR ", "AED": "AED "}.get(currency, "")
    digits = CURRENCY_MINOR_UNITS.get(currency, 2)
    formatted = f"{abs(value):,.{digits}f}"
    prefix = "-" if value < 0 else ""
    return f"{prefix}{symbol}{formatted}" if symbol else f"{prefix}{formatted} {currency}"


def report_row(label: str, value: Decimal, currency: str, emphasis: bool = False) -> dict[str, Any]:
    return {
        "label": label,
        "value": money_text(value, currency),
        "rawValue": decimal_text(value),
        "emphasis": emphasis,
    }


def additive_section(amount: Decimal, components: list[dict[str, Any]],
                     currency: str) -> tuple[dict[str, Any], Decimal]:
    subtotal = money_round(amount, currency)
    taxes = [(component, money_round(amount * Decimal(str(component["rate"])), currency))
             for component in components]
    total = subtotal + sum((value for _, value in taxes), Decimal(0))
    rows = [report_row("Subtotal", subtotal, currency)]
    rows.extend(report_row(f'{component["code"]} ({rate_text(Decimal(str(component["rate"])))})',
                           value, currency) for component, value in taxes)
    rows.append(report_row("Total", total, currency, True))
    return {"id": "add", "title": "Add tax", "rows": rows}, total


def inclusive_section(amount: Decimal, components: list[dict[str, Any]], currency: str,
                      identifier: str = "included", title: str = "Tax included") -> tuple[dict[str, Any], Decimal]:
    total = money_round(amount, currency)
    total_rate = sum((Decimal(str(component["rate"])) for component in components), Decimal(0))
    exact_base = amount / (Decimal(1) + total_rate)
    taxes = [(component, money_round(exact_base * Decimal(str(component["rate"])), currency))
             for component in components]
    base = total - sum((value for _, value in taxes), Decimal(0))
    rows = [report_row("Before tax", base, currency)]
    rows.extend(report_row(f'{component["code"]} ({rate_text(Decimal(str(component["rate"])))})',
                           value, currency) for component, value in taxes)
    rows.append(report_row("Total", total, currency, True))
    return {"id": identifier, "title": title, "rows": rows}, base


def report_copy_text(name: str, currency: str, sections: list[dict[str, Any]],
                     assumption: str) -> str:
    lines = [f"{name} tax report · {currency}", assumption]
    for section in sections:
        lines.append("")
        lines.append(str(section["title"]))
        lines.extend(f'{row["label"]}: {row["value"]}' for row in section["rows"])
    return "\n".join(lines)


def build_report(amount: Decimal, jurisdiction: dict[str, Any], catalog: dict[str, Any],
                 inferred: bool) -> dict[str, Any]:
    currency = str(jurisdiction["currency"])
    components = list(jurisdiction["components"])
    add, total = additive_section(amount, components, currency)
    included, before_tax = inclusive_section(amount, components, currency)
    sections = [add, included]
    formats = [
        {"label": "Tax-added total", "value": decimal_text(total)},
        {"label": "Before-tax amount", "value": decimal_text(before_tax)},
    ]

    federal = jurisdiction.get("federalReverse")
    if federal:
        federal_section, federal_base = inclusive_section(
            amount, [federal], currency, "federal", f'{federal["code"]} only included'
        )
        sections.append(federal_section)
        formats.append({"label": f'{federal["code"]}-only before-tax amount',
                        "value": decimal_text(federal_base)})

    assumption = str(jurisdiction.get(
        "assumption", catalog.get("assumption", "Standard taxable purchase")
    ))
    name = str(jurisdiction["name"])
    reviewed = str(catalog.get("reviewedOn", ""))
    report = {
        "title": f"{name} · {currency}",
        "location": str(jurisdiction["id"]),
        "locationName": name,
        "locationInferred": inferred,
        "assumption": assumption,
        "reviewedOn": reviewed,
        "effectiveFrom": str(jurisdiction.get("effectiveFrom", "")),
        "sources": list(jurisdiction.get("sources", [])),
        "sections": sections,
    }
    report["copyText"] = report_copy_text(name, currency, sections, assumption)
    report["detailText"] = report["copyText"] + (f"\n\nRates reviewed {reviewed}." if reviewed else "")
    if report["sources"]:
        report["detailText"] += "\nSource: " + "\n".join(report["sources"])
    report["formats"] = formats
    report["result"] = money_text(total, currency)
    report["rawResult"] = decimal_text(total)
    return report
