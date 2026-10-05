# Gary — Progress

Where each Gary version stands against [ARCHITECTURE.md](ARCHITECTURE.md). The architecture
says what Gary should become; this file says what exists. Only the components that matter at the
current stage are listed; later ones (narrator, broadcaster, language models...) join when work
on them starts.

Legend: **—** not started · **○** scripted stand-in · **◐** partial · **●** working (for now)

## Components by version

| Component | What it is | Now (v0.3) | v0.3 | v0.2 | v0.1 | v0 |
|---|---|---|---|---|---|---|
| Game: headless | OpenBW game Gary plays in for development and tests (`env/`, `gary/env.py`) | Melee games on any map, network-style command delay, replays saved | ● | ● | ● | ● |
| Game: live Remastered | Gary in a real StarCraft: Remastered client over LAN (`adapters/scr_bridge`) | Plays; known gaps in the bridge's map checks and hotkeys (its README) | ◐ | ◐ | ◐ | — |
| Human interface | The only path to the game: screen clicks, camera, fog, reaction delay, APM (§6.3) | Clicks, drag boxes, camera hotkeys, fog, 0.3 s delay, APM budget; profiles not fitted from data yet | ● | ● | ● | ● |
| Perception and memory | What Gary knows: visible units, remembered enemy units (§6.9, §6.10) | Fog and hidden enemy HP; remembers enemy buildings and the enemy army seen in the last 3 min | ◐ | ◐ | ◐ | ◐ |
| Macro decisions | What to build, train, research, and when | Learned from ~14k pro TvZ games; steerable by build style | ● | ● | ○ | — |
| Macro executor | Carries out macro decisions: placement, production, gas, mining (§5) | Scripted: any Terran building, unit, add-on, research, upgrade, expansion | ○ | ○ | ○ | ○ |
| Army decisions | Where armies go, move vs attack, whether a fight is worth taking | Learned destinations and a learned fight estimate; holds attacks it expects to lose | ● | ○ | ○ | — |
| Micro | Unit control in fights: stim, spread, siege, focus fire, spells | Nothing yet: armies only move or attack-move | — | — | — | — |
| Scouting | Finding out what the opponent does | One worker at 9 SCVs to the enemy start locations | ○ | — | — | — |
| Reflexes | Quick reactions outside the plan (worker defense, repair, retreat) | Pulls about two SCVs per attacker when a base is outnumbered | ○ | — | — | — |
| Attention arbiter | One camera and one APM budget shared by all tasks (§6.7) | One task at a time in a fixed priority order | ○ | ○ | ○ | ○ |
| Strategy layer | Picks the build and switches plans from what it sees (§6.8) | You pick the build style by hand (`--style`) | ○ | ○ | — | — |
| Opponent model | Beliefs about the opponent's build and army | Not started | — | — | — | — |
| Replay pipeline | Inventory, build orders, resim, desync checks (§7.1–7.2) | ~70k replays indexed; TvZ re-simulated with fog-of-war views | ● | ● | ● | ● |
| Build taxonomy | Build styles discovered from replays (§7.3) | TvZ clusters with readable rules; style labels for ~45% of players | ● | ● | ● | ● |
| Training sets | Data for the learned models | Macro and army sets for TvZ | ◐ | ◐ | — | — |
| Learning beyond imitation | Outcome-weighted learning, reinforcement learning | Fight estimate learned from outcomes; no reinforcement learning | ◐ | — | — | — |
| POV viewer | Watch any game from Gary's screen (`viewer/`) | Cursor, clicks, every action in words; Remastered replays; videos | ● | ● | ● | — |
| Trace | Gary's decisions and reasons, recorded (§6.5) | Decision log with model probabilities and fight estimates; POV action log | ◐ | ◐ | ◐ | — |
| Evaluation | Matches against opponents, many seeds, a scoreboard (§9) | `eval/vs_rush.py`: several seeds against one scripted Zerg rush | ◐ | ○ | ○ | — |
| Matchups and races | | Terran in TvZ only | T | T | T | T |

## Versions

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
  1. Holding early all-ins (bunker and marines timed to an early pool).
  2. Closing out won games (armies advance one or two grid cells per order).
  3. Micro.
  4. Live play: the bridge's town-hall placement check is a tile off.

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
- **Day-to-day tasks** (bugs, next steps, ideas) belong in GitHub Issues, not here: this file is
  the snapshot per version.
