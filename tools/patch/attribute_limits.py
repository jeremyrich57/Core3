#!/usr/bin/env python3
"""Generate patches/datatables/creation/attribute_limits.iff to match the server's attribute rescale.

    python3 tools/patch/attribute_limits.py ~/tre
    python3 tools/patch/build.py --install ~/tre

The server rescales new characters' starting attributes (attributeRangeMin/Max/Rounding in
MMOCoreORB/bin/scripts/managers/player_creation_manager.lua). Stat migration limits come from
attribute_limits.iff, which the client also uses for its sliders, so both need a copy rescaled the
same way. This reads the stock tables from the TREs (ignoring core3_custom.tre) and applies the
formulas in PlayerCreationManager.cpp:

    source range  lowest/highest profession_mods + racial_mods value over all species and professions
    min/max       rescaleAttribute: map proportionally into the target range, round to the nearest step
    total         rescaleAttributeTotal: the same mapping applied to the sum of all 9 attributes

With rescaling off (range 0/0) the patched file is removed so the stock one is used.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datatable  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = os.path.join(REPO, "MMOCoreORB", "bin", "conf", "config.lua")
CREATION_CONFIG = os.path.join(REPO, "MMOCoreORB", "bin", "scripts", "managers", "player_creation_manager.lua")
OUTPUT = os.path.join(REPO, "patches", "datatables", "creation", "attribute_limits.iff")
CUSTOM_TRE = "core3_custom.tre"

LIMITS = "datatables/creation/attribute_limits.iff"
RACIAL_MODS = "datatables/creation/racial_mods.iff"
PROFESSION_MODS = "datatables/creation/profession_mods.iff"


def lua_int(text: str, name: str) -> int:
    m = re.search(rf"^\s*{name}\s*=\s*(-?\d+)", text, re.MULTILINE)
    if not m:
        raise SystemExit(f"{CREATION_CONFIG}: {name} not found")
    return int(m.group(1))


def lround(x: float) -> int:
    """std::lround: round half away from zero."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tre_dir", help="directory with the stock client TREs (the server's Core3.TrePath)")
    ap.add_argument("--out", default=OUTPUT, help="output file (default: patches/datatables/creation/attribute_limits.iff)")
    args = ap.parse_args()

    with open(CREATION_CONFIG) as f:
        lua = f.read()
    range_min = lua_int(lua, "attributeRangeMin")
    range_max = lua_int(lua, "attributeRangeMax")
    rounding = max(1, lua_int(lua, "attributeRounding"))

    if range_max <= range_min:
        if os.path.exists(args.out):
            os.remove(args.out)
            print(f"Attribute rescaling is off; removed {args.out} so the stock file is used.")
        else:
            print("Attribute rescaling is off; nothing to generate.")
        return 0

    with open(CONFIG) as f:
        tre_order = [n for n in re.findall(r'"([A-Za-z0-9_]+\.tre)"', f.read()) if n != CUSTOM_TRE]
    tres = datatable.TreSet(args.tre_dir, tre_order)
    if not tres.archives:
        raise SystemExit(f"No TRE files from {CONFIG} found in {args.tre_dir}")

    limits = datatable.parse(tres.get(LIMITS)[1])
    racial = {row[0]: row[2:11] for row in datatable.parse(tres.get(RACIAL_MODS)[1]).rows}
    professions = {row[0]: row[1:10] for row in datatable.parse(tres.get(PROFESSION_MODS)[1]).rows}
    professions = {name: mods for name, mods in professions.items() if sum(mods) > 0}

    values = [p[i] + racial[row[0]][i] for row in limits.rows for p in professions.values() for i in range(9)]
    source_min, source_max = min(values), max(values)
    ratio = (range_max - range_min) / (source_max - source_min)

    def rescale(value: int) -> int:
        scaled = range_min + (value - source_min) * ratio
        return min(max(lround(scaled / rounding) * rounding, range_min), range_max)

    def rescale_total(total: int) -> int:
        scaled = 9 * range_min + (total - 9 * source_min) * ratio
        return lround(scaled / rounding) * rounding

    print(f"Rescaling {source_min}-{source_max} -> {range_min}-{range_max} (rounded to {rounding})")
    total_col = limits.column("total")
    for row in limits.rows:
        for col in range(2, total_col):
            row[col] = rescale(row[col])
        row[total_col] = rescale_total(row[total_col])

        mins, maxes = row[2:total_col:2], row[3:total_col:2]
        note = ""
        if not sum(mins) <= row[total_col] <= sum(maxes):
            note = f"  WARNING: total outside {sum(mins)}-{sum(maxes)}, migration can't reach it"
        print(f"  {row[0]:<16} total {row[total_col]:>5}  " +
              " ".join(f"{lo}-{hi}" for lo, hi in zip(mins, maxes)) + note)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(datatable.dump(limits))
    print(f"wrote {args.out}")
    print("Next: python3 tools/patch/build.py --install <tre_dir>, restart the server, publish the patch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
