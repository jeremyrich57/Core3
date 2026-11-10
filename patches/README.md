# Custom client files

Files here override the original SWG client data for both the server and players' clients.
Put each file at its client path, for example
`patches/datatables/creation/attribute_limits.iff`.

```sh
python3 tools/patch/build.py --install ~/tre   # pack into build/patches/core3_custom.tre and install for the server
```

- The server loads `core3_custom.tre` first (top of `Core3.TreFiles` in `MMOCoreORB/bin/conf/config.lua`), so these files win over the stock TREs.
- The launcher downloads the TRE using `build/patches/manifest.json` and gives it the highest client search priority.
- Server and client must see the same data. After changing a file, rebuild, restart the server, and publish the patch.

## Generated files

- `datatables/creation/attribute_limits.iff`: stat migration limits rescaled to match `attributeRangeMin/Max/Rounding`
  in `MMOCoreORB/bin/scripts/managers/player_creation_manager.lua`. Regenerate after changing those values:
  `python3 tools/patch/attribute_limits.py ~/tre`. If it doesn't match, the server disables stat migration at startup.
- `ui/` and `texture/font/`: larger UI for high-resolution screens, from `python3 tools/patch/large_ui.py ~/tre`
  (see the script's docstring).
  - `ui/ui_textstylemanager.inc` + `ui/font/l1|l2/`: opt-in larger text, chosen by the client's `[SharedGame] fontLocale`
    (`l1` ≈1.2x, `l2` ≈1.4x), which the launcher's "In-game text size" setting writes. `texture/font/` restores stock
    font sizes that patch_10 blanked.
  - `ui/ui_ground_hud_{toolbar,buttonbar,attribmod,combat_queue}.inc`: toolbar, button bar, buff icons and combat queue
    scaled 1.5x for everyone (`--hud-scale`).
