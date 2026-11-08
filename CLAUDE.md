# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

SWGEmu Core3 is a C++ server emulator for Star Wars Galaxies (Pre-CU era), built on the **engine3** framework (git submodule at `MMOCoreORB/utils/engine3`). Nearly all code lives under `MMOCoreORB/`. Game content and tuning live in Lua under `MMOCoreORB/bin/scripts/`. Running the server requires the original client `.tre` files plus MariaDB.

Toolchain: Debian 12, clang 19, CMake 3.18+, Ninja, Java runtime (for the IDL compiler), BerkeleyDB 5.3, Lua 5.3, MariaDB client, OpenSSL, boost. Setup helpers: `docker/` (`build.sh`, `run.sh`, then `build`/`run` inside the container), `linux/bootstrap.sh`, `wsl2/`.

## Build

Run from `MMOCoreORB/`:

```sh
git submodule update --init            # engine3, if not already checked out
make build-ninja-debug                 # dev build -> build/unix/ninja-debug (Debug)
make build-ninja-debugoptimized        # RelWithDebInfo -> build/unix/ninja-debugoptimized
make build-ninja                       # Release -> build/unix/ninja
make -j$(nproc)                        # production (make-based, RelWithDebInfo, build/unix)
make build-ninja-debug NINJA_ARGS=core3   # pass extra args/targets to ninja
make build-ninja-debug CMAKE_ARGS="-DENABLE_ASAN=ON"
```

Notable CMake options (`MMOCoreORB/CMakeLists.txt`): `COMPILE_TESTS` (ON), `ENABLE_ERROR_ON_WARNINGS` (ON — warnings break the build), `ENABLE_ASAN`/`ENABLE_TSAN`/`ENABLE_UBSAN`, `ENABLE_DEV_MODE`, `ENABLE_ODB`, `ENABLE_SWGREALMS`, `ENABLE_REST_SERVER`. `make build-cmake-compdb` produces `compile_commands.json`.

The resulting `core3` binary runs from `MMOCoreORB/bin/` (working directory matters — it loads `conf/`, `scripts/`, `databases/` relative to it).

## Run / Test

```sh
cd MMOCoreORB/bin
gdb ./core3                    # then `r`; or ./core3 directly
./core3 runUnitTests                                   # all gtest/gmock tests
./core3 runUnitTests --gtest_filter='StringTest.*'     # single suite/test
./core3 testScreenPlays                                # load-check all Lua screenplays
```

Tests are not a separate executable: `src/tests/*.cpp` are compiled into `core3` itself (guarded by `COMPILE_CORE3_TESTS`) and invoked via the `runUnitTests` argument (see `src/main.cpp`). `ctest` in the build dir runs the same thing. `src/tests/TestCore.h` sets up the minimal server environment tests need.

Local config overrides go in `MMOCoreORB/bin/conf/config-local.lua` (defaults in `config.lua`). `make cleardb` wipes `bin/databases/` (the BerkeleyDB object store).

## Architecture

### IDL-generated distributed objects (most important concept)

Core game classes are declared in `.idl` files (e.g. `src/server/zone/objects/creature/CreatureObject.idl`) and compiled by engine3's Java `idlc` into C++ in `MMOCoreORB/src/autogen/` during the build. Each IDL class `Foo` produces:
- `Foo` — the stub/proxy (`ManagedReference<Foo>`) that callers use,
- `FooImplementation` — the actual logic, hand-written in `FooImplementation.cpp` next to the `.idl`,
- serialization, adapters, and (with `@mock`) a gmock `MockFoo` for tests.

Implications:
- To add/change a method or field on an IDL class, edit the `.idl` **and** the `*Implementation.cpp`; never edit `autogen/`.
- Fields are persisted automatically unless marked `transient`. Persistence is BerkeleyDB via engine3's object broker; objects are loaded/saved by object ID into `.db` files in `bin/databases/` (which db an object lands in depends on how it's created — persistent vs. transient objects matter, and many recent fixes concern objects stranded/orphaned in the wrong db or never destroyed).
- Annotations such as `@dirty`, `@read`, `@preLocked`, `@arg1preLocked`, `@local`, `@json`, `@dereferenced`, `@weakReference` change generated code (locking assertions, JSON dumps, reference types).
- Plain (non-IDL) C++ classes use `Reference<>`/`Object`; IDL objects use `ManagedReference<>`/`ManagedWeakReference<>`.

### Locking

engine3 objects carry their own locks. Use `Locker`/`ReadLocker` and `Locker(obj, alreadyLockedObj)` (cross-lock) for a second object. Methods annotated `@preLocked` assert the caller holds the lock. Many stability fixes in history are missing cross-locks or null checks on `ManagedReference`s — check both when touching gameplay code. Delayed work is done via `Task` subclasses / `Core::getTaskManager()` rather than blocking.

### Server layout (`src/server/`)

`ServerCore` boots the subsystems: `login/` (auth, character select), `zone/` (the game world), `chat/`, `db/` (MySQL + Berkeley wrappers), `status/`, `ping/`, `web/`, `metrics/`, `features/`.

Within `zone/`:
- `ZoneServer` owns everything; `Zone` (ground: `GroundZone`, space: `SpaceZone`) is a planet/space instance with a QuadTree/Octree for spatial queries and `CloseObjectsVector` for in-range tracking.
- `objects/` — the SceneObject hierarchy (`SceneObject` → `TangibleObject` → `CreatureObject` → `AiAgent`, plus building, cell, ship, player, intangible, etc.). Behavior is also extended via components (container, zone, data-object components) configured in templates.
- `managers/` — singletons/services per game system (combat, crafting, mission, structure, player, creature, loot, resource, ship/space, `director/` = Lua screenplay engine, `objectcontroller/` = command queue dispatch).
- `packets/` — client message (de)serialization; `ZonePacketHandler` dispatches inbound messages.
- `objects/creature/commands/` — one header per player command (`*Command.h`), wired to `bin/scripts/commands/*.lua`.

Other `src/` dirs: `templates/` (C++ side of object templates loaded from Lua), `terrain/`, `pathfinding/` (Recast navmeshes), `tre3/` (reading client TRE archives), `conf/` (ConfigManager), `client/` (test client), `odb/` (`odb3` offline database tool, `ENABLE_ODB`).

### Lua content (`bin/scripts/`)

Object templates (`object/`), mobiles (`mobile/`), loot, skills, command definitions, AI behavior trees (`ai/`, `ai_space/`), manager configuration (`managers/`), and screenplays (`screenplays/` — quests/events run by `DirectorManager`). Many systems are data-driven from here; prefer changing Lua over C++ when the behavior is configured there. Use `nil` (not `nullptr`) in Lua.

## Conventions

- Code style: tabs for indentation, `ClassNameImplementation::method` in Implementation files, `info()/error()/debug()` logging via `Logger`.
