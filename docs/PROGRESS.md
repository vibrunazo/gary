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
| P0 Infra | ◐ | OpenBW env, human interface v1, POV and decision logs, eval against a scripted rush and pro scenarios | Vectorized env and its games/hour benchmark; the formal trace schema; classic bots to play against; the interface parity test |
| P1 Data | ◐ | ~70k replays indexed, resim with Remastered support (go decided: it works), fog-of-war views | Camera logger, camera inference, fitting human profiles from data (the interface's numbers are still placeholders) |
| P1b Taxonomy | ◐ | TvZ build clusters with readable rules (`taxonomy/discover.py`) | A reviewed `taxonomy/tvz/v1.yaml`, stability and gold-set reports |
| P1c Strategy stats | — | | Win-rate table, feature library, guide claims |
| **P2 Micro** | **◐ (current)** | Fight model learned from pro skirmishes; scenario suite from pro replays (`eval/scenarios.py`); first reinforcement learning on scenarios (`train/fight_rl.py`) | Responses within the human band: on the scenarios Gary is barely better than doing nothing (pro +74, Gary about −210, nothing −255) |
| P2b First playable | ◐ | Full games against people, offline, via the bridge; learned macro steered by build style | Build timings within tolerance (≥18/20 unharassed runs); supply blocks and idle production under harass within the human band |
| P2c Debug viewer | ● | POV viewer with cursor, clicks and every action in words; videos | Trace overlays beyond actions |
| P3 BC full game | ◐ (early) | Separate imitation models for macro, army movement and fights | One policy with intent and belief heads, Opponent Model, value network |
| P4 RL | ◐ (started) | Segment RL (T2a) on 45 s fight scenarios: runs, no gain yet | Elo gain at equal humanlikeness |
| P5 Explain, P5b Broadcast | — | (The POV viewer's action overlay is a start) | |
| P6 Deploy | ◐ | Remastered bridge for offline games | Pro blind-test sessions |

## Components by version

| Component | What it is | Now (v0.4) | v0.4 | v0.3 | v0.2 | v0.1 | v0 |
|---|---|---|---|---|---|---|---|
| Game: headless | OpenBW game Gary plays in for development and tests (`env/`, `gary/env.py`) | Melee games on any map, network-style command delay, replays saved | ● | ● | ● | ● | ● |
| Game: live Remastered | Gary in a real StarCraft: Remastered client over LAN (`adapters/scr_bridge`) | Plays; known gaps in the bridge's map checks and hotkeys (its README) | ◐ | ◐ | ◐ | ◐ | — |
| Human interface | The only path to the game: screen clicks, camera, fog, reaction delay, APM (§6.3) | Clicks, drag boxes, camera hotkeys, fog, 0.3 s delay, APM budget; profiles not fitted from data yet | ● | ● | ● | ● | ● |
| Perception and memory | What Gary knows: visible units, remembered enemy units (§6.9, §6.10) | Fog and hidden enemy HP; remembers enemy buildings and the enemy army seen in the last 3 min | ◐ | ◐ | ◐ | ◐ | ◐ |
| Macro decisions | What to build, train, research, and when | Learned from ~14k pro TvZ games; steerable by build style | ● | ● | ● | ○ | — |
| Macro executor | Carries out macro decisions: placement, production, gas, mining (§5) | Scripted: any Terran building, unit, add-on, research, upgrade, expansion | ○ | ○ | ○ | ○ | ○ |
| Army decisions | Where armies go, move vs attack, whether a fight is worth taking | Learned destinations and a learned fight estimate; holds attacks it expects to lose | ● | ● | ○ | ○ | — |
| Micro | Unit control in fights: stim, spread, siege, focus fire, spells | Learned fight model (#2) gives each unit near a fight an order (attack, move, gather, repair, stim, hold...); weak so far | ◐ | — | — | — | — |
| Scouting | Finding out what the opponent does | One worker at 9 SCVs to the enemy start locations | ○ | ○ | — | — | — |
| Reflexes | Quick reactions outside the plan (worker defense, repair, retreat) | Replaced by the fight model in v0.4 (v0.3: scripted worker pull) | ○ | ○ | — | — | — |
| Attention arbiter | One camera and one APM budget shared by all tasks (§6.7) | One task at a time in a fixed priority order | ○ | ○ | ○ | ○ | ○ |
| Strategy layer | Picks the build and switches plans from what it sees (§6.8) | You pick the build style by hand (`--style`) | ○ | ○ | ○ | — | — |
| Opponent model | Beliefs about the opponent's build and army | Not started | — | — | — | — | — |
| Replay pipeline | Inventory, build orders, resim, desync checks (§7.1–7.2) | ~70k replays indexed; TvZ re-simulated with fog-of-war views | ● | ● | ● | ● | ● |
| Build taxonomy | Build styles discovered from replays (§7.3) | TvZ clusters with readable rules; style labels for ~45% of players | ● | ● | ● | ● | ● |
| Training sets | Data for the learned models | Macro, army and fight sets for TvZ (fight: 7.2M snapshots) | ◐ | ◐ | ◐ | — | — |
| Learning beyond imitation | Outcome-weighted learning, reinforcement learning | Fight estimate learned from outcomes; reinforcement learning on pro scenarios runs, no gain yet | ◐ | ◐ | — | — | — |
| POV viewer | Watch any game from Gary's screen (`viewer/`) | Cursor, clicks, every action in words; Remastered replays; videos | ● | ● | ● | ● | — |
| Trace | Gary's decisions and reasons, recorded (§6.5) | Decision log with model probabilities and fight estimates; POV action log | ◐ | ◐ | ◐ | ◐ | — |
| Evaluation | Matches against opponents, many seeds, a scoreboard (§9) | `eval/vs_rush.py`: several seeds against one scripted Zerg rush; `eval/scenarios.py`: 45 pro skirmishes where Gary takes over the Terran | ◐ | ◐ | ○ | ○ | — |
| Matchups and races | | Terran in TvZ only | T | T | T | T | T |

## Versions

### v0.4 (October 2026): learned fight model (in progress, #2)

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
