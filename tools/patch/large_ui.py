#!/usr/bin/env python3
"""Generate the large-UI client files in patches/ui/ (bigger text and bigger HUD icons).

    python3 tools/patch/large_ui.py ~/tre
    python3 tools/patch/build.py --install ~/tre

The SWG client has no global UI scale; every window is laid out in pixels for 1024x768. This adds two things:

Larger text (opt-in per player)
    UI elements ask for fonts by face and size ("default_12", "bold_20"). ui_textstylemanager.inc maps faces to
    bitmap fonts per *font locale* (FontFaces_<locale>_<face>, Fonts_<locale>), and the client picks the locale
    with the config key [SharedGame] fontLocale (default "en"). This adds locales whose fonts are the stock
    glyphs one or two sizes up, saved under the smaller sizes' names:

        l1  "Large"   about 1.2x   (default_12 draws verdana 14)
        l2  "Larger"  about 1.4x   (default_12 draws verdana 17)

    The launcher's "UI text size" setting writes fontLocale. Without it nothing changes. Window and button
    sizes stay the same, so bigger text can be clipped in tight spots.
    Some stock sizes (verdana 24/30/34, bold 30/34, lucida console 16/18) were blanked by patch_10; their last
    good version (font file + textures from the same TRE) is restored to have bigger glyphs to draw from.

Bigger HUD icons (everyone)
    The toolbar, button bar, buff icons and combat queue are scaled by --hud-scale (default 1.5): every position
    and size in those windows, plus their fonts. The window keeps its screen anchor (left/right/center edge).
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datatable  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = os.path.join(REPO, "MMOCoreORB", "bin", "conf", "config.lua")
PATCHES = os.path.join(REPO, "patches")
CUSTOM_TRE = "core3_custom.tre"

STYLE_MANAGER = "ui/ui_textstylemanager.inc"
# Font face -> bitmap font name. "aurabesh" stays as is.
FACES = {"default": "verdana", "bold": "verdana_bold", "fixed": "lucida_console"}
# Font locale -> text scale.
LOCALES = {"l1": 1.2, "l2": 1.4}
# Blanked stock sizes worth restoring (only bigger sizes are useful here).
MIN_RESTORE_SIZE = 16

HUD_FILES = [
    "ui/ui_ground_hud_toolbar.inc",
    "ui/ui_ground_hud_buttonbar.inc",
    "ui/ui_ground_hud_attribmod.inc",
    "ui/ui_ground_hud_combat_queue.inc",
]
# The ground HUD page these windows sit in is laid out at this size.
HUD_SIZE = (1024, 768)
GEOMETRY = (
    "Location", "Size", "ScrollExtent", "MinimumSize", "MaximumSize", "MinimumScrollExtent",
    "CellSize", "CellPadding", "SizeIncrement", "IconMargin", "Margin",
)
GEOMETRY_RE = re.compile(r"(?<![A-Za-z.])(" + "|".join(GEOMETRY) + r")='(-?\d+(?:,-?\d+)*)'")
FONT_RE = re.compile(r"Font='(default|bold|fixed)_(\d+)'")
STYLE_NAME_RE = re.compile(r"(<textstyle\b[^>]*?\bname=)'([^']*)'", re.IGNORECASE | re.DOTALL)
SOURCE_FILE_RE = re.compile(r"sourcefile='([^']+)'", re.IGNORECASE)


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


class Archives:
    """Every version of a file across the stock TREs, newest (highest priority) first."""

    def __init__(self, tre_dir: str):
        with open(CONFIG) as f:
            order = [n for n in re.findall(r'"([A-Za-z0-9_]+\.tre)"', f.read()) if n != CUSTOM_TRE]
        self.set = datatable.TreSet(tre_dir, order)
        if not self.set.archives:
            raise SystemExit(f"No TRE files from {CONFIG} found in {tre_dir}")

    def latest(self, name: str) -> bytes:
        return self.set.get(name)[1]

    def has(self, name: str) -> bool:
        try:
            return bool(self.latest(name))
        except FileNotFoundError:
            return False

    def versions(self, name: str):
        for archive, records, raw in self.set.archives:
            if name in records:
                yield archive, datatable.tre.read_file(raw, records[name])

    def in_archive(self, archive: str, name: str) -> bytes | None:
        for a, records, raw in self.set.archives:
            if a == archive and name in records:
                return datatable.tre.read_file(raw, records[name])
        return None


def font_sizes(arc: Archives, font: str, restored: dict[str, bytes]) -> dict[int, bytes]:
    """Usable sizes of a bitmap font -> its .inc text. Restored textures are added to `restored`."""
    sizes = {}
    names = {r for _, records, _ in arc.set.archives for r in records}
    for name in names:
        m = re.fullmatch(rf"ui/font/{font}_(\d+)\.inc", name)
        if not m:
            continue
        size = int(m.group(1))
        data = arc.latest(name)
        if data:
            textures = {f"texture/{s}.dds" for s in SOURCE_FILE_RE.findall(data.decode("latin-1"))}
            if textures and all(arc.has(t) for t in textures):
                sizes[size] = data
            continue
        if size < MIN_RESTORE_SIZE:
            continue
        for archive, old in arc.versions(name):
            if not old:
                continue
            textures = {f"texture/{s}.dds" for s in SOURCE_FILE_RE.findall(old.decode("latin-1"))}
            found = {t: arc.in_archive(archive, t) for t in textures}
            if textures and all(found.values()):
                sizes[size] = old
                restored.update(found)
            break
    return sizes


def pick_size(size: int, scale: float, available: list[int]) -> int:
    """The available size nearest to size * scale (ties go up), never smaller than size."""
    want = size * scale
    bigger = [s for s in available if s >= size] or [max(available)]
    return min(bigger, key=lambda s: (abs(s - want), -s))


def font_files(arc: Archives) -> tuple[dict[str, bytes], dict[str, bytes]]:
    """Files for the large-text locales, and the textures restored for them."""
    restored: dict[str, bytes] = {}
    available = {face: font_sizes(arc, font, restored) for face, font in FACES.items()}
    out: dict[str, bytes] = {}

    manager = arc.latest(STYLE_MANAGER).decode("latin-1")
    stock_fonts = re.search(r"Fonts_en='([^']*)'", manager).group(1)
    aurabesh = [p for p in re.split(r"[\r\n]+", stock_fonts) if p.startswith("font/aurabesh")]

    faces_lines, fonts_lines = [], []
    used_textures = set()
    for locale, scale in LOCALES.items():
        paths, mapping = [], []
        for face, font in FACES.items():
            sizes = sorted(available[face])
            faces_lines.append(f"\t\t\tFontFaces_{locale}_{face}='{font}_{locale}'")
            for size in sizes:
                source = available[face][pick_size(size, scale, sizes)].decode("latin-1")
                text, n = STYLE_NAME_RE.subn(rf"\1'{font}_{locale}_{size}'", source, count=1)
                if n != 1:
                    raise SystemExit(f"{font}_{size}: no <TextStyle Name=...> found")
                used_textures |= {f"texture/{s}.dds" for s in SOURCE_FILE_RE.findall(text)}
                mapping.append(f"{face}_{size}->{pick_size(size, scale, sizes)}")
                path = f"font/{locale}/{font}_{size}.inc"
                out[f"ui/{path}"] = text.encode("latin-1")
                paths.append(path)
        faces_lines.append(f"\t\t\tFontFaces_{locale}_aurabesh='aurabesh'")
        print(f"fontLocale={locale} (x{scale}): {' '.join(mapping)}")
        fonts_lines.append(f"\t\t\tFonts_{locale}='" + "\r\n".join(paths + aurabesh) + "'")

    if "FontFaces_l1_" in manager:
        raise SystemExit(f"{STYLE_MANAGER} already has the large-text locales")
    anchor = re.search(r"\t*FontLocale=", manager)
    manager = manager[:anchor.start()] + "\r\n".join(faces_lines) + "\r\n" + manager[anchor.start():]
    end = re.search(r"\t*/>", manager)
    manager = manager[:end.start()] + "\r\n".join(fonts_lines) + "\r\n" + manager[end.start():]
    out[STYLE_MANAGER] = manager.encode("latin-1")

    return out, {t: d for t, d in restored.items() if t in used_textures}


def scale_hud(text: str, scale: float, bold_sizes: list[int], default_sizes: list[int]) -> str:
    first = text.index(">")
    root, rest = text[:first], text[first:]

    def scale_attr(m: re.Match) -> str:
        # A resize step of 1 pixel means "any size"; keep it.
        keep = (0, 1) if m.group(1) == "SizeIncrement" else (0,)
        values = ",".join(v if int(v) in keep else str(round_half_up(int(v) * scale)) for v in m.group(2).split(","))
        return f"{m.group(1)}='{values}'"

    def attr(block: str, name: str) -> str | None:
        m = re.search(rf"(?<![A-Za-z.]){name}='([^']*)'", block)
        return m.group(1) if m else None

    # The window itself: scale its size but keep the edge it is anchored to.
    old_size = [int(v) for v in attr(root, "Size").split(",")]
    location = [int(v) for v in attr(root, "Location").split(",")]
    pack = (attr(root, "PackLocation") or "nfn,nfn").split(",")
    new_root = GEOMETRY_RE.sub(lambda m: m.group(0) if m.group(1) == "Location" else scale_attr(m), root)
    new_size = [round_half_up(v * scale) for v in old_size]
    for axis in (0, 1):
        anchor = pack[axis][:1] if axis < len(pack) else "n"
        grow = new_size[axis] - old_size[axis]
        if anchor == "f":
            location[axis] -= grow
        elif anchor == "c":
            location[axis] -= grow // 2
        location[axis] = max(0, min(location[axis], HUD_SIZE[axis] - new_size[axis]))
    new_root = re.sub(r"(?<![A-Za-z.])Location='[^']*'", f"Location='{location[0]},{location[1]}'", new_root, count=1)

    def scale_font(m: re.Match) -> str:
        sizes = bold_sizes if m.group(1) == "bold" else default_sizes
        return f"Font='{m.group(1)}_{pick_size(int(m.group(2)), scale, sizes)}'"

    rest = GEOMETRY_RE.sub(scale_attr, rest)
    return FONT_RE.sub(scale_font, new_root + rest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tre_dir", help="directory with the stock client TREs (the server's Core3.TrePath)")
    ap.add_argument("--hud-scale", type=float, default=1.5, help="HUD icon window scale (default 1.5; 1 = stock)")
    args = ap.parse_args()

    arc = Archives(args.tre_dir)
    files, textures = font_files(arc)

    if args.hud_scale != 1:
        # HUD fonts must exist in the stock "en" locale, so only use sizes it loads.
        stock_fonts = re.search(r"Fonts_en='([^']*)'", arc.latest(STYLE_MANAGER).decode("latin-1")).group(1)
        en = re.findall(r"font/(verdana|verdana_bold)_(\d+)\.inc", stock_fonts)
        default_sizes = sorted(int(s) for f, s in en if f == "verdana")
        bold_sizes = sorted(int(s) for f, s in en if f == "verdana_bold")
        for name in HUD_FILES:
            text = arc.latest(name).decode("latin-1")
            files[name] = scale_hud(text, args.hud_scale, bold_sizes, default_sizes).encode("latin-1")

    # Start clean so files from an earlier run with other settings don't linger.
    for d in (os.path.join(PATCHES, "ui"), os.path.join(PATCHES, "texture", "font")):
        shutil.rmtree(d, ignore_errors=True)
    for name, data in {**files, **textures}.items():
        path = os.path.join(PATCHES, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    print(f"Wrote {len(files)} UI file(s) and {len(textures)} restored font texture(s) under {PATCHES}")
    print(f"  HUD icons x{args.hud_scale}: {', '.join(os.path.basename(n) for n in HUD_FILES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
