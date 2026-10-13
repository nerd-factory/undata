"""Build src/undata/tiles.csv: one square per M49 country, placed roughly where it is.

    uv run python scripts/build_tile_grid.py

Tile maps show every country at the same size and draw no borders, which keeps small
island States visible and avoids drawing disputed boundaries. Each country's
centre (latitude and longitude, from the platform) is projected onto a grid, then
countries are placed one by one, most crowded first, on the free cell nearest their
true position. Empty rows and columns are dropped at the end.
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import undata
from undata.places import m49

TARGET = Path(__file__).resolve().parent.parent / "src" / "undata" / "tiles.csv"

#: Degrees per cell. Smaller keeps shapes truer; larger keeps the map compact.
CELL_LON = 10.0
CELL_LAT = 8.0

#: Places the platform holds no centre for: approximate centres, in degrees.
FALLBACK = {"ALA": (60.2, 20.0), "BES": (12.2, -68.3), "CUW": (12.2, -69.0)}


def centres() -> dict[str, tuple[float, float]]:
    """Latitude and longitude per ISO3 code, by POST (some codes trip the firewall on GET)."""
    found: dict[str, tuple[float, float]] = {}
    codes = [c.iso3 for c in m49()]
    with undata.Transport() as transport:
        for start in range(0, len(codes), 40):
            batch = [f"country/{c}" for c in codes[start : start + 40]]
            values: dict[str, dict[str, float]] = {}
            for prop in ("latitude", "longitude"):
                body = transport.post(
                    "/core/api/v2/node", {"nodes": batch, "property": f"->{prop}"}
                )
                for node, entry in body.get("data", {}).items():
                    nodes = entry.get("arcs", {}).get(prop, {}).get("nodes", [])
                    if nodes:
                        values.setdefault(node, {})[prop] = float(nodes[0]["value"])
            for node, pair in values.items():
                if len(pair) == 2:  # noqa: PLR2004
                    found[node.removeprefix("country/")] = (pair["latitude"], pair["longitude"])
    return found


def layout(points: dict[str, tuple[float, float]]) -> dict[str, tuple[int, int]]:
    """Place each country on the free grid cell nearest its projected centre."""
    ideal = {
        iso: ((90 - lat) / CELL_LAT, (lon + 180) / CELL_LON) for iso, (lat, lon) in points.items()
    }

    def crowding(iso: str) -> int:
        r, c = ideal[iso]
        return sum(1 for rr, cc in ideal.values() if abs(rr - r) < 2 and abs(cc - c) < 2)  # noqa: PLR2004

    taken: dict[tuple[int, int], str] = {}
    placed: dict[str, tuple[int, int]] = {}
    for iso in sorted(ideal, key=lambda i: (-crowding(i), i)):
        r, c = ideal[iso]
        best: tuple[float, tuple[int, int]] | None = None
        for radius in range(0, 30):
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    if max(abs(dr), abs(dc)) != radius:
                        continue
                    cell = (round(r) + dr, round(c) + dc)
                    if cell in taken:
                        continue
                    distance = math.hypot(cell[0] - r, cell[1] - c)
                    if best is None or distance < best[0]:
                        best = (distance, cell)
            if best is not None and best[0] <= radius:
                break
        if best is None:
            raise RuntimeError(f"no free cell near {iso}")
        taken[best[1]] = iso
        placed[iso] = best[1]
    rows = sorted({r for r, _ in placed.values()})
    cols = sorted({c for _, c in placed.values()})
    return {iso: (rows.index(r), cols.index(c)) for iso, (r, c) in placed.items()}


if __name__ == "__main__":
    points = {**FALLBACK, **centres()}
    missing = sorted({c.iso3 for c in m49()} - set(points))
    grid = layout(points)
    with TARGET.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["iso3", "row", "col"])
        for iso, (row, col) in sorted(grid.items()):
            writer.writerow([iso, row, col])
    print(f"Placed {len(grid)} countries; no centre for {missing}", file=sys.stderr)
