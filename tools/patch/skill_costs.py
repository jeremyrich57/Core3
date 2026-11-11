#!/usr/bin/env python3
"""Generate patches/datatables/skill/skills.iff with custom skill point costs and extra command grants.

    python3 tools/patch/skill_costs.py ~/tre
    python3 tools/patch/build.py --install ~/tre

Skill point costs (POINTS_REQUIRED) come from datatables/skill/skills.iff. The server reads it from the TREs
(SkillManager) to charge points, and the client reads it to show costs and remaining points, so both need the
same patched copy. This reads the stock table from the TREs (ignoring core3_custom.tre), applies COST_OVERRIDES
and COMMAND_GRANTS and writes the result. With no overrides the patched file is removed so the stock one is used.

Existing characters: the server recalculates spent points from the current costs whenever a skill is learned or
surrendered, so characters who already own a cheaper box get the difference back on their next skill change.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datatable  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG = os.path.join(REPO, "MMOCoreORB", "bin", "conf", "config.lua")
OUTPUT = os.path.join(REPO, "patches", "datatables", "skill", "skills.iff")
CUSTOM_TRE = "core3_custom.tre"

SKILLS = "datatables/skill/skills.iff"

# Skill name prefix -> new POINTS_REQUIRED for every skill (box) whose name starts with it.
# Later prefixes override earlier ones if both match.
COST_OVERRIDES = {
    "social_entertainer_hairstyle": 0,  # Entertainer's Image Design I-IV line
    "social_imagedesigner": 0,  # Image Designer: all boxes
    "science_medic_novice": 0,  # Novice Medic only; the rest of Medic keeps its stock cost
    "crafting_artisan_survey": 0,  # Artisan Survey I-IV (Novice Artisan keeps its stock 15)
    "crafting_artisan_business": 0,  # Artisan Business I-IV (Novice Merchant's prerequisite)
    "crafting_merchant_novice": 0,  # Novice Merchant only; the rest of Merchant keeps its stock cost
}

# Skill (box) name -> commands appended to its COMMANDS list. Learning the box grants the command (server) and the
# client shows it on the box. The command must exist in MMOCoreORB/bin/scripts/commands.
COMMAND_GRANTS = {
    "combat_smuggler_master": ["fastBlast"],  # Bounty Hunter master pistol attack, shared with Master Smuggler
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tre_dir", help="directory with the stock client TREs (the server's Core3.TrePath)")
    ap.add_argument("--out", default=OUTPUT, help="output file (default: patches/datatables/skill/skills.iff)")
    args = ap.parse_args()

    if not COST_OVERRIDES and not COMMAND_GRANTS:
        if os.path.exists(args.out):
            os.remove(args.out)
            print(f"No overrides; removed {args.out} so the stock file is used.")
        else:
            print("No overrides; nothing to generate.")
        return 0

    with open(CONFIG) as f:
        tre_order = [n for n in re.findall(r'"([A-Za-z0-9_]+\.tre)"', f.read()) if n != CUSTOM_TRE]
    tres = datatable.TreSet(args.tre_dir, tre_order)
    if not tres.archives:
        raise SystemExit(f"No TRE files from {CONFIG} found in {args.tre_dir}")

    source, data = tres.get(SKILLS)
    skills = datatable.parse(data)
    name_col = skills.column("NAME")
    cost_col = skills.column("POINTS_REQUIRED")

    print(f"Read {SKILLS} from {source}")
    for prefix, cost in COST_OVERRIDES.items():
        matched = [row for row in skills.rows if row[name_col].startswith(prefix)]
        if not matched:
            raise SystemExit(f"No skills start with {prefix!r}")
        before = sum(row[cost_col] for row in matched)
        for row in matched:
            row[cost_col] = cost
        print(f"  {prefix:<24} {len(matched):>3} skills, total cost {before} -> {sum(row[cost_col] for row in matched)}")

    commands_col = skills.column("COMMANDS")
    for skill, commands in COMMAND_GRANTS.items():
        rows = [row for row in skills.rows if row[name_col] == skill]
        if len(rows) != 1:
            raise SystemExit(f"Expected one skill named {skill!r}, found {len(rows)}")
        row = rows[0]
        existing = [c for c in row[commands_col].split(",") if c]
        added = [c for c in commands if c.lower() not in {e.lower() for e in existing}]
        row[commands_col] = ",".join(existing + added)
        print(f"  {skill:<24} +{','.join(added) or '(already granted)'}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "wb") as f:
        f.write(datatable.dump(skills))
    print(f"wrote {args.out}")
    print("Next: python3 tools/patch/build.py --install <tre_dir>, restart the server, publish the patch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
