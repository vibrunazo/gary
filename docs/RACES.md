# Gary across races: where the code stands

Gary is one player for every race and every matchup ([ARCHITECTURE.md §1](ARCHITECTURE.md)). TvZ
with Gary as Terran was built first. This file is the audit of how far the code is from that
goal, as of 2026-10-30, and the order in which it gets there. Update it when a step lands.

## Data

| Matchup | Replays in the inventory (Remastered era) | Re-simulated (ok) | Games in the datasets: macro / army / fight |
|---|---|---|---|
| PvZ | 22,694 (3,424) | 2,928 (2,872) | 2,820 / 2,665 / 2,665 |
| PvT | 22,456 (3,455) | 2,610 (2,562) | 2,273 / 2,166 / 2,166 |
| TvZ | 19,324 (3,329) | 18,066 (17,760) | 16,550 / 16,549 (army v5; v3 12,953) / 16,502 |
| PvP | 10,605 (3,158) | 2,781 (2,723) | 2,694 / 2,564 / 2,564 |
| ZvZ | 9,509 (3,041) | 9,216 (9,112) | 8,928 / 8,928 / 8,910 |
| TvT | 6,142 (3,048) | 5,367 (5,259) | 4,639 / 4,639 / 4,621 |

92,027 replays in all. The cwal.gg packs (2026) bring 18,886 Remastered-era games, about 3,000 per matchup;
the rest is 1.16 and before (StarData, the TL packs): old maps, old metas. Protoss's re-simulated games are
mostly the modern ones; its old packs aren't re-simulated yet. The inventory records era (`version`), source and bot flags per
replay; the trainers select on them (`train/select.py`: `--era old|modern`, `--source`, `--bots`),
so one set of datasets can train an old-era, a modern-era or a mixed model.

The pipeline is matchup-general already: `resim/run_batch.py`, the dataset builders and the
trainers take `--matchup`, and each race's unit types come from the data (`FeatureSpec.own_types`,
`seen_types`). The tech-cluster taxonomy (`taxonomy/discover.py`) runs per matchup and race; every
matchup's build styles are named in the catalogue (`gary/styles.py`) and every game labelled by
`taxonomy/label_all.py`, both sides, so each race's macro model learns every matchup's styles.

### Adding replays

Every stage is incremental, keyed by the replay's sha1: the inventory re-parses only new files,
`run_batch.py` re-simulates only replays missing from its index, the macro, army and fight
builders skip games already in theirs, and `build_orders.py` skips games already extracted and
keeps the rows of other matchups. Nothing is recomputed from scratch when replays are added;
`--force` redoes a stage on purpose. What does need redoing after new data:

- **Models** retrain from the whole dataset (hours, not days); there is no incremental training.
- **The tech-cluster taxonomy** (`taxonomy/discover.py`, HDBSCAN) can assign different cluster
  ids when re-run on more data, so the macro index's styles are rewritten
  (`macro_dataset.py --restyle`) and the macro model, which is conditioned on them, retrains. The
  Zerg plans (`taxonomy/plans.py`) are rules and stay stable.
- **The pros' decision history** (`train/macro_history.py`) is derived from the macro dataset and
  the macro model's decision index: re-run after either changes.

The inventory (`data/interim/inventory.jsonl`, one row per replay) is the index the scripts look
things up in: sha1, source and pack, era (`version`), matchup, map name and hash, duration, the
two players with race, APM, EAPM and bot flags, the winner, 1v1-human and duplicate flags. The
per-stage indexes (`resim_index.jsonl`, each dataset's `index.jsonl`, `build_orders.jsonl`) join
to it by sha1; `train/select.py` is that join for the trainers.

## Models

Every race has the same set: one macro model per race over every matchup, the matchup an input and every
matchup's styles (`runs/macro_exp/{T,Z,P}_all_v2all`); army and commit models per matchup-race; a fight role
model per matchup-race from the pros' units in that matchup (`ingest/response_dataset.py`, `train/roles.py`),
mirrors included; the critic (`train/value.py`) and the belief model per matchup and race too (2026-11-01, step 4).
Left uneven: the Terran's TvZ role model alone has had RL (rl1). Every model is found by
`manifests.model_for(kind, matchup, race)` or given per matchup in the manifest (`roles_data` keyed by matchup).

## One agent, three race plugs

The layers (arbiter, leases, macro decision loop, army, fight, motor, grouping, trace) are shared; a race is a
data module (`gary/terran.py`, `zerg.py`, `protoss.py`, read through `g.race`), an executor (the hands:
`terran_executor.py`, `zerg_executor.py`, `protoss_executor.py`) and race-keyed tables (`gary/races.py` for the
enemy, the key layouts in `grouping.py`). Each race has a manifest that plays and a
dev build where learning is done and judged without the stop-gaps (AGENTS.md):

| | Terran | Zerg | Protoss |
|---|---|---|---|
| Plays | `gt1` gt0.11 | `gz1` gz0.4 | `gp1` gp0.7 (crude) |
| Dev build | `gt1dev` gt0.28dev | `gz1dev` gz0.17dev | `gp1dev` gp0.27dev (gp0.4dev, 2026-10-30: 96 paired games a matchup against gp1, PvT -0.029, PvZ -0.068, PvP -0.076) |

## What still differs between the races

Differences of the game's mechanics are expected: each executor (add-ons, bunkers and SCVs building for the
Terran; larvae, morphs and eggs counted once for the Zerg; probes placing and leaving and pylon power for the
Protoss) and the Zerg's arbiter rotating its jobs. The rest is uneven work, to fold into shared code or race
tables over time. In the dev builds:

| Area | Terran (`gt1dev`) | Zerg (`gz1dev`) | Protoss (`gp1dev`) |
|---|---|---|---|
| Macro decoder | dice, summed odds for expansions, a queue of two in the building, built and unit counts | dice, its own extras: `pace`, `hold`, a tech floor (10%), a wait floor (5%), `hatch_mass`; built counts (gz0.13dev), no unit count | dice, summed odds, a queue of two in the building (gp0.5dev), built (gp0.6dev) and unit counts |
| Scripted macro | the answers to lurkers and mutalisks (TvZ, AGENTS.md) | the early-pool alarm's builds (the Terran's are off since gt0.18dev) | none |
| First producer by a time (`rax_by`) | 78 s | 2:45 | none |
| Fight | TvZ: the RL'd role model and the fight rules (repair, pull, load, detect, stim, reinforce); PvT and TvT: the matchup's role model | its own provider (`zerg_fight.py`: the role model, lurkers, retreat when outweighed) | the matchup's role model, the Terran's pull and reinforce; buildings placed by the pros' tables; Archons merged as a macro decision (gp0.9dev), Reavers and Carriers kept armed; Psionic Storms when and where the pros cast them (gp0.11dev); no shuttles |
| Army | the commit model, the hunt as advice, the static-defense nudge, scans | the commit model; overlord posts and mutalisk raid as rules (no model moves those units) | the commit model |
| Control groups | by type, keys 1-4 (the pros' layout) | by type, keys 1-3 | by type, keys 1-4, production 5-8 (the Protoss pros' layout, gp0.10dev) |
| Critic | every matchup (2026-11-01) | every matchup | every matchup |

The playing builds differ more: `gt1` keeps every stop-gap, `gz1` the pros' decision history in its macro inputs,
`gp1` the hunt, a Pylon ahead of production and no control groups.

## Order of work

1. **A dev build per race.** Done: `gp1dev` (2026-10-30) completes the three.
2. **One macro decoder.** Measured (2026-10-31, docs/PROGRESS.md): the Terran's queue of two in the building carries to
   the Protoss (gp0.5dev, nearer the pros at 0-10 minutes); the Zerg's `pace`, `hold` and 5% wait floor don't carry to
   the Terran or the Protoss (further from the pros in both: they are the larvae's), so they stay the Zerg's, as its
   `hatch_mass` and tech floor; the under-half rule stays for races that wait for a busy building. The Terran's built
   counts are every dev build's (gz0.13dev, gp0.6dev). Left: the Zerg's unit count (its eggs counted otherwise, #50).
3. **The fight rules as race tables.** Done (2026-10-31, docs/PROGRESS.md): the Terran's pull and reinforce run in
   any race's fight layer (option `fightrules`, one list of flyers for every race), with no measurable difference in
   TvZ for the Zerg or in PvZ and PvT for the Protoss over 96 paired games each, so off in the dev builds. The
   Terran's rules have stop-gap entries (AGENTS.md): none can go before a learned layer owns its job. The Zerg's
   retreat and its overlord posts and raid stay its own until a model moves those units; observers with the
   Protoss's army are its mechanics (step 5).
4. **A critic per matchup** (#62), then the belief model per matchup. Both trained for every matchup and race
   (2026-11-01, docs/PROGRESS.md); calibrated at the ends, the middle leaning to the pros' even games. Left: the gg
   rule itself (#62) and the league's games at time graded by the critic rather than the supply ratio (#63).
5. **The Protoss's own mechanics** (#36): archon merges, shuttles, its early defense, its key layout from the pros'
   hotkeys. Begun (2026-11-01, docs/PROGRESS.md): Reavers and Carriers kept full of Scarabs and Interceptors (they were
   built empty and never fired); Archons merged as a macro decision learned from the pros' merges, at about their rate
   in PvZ (gp0.9dev); its keys laid out as the Protoss pros' (gp0.10dev); Psionic Storms learned from the pros'
   casts (gp0.11dev); Pylons placed where they power new room, so its Gateways stand (gp0.12dev: 17 a game had been
   dropped with no spot); refused buildings taken out of its decisions so far at once (gp0.13dev); a decided building counted among its own
   until it starts, as the pros' data counts it (gp0.14dev: its second Stargate, 1.5 a game, now 1.2; the pros 1.0); its
   buildings placed where the pros place them, by base and side (gp0.15dev, eval/placement.py: the forge-first wall at
   the natural, cannons at every base; Probes lost to raids at 3-8 minutes 9.9 a game to 3.6, the pros 0.9); cannons by
   the mineral line where the pros' stand and a cannon at every base in each game (gp0.16dev: Probes lost to raids 0.75 a
   game, Mutalisk raids 4.6 Probes each to 0.38; Probes at 12:00 45.9, the pros 46.2); idle Probes sent back at once
   (gp0.17dev: idle at the main 0.46 at a time to 0.22, the pros 0.13); each building's first and second by the pros'
   shares for its build style, and tables for PvT and PvP (gp0.18dev); the gateway-first Gateway on time (gp0.19dev:
   2:26 to 1:33, the pros 1:13); Probes pulled against raids (gp0.20dev: lost at 3-8 minutes 3.48 a game to
   2.31 in 48 paired games, the pros 0.90); a building's base and side by a learned placement model in place of the
   pros' table (gp0.21dev, #65: cannons by the minerals once a Spire or Mutalisks are seen, 0.51 at 7-9 minutes, the
   table's 0.35, the pros 0.54; Mutalisk raids with no cannon by the Nexus 50% to 32%, the pros 6%); its Corsairs
   clustered apart from the ground army by a commit model that learned the pros' air clusters (gp0.23dev, army dataset
   v6: the first Corsair within 25 tiles of the Zerg's start in 35% of PvZ games, 12% before, the pros 80%); the macro
   model saving for what a building nearing done makes (gp0.24dev and gp0.25dev: the first Corsair within 10 s of the Stargate in 47%
   of PvZ games, 3% before, the pros 88%); its buildings on the tiles of one pro's layout of the map and start
   (gp0.27dev, ingest/build_tiles.py: on a tile a pro used there 97% in PvZ, 98% in PvT, 97% in PvP; 36%, 32% and 50%
   before; the pros 81%, 78%, 83%). Left: the commit
   model's answer to raids at home, shuttles, cannons at newer bases (its third Nexus later than the pros'), and
   unit mix (cannons: PvZ 24.5 at 20:00, the pros 13.8; High Templar two thirds of the pros'). The placement model is
   the Protoss's; the other races (turrets, bunkers, colonies) can have theirs from the same dataset builder.
