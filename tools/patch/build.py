#!/usr/bin/env python3
"""Pack the custom client files in patches/ into a TRE and write the launcher manifest.

    python3 tools/patch/build.py                       # -> build/patches/
    python3 tools/patch/build.py --install ~/tre       # also copy the TRE to the server's TrePath

Every file under patches/ is stored at its path relative to patches/, e.g.
patches/datatables/creation/attribute_limits.iff -> datatables/creation/attribute_limits.iff.
The server loads the TRE because "core3_custom.tre" is first in Core3.TreFiles (bin/conf/config.lua),
and the launcher gives it the highest client search priority, so these files override the originals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tre  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRE_NAME = "core3_custom.tre"
MANIFEST_SCHEMA = 1
IGNORED = {"README.md", ".gitkeep", ".DS_Store", "Thumbs.db"}


def collect(src: str) -> dict[str, bytes]:
    files = {}
    for root, dirs, names in os.walk(src):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(names):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, src).replace(os.sep, "/")
            if name in IGNORED or name.startswith("."):
                continue
            with open(full, "rb") as f:
                files[rel] = f.read()
    return files


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=os.path.join(REPO, "patches"), help="custom client files (default: patches/)")
    ap.add_argument("--out", default=os.path.join(REPO, "build", "patches"), help="output dir (default: build/patches/)")
    ap.add_argument("--install", metavar="TRE_DIR", help="copy the TRE into this dir (the server's Core3.TrePath)")
    args = ap.parse_args()

    files = collect(args.src)
    if not files:
        print(f"No files in {args.src}; nothing to build.")
        return 1

    os.makedirs(args.out, exist_ok=True)
    tre_path = os.path.join(args.out, TRE_NAME)
    tre.write(tre_path, files)

    manifest = {
        "schema": MANIFEST_SCHEMA,
        # Highest client search priority first.
        "files": [{"name": TRE_NAME, "size": os.path.getsize(tre_path), "sha256": sha256(tre_path)}],
    }
    with open(os.path.join(args.out, "manifest.json"), "w", newline="\n") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"{tre_path}: {len(files)} file(s), {manifest['files'][0]['size']} bytes")
    for name in sorted(files):
        print(f"  {name}")

    if args.install:
        dest = os.path.join(os.path.expanduser(args.install), TRE_NAME)
        shutil.copyfile(tre_path, dest)
        print(f"installed -> {dest} (restart the server to load it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
