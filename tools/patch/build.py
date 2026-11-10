#!/usr/bin/env python3
"""Pack the custom client files in patches/ into a TRE and write the launcher manifest.

    python3 tools/patch/build.py                       # -> build/patches/
    python3 tools/patch/build.py --install ~/tre       # also copy the TRE to the server's TrePath

Every file under patches/ is stored at its path relative to patches/, e.g.
patches/datatables/creation/attribute_limits.iff -> datatables/creation/attribute_limits.iff.
The server loads the TRE because "core3_custom.tre" is first in Core3.TreFiles (bin/conf/config.lua),
and the launcher gives it the highest client search priority, so these files override the originals.

Optional client-only patches: each folder patches-opt/<option>/ is packed into core3_opt_<option>.tre and listed
in the manifest above core3_custom.tre. The launcher downloads them all but only loads the ones selected in its
Mods screen (it recognizes them by the core3_opt_ prefix). The server doesn't load them, so they must not change
anything the server reads (datatables, object templates); client UI layouts are fine.
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
OPTIONAL_PREFIX = "core3_opt_"
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
    ap.add_argument("--opt", default=os.path.join(REPO, "patches-opt"), help="optional patch folders (default: patches-opt/)")
    ap.add_argument("--out", default=os.path.join(REPO, "build", "patches"), help="output dir (default: build/patches/)")
    ap.add_argument("--install", metavar="TRE_DIR", help="copy the TRE into this dir (the server's Core3.TrePath)")
    args = ap.parse_args()

    files = collect(args.src)
    if not files:
        print(f"No files in {args.src}; nothing to build.")
        return 1

    os.makedirs(args.out, exist_ok=True)
    # Highest client search priority first: optional patches override the base one.
    archives = []
    if os.path.isdir(args.opt):
        for option in sorted(os.listdir(args.opt)):
            if os.path.isdir(os.path.join(args.opt, option)) and not option.startswith("."):
                if not option.replace("_", "").isalnum():
                    raise SystemExit(f"{args.opt}/{option}: option names may only use letters, digits and _")
                archives.append((f"{OPTIONAL_PREFIX}{option}.tre", collect(os.path.join(args.opt, option))))
    archives.append((TRE_NAME, files))

    # Remove archives from earlier builds whose option folder is gone.
    for old in os.listdir(args.out):
        if old.startswith(OPTIONAL_PREFIX) and old.endswith(".tre") and old not in dict(archives):
            os.remove(os.path.join(args.out, old))

    entries = []
    for name, contents in archives:
        if not contents:
            continue
        path = os.path.join(args.out, name)
        tre.write(path, contents)
        entries.append({"name": name, "size": os.path.getsize(path), "sha256": sha256(path)})
        print(f"{path}: {len(contents)} file(s), {entries[-1]['size']} bytes")
        for f_name in sorted(contents):
            print(f"  {f_name}")

    manifest = {"schema": MANIFEST_SCHEMA, "files": entries}
    with open(os.path.join(args.out, "manifest.json"), "w", newline="\n") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    tre_path = os.path.join(args.out, TRE_NAME)

    if args.install:
        dest = os.path.join(os.path.expanduser(args.install), TRE_NAME)
        shutil.copyfile(tre_path, dest)
        print(f"installed -> {dest} (restart the server to load it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
