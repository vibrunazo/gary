# resim

`gary_resim` re-simulates a replay in [OpenBW](https://github.com/OpenBW/openbw) without graphics
and prints state snapshots as JSON lines: resources, supply, unit counts (all / completed) per
player, and how many replay commands the engine accepted or rejected. A sustained spike in
rejected commands is the main desync signal (docs/ARCHITECTURE.md §7.2).

**Status:** builds; not yet run, waiting for game data files.

## Build (Windows)

1. Clone OpenBW next to the repo's code (it's gitignored; OpenBW has no license file, so it's
   used as an external dependency and never vendored):

   ```
   git clone --depth 1 https://github.com/OpenBW/openbw.git external/openbw
   ```

2. With Visual Studio's C++ workload installed, run `resim\build.bat`. It produces
   `resim\build\gary_resim.exe`.

## Game data

OpenBW needs StarCraft's original game data. `--data` accepts either:

- **A folder with the three classic MPQs** (`StarDat.mpq`, `BrooDat.mpq`, `Patch_rt.mpq`) from
  StarCraft 1.16.1 or 1.18.
- **A folder of loose files extracted from a newer install** (StarCraft / Remastered since 1.23
  store data in CASC, not MPQ), keeping their in-archive paths. Files OpenBW reads:
  `arr/{units,weapons,flingy,sprites,images,orders,techdata,upgrades}.dat`, `arr/images.tbl`,
  `scripts/iscript.bin`, `Tileset/*.cv5`, `Tileset/*.vf4`, `triggers/Melee.trg`, and the
  classic unit graphics under `unit/` (used for image sizes). Whether a CASC install still has
  all of these in the classic format is untested.

Game data never goes in the repo.

## Run

```
resim\build\gary_resim.exe --data <data dir> --replay tests\fixtures\replays\stardata_tvz_short_2yus7.rep --every 24
```
