# data/

Local datasets. **Everything in this folder is gitignored** except this file and
[`sources.yaml`](sources.yaml), the provenance index.

Datasets can be large (STARDATA alone is ~365 GB compressed). If you keep them on another
drive, point `GARY_DATA` at that folder; tools default to `./data` when it is unset.

## Layout

```
data/
  raw/                  # replays exactly as downloaded; never modified
    stardata/           # STARDATA (1.16.1). Original .rep files and/or TorchCraft dumps
      replays/          #   original .rep files
      dumped/           #   TorchCraft-extracted states, if downloaded
    tl/                 # TeamLiquid community replay packs, one subfolder per pack
      progames/         #   pro players' replay folders, one subfolder per original pack
    cwal/               # cwal.gg ladder replays (SC:R)
  interim/              # parsed outputs: screp JSON, resim states, desync reports
  processed/            # training-ready datasets, indexes, splits
```

## Rules

1. **`raw/` is read-only.** Never edit or rename downloaded files. Derived data goes to
   `interim/` or `processed/`.
2. **One folder per source.** Each source has an entry in `sources.yaml` with its URL, license or
   terms, game version and download date.
3. **Sub-packs keep their original names**, e.g. `raw/tl/<pack-name>/`.
4. **Nothing from here goes to GitHub.** A small, vetted subset lives in
   [`tests/fixtures/replays/`](../tests/fixtures/replays/) instead.
