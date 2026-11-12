#!/usr/bin/env python3
"""Set vehicle movement stats in patches/object/mobile/vehicle/shared_<vehicle>.iff.

    python3 tools/patch/vehicle_stats.py ~/tre
    python3 tools/patch/build.py --install ~/tre

The vehicle's shared (client) object template holds its movement stats. The client simulates movement from
them, and the server takes the vehicle's run speed from speed[0], so both have to load the same patched file.
Each stat is a {run, walk} pair:

    speed         top speed in m/s
    acceleration  m/s^2 (top speed / acceleration = seconds to reach it)
    turnRate      degrees per second (top speed / turn rate in rad/s = turning radius at top speed)

Stock vehicles are read from the stock TREs (ignoring core3_custom.tre). Imported vehicles (the BARC and STAP from
import_aotc.py) have no stock copy, so their file in patches/ is edited in place; run this again after re-importing.
Only the values listed in STATS change; everything else in the template is kept byte for byte.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datatable  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = os.path.join(REPO, "MMOCoreORB", "bin", "conf", "config.lua")
PATCHES = os.path.join(REPO, "patches")
CUSTOM_TRE = "core3_custom.tre"
TEMPLATE = "object/mobile/vehicle/shared_{}.iff"

# Turn rates keep each vehicle's stock turning radius at top speed. Acceleration reaches top speed in about
# 1.7 s (the stock norm); BARC and STAP keep their faster ~1.15 s.
#   vehicle               speed {run, walk}  acceleration  turnRate
STATS = {
    "landspeeder_x31":   {"speed": (17, 9),  "acceleration": (10, 3), "turnRate": (119, 238)},
    "speederbike":       {"speed": (20, 11), "acceleration": (12, 4), "turnRate": (120, 240)},
    "speederbike_swoop": {"speed": (20, 11), "acceleration": (12, 4), "turnRate": (121, 242)},
    "landspeeder_x34":   {"speed": (20, 11), "acceleration": (12, 4), "turnRate": (118, 236)},
    "landspeeder_av21":  {"speed": (25, 13), "acceleration": (15, 4), "turnRate": (113, 226)},
    "speederbike_flash": {"speed": (25, 13), "acceleration": (15, 4), "turnRate": (151, 302)},
    "jetpack":           {"speed": (25, 13), "acceleration": (15, 4), "turnRate": (148, 296)},
    "barc_speeder":      {"speed": (22, 12), "acceleration": (19, 4), "turnRate": (85, 170)},
    "stap_speeder":      {"speed": (25, 13), "acceleration": (22, 5), "turnRate": (109, 244)},
}

# Vehicles that only exist in patches/ (imported, no stock template).
IMPORTED = {"barc_speeder", "stap_speeder"}

ENTRY = struct.Struct("<BBf")  # 1 (value present), 0x20 (set), float


def chunks(data: bytes, base: int = 0):
    """Yield (tag, body offset, body length) for every leaf chunk, descending into FORMs."""
    pos = 0
    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]
        size = struct.unpack_from(">I", data, pos + 4)[0]
        if tag == b"FORM":
            yield from chunks(data[pos + 12:pos + 8 + size], base + pos + 12)
        else:
            yield tag, base + pos + 8, size
        pos += 8 + size


def find_param(data: bytes, name: str) -> int:
    """Offset of the value of the template's own XXXX parameter `name` (a list of 2 floats)."""
    key = name.encode() + b"\0"
    for tag, off, size in chunks(data):
        if tag == b"XXXX" and data[off:off + len(key)] == key:
            value = off + len(key)
            if size != len(key) + 4 + 2 * ENTRY.size or data[value] != 2:
                raise ValueError(f"{name}: not a list of 2 floats")
            return value + 4
    raise KeyError(name)


def patch(data: bytes, stats: dict[str, tuple[float, float]]) -> tuple[bytes, list[str]]:
    out = bytearray(data)
    changes = []
    for name, values in stats.items():
        off = find_param(data, name)
        old = []
        for i, value in enumerate(values):
            present, kind, before = ENTRY.unpack_from(data, off + i * ENTRY.size)
            if present != 1 or kind != 0x20:
                raise ValueError(f"{name}[{i}]: unexpected entry {present:#x} {kind:#x}")
            ENTRY.pack_into(out, off + i * ENTRY.size, 1, 0x20, float(value))
            old.append(before)
        changes.append(f"{name} {{{old[0]:g}, {old[1]:g}}} -> {{{values[0]:g}, {values[1]:g}}}")
    return bytes(out), changes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tre_dir", help="directory with the stock client TREs (the server's Core3.TrePath)")
    args = ap.parse_args()

    with open(CONFIG) as f:
        tre_order = [n for n in re.findall(r'"([A-Za-z0-9_]+\.tre)"', f.read()) if n != CUSTOM_TRE]
    tres = datatable.TreSet(args.tre_dir, tre_order)
    if not tres.archives:
        raise SystemExit(f"No TRE files from {CONFIG} found in {args.tre_dir}")

    for vehicle, stats in STATS.items():
        name = TEMPLATE.format(vehicle)
        out_path = os.path.join(PATCHES, name)
        if vehicle in IMPORTED:
            if not os.path.exists(out_path):
                raise SystemExit(f"{out_path} missing; run import_aotc.py first")
            with open(out_path, "rb") as f:
                data = f.read()
            source = "patches"
        else:
            source, data = tres.get(name)

        patched, changes = patch(data, stats)
        run, accel, turn = stats["speed"][0], stats["acceleration"][0], stats["turnRate"][0]
        print(f"{vehicle} ({source}): {'; '.join(changes)}")
        print(f"  {run / accel:.2f} s to top speed, {run / math.radians(turn):.1f} m turning radius at top speed")

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(patched)

    print("Next: python3 tools/patch/build.py --install <tre_dir>, restart the server, publish the patch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
