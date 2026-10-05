# Gary — Progress

Where each Gary version stands against [ARCHITECTURE.md](ARCHITECTURE.md). The architecture
says what Gary should become; this file says what exists. Only the components that matter at the
current stage are listed; later ones (narrator, broadcaster, language models...) join when work
on them starts.

Legend: **—** not started · **○** scripted stand-in · **◐** partial · **●** working (for now)

## Roadmap phase

**Now: P2 Micro** ([ARCHITECTURE.md §12](ARCHITECTURE.md#12-roadmap)), with a rough
P2b (first playable) reached early: Gary already plays whole TvZ games against people, through
the Remastered bridge. The phases didn't go strictly in order: the macro and army are learned
by imitation (P3-style pieces) rather than scripted, because the replay pipeline made that the
quicker way to a playable Gary.

| Phase | Status | What exists | What's missing for its exit criteria |
|---|---|---|---|
| P0 Infra | ◐ | OpenBW env, human interface v1, POV and decision logs, eval against a scripted rush and pro scenarios; ~150k 45-second scenario plays per hour on 16 parallel workers (3x faster than before profiling, same results bit for bit) | Full-game games/hour benchmark; the formal trace schema; classic bots to play against; the interface parity test |
| P1 Data | ◐ | ~70k replays indexed, resim with Remastered support (go decided: it works), fog-of-war views | Camera logger, camera inference, fitting human profiles from data (the interface's numbers are still placeholders) |
| P1b Taxonomy | ◐ | TvZ build clusters with readable rules (`taxonomy/discover.py`) | A reviewed `taxonomy/tvz/v1.yaml`, stability and gold-set reports |
| P1c Strategy stats | — | | Win-rate table, feature library, guide claims |
| **P2 Micro** | **◐ (current)** | Fight and command models learned from pro skirmishes; scenario suite from pro replays (`eval/scenarios.py`); first reinforcement learning on scenarios (`train/fight_rl.py`) | Responses within the human band: on home-defense scenarios v0.7 (rules for the basics, the command model for the rest) is the first Gary better than v0.3's scripted pull (pro +29, v0.7 −117, v0.3 −157, nothing −260) |
| P2b First playable | ◐ | Full games against people, offline, via the bridge; learned macro steered by build style | Build timings within tolerance (≥18/20 unharassed runs); supply blocks and idle production under harass within the human band |
| P2c Debug viewer | ● | POV viewer with cursor, clicks and every action in words; videos | Trace overlays beyond actions |
| P3 BC full game | ◐ (early) | Separate imitation models for macro, army movement and fights | One policy with intent and belief heads, Opponent Model, value network |
| P4 RL | ◐ (started) | Segment RL (T2a) on 45 s fight scenarios: runs, no gain yet | Elo gain at equal humanlikeness |
| P5 Explain, P5b Broadcast | — | (The POV viewer's action overlay is a start) | |
| P6 Deploy | ◐ | Remastered bridge for offline games | Pro blind-test sessions |

## Components by version

| Component | What it is | Now (v0.7) | v0.7 | v0.6 | v0.5 | v0.4 | v0.3 | v0.2 | v0.1 | v0 |
|---|---|---|---|---|---|---|---|---|---|---|
| Game: headless | OpenBW game Gary plays in for development and tests (`env/`, `gary/env.py`) | Melee games on any map, network-style command delay, replays saved | ● | ● | ● | ● | ● | ● | ● | ● |
| Game: live Remastered | Gary in a real StarCraft: Remastered client over LAN (`adapters/scr_bridge`) | Plays; known gaps in the bridge's map checks and hotkeys (its README) | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | — |
| Human interface | The only path to the game: screen clicks, camera, fog, reaction delay, APM (§6.3) | Clicks, drag boxes, camera hotkeys, fog, reaction delay, APM budget; pro-speed hands fitted to pro replays' select-to-order times yet | ● | ● | ● | ● | ● | ● | ● | ● |
| Perception and memory | What Gary knows: visible units, remembered enemy units (§6.9, §6.10) | Fog and hidden enemy HP; remembers enemy buildings and the enemy army seen in the last 3 min | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ |
| Macro decisions | What to build, train, research, and when | Learned from ~14k pro TvZ games; steerable by build style | ● | ● | ● | ● | ● | ● | ○ | — |
| Macro executor | Carries out macro decisions: placement, production, gas, mining (§5) | Scripted: any Terran building, unit, add-on, research, upgrade, expansion | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Army decisions | Where armies go, move vs attack, whether a fight is worth taking | Learned destinations and a learned fight estimate; holds attacks it expects to lose | ● | ● | ● | ● | ● | ○ | ○ | — |
| Micro | Unit control in fights: stim, spread, siege, focus fire, spells | Learned command model (#2) with memory of its own recent commands, for everything but workers: one command at a time to a selection of up to 12; marines loaded into bunkers by rule | ◐ | ◐ | ◐ | ◐ | — | — | — | — |
| Scouting | Finding out what the opponent does | One worker at 9 SCVs to the enemy start locations | ○ | ○ | ○ | ○ | ○ | — | — | — |
| Reflexes | Quick reactions outside the plan (worker defense, repair, retreat) | Scripted worker pull (v0.3's rule; v0.4–v0.6 left it to the fight models, which did worse); unfinished buildings get a new SCV | ○ | ○ | ○ | ○ | ○ | — | — | — |
| Attention arbiter | One camera and one APM budget shared by all tasks (§6.7) | One task at a time in a fixed priority order | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ○ |
| Strategy layer | Picks the build and switches plans from what it sees (§6.8) | You pick the build style by hand (`--style`) | ○ | ○ | ○ | ○ | ○ | ○ | — | — |
| Opponent model | Beliefs about the opponent's build and army | Not started | — | — | — | — | — | — | — | — |
| Replay pipeline | Inventory, build orders, resim, desync checks (§7.1–7.2) | ~70k replays indexed; TvZ re-simulated with fog-of-war views | ● | ● | ● | ● | ● | ● | ● | ● |
| Build taxonomy | Build styles discovered from replays (§7.3) | TvZ clusters with readable rules; style labels for ~45% of players | ● | ● | ● | ● | ● | ● | ● | ● |
| Training sets | Data for the learned models | Macro, army and fight sets for TvZ (fight v3: own units from twice as far, unit IDs, every command) | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | — | — |
| Learning beyond imitation | Outcome-weighted learning, reinforcement learning | Fight estimate learned from outcomes; reinforcement learning on pro scenarios runs, no gain yet | ◐ | ◐ | ◐ | ◐ | ◐ | — | — | — |
| POV viewer | Watch any game from Gary's screen (`viewer/`) | Cursor, clicks, every action in words; Remastered replays; videos | ● | ● | ● | ● | ● | ● | ● | — |
| Trace | Gary's decisions and reasons, recorded (§6.5) | Decision log with model probabilities and fight estimates; POV action log | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | — |
| Evaluation | Matches against opponents, many seeds, a scoreboard (§9) | `eval/vs_rush.py`: several seeds against one scripted Zerg rush; `eval/scenarios.py`: 114 pro home defenses where Gary takes over the Terran | ◐ | ◐ | ◐ | ◐ | ◐ | ○ | ○ | — |
| Matchups and races | | Terran in TvZ only | T | T | T | T | T | T | T | T |

## Versions

### v0.7 (October 2026): defense fundamentals (in progress, #2)

- **What it is:** v0.6 with the basics a player does in a home defense, as rules, each found by
  watching Gary and the pro side by side in the same scenario and then counted on the suite:
  - **finish what it started:** an unfinished building nobody builds (its SCV was killed) gets
    another SCV (all versions; unfinished buildings left: 0.20 → 0.07 per scenario, pro 0.04)
  - **produce during fights:** after each fight command, production gets a turn, not chores like
    refilling gas (marines finished in 45 s: 1.5 → 2.4, pro 2.1)
  - **load the bunker** when zerglings come at it (pro ~1 load per scenario)
  - **workers pulled by v0.3's rule**, first in a fight, faster; the command model no longer
    commands SCVs
  - **no plain moves or stops from the model** for fighting units (a guard rail: they took
    marines out of fights, as watching Gary vs the pro showed; −129 with them, −117 without, the
    same as no model in fights at all), until reinforcement learning teaches when a move helps
- **Pro-speed hands** (all versions, live too): the `pro` profile is fitted to pro replays: from
  selecting units to the next targeted command pros take 168 ms (median, home defenses), Gary's
  old b_rank hands 504 ms. Gary now gives 107 commands a minute there (b_rank 80; the pros 185
  effective: the rest is Gary's decision loop, not its hands). With them: home defenses v0.7 −92,
  v0.3 −131, v0.6 −185; the immediate 9-pool: v0.3 holds 4 of 8, v0.7 2.
- **Results** (b_rank hands; 114 home defenses, 4 draws): **−117**, 2.1 SCVs lost: the first Gary better than
  v0.3's −157 (v0.6 with the first three fixes −195; pro +29; nothing −260). Against the
  immediate 9-pool it holds 2 of 8 seeds, like v0.3: that's decided by placement and macro
  (bunker, marines, walls in time), not by fight micro.
- **Most urgently missing:** the pulled SCVs fight as a blob; the pros put them between the lings
  and the marines (a scripted "screen" next, then the ways for a model to learn it: unit features
  for the relation, synthetic micro drills with RL); macro against the immediate 9-pool.

### v0.6 (October 2026): the command model remembers (#2)

- **What it is:** v0.5 with a command model that also sees Gary's own commands of the last 8 s:
  per unit, what it was last told (kind, how long ago, where to), and the last 6 commands as
  extra tokens (`gary/policy/fight_memory.py`). In training these are the pro's own preceding
  commands (fight set v3 keeps unit IDs, fight centers and every command); in play, the human
  interface's log of what Gary's hands did.
- **Results:** offline, memory helps most with where to send units (destination within one cell
  54%, without memory 30%), then targets (57% vs 50%), selection IoU 0.70 vs 0.65, command type
  0.56 vs 0.49. Pro scenarios: −173 net, 2.7 SCVs lost (v0.5 −191, 3.2; pro +74; nothing −255).
- **What the pros do that Gary doesn't (counted in the data):** worker drilling. The pro
  right-clicks SCVs onto a far mineral patch so they pass through each other and the zerglings
  (mining workers don't collide), then attack-moves when the stack is on top of the lings. In the
  45 decisive scenarios the pro drilled in 22–24% (in the rest 7–10%), and those are the biggest
  swings (the pro's edge over doing nothing: 441–475 with a drill, ~290 without), about a third of
  the pro's total edge. A two-step, precisely timed trick like this isn't learned from clicks.
- **The suite was partly wrong:** 14 of those 45 scenarios were the Terran attacking (10 bunker
  rushes), which Gary's macro never plans. The picker now keeps only defenses at the Terran's home
  (114 games, one fight each). Re-scored there: pro +29, **v0.3's scripted worker pull −157**,
  v0.6 −209, v0.5 −211, v0.4 −216, nothing −260. On plain defense every learned fight model is
  worse than v0.3's simple rule. Drilling: 18% of these defenses, about a quarter of the pro's
  edge ([#21](https://github.com/vibrunazo/gary/issues/21); bunker rushes:
  [#22](https://github.com/vibrunazo/gary/issues/22); both are advanced techniques for later
  intents, not now).
- **Most urgently missing:** the fundamentals of defense, measured on this suite and on the
  immediate 9-pool (`eval/vs_rush`).

### v0.5 (October 2026): fight command model (#2)

- **What it is:** v0.4 with the fight model replaced by a command model: in a fight, every half
  second Gary draws the next command a pro would give (its type, which of Gary's units it goes to,
  up to 12, and its target unit or point), instead of an order per unit that Gary then regroups.
- **New:** `gary/policy/fight_cmd.py` and `train/fight_cmd.py` (commands rebuilt from the fight
  set: units told the same thing in the same half second; 0.7M training commands); its encoder
  starts from the fight model's; destinations as cells of a 32x32 grid around the fight.
- **Results:** offline (held-out games): selection IoU 0.74 (all own units: 0.55), target 52%
  (nearest unit: 27%), destination within one cell 32% (staying put: 19%); command type 59% when
  the pro commanded (most common: 65%, rare commands are weighted up). Pro scenarios (45, 4 draws
  each): −192 net, 2.8 SCVs lost (v0.4: −207, 3.3; pro +74; nothing −255). It now pulls SCVs,
  attack-moves, stims and sends workers back to mining, but in groups of 1–4 where the pro pulls
  12, and about one command every 1–2 s against the pro's ~1 per second.
- **Hands are not the bottleneck:** in fights pros select 3.9 units per command on average (5%
  of commands: 12); the model picks ~3. Of those, only 1.7 got the order; with the camera on the
  group, a wider drag box, reusing the selection and camera hotkeys, 2.2 do and Gary gives 24
  orders per scenario instead of 19, but the score stays (−193). With hands twice as fast (46
  orders, the pro's count) it's −210, and sampling closer to the model's likeliest commands
  (temperature 0.5, 0.25) gives −189: what Gary decides is what's missing, not how fast.
- **Wider view (fight set v2):** the fight snapshot now takes Gary's own units from 768 px (the
  whole mineral line; up to 64 units). Retrained on it (0.75M commands; selection IoU 0.65 vs
  0.43 for all own units, target 50%, destination 31%), Gary's commands grow to the pros' size
  (3.7 units chosen, the pros' real average is 3.9), but the score stays (−191).
- **Most urgently missing:** coherence over time. The model decides each command from the
  current snapshot alone, so Gary switches plans every second or two (move, attack-move, back to
  mining, move) where a pro holds one for several seconds (evacuate the mineral line, then come
  back): the command model needs memory of its recent commands, or a slower plan (intent) above it.

### v0.4 (October 2026): learned fight model (#2)

- **What it is:** v0.3 plus the fight model: whenever enemy fighters are near Gary's units, a
  transformer trained on 7.2M pro TvZ skirmish snapshots gives each unit near the fight an order
  (attack which unit, move where, attack-move, gather, repair, stop, hold, stim), carried out with
  human hands, one group per half second. Fights come first and may interrupt chores.
- **New:** fight data (resim `--fights`), fight model and training, env observes weapon cooldown,
  order target and carrying, chat announcement of the version and models, screencast-style action
  overlay in POV videos.
- **Results:** offline, the right action 55% of the time when the pro acted, the right target 35%
  (21% for "nearest unit"). In games, no better than v0.3 yet (8 seeds: immediate rush 5 lost; 7:00
  rush 1 won, 6 ahead). In pro scenarios (`eval/scenarios.py`: 45 early skirmishes from held-out
  games where the pro's control mattered; net value over 45 s, zerg lost minus terran lost): the
  pro +74, v0.3 −194, v0.4 −253, doing nothing −255. The fight model gives about 14 orders where
  the pro gives about 40, and rarely commits to what decided these fights: pulling a dozen SCVs
  with attack-move while marines kite. Sampling decisions from the model (instead of fixed
  thresholds) scores −207, and is now the default. Reinforcement learning from scenarios (`train/fight_rl.py`: 40 rounds
  of 512 plays, group-relative advantages, reward-to-go over 20 s, KL to the imitation model) left
  the held-out score where it started (−222 → −217); on 4 scenarios it trains and is scored on it
  gains about +90, so the loop learns but doesn't yet generalize from this much play.
- **Most urgently missing:** a fight model that acts like the pros in those scenarios (the
  scenarios are now the test); holding the immediate rush through the macro (bunker and marines
  in time).

### v0.3 (October 2026): learned macro and learned army

- **What it is:** v0.2's learned macro plus the army model: where each army cluster goes, move or
  attack-move, and a fight estimate that holds back attacks expected to lose army share. Scripted
  early scout and worker-defense reflex.
- **New:** army model with 3-minute enemy memory and fight estimate; armies as location clusters
  ordered by drag box; tile fallback for town halls; mining at Gary's own bases only; idle-worker
  sweep; actions recorded in words in the POV log.
- **Results** (Fighting Spirit, steered to standard bio with `--style 1`, 8 seeds,
  `eval/vs_rush.py`): against a zergling rush that attacks at 7:00, 1 win and 4 games far ahead at
  14:00, 3 nearly lost; against an immediate rush, 5 lost, 2 nearly lost, 1 holding.
- **Most urgently missing:**
  1. Holding early all-ins (bunker and marines timed to an early pool): [#2](https://github.com/vibrunazo/gary/issues/2).
  2. Closing out won games (armies advance one or two grid cells per order): [#3](https://github.com/vibrunazo/gary/issues/3).
  3. Micro: [#4](https://github.com/vibrunazo/gary/issues/4).
  4. Live play: the bridge's town-hall placement check is a tile off: [#5](https://github.com/vibrunazo/gary/issues/5).

### v0.2 (October 2026): learned macro

- **What it is:** production decided by the macro model, trained on ~14k pro TvZ games; v0.1's
  scripted army (attack-move with every 16 units).
- **New:** macro model and executor for the whole Terran tech tree; waits for busy buildings;
  never takes a decision under 5%; count caps learned from pros.
- **Results:** plays pro-like builds when steered (`--style 1`); unsteered, it can drift into tech
  paths without building the units. Against the 7:00 rush, 2 of 4 seeds won.

### v0.1 (October 2026): scripted Terran

- **What it is:** a fixed one-Barracks expand into marines, attack-move with every 16 marines.
- **Results:** loses to any early pressure; no defense at all.

### v0 (October 2026): hello world

- **What it is:** mines and makes workers through the human interface. Proves the loop works.

## Keeping this file

- **A new version:** add its column right after "Now" (newest first; older versions are a
  horizontal scroll away), update "Now", and add a section on top.
- **When the table gets too wide:** keep the latest versions as columns; older versions keep their
  sections below, and git history has the old tables.
- **Day-to-day tasks** (bugs, next steps, ideas) belong in [GitHub Issues](https://github.com/vibrunazo/gary/issues),
  not here: this file is the snapshot per version.
