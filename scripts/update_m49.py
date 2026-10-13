"""Refresh src/undata/m49.csv from the UN Statistics Division's M49 page.

    uv run python scripts/update_m49.py

M49 is the UN's standard list of countries and areas, its regions, and its LDC,
LLDC and SIDS groupings. The live test suite checks that the shipped copy still
matches the UN's, so a change (an LDC graduation, a renamed country) shows up as a
failing nightly run, and this script brings the copy up to date.
"""

from __future__ import annotations

import csv
import html
import re
import sys
from pathlib import Path

import httpx

SOURCE = "https://unstats.un.org/unsd/methodology/m49/overview/"
TARGET = Path(__file__).resolve().parent.parent / "src" / "undata" / "m49.csv"

COLUMNS = {
    "ISO-alpha3 Code": "iso3",
    "M49 Code": "m49",
    "Country or Area": "name",
    "Region Code": "region_code",
    "Region Name": "region",
    "Sub-region Code": "sub_region_code",
    "Sub-region Name": "sub_region",
    "Intermediate Region Code": "intermediate_region_code",
    "Intermediate Region Name": "intermediate_region",
    "Least Developed Countries (LDC)": "ldc",
    "Land Locked Developing Countries (LLDC)": "lldc",
    "Small Island Developing States (SIDS)": "sids",
    "Developed / Developing Countries": "development",
}


def fetch() -> list[dict[str, str]]:
    """The English M49 table, one dict per country or area."""
    page = httpx.get(SOURCE, timeout=60, follow_redirects=True, headers={"User-Agent": "undata"})
    page.raise_for_status()
    table = re.search(r'<table id\s*=\s*"downloadTableEN"[^>]*>(.*?)</table>', page.text, re.S)
    if table is None:
        raise SystemExit("The M49 page no longer has the table this script reads.")
    rows = [
        [
            html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
            for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)
        ]
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", table.group(1), re.S)
    ]
    header, body = rows[0], rows[1:]
    records = [dict(zip(header, row, strict=True)) for row in body]
    return [
        {short: record.get(long, "") for long, short in COLUMNS.items()}
        for record in records
        if record.get("ISO-alpha3 Code")  # Sark has an M49 code but no ISO code, so no data
    ]


def write(records: list[dict[str, str]], target: Path = TARGET) -> None:
    """Write the records sorted by ISO code, so a refresh shows a readable diff."""
    with target.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(COLUMNS.values()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(records, key=lambda r: r["iso3"]))


if __name__ == "__main__":
    found = fetch()
    write(found)
    print(f"Wrote {len(found)} countries and areas to {TARGET}", file=sys.stderr)
