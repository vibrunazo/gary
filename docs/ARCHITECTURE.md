# BW Sparring Partner — Architecture

Status: **draft v0.2** (2026-09-30)

A StarCraft: Brood War AI that pro and aspiring players can use as a **sparring partner**:
it plays with pro-level game sense, but with **human hands** (human APM, attention, reaction time
and mistakes), it can be **told what to play** ("go 2 hatch muta", "play the PvT build from this
replay"), and it can **explain why** it did what it did.

---

## 1. Goals and non-goals

### Goals

| # | Goal | What "done" looks like |
|---|------|------------------------|
| G1 | **Plays like a real opponent** | Survives and punishes harass like a human would. A 5-muta rush is neither free (built-in AI) nor hopeless (Pluto's 3-marine micro). |
| G2 | **Human constraints, not superhuman control** | Camera, selection limits, burst-limited APM, reaction delay, imprecision and lapses are enforced *in the action space*. |
| G3 | **Steerable** | A text prompt or a replay produces a strategy spec the bot follows reliably, game after game ("practice it 20 times in a row"). |
| G4 | **Adjustable skill** | One model, many skill levels: a "middle ground" between built-in AI and Pluto, set by a profile. |
| G5 | **Explainable** | Every game has a queryable trace: what it intended, what it believed, which alternatives it considered, and which human constraint got in the way. |
| G6 | **Modular for experiments** | Models, training recipes and pipeline variants can be swapped through config and compared on a shared evaluation harness. |

### Non-goals

- Beating Pluto or winning bot tournaments. Strength only matters up to "representative of the target human level".
- Playing on the Battle.net ladder. The bot is for offline practice and custom games only (see §10).
- Full transparency of the neural policy. We aim for *faithful, structured* explanations (§8), not a white box.

---

## 2. Background and key findings

**Pluto** (tscmoo, Computer Olympiad 2026 winner) shows full-game self-play RL for BW is feasible:
- A 315M-parameter network: a transformer over units, convolutions over the map, a GRU, and a slow memory module.
- One model step every 6 frames, roughly 240 steps/min at Fastest.
- **Why it feels superhuman: bandwidth per action, not raw APM.** A single action can command any number of units, with no 12-unit selection limit and no camera, so visible APM reads in the thousands. Capping APM alone would not humanize it.
- Its opening is chosen by a Thompson-sampling bandit and fed to the network as a 32-bit mask. That's a crude version of the strategy conditioning we want (G3).
- Binary-only release. We cannot retrain it or legally fork it. It's useful as an **upper reference opponent** in evaluation.

**Remastered (SC:R)**:
- BWAPI officially supports only 1.16.1.
- An unofficial bridge (Pluto-AI-Starcraft-Remaster) injects a DLL into SC:R build 1.23.10.13515. It translates SC:R memory into what BWAPI 4.4 expects and turns the bot's commands back into SC:R packets.
- Anything that speaks BWAPI 4.4 could, in principle, use the same approach. It's pinned to one build and unofficial.

**AlphaStar (SC2)** is the closest precedent for G2 and G3:
- Supervised learning from human replays, conditioned on a strategy statistic *z* (build order plus cumulative unit counts) taken from the same replay.
- RL fine-tuning with pseudo-rewards for following *z* and a KL penalty toward the supervised policy.
- A camera interface and APM limits. It was still criticized for superhuman *burst* precision, so we need **burst limits, not averages**.

**Decision models (the "System One" class, Sept 2026)**: models that pick from options you supply and return probabilities, with no text generation.

| Model | Access | Latency | Fine-tunable | Calibration |
|---|---|---|---|---|
| Jev (TypeSafe) | Hosted API | 70–500 ms | No | Trained for calibration (RLCD) |
| OpenAI Decisions API (GPT-6 Luna) | Hosted API | ~150 ms | — | Probabilities are self-reported by the LLM, not calibrated against outcomes |
| Laya (convaiinnovations) | Open weights, Apache-2.0, ModernBERT-large 421M | ~33 ms on a T4 GPU; 0.2–0.5 s on CPU | Yes (RLCD) | Over-confident out of the box; needs temperature scaling per domain |
| Kev / AnyJev / DiffusionGemma | Open | varies | varies | varies |

**Verdict:**
- Open, local, fine-tunable models (Laya) remove the hosted-API and no-fine-tuning objections. They can run on our own GPU, and they're fast enough for the Plan Supervisor (one decision every few seconds) and for labeling replays at scale.
- They are still **not** the per-step policy and **not** an RL teacher. A decision model fine-tuned on replay labels learns the same thing the policy's own belief and intent heads learn from the same data, but through a lossy text version of the game state.
- They are treated as **providers in decision slots** (§6.6), compared against scripts, LLMs and human labels on a gold set. Calibration (ECE) is measured by us, not taken from vendor claims.

---

## 3. Design principles

1. **Constraints live in the action space, during training.** The policy only ever acts through the human interface (§6.3). Adding a humanizer after training breaks policies that learned to rely on superhuman control. The **same implementation** of the interface is used in training and at runtime.
2. **Steering goes through explicit conditioning.** What to play (*z*) and how well to play (*h*) are both policy inputs. Prompts and replays are compiled into *z*. They are never free-text instructions to the policy.
3. **Neural for skill, symbolic for structure.** The neural policy handles perception, micro and macro execution. Symbolic components provide:
   - the strategy language (*z*)
   - the intent bottleneck
   - the plan supervisor (branch logic)
   - the trace
4. **Explanations come from records, not stories.** Explanations are built from logged intents, beliefs, candidate probabilities and constraint events. The LLM only narrates. It never reconstructs reasoning after the fact.
5. **Contracts are stable, implementations are swappable.** Schemas are versioned. Everything else is a plugin selected by a run manifest.
6. **Every decision or label outside the policy is a slot.** Opening classification, intent labels, branch selection, camera inference and so on each have a typed interface. A deterministic script, a decision model, an LLM or a human can fill it, and they can be swapped and compared (§6.6).
7. **Everything is reproducible.** Seeded sampling and humanization, plus logged model versions, let any game be re-run and **decision-diffed** against another pipeline.

---

## 4. System overview

```
           ┌──────────────── Offline / authoring ────────────────┐
 prompt ──►│ Strategy Compiler (LLM)        ─┐                   │
 replay ──►│ Replay Extractor (screp+resim) ─┼──► z  StrategySpec │
 library ─►│ Strategy Library               ─┘                   │
 preset ──►│ Profile Library  ──────────────────► h  HumanProfile │
           └─────────────────────────────────────────────────────┘
                                   │
 ┌──────────────────────────────── Runtime (per game) ─────────────────────────────┐
 │                                                                                 │
 │  Game Adapter ──► Perception (fog-filtered obs + symbolic facts)                │
 │       ▲                     │                                                   │
 │       │                     ▼                                                   │
 │       │         Plan Supervisor (symbolic) ── selects active z segment          │
 │       │                     │  (branches on facts + belief heads)               │
 │       │                     ▼                                                   │
 │       │     ┌────────── Policy π(a | obs, z_active, h) ─────────┐               │
 │       │     │ encoders → core → INTENT head ─► ACTION head      │               │
 │       │     │                 └► BELIEF heads (aux)             │               │
 │       │     └───────────────────────────┬───────────────────────┘               │
 │       │                                 ▼                                       │
 │       └──────────── Human Interface (camera, select≤12, APM bucket,             │
 │                     reaction delay, click scatter, lapses) ◄── h                │
 │                                                                                 │
 │  Trace Bus ◄── facts · z switches · intents+probs · beliefs · constraint events │
 └─────────────────────────────────────────────────────────────────────────────────┘
                                   │
                    Trace Store ──► Query API ──► Narrator (LLM) ──► "why…?" answers

 Game backends:  OpenBW headless (training/eval)  |  BWAPI 1.16.1  |  SC:R via bridge
```

---

## 5. Components

| Component | Responsibility | Inputs → Outputs | Swappable implementations |
|---|---|---|---|
| **Game Adapter** | Step the game, read state, submit low-level commands. Hides the differences between backends. | backend ↔ `RawState`, `GameCommand[]` | OpenBW headless (vectorized, many games in parallel), BWAPI 4.4 client, SC:R bridge |
| **Perception** | Build the fog-filtered observation tensors and symbolic facts the player is allowed to know. Track memory of last-seen enemy units. | `RawState` → `Observation`, `Fact[]` | Feature sets v1/v2…; fact extractors |
| **Strategy Compiler** | Turn a natural-language request into a valid *z*. Ask for clarification or reject if impossible. | text → `StrategySpec` | LLM model/prompt versions; template library |
| **Replay Extractor** | Turn a replay into *z* for one player: build order, timing targets, style statistics. Optionally suggest branches for human review. | `.rep` → `StrategySpec` | screp-only (commands) vs. resim (full state) |
| **Plan Supervisor** | Deterministic branch logic over facts and belief heads. Decides which segment of *z* is active. Logs every switch with its evidence. | `Fact[]`, beliefs, *z* → `z_active` | Rule engine (default); later a learned branch selector |
| **Policy** | Perception → intent → human-interface actions, conditioned on *z* and *h*. | obs, `z_active`, *h* → `Intent`, `HumanAction` | Backbone size/architecture, training recipe, checkpoint |
| **Human Interface** | The only path from policy to game. Enforces human limits and emits a `ConstraintEvent` whenever it blocks, delays or perturbs an action. | `HumanAction` → `GameCommand[]` | **Single implementation** shared by training and runtime; parameterized only by *h* |
| **Trace Bus / Store** | Append-only, frame-stamped event log for every game, plus indexes for querying. | events → JSONL/Parquet | Storage backend |
| **Narrator** | Answer "why" questions by retrieving trace records and turning them into text, citing event IDs. | question + trace slice → answer | LLM model/prompt versions |
| **Eval Harness** | Run matches and scenarios at scale, compute metrics, keep the scoreboard. | manifests → metrics | Scenario suites, opponent pools |

---

## 6. Contracts (schemas)

All schemas are versioned protobuf definitions (`schemas/`). They are shown here as YAML for readability.
**Numbers in examples are placeholders** to be fitted from replay data (§7.2).

### 6.1 `StrategySpec` (*z*): what to play

Modeled on AlphaStar's *z*, extended with explicit branches and style.

```yaml
strategy:
  schema: strategy/v1
  id: zvt_2hatch_muta_std
  race: zerg
  matchup: ZvT
  source: {type: prompt, ref: "go 2 hatch muta"}   # prompt | replay | library
  adherence: strict            # strict | loose → weight of the adherence pseudo-reward / supervisor
  segments:
    - id: opening
      build_order:             # supply-anchored, with tolerance
        - {item: drone,     until_supply: 9}
        - {item: overlord,  at_supply: 9}
        - {item: hatchery,  at_supply: 12, where: natural}
        - {item: pool,      at_supply: 11}
        - {item: extractor, at_supply: 11}
        - {item: lair,      when: "minerals>=150 && gas>=100"}
        - {item: spire,     when: "lair_done"}
      tolerance: {supply: 1, seconds: 10}
      targets:                 # cumulative statistics by game time
        - {by: "7:30", units: {mutalisk: 9, zergling: 6}, bases: 3}
    - id: muta_harass
      style: {aggression: 0.7, harass_bias: high}
    - id: vs_early_bio_push
      build_order: [{item: sunken, count: 2, where: natural}]
  branches:                    # evaluated by the Plan Supervisor, not by the policy
    - from: opening
      when: "fact.enemy_marines_seen >= 8 && time < '5:30'"
      or_belief: {enemy_opening: bio_timing, p_min: 0.6}
      to: vs_early_bio_push
    - from: opening
      when: "fact.spire_done"
      to: muta_harass
  style:                       # continuous knobs, also policy inputs
    aggression: 0.5
    expand_tempo: standard     # fast | standard | greedy
    tech_bias: air
```

The policy encoder sees the **active segment** (build order tokens, targets, style vector), not the whole tree.

### 6.2 `HumanProfile` (*h*): how well to play

Two parts:
- `conditioning`: fed to the policy, so it learns to play like players at that level.
- `limits`: enforced by the Human Interface.

```yaml
human_profile:
  schema: profile/v1
  id: b_rank_terran
  conditioning:
    race: terran
    rating_band: B             # learned from replay metadata
    style_tags: [bio, standard]
  limits:
    apm:
      bucket: {capacity: 10, refill_per_sec: 3.5}   # burst limit (token bucket)
      min_action_gap_ms: 55
    reaction:
      model: lognormal
      median_ms: 300
      sigma: 0.35
      attention_switch_ms: 180   # extra delay when the event is off-screen / off-focus
    interface:
      viewport: {w: 640, h: 400} # playable screen area in px (excl. HUD); confirm per backend
      max_selection: 12
      precise_commands_require_on_screen: true
      minimap_scatter_px: 48
    precision:
      click_scatter_px: {base: 3, per_bucket_pressure: 6}  # sloppier when spamming
      misclick_rate: 0.008
    lapses:                      # probability per opportunity, scaled by load
      idle_production: 0.10
      missed_supply: 0.05
      forgotten_unit_group: 0.03
  seed: 42
```

### 6.3 `HumanAction`: the policy's action space

Every action costs APM tokens. Screen-space targets are only valid inside the current viewport.

| Action | Args | Notes |
|---|---|---|
| `CAMERA_MOVE` | map point | Costs a token. Edge scrolling is modeled as a series of moves. |
| `CAMERA_JUMP` | hotkey / base / last alert | |
| `SELECT_BOX` | screen rect, shift? | At most 12 units. Selection rules (type filters, buildings) follow BW. |
| `SELECT_CLICK` | on-screen unit, shift?, double? | Double-click selects same-type units on screen, at most 12. |
| `HOTKEY_RECALL` / `HOTKEY_SET` / `HOTKEY_ADD` | 0–9 | |
| `COMMAND` | type, target (screen point / on-screen unit / minimap point), queued? | Minimap targets get extra scatter. |
| `BUILD` | type, screen point | Applies to the selected worker. |
| `TRAIN` / `RESEARCH` / `UPGRADE` | type | Applies to selected buildings. |
| `NOOP` | | Explicit "do nothing this step". |

Unlike Pluto, one action affects **at most one selection**, and precise targets require the camera to be there.

### 6.4 `Intent`: the symbolic bottleneck

Emitted by the intent head every K policy steps, or whenever it changes. The action head is conditioned on the current intent.

```yaml
intent_vocab:
  schema: intent/v1
  macro:   [EXPAND(base), TECH(item), PRODUCE(unit_mix), SUPPLY]
  army:    [ATTACK(region), HARASS(region, group), DEFEND(region),
            RETREAT(region), CONTAIN(region), REGROUP(region)]
  info:    [SCOUT(region), DENY_SCOUT]
  meta:    [TRANSITION(segment_id), ALL_IN]
```

Each intent record includes the **probabilities of the top-k alternatives**. That's what makes "why X instead of Y?" answerable.

### 6.5 Trace events

```yaml
# common envelope
{ game_id, frame, t_game, seq, kind, payload, refs: [event ids] }

kind: fact            # {key, value, source: seen|memory|inferred}
kind: belief          # {head, distribution}  e.g. enemy_opening: {bio_timing: .62, mech: .21, ...}
kind: z_switch        # {from, to, rule, evidence: [fact/belief ids]}
kind: intent          # {chosen, params, alternatives: [{intent, p}], policy_ckpt}
kind: action          # {human_action, tokens_left}
kind: constraint      # {type: delayed|dropped|scattered|lapse|offscreen, detail}
kind: outcome         # {engagement result, units lost/killed, ...}
kind: slot_decision   # {slot, provider, provider_version, answer, p, alternatives, cached?}
```

### 6.6 Decision slots: swappable providers

Any decision or label that isn't made by the policy network goes through a **slot**. A slot has:
- a typed question and answer schema
- a latency class
- any number of **providers** that implement it

Providers are chosen per run in the manifest (§9.1). This is what makes comparisons like "decision-model classifier vs. Python script vs. human label" a config change instead of a code change.

```python
class SlotQuestion(Protocol):     # one schema per slot, versioned
    slot: str                     # e.g. "opening_class/v1"
    context: dict                 # typed facts / state summary / replay window ref
    options: list[str] | None     # choice slots; None for score/bool

class SlotAnswer:
    answer: str | float | bool
    p: float | None               # probability; None if the provider has none (e.g. a script)
    alternatives: list[tuple[str, float]]
    provider: str                 # "rules_py", "laya_ft", "jev", "openai_decisions", "llm", "human"
    provider_version: str         # code hash / checkpoint / prompt version / annotator id
    latency_ms: float

class Provider(Protocol):
    def answer(self, qs: list[SlotQuestion]) -> list[SlotAnswer]: ...   # batched
```

**Provider types:**

| Provider | Notes |
|---|---|
| `script` | Deterministic Python rules. Free and reproducible. `p` is either 1.0 or a hand-set confidence. |
| `decision_model` | Laya/Kev (local, fine-tunable), Jev/OpenAI Decisions (hosted). A per-provider calibrator (temperature scaling) is fitted on the gold set. |
| `llm` | Prompted LLM returning a structured answer. Good for rare or complex cases. |
| `human` | Async **annotation queue**: questions are written to a queue and answered in a small labeling UI. Answers become the **gold set**. |
| `learned_head` | A head of the policy itself (e.g. a belief head) exposed as a provider, for comparison. |
| `cascade` | A composite: try A; if `p` < threshold, ask B; then C. For example script → laya_ft → human. Calibrated `p` makes this routing meaningful. |

**Label store:**
- Every answer is stored keyed by `(slot, item_id, provider, provider_version)`. Labels from different providers coexist and are never overwritten.
- A training dataset is defined by `slot → provider selection`, so you can train the same model on "script labels" vs. "laya labels" vs. "human labels" and compare.
- **Gold sets** (human-labeled, held out) are versioned per slot. Every provider is scored on them for accuracy, ECE/calibration, coverage at a fixed error rate, latency and cost.

**Slot inventory (v1):**

| Slot | Latency class | Candidate providers |
|---|---|---|
| `opening_class` (replay or live) | offline / ≤1 s | script, laya_ft, jev, llm, human |
| `intent_label` (replay windows) | offline | script, laya_ft, llm, human |
| `z_extract` (replay → StrategySpec) | offline | script (default), llm |
| `branch_suggest` (replay → branches) | offline | llm, human |
| `camera_infer` (replay → camera track) | offline | script, small learned model |
| `supervisor_branch` (live z switch) | ≤50 ms, every few seconds | rules (default), laya_ft, learned_head |
| `strategy_compile` (prompt → z) | interactive | llm, template script |
| `narrate` (trace → answer) | interactive | llm |
| `engagement_outcome` (eval labeling) | offline | script, human |

**Live slots in training:** if a non-deterministic or slow provider fills a live slot (e.g. `supervisor_branch`), it must also be used during RL, or the policy will train against a different supervisor than the one it plays with. Hosted providers are therefore limited to offline slots in practice.

---

## 7. Training pipeline

### 7.1 Data sources

| Source | What it is | Notes |
|---|---|---|
| **STARDATA** | ~65k human games (1.16.1), already extracted into states, public S3 bucket | Easiest first dataset (no resim needed). Older meta and mixed skill. Repo archived 2022. ~365 GB compressed: plan disk accordingly. |
| **RepMastered** (repmastered.app, by the author of screp) | Large SC:R database with pro, ladder and tournament games; filter by matchup, player, map, APM, date | Best source of modern pro TvZ. Downloads are blocked for unverified email domains unless you donate. **No bulk API: contact the maintainer rather than scraping.** |
| **Liquipedia replay packs** | Tournament packs (ASL and others) linked from event pages | Small, high quality. Good for gold sets and the strategy library. |
| **bwreplays.com, reps.ru, TL.net replay pack threads** | Community archives | Variable quality; many old links are dead. |
| **Contributor-recorded games** | Self-recorded | The only source with **ground-truth camera**, if recorded with a camera-logging tool. Needed to validate camera inference. |
| Bot self-play games | Generated | RL stage only. |

Check each site's terms before bulk use, and keep provenance (source, URL, date) per replay in the dataset index.

### 7.2 Data processing

1. **Parse** with screp: commands, players, APM, metadata.
2. **Resim** in OpenBW to recover full state per frame. **Risk:** SC:R (1.18+) replays must replay correctly in a 1.16.1 engine. Validate early on a sample.
3. **Per-player observations**, fog-filtered.
4. **Infer the camera.** Replays don't record screen position, so estimate it from click targets, selection boxes and hotkey jumps. Use a heuristic first, then a small model.
5. **Map labels to the action space.** Convert human commands into the `HumanAction` format (selections, hotkeys and commands are recorded).
6. **Extract *z*** (deterministic) from each player's own game. This gives hindsight conditioning for supervised learning.
7. **Extract *h*-conditioning** (rating band, APM and burst statistics) from metadata and command timing.
8. **Fit `HumanProfile.limits`** per rating band from command timing: inter-action gaps, burst sizes, reaction to events (for example, time from first sight of an enemy unit to the first related command).
9. **Label intents.** Start with heuristic rules, then add LLM/Jev classification over windowed summaries. Keep labels above a confidence threshold, using calibrated probabilities. Spot-check by hand.
10. **Belief targets** come from ground truth in the full resim state (enemy opening, composition, tech).

### 7.3 Stages

| Stage | Method | Constraints on? | Output |
|---|---|---|---|
| **T0 Micro curriculum** | Supervised on replay snippets plus RL in scenarios (muta vs marine/medic/turret, drops, ling runbys) | Yes | Validates the human interface. Micro-capable action head. |
| **T1 Behavior cloning** | Supervised π(intent, action \| obs, z, h) plus belief heads | Yes (actions are human by construction) | Humanlike, steerable, weak-ish |
| **T2 RL fine-tune** | League self-play against frozen supervised and earlier RL agents. Reward = win + λ_z·adherence + λ_KL·KL(π‖π_BC) + λ_D·discriminator | Yes | Stronger, still humanlike |
| **T3 Export** | Quantize and distill for runtime latency | n/a | Runtime checkpoint |

The adherence pseudo-reward compares the bot's build order with *z* (supply/time-aligned edit distance) plus distance from the cumulative targets.

---

## 8. Explainability

| Question type | Answered from |
|---|---|
| "Why mutas?" | *z* (it was instructed) and `z_switch` events with their evidence |
| "Why mutas instead of lurkers?" | `intent.alternatives` at the decision frames, plus beliefs at that time |
| "Why didn't you defend the drop?" | `constraint` events (off-screen, reaction delay, empty APM bucket) and the intent at that time |
| "What did you think I was doing?" | `belief` history, compared with ground truth after the game |
| "Would you have done X if…?" | Counterfactual rerun: same frame, edited facts or beliefs, compare intent distributions |

Rules:
- Narrator answers must cite trace event IDs.
- Counterfactual consistency is tracked as a metric: if an explanation names fact F as the reason, removing F should change the choice.

---

## 9. Experiment framework

### 9.1 Run manifest

```yaml
run:
  name: bc_vs_rl_tvz_v3
  backend: openbw
  policy: {arch: unit_transformer_gru_m, ckpt: rl/tvz/0042}
  recipe: bc+rl+kl            # bc | bc+rl | bc+rl+kl | bc+rl+kl+disc
  profile: b_rank_terran
  slots:                      # §6.6 — provider per slot
    opening_class:     {provider: cascade, chain: [script/v2, laya_ft/0007@t=1.8, human]}
    intent_label:      {provider: laya_ft/0007}
    supervisor_branch: {provider: rules/v1}
    strategy_compile:  {provider: llm, model: <model-id>, prompt: v3}
  data: {index: tvz_modern_v1, label_sources: {intent_label: laya_ft/0007}}
  budget: {tier: B0, wall_clock: 1h}    # §13
  seeds: [1, 2, 3, 4, 5]
  eval: [suite/core, suite/harass_tvz]
```

A **slot bake-off** is its own run type. It answers the gold set with several providers and reports accuracy, ECE, coverage at a fixed error rate, latency and cost side by side:

```yaml
bakeoff:
  slot: opening_class/v1
  gold: gold/opening_class/tvz_v1      # human-labeled
  providers: [script/v2, laya_zeroshot, laya_ft/0007, jev, openai_decisions, llm/<model-id>]
```

### 9.2 Experiment axes

- Policy architecture and size
- Training recipe and λ weights
- Intent vocabulary and label source
- Supervisor rules vs. learned
- Humanizer parameters and profile fitting method
- Compiler model/prompt
- Data mix (STARDATA vs. modern replays)

### 9.3 Metrics

| Metric | Measures |
|---|---|
| Elo vs. opponent pool (classic bots, earlier checkpoints, Pluto as ceiling) | Strength per profile |
| **Adherence**: build-order edit distance and target error vs. *z*, plus variance over N runs | Steerability, repeatability (G3) |
| **Humanlikeness**: accuracy of a human-vs-bot classifier on replays (lower is better); APM/burst/reaction distribution distance from the target band | G2 |
| **Harass response suite** score (see below) | G1 |
| Explanation counterfactual consistency, % of narrator answers with valid citations | G5 |
| Runtime latency per step, cost | Feasibility |

### 9.4 Scenario suites

Scenarios are reproducible starting states with fixed opponent scripts. A scenario passes when the bot's response falls **within the human distribution**, not when it wins.
- `harass_tvz/muta_5_at_7m30`: 5 mutas hit the main while the Terran takes a third
- `harass_tvz/ling_runby_natural`
- `harass_pvz/muta_vs_cannon_sair`
- `drop_zvt/2_dropship_main_and_nat`
- …

### 9.5 Human evaluation

Blind sessions: pros play a mix of the bot (various profiles) and real human sparring partners, then rate "was this a human?" and "was this useful practice?".

---

## 10. Deployment

| Target | Path | Notes |
|---|---|---|
| Headless eval | OpenBW | Primary dev loop |
| Play vs. humans (1.16.1) | BWAPI 4.4 client (32-bit module, IPC to 64-bit inference process, like Pluto) | Stable, official API |
| Play vs. humans (SC:R) | BWAPI-compatible bridge, same approach as Pluto-AI-Starcraft-Remaster | Pinned to one SC:R build and breaks on patches. Unofficial: **offline and custom games only, never ladder.** Check the bridge's license before reuse. |

---

## 11. Repository layout (proposed)

```
schemas/      protobuf contracts (strategy, profile, action, intent, trace) — versioned
adapters/     openbw_env (vectorized), bwapi_client (C++ shim), scr_bridge
interface/    human interface + humanizer — ONE implementation (C++ core + pybind11)
perception/   observation encoding, fact extractors
data/         replay ingest (screp), resim, camera inference, labeling, profile fitting
compiler/     prompt→z (LLM), replay→z
supervisor/   plan supervisor (rules engine)
slots/        slot schemas, providers (script, decision_model, llm, human, cascade), label store, calibrators, bake-off runner
annotate/     small labeling UI for the human provider queue
policy/       model definitions, encoders, heads
train/        bc, rl, league, rewards
trace/        bus, store, query API, narrator
eval/         harness, scenarios, metrics, dashboards
configs/      run manifests, profiles, strategy library
docs/         this document, ADRs
```

---

## 12. Roadmap

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **P0 Infra** | OpenBW vectorized env, human interface v1, trace schema, eval harness with classic bots | 1k headless games/hour on dev hardware; interface parity test (train vs. runtime) passes |
| **P1 Data** | Replay → (obs, HumanAction, z, h) pipeline; camera inference; profile fitting | SC:R resim validity measured; camera inference accuracy measured on games with known camera (e.g. self-recorded) |
| **P2 Micro** | T0 curriculum in muta/marine/drop scenarios | Harass suite: responses within human distribution for ≥2 profiles |
| **P3 BC full game** | T1 policy with *z*, *h*, intent and belief heads; supervisor; compiler | Adherence target met for 10 library strategies; humanlikeness classifier ≤ X% |
| **P4 RL** | T2 league fine-tuning | Elo gain at equal humanlikeness and adherence |
| **P5 Explain** | Query API, narrator, counterfactual tool | Counterfactual consistency ≥ target |
| **P6 Deploy** | BWAPI client; SC:R bridge (offline) | Pro blind-test sessions |

---

## 13. Compute budgets

Start small and scale up. Every run manifest declares a budget tier, so results from different budgets are never compared as if they were equal.

**Reference workstation** (the baseline for B0–B2; budgets are stated in wall-clock hours on this class of machine):
- Modern desktop CPU with 12+ cores
- 64 GB RAM
- One consumer GPU with 16 GB VRAM, on a recent CUDA/PyTorch build
- 1–2 TB NVMe storage
- OpenBW and the training stack are Linux-first. On Windows, run them under **WSL2** with CUDA passthrough. The BWAPI/SC:R play path stays on Windows.

Contributors with different hardware should report their throughput benchmark (P0) alongside results.

| Tier | Budget | Purpose |
|---|---|---|
| **B0** | 1 h on a reference workstation | Smoke tests, bake-offs, micro-scenario learning curves |
| **B1** | Overnight (~10 h) on a reference workstation | Data preprocessing, small supervised runs, longer micro RL |
| **B2** | Weekend (~48 h) on a reference workstation | Small full-game supervised policy, early RL fine-tuning |
| **B3** | Rented multi-GPU (budget set later) | Full-game RL league at meaningful scale |

**What fits in B0 (1 hour).** All throughput numbers are **estimates to be measured in P0**. OpenBW's headless speed in our setup is the key unknown.

| Experiment | Setup | Expected outcome |
|---|---|---|
| **B0-a Slot bake-off** | `opening_class` gold set of ~300–500 human labels. Providers: script, Laya zero-shot, Laya fine-tuned (421M fits on 16 GB with bf16 and small batches), hosted Jev/OpenAI (cents) | A complete comparison table in well under an hour. **The bottleneck is human labeling time, not compute.** |
| **B0-b Micro RL** | `harass_tvz/muta_5_vs_marines` scenario on a small map. Policy of ~1–5M params (small unit transformer). PPO with ~16–20 parallel OpenBW envs on CPU, learner on GPU. Human interface **on**. | Roughly 10⁶–10⁷ agent steps. Enough to see learning curves and compare 2–3 humanizer settings (e.g. C vs. B profile). Not enough for polished micro. |
| **B0-c Supervised smoke test** | ~10–30M param model on a preprocessed TvZ subset (1–2k games, prepared in B1) | Action-prediction accuracy curves. Confirms the data pipeline end to end. |

**Not in B0 or B1:** full-game RL, Pluto-scale models (315M params; training would be slow and tight on 16 GB), leagues.

**Storage:** STARDATA alone is ~365 GB compressed. Extracted features for modern replays add more. Plan for 1–2 TB of fast disk (NVMe).

---

## 14. Risks and open questions

| Risk / question | Mitigation / next step |
|---|---|
| RL compute for full-game BW is unknown (Pluto's budget is unpublished) | Prove value in P2 (micro) first; scale model size gradually; supervised-only fallback |
| SC:R replays may not resim in OpenBW 1.16.1 | Validate on a sample in P1; fall back to STARDATA plus 1.16.1 games |
| Camera inference quality limits how human the interface is | Record ground-truth camera from self-played games to train and evaluate the inference model |
| Humanlike vs. strong is a trade-off | Make it explicit via λ_KL, λ_D and profile conditioning; track both metrics together |
| Intent labels are noisy | Confidence filtering, manual audit set, and iterating on intent vocab versions |
| SC:R bridge fragility and ToS | Primary target is 1.16.1; SC:R is offline only; no ladder |
| Pluto is closed source | Use only as an evaluation opponent. Do not distill from it (license, and it would import superhuman habits). |
| Decision-model probabilities aren't trustworthy out of the box (Laya ships over-confident; OpenAI's are self-reported) | Fit a calibrator per provider and slot on the gold set; report ECE in every bake-off |
| No bulk access to modern pro replays | Start with STARDATA plus Liquipedia packs; ask the RepMastered maintainer about research access |
| OpenBW headless throughput is unmeasured (native Linux vs. WSL2) | First P0 benchmark; it decides the B0-b numbers |
| **Decided:** first matchup | **TvZ**: Terran bot vs. Zerg human |
| **Decided:** compute | Start at B0 (1 h on a reference workstation) and scale up through the tiers (§13) |
| **Open:** STARDATA subset strategy | Full dataset is ~365 GB compressed; decide whether to mirror it or stream a TvZ subset |

---

## 15. Role summary: which tool does what

| Tool | Used for | Not used for |
|---|---|---|
| **Neural policy (BC → RL)** | All in-game perception, micro, macro execution, intent selection | — |
| **Symbolic layer** (*z*, supervisor, intents, facts, trace) | Steering, branch logic, accountability, explanations | Low-level control |
| **LLM** | Prompt → *z* compiler, replay branch suggestions, intent labeling, narrator | Real-time decisions |
| **Decision models** (Laya/Kev local; Jev/OpenAI Decisions hosted) | Providers in decision slots: replay labeling, opening classification, a learned alternative for `supervisor_branch` (local models only) | Per-step control (that's the policy's job), RL teacher (it would only re-learn the replay labels through a lossy text view) |
| **Python scripts** | Default provider for deterministic slots (z extraction, simple classifiers); baseline in every bake-off | — |
| **Humans** | Gold sets, branch approval, blind evaluation | Bulk labeling |
| **Classic bots / Pluto** | Evaluation opponents, strength reference | Training data |

---

## References

- Pluto: https://github.com/tscmoo/pluto
- Pluto reverse-engineering notes: https://github.com/hwkim3330/pluto-re
- Pluto SC:R bridge: https://github.com/chan22222/Pluto-AI-Starcraft-Remaster
- Pluto ladder incident: https://www.dexerto.com/gaming/ai-bot-destroys-top-starcraft-pros-after-invading-ladder-and-using-absurd-strategies-3410863/
- AlphaStar: Vinyals et al., "Grandmaster level in StarCraft II using multi-agent reinforcement learning", Nature 2019
- STARDATA: https://github.com/TorchCraft/StarData · https://arxiv.org/abs/1708.02139
- screp: https://github.com/icza/screp
- OpenBW / headless eval example: https://github.com/lukecameron/starcraft-ai
- Human-like agent constraints: https://arxiv.org/abs/2505.20011
- Jev: https://www.datacamp.com/blog/system-one-models-jev · https://www.mindstudio.ai/blog/jev-system-one-model-launch
- Laya (open decision model): https://huggingface.co/convaiinnovations/laya
- OpenAI Decisions API: https://startupfortune.com/openais-new-decisions-api-looks-a-lot-like-its-answer-to-a-rivals-jev-model/
- Open Jev rivals overview: https://trilogyai.substack.com/p/jev-open-decision-models
- RepMastered: https://repmastered.app
- Liquipedia replay packs: https://liquipedia.net/starcraft/Template:ReplayPack
