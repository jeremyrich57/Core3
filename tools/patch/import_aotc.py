#!/usr/bin/env python3
"""Import vehicles from an SWG AotC client install into patches/.

    python3 tools/patch/import_aotc.py /mnt/c/SWGAoTC ~/tre
    python3 tools/patch/build.py --install ~/tre

AotC ships extra client content (e.g. the BARC and STAP speeders) in its own TREs. This copies what the vehicles in
VEHICLES need into patches/ at their client paths, so core3_custom.tre carries them for both the server (which reads
the shared object templates and mount tables) and players' clients (models, textures, rider animations):

- Every file the vehicles' object templates reference, followed recursively (appearances, meshes, skeletons,
  shaders, textures, client data, rider animations), but only files the stock TREs don't already have.
- datatables/mount/*.iff: the stock tables plus AotC's rows for these vehicles' saddles.
- appearance/lat/all_m.lat: the stock humanoid animation table plus AotC's rider poses for these vehicles, so the
  rider sits on the vehicle with the right pose instead of a T-pose.
- string/en/*.stf: the stock tables plus the vehicles' names and descriptions.

AotC's own copies of the shared tables (all_m.lat, the mount datatables, string tables) carry many other changes, so
only the rows for these vehicles are grafted onto the stock files. Re-run after adding a vehicle to VEHICLES.
Server-side templates (deeds, control devices, draft schematics) live in MMOCoreORB/bin/scripts as usual.
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datatable  # noqa: E402
import stf  # noqa: E402
import tre  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = os.path.join(REPO, "MMOCoreORB", "bin", "conf", "config.lua")
PATCHES = os.path.join(REPO, "patches")
CUSTOM_TRE = "core3_custom.tre"

VEHICLES = {
    "barc_speeder": {
        "templates": [
            "object/mobile/vehicle/shared_barc_speeder.iff",
            "object/intangible/vehicle/shared_barc_speeder_pcd.iff",
            "object/tangible/deed/vehicle_deed/shared_barc_speeder_deed.iff",
            "object/draft_schematic/vehicle/civilian/shared_barc_speeder.iff",
            "object/tangible/loot/loot_schematic/shared_barc_speeder_schematic.iff",
        ],
        "saddle": "lookup/clone_barc_speeder",  # logical saddle name in datatables/mount
        "rider_pose": "vehicle_barc_speeder",  # rider_pose value in all_m.lat
        "strings": {
            "monster_name": ["barc_speeder"],
            "monster_detail": ["barc_speeder"],
            "pet_deed": ["barc_speeder"],
            "craft_vehicle_ingredients_n": ["barc_speeder_schematic"],
            "craft_vehicle_ingredients_d": ["barc_speeder_schematic"],
        },
    },
    "stap_speeder": {
        "templates": [
            "object/mobile/vehicle/shared_stap_speeder.iff",
            "object/intangible/vehicle/shared_stap_speeder_pcd.iff",
            "object/tangible/deed/vehicle_deed/shared_speeder_stap_deed.iff",
            "object/draft_schematic/vehicle/civilian/shared_speeder_stap.iff",
            "object/tangible/loot/loot_schematic/shared_speeder_stap_schematic.iff",
        ],
        "saddle": "lookup/stap_speeder",
        "rider_pose": "vehicle_stap_speeder",
        "strings": {
            "monster_name": ["stap_speeder"],
            "monster_detail": ["stap_speeder"],
            "item_n": ["speeder_stap_deed"],
            "item_d": ["speeder_stap_deed"],
            "craft_vehicle_ingredients_n": ["speeder_stap_schematic"],
            "craft_vehicle_ingredients_d": ["speeder_stap_schematic"],
        },
    },
}

RIDER_LAT = "appearance/lat/all_m.lat"
MOUNT_TABLES = "datatables/mount/"

# Paths inside IFF data. The bytes before a path are often IFF lengths that happen to be printable, so candidates are
# cut back to a known top-level folder; LOD files name meshes relative to appearance/.
TOP_DIRS = ("appearance/", "clientdata/", "datatables/", "object/", "palette/", "shader/", "sound/", "texture/",
            "effect/", "misc/")
PATH_RE = re.compile(
    rb"[A-Za-z0-9_\-/.]+\.(?:iff|apt|sat|lod|msh|mgn|lmg|skt|ans|lat|ash|sht|eft|dds|cdf|cmp|prt|pal|snd|wav|psh|vsh)\b"
)


class Archives:
    """Files across a list of TREs, highest priority first. Only the record tables are read up front."""

    def __init__(self, paths: list[str]):
        self.index: dict[str, list[tuple[str, tre.Record]]] = {}
        for path in paths:
            for record in _read_records(path):
                self.index.setdefault(record.name, []).append((path, record))

    def __contains__(self, name: str) -> bool:
        return name in self.index

    def get(self, name: str) -> bytes:
        path, record = self.index[name][0]
        return _read_record(path, record)

    def source(self, name: str) -> str:
        return os.path.basename(self.index[name][0][0])


def _read_records(path: str) -> list[tre.Record]:
    with open(path, "rb") as f:
        header = f.read(tre.HEADER.size)
        magic, version, count, toc_offset, toc_comp, toc_size, names_comp, names_size, names_usize = \
            tre.HEADER.unpack(header)
        if magic != tre.MAGIC or version != tre.VERSION:
            raise SystemExit(f"{path}: not a version 0005 TRE")
        f.seek(toc_offset)
        toc = tre._unpack_block(f.read(toc_size), toc_comp, count * tre.RECORD.size)
        names = tre._unpack_block(f.read(names_size), names_comp, names_usize)
    records = []
    for i in range(count):
        crc, size, offset, comp, stored, name_off = tre.RECORD.unpack_from(toc, i * tre.RECORD.size)
        name = names[name_off:names.index(b"\0", name_off)].decode("ascii")
        records.append(tre.Record(name, crc, size, offset, comp, stored, b""))
    return records


def _read_record(path: str, record: tre.Record) -> bytes:
    stored = record.size if record.compression == tre.COMPRESSION_NONE else record.stored_size
    with open(path, "rb") as f:
        f.seek(record.offset)
        data = f.read(stored)
    if record.compression == tre.COMPRESSION_ZLIB:
        return zlib.decompress(data)
    return data[:record.size]


def stock_archives(tre_dir: str) -> Archives:
    with open(CONFIG) as f:
        order = [n for n in re.findall(r'"([A-Za-z0-9_]+\.tre)"', f.read()) if n != CUSTOM_TRE]
    paths = [os.path.join(tre_dir, n) for n in order if os.path.exists(os.path.join(tre_dir, n))]
    if not paths:
        raise SystemExit(f"No TRE files from {CONFIG} found in {tre_dir}")
    return Archives(paths)


def aotc_archives(client_dir: str) -> Archives:
    """AotC's TREs in its client search order (swgemu_live.cfg: higher searchTree priority wins)."""
    with open(os.path.join(client_dir, "swgemu_live.cfg"), errors="replace") as f:
        entries = re.findall(r"searchTree_\d+_(\d+)\s*=\s*(\S+\.tre)", f.read())
    paths = [os.path.join(client_dir, name) for _, name in sorted(entries, key=lambda e: -int(e[0]))]
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        raise SystemExit(f"No searchTree TREs from {client_dir}/swgemu_live.cfg found")
    return Archives(paths)


# --- IFF ---

def iff_parse(data: bytes, pos: int = 0, end: int | None = None) -> list:
    """[(tag, form_type | None, children | bytes)]"""
    end = len(data) if end is None else end
    nodes = []
    while pos < end:
        tag = data[pos:pos + 4].decode("latin1")
        (size,) = struct.unpack_from(">I", data, pos + 4)
        if tag == "FORM":
            nodes.append(["FORM", data[pos + 8:pos + 12].decode("latin1"), iff_parse(data, pos + 12, pos + 8 + size)])
        else:
            nodes.append([tag, None, data[pos + 8:pos + 8 + size]])
        pos += 8 + size
    return nodes


def iff_dump(nodes: list) -> bytes:
    out = b""
    for tag, form, body in nodes:
        if tag == "FORM":
            body = form.encode("latin1") + iff_dump(body)
        out += tag.encode("latin1") + struct.pack(">I", len(body)) + body
    return out


# --- asset closure ---

def _candidates(path: str) -> list[str]:
    path = path.lower()
    out = [path]
    for top in TOP_DIRS:
        i = path.find(top)
        if i > 0:
            out.append(path[i:])
    out.append("appearance/" + path)
    return out


def references(data: bytes) -> list[str]:
    return [m.decode("latin1") for m in PATH_RE.findall(data) if b"/" in m]


def asset_closure(roots: list[str], aotc: Archives, stock: Archives) -> tuple[dict[str, bytes], set[str]]:
    """AotC files reachable from roots that the stock TREs lack. Also returns references found nowhere."""
    files: dict[str, bytes] = {}
    missing: set[str] = set()
    known = lambda p: p in aotc or p in stock  # noqa: E731
    queue = [next((c for c in _candidates(r) if known(c)), r) for r in roots]
    seen = set()
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        if name in stock and name not in roots:
            continue
        if name not in aotc:
            missing.add(name)
            continue
        data = aotc.get(name)
        files[name] = data
        for ref in references(data):
            hit = next((c for c in _candidates(ref) if known(c)), None)
            if hit:
                queue.append(hit)
            else:
                # e.g. a shader AotC itself doesn't ship: reported, not fatal.
                missing.add(ref.lower())
    return files, missing


# --- mount datatables ---

def merge_rows(stock: datatable.DataTable, aotc: datatable.DataTable, keep) -> tuple[datatable.DataTable, list]:
    if stock.columns != aotc.columns:
        raise SystemExit(f"column mismatch: stock {stock.columns} vs AotC {aotc.columns}")
    added = []
    for row in aotc.rows:
        if keep(row) and row not in stock.rows and row not in added:
            added.append(row)
    stock.rows.extend(added)
    return stock, added


def mount_tables(vehicles: dict, aotc: Archives, stock: Archives) -> tuple[dict[str, bytes], set[str]]:
    saddles = {v["saddle"] for v in vehicles.values()}
    load = lambda src, name: datatable.parse(src.get(MOUNT_TABLES + name))  # noqa: E731
    out = {}

    logical, rows = merge_rows(load(stock, "logical_saddle_name_map.iff"), load(aotc, "logical_saddle_name_map.iff"),
        lambda r: r[1] in saddles)
    sats = {r[0] for r in rows}
    out["logical_saddle_name_map.iff"] = (logical, rows)

    appearance, rows = merge_rows(load(stock, "saddle_appearance_map.iff"), load(aotc, "saddle_appearance_map.iff"),
        lambda r: r[0] in saddles)
    apts = {r[2] for r in rows}
    client_data = {r[3] for r in rows if r[3]}
    out["saddle_appearance_map.iff"] = (appearance, rows)

    out["rider_pose_map.iff"] = merge_rows(load(stock, "rider_pose_map.iff"), load(aotc, "rider_pose_map.iff"),
        lambda r: r[0] in apts)
    out["valid_scale_range.iff"] = merge_rows(load(stock, "valid_scale_range.iff"), load(aotc, "valid_scale_range.iff"),
        lambda r: r[0] in sats)

    for vehicle in vehicles.values():
        if not any(r[1] == vehicle["saddle"] for r in logical.rows):
            raise SystemExit(f"AotC has no logical_saddle_name_map row for {vehicle['saddle']}")

    files = {}
    for name, (table, rows) in out.items():
        files[MOUNT_TABLES + name] = datatable.dump(table)
        print(f"{MOUNT_TABLES}{name}: +{len(rows)} row(s)")
        for row in rows:
            print(f"  {row}")
    return files, client_data | apts


# --- rider poses in all_m.lat ---

def _ssats(nodes: list, out: list) -> list:
    for node in nodes:
        if node[0] == "FORM":
            if node[1] == "SSAT":
                out.append(node)
            _ssats(node[2], out)
    return out


def _selector(ssat: list) -> tuple[str, list, list, dict[str, int], bytes]:
    """An SSAT picks one of its ANMS animations by a variable; VAL maps each value to an animation index."""
    body = ssat[2][0][2]
    variable = body[0][2].split(b"\0")[0].decode()
    anms = next(n for n in body if n[0] == "FORM" and n[1] == "ANMS")
    val = next(n for n in body if n[0] == "VAL ")
    data = val[2]
    (count,) = struct.unpack_from("<H", data, 0)
    pos = 2
    mapping = {}
    for _ in range(count):
        end = data.index(b"\0", pos)
        (index,) = struct.unpack_from("<H", data, end + 1)
        mapping[data[pos:end].decode()] = index
        pos = end + 3
    return variable, anms, val, mapping, data[pos:]


def _animations(lat: list) -> dict[str, list]:
    form = lat[0][2][0]  # FORM LATT > FORM 0000: INFO, then one FORM ANIM per logical animation
    return {node[2][0][2].split(b"\0")[0].decode(): node for node in form[2][1:]}


def graft_rider_poses(poses: list[str], aotc: Archives, stock: Archives) -> tuple[bytes, set[str]]:
    stock_data = stock.get(RIDER_LAT)
    lat = iff_parse(stock_data)
    if iff_dump(lat) != stock_data:
        raise SystemExit(f"{RIDER_LAT}: stock file did not round-trip")
    aotc_anims = _animations(iff_parse(aotc.get(RIDER_LAT)))
    animations = set()
    grafted = 0
    for name, anim in _animations(lat).items():
        stock_selectors = [s for s in _ssats([anim], []) if _selector(s)[0] == "rider_pose"]
        if not stock_selectors:
            continue
        if name not in aotc_anims:
            raise SystemExit(f"{RIDER_LAT}: AotC has no {name} animation to take rider poses from")
        aotc_selectors = [s for s in _ssats([aotc_anims[name]], []) if _selector(s)[0] == "rider_pose"]
        if len(aotc_selectors) != len(stock_selectors):
            raise SystemExit(f"{RIDER_LAT}: {name} has a different number of rider_pose selectors in AotC")
        for ours, theirs in zip(stock_selectors, aotc_selectors):
            _, anms, val, mapping, tail = _selector(ours)
            _, their_anms, _, their_mapping, _ = _selector(theirs)
            for pose in poses:
                if pose in mapping:
                    continue
                if pose not in their_mapping:
                    raise SystemExit(f"{RIDER_LAT}: AotC's {name} has no {pose} rider pose")
                entry = their_anms[2][1 + their_mapping[pose]]  # ANMS children: INFO (count), then animations
                anms[2].append(entry)
                mapping[pose] = len(anms[2]) - 2
                animations |= {r.lower() for r in references(iff_dump([entry]))}
                grafted += 1
            anms[2][0][2] = struct.pack("<H", len(anms[2]) - 1)
            data = struct.pack("<H", len(mapping))
            for pose, index in mapping.items():
                data += pose.encode() + b"\0" + struct.pack("<H", index)
            val[2] = data + tail
    print(f"{RIDER_LAT}: +{grafted} rider pose animation(s)")
    return iff_dump(lat), animations


# --- strings ---

def merge_strings(vehicles: dict, aotc: Archives, stock: Archives) -> dict[str, bytes]:
    wanted: dict[str, list[str]] = {}
    for vehicle in vehicles.values():
        for table, keys in vehicle["strings"].items():
            wanted.setdefault(table, []).extend(keys)
    files = {}
    for table, keys in sorted(wanted.items()):
        path = f"string/en/{table}.stf"
        # A table the stock client lacks (e.g. craft_vehicle_ingredients_d) starts out empty.
        ours = stf.parse(stock.get(path)) if path in stock else stf.StringTable(next_id=1)
        theirs = stf.parse(aotc.get(path))
        for key in keys:
            text = theirs.get(key)
            if text is None:
                raise SystemExit(f"AotC's {path} has no {key}")
            if ours.get(key) is not None and ours.get(key) != text:
                raise SystemExit(f"stock {path} already has {key}; drop it from VEHICLES")
            ours.set(key, text)
            print(f"{path}: {key} = {text!r}")
        files[path] = stf.dump(ours)
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("aotc_dir", help="AotC client install (has swgemu_live.cfg and its TREs)")
    ap.add_argument("tre_dir", help="stock TREs (the server's Core3.TrePath)")
    ap.add_argument("--out", default=PATCHES, help="patch folder (default: patches/)")
    args = ap.parse_args()

    stock = stock_archives(os.path.expanduser(args.tre_dir))
    aotc = aotc_archives(args.aotc_dir)

    files: dict[str, bytes] = {}
    mount_files, saddle_refs = mount_tables(VEHICLES, aotc, stock)
    files.update(mount_files)
    lat, rider_animations = graft_rider_poses([v["rider_pose"] for v in VEHICLES.values()], aotc, stock)
    files[RIDER_LAT] = lat
    files.update(merge_strings(VEHICLES, aotc, stock))

    roots = [t for v in VEHICLES.values() for t in v["templates"]]
    assets, missing = asset_closure(roots + sorted(saddle_refs | rider_animations), aotc, stock)
    for name in roots:
        if name not in assets:
            raise SystemExit(f"AotC has no {name}")
    files.update(assets)

    for name, data in sorted(files.items()):
        dest = os.path.join(args.out, *name.split("/"))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
    print(f"wrote {len(files)} file(s) to {args.out}:")
    for name in sorted(assets):
        print(f"  {name} ({aotc.source(name)}, {len(assets[name])} bytes)")
    if missing:
        print("referenced but in neither the stock nor the AotC TREs (AotC's client lives without them):")
        for name in sorted(missing):
            print(f"  {name}")
    print("Next: python3 tools/patch/build.py --install <tre_dir>, restart the server, publish the patch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
