# resim

`gary_resim` re-simulates a replay in [OpenBW](https://github.com/OpenBW/openbw) without graphics
and prints state snapshots as JSON lines: resources, supply, unit counts (all / completed) per
player, and how many replay commands the engine accepted or rejected. A sustained spike in
rejected commands is the main desync signal (docs/ARCHITECTURE.md §7.2).

**Status:** works with game data extracted from the free StarCraft client (CASC storage). The four
fixture replays (1.16.1-era) simulate in sync: buildings appear in the simulation within seconds of
the replay's build commands. Speed: a 30-minute game takes ~3 s (~15,000 frames per second).

## Build (Windows)

1. Clone OpenBW next to the repo's code (it's gitignored; OpenBW has no license file, so it's
   used as an external dependency and never vendored):

   ```
   git clone --depth 1 https://github.com/OpenBW/openbw.git external/openbw
   ```

2. With Visual Studio's C++ workload installed, run `resim\build.bat`. It produces
   `resim\build\gary_resim.exe`.

## Game data

OpenBW needs StarCraft's original game data. The free StarCraft client from the Battle.net app
works: `extract_gamedata` (built alongside `gary_resim` when CascLib is cloned to
`external/CascLib`) copies the needed files out of its CASC storage:

```
git clone --depth 1 https://github.com/ladislav-zezula/CascLib.git external/CascLib
resim\build.bat
resim\build\extract_gamedata.exe --install "%GARY_SC_INSTALL%" --out data\gamedata\scr
```

Set `GARY_SC_INSTALL` to your StarCraft folder (the one with `.build.info`) on your machine only;
never commit local paths. `data/` is gitignored, so the extracted files stay local.

`--data` accepts either:

- **A folder with the three classic MPQs** (`StarDat.mpq`, `BrooDat.mpq`, `Patch_rt.mpq`) from
  StarCraft 1.16.1 or 1.18.
- **A folder of loose files extracted from a newer install** (StarCraft / Remastered since 1.23
  store data in CASC, not MPQ), keeping their in-archive paths. Files OpenBW reads:
  `arr/{units,weapons,flingy,sprites,images,orders,techdata,upgrades}.dat`, `arr/images.tbl`,
  `scripts/iscript.bin`, `Tileset/*.cv5`, `Tileset/*.vf4`, `triggers/Melee.trg`, and the
  classic unit graphics and overlay files under `unit/`. The free StarCraft client's CASC storage
  has all of them in the classic format (1,098 files, ~160 MB).

Game data never goes in the repo.

## Remastered replays

OpenBW reads only the pre-1.18 replay layout. `scr_format.py` decodes 1.18+ replays into the
stream `gary_resim` reads with `--flat`, and `gary_resim` translates what changed:

- zlib-compressed sections (1.18+), plus 1.21's extra length field and new sections
- the six 1.21 command variants (right click, targeted order, unload, select, select add,
  select remove), which add a zero field after each unit ID
- map version 206 and strings in `STRx` (Remastered maps)
- the larger unit table of recent games (`--unit-limit`, from the replay's `LMTS` section):
  unit IDs use a 13-bit index and units start at the top of the bigger table
- observers' commands (player IDs 128+), which are skipped

`run_batch.py` does this automatically. What can't be carried over: the Remastered-only engine
settings (raised object limits, bug-fix flags), so some games drift; the desync detector flags
them. Set `GARY_DEBUG_REJECTS=1` to log every rejected command and unit ID that doesn't resolve.

## Run

```
resim\build\gary_resim.exe --data data\gamedata\scr --replay tests\fixtures\replays\stardata_tvz_short_2yus7.rep --every 24
```
