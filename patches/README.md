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
