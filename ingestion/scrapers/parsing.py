"""Utilidades compartidas por los parsers de Kayak."""

import re

from bs4 import Tag


def text(el: Tag | None) -> str:
    return el.get_text(" ", strip=True) if el else ""


def parse_price(value: str) -> float | None:
    digits = re.sub(r"[^\d.]", "", value)
    return float(digits) if digits else None


def parse_float(value: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", value)
    return float(match.group()) if match else None


def parse_int(value: str) -> int | None:
    match = re.search(r"\d+", value.replace(",", ""))
    return int(match.group()) if match else None


def is_ad(card: Tag) -> bool:
    return any(div.get_text(strip=True) == "Ad" for div in card.find_all("div"))
