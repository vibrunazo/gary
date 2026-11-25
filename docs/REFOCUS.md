# Gary — Strategic Trunk, Explainability & Control-Flow Plan (v2.1)

Status: **v2.1, Phase 0 and Phase 1 completed** (Phase 1 on 2026-11-25, on the user's sign-off: §4.3 "Phase 1 Results"; what shipped is in `docs/ARCHITECTURE.md` §6.11). **Phase 2 and Phase 3 open.** (Draft v2.1 of 2026-11-23, revised after Phase 0 and the round-two review of its results; `docs/REFOCUSReviews.md` section 2)  
Scope: Implementation plan for completing the unbuilt upper layers of `docs/ARCHITECTURE.md` (§6.1, §6.8, §7.5, §7.6, §8) inside Gary's existing provider architecture, with pre-written gates and a staged games budget. Time is not a constraint; games are.  
Audience: Project owner and implementing agents.

---

## Executive Summary

Gary already has a strong foundation: a single pair of human hands (`gary/interface.py`), a 1:1 offline StarCraft: Remastered bridge (`adapters/scr_bridge/`), an indexed replay corpus (~92k replays total; ~18.9k modern SC:R era across matchups, including 2,683 modern TvZ games in `data/interim/taxonomy/v2/TvZ_Z.json`), deterministic branching games (`eval/pairs.py`), unified decision records (`gary/decision_log.py`, `eval/why.py`, `gary/policy/attribution.py`), a race-agnostic execution core (`gary/race.py`, `gary/agent/executor.py`), and a working per-situation diagnostic loop (`eval/judge.py`, `eval/pipe_table.py`).

**Where the current trajectory succeeds and where it cannot reach the design goals:**
- **G1 (tactical/execution fidelity):** The `TODO.md` (2026-11-12) judge-and-pipe loop is moving targeted fidelity metrics severalfold (e.g., Terran tanks sieging from 0% to 58–61% in TvZ fight moments; commit orders matching pro cluster sizes; calm first-rest matching the pros' 8 s). The bottom-up imitation stack is **not** a dead end and should **not** be torn down.
- **G3 (steerability) and G5 (learner explainability):** More ability, pipe, and decoder fixes will **never** deliver G3 or G5, because the components they require are unbuilt: an enemy-plan belief in play (`TODO #40`), a persistent strategic plan / recipe card (`TODO #26`), a prompt-to-plan compiler (`ARCHITECTURE.md:191`), and discrete logged branch alternatives (`ARCHITECTURE.md` §8). In addition, `TODO.md`'s ability-by-matchup grid has no stopping rule, so local fidelity work continuously crowds out upper-stack work.

**This plan is a priority and control-flow refocus executed incrementally inside the existing agent — not a clean-slate rewrite:**
1. **No new build line (`gt_ns`) and no premature delete list.** Build the missing upper layers of `docs/ARCHITECTURE.md` on the existing provider seams (`gary/policy/belief.py`, `gary/agent/selector.py`, `gary/decision_log.py`, `gary/agent/manifests.py`) inside `gt1dev`. Existing modules and stop-gaps stay until a successor holds their `AGENTS.md` measure, removed **one at a time**.
2. **Real control-flow shift up the stack:** Replace the current static `style` roll at 0:00 and unleased multi-rule macro contention with a persistent `StrategyState` (opening recipe card + reactive directives), a joint enemy-plan belief `P(enemy_z | seen)`, single-owner macro resource control, and structured coaching traces.
3. **Three explicit additions/departures beyond `docs/ARCHITECTURE.md`:**
   - **Pro conditional choice frequencies as V1 default scorer** ($P_{\text{pro}}(\text{branch} \mid \text{belief}, \text{context})$ with a support floor and printed `n`), explicitly departing from `ARCHITECTURE.md:194` (§6.8 win-rate tables) because observational pro win rates are confounded and self-play win rates against weak `gz1` previously taught style-4 cheese. Causal outcome overrides require randomized `eval/pairs.py` branches on Gary's own games.
   - **Phase 1 (belief + recipe card + counted branching + 5 templated Q&As) moves to the foreground** with a pre-written gate, capping other G1 fidelity work to regressions caught in watched games. **Since round two its first build is scouting:** plain fixes and counts that cost no games, then how Gary looks at the Zerg, judged on fidelity. Phase 0 showed the belief has nothing to read in Gary's own games (§3.1). There is no time box.
   - **The army's persistence test, narrowed (round two):** its hold on commitments was already run and rejected (`holdtarget`, `unitcommits`), so the retreat hold is judged as a pipe fix in 16 games and an owned intent waits for a 0-game read (§3.4).
4. **Scope & cuts (split code/offline work from heavy game gates):** Every Phase 1 component, schema, dataset builder, trainer, and 0-game offline count (`SightingState`, `contracts.py`, `plan_belief.py`, scouting counts, `StrategyState`, pro-frequency tables, `eval/coach.py`) is built **race-keyed across all 3 races and all 6 matchups (including mirrors) from day 1**, with `tests/test_matchups.py` exercising the real providers in every matchup—never TvZ-only code (preventing fresh repeats of `calm` crashing TvT/PvT in `a16de8f` or `sighting_dataset.py:44` breaking mirrors). Only the **expensive headless game gates and blind human evaluation** (multi-style suite rounds, blind ≥25-moment Q&A study, Gate 4's 96-game round) run in **TvZ Terran first** (against `gz1dev` told the suite's styles, each game labelled as played, and `gz1`) to keep the games budget bounded. **Remove** online bounded leaf RL (RL stays parked) and **defer** Phase 3 residual concept invention until Phase 1 passes its gate.
5. **What this plan does not aim at (round two, the user's decision):** promotion. No phase targets the promotion rule's second condition: `gt1` stays the playing build, cannot be told a style (told style 4, it played style 1 in 96 of 96 games), and the live games and the blind evaluation use the dev build by flag. Finishing games has no successor while RL is parked, and the unfinished leads against `gz1` are partly `gz1` not resigning.

---

## 1. Context, Design Goals & Honest Standing (2026-11-23)

From `docs/ARCHITECTURE.md` (§1), Gary's purpose is to be a **sparring partner and training tool** for StarCraft: Brood War players across all races and matchups—not a superhuman tournament bot.

| Goal | Requirement (`ARCHITECTURE.md` §1) | Verified Standing (2026-11-23) |
|---|---|---|
| **G1. Real human-like opponent** | Coherent macro, timing, adaptation, and micro that feels like a real player | **Weak in actual play; moving only on local/marginal proxies:** Plays full 3-race games, but in live games still plays like a beginner with one hand (e.g., failing to scout for 8 min and losing 20 SCVs to unscouted Lurkers; Zerg stalling on 11–16 drones; 30 of 96 leads unclosed at 30:00). `eval/humanlike.py` distinguishes Gary at AUC 0.99+. Targeted fixes move local rates (`eval/judge.py`: tanks sieged 0% → 58–61%, cluster order sizes, 8 s first rest), and `gt0.49dev` is nearer pro summary-feature averages than `gt1` in every window (`eval/gap_windows.py`, 0.19–0.41 vs. 0.27–0.62) — a marginal proxy comparison against `gt1`, **not** a claim that Gary plays like a pro — while still trailing `gt1` by `-0.219 [-0.294, -0.141]`. |
| **G2. Human hands in the action space** | Single camera, 12-unit selection, burst APM, reaction delay, hit-testing, fog memory, hidden enemy HP | **Built and strong** (`gary/interface.py`, 1:1 in OpenBW and SC:R; LAN `tools/parity.py` passed 0/120,471 unit mismatches in Phase 0, with non-zero `stim`/`ammo` fields still unverified). |
| **G3. Steerable** | Prompt or replay compiles into a `StrategySpec` (*z*) followed reliably ("practice vs. 2-hatch muta 20 times", 18/20 unharassed drills within tolerance) | **Partial / stalled:** Only a static coarse `style` integer (`--style`) fixed at 0:00. After October's `gt0.18dev` drift (Factory 59%, Starport 10%; Zerg style 4 17%), `gt0.20dev` (`gastarget`) reached **95%** style-1 Factory (pros 88%) and **81%** style-2 Starport (pros 69%), and `gz0.8dev`/`gz0.11dev` raised Zerg style 4 to **75%** and style 0 to **62%**. Still missing: concrete recipe cards/timings, strict 18/20 drill obedience (`ARCHITECTURE.md:456, 471`), `--from-replay` extraction, and a prompt compiler (`strategy_compile`). |
| **G4. Adjustable skill** | One system, multiple human skill bands via `HumanProfile` (*h*) | **Partial:** `HumanProfile` exists for pro and lower bands (`ARCHITECTURE.md:19`); select-to-order timings fitted to pros, remaining hand/click/skill-band parameters unbuilt (`TODO #15`). |
| **G5. Faithfully explainable for learners** | Queryable causal trace answering *why* a strategic/tactical decision was made, what Gary believed, what alternatives lost, and what hand constraint intervened | **Missing strategic state:** `gary/decision_log.py` (`records/v1`) and `gary/policy/attribution.py` (already excluding unactionable own-unit/supply/time groups) log model odds, dice rolls, interventions, and input ablations for debugging. Records hold no opponent-plan belief, no active recipe card, and no discrete strategic branch choices—so no narrator can produce useful coaching reasons (`TODO #41`). |
| **G6. Modular for experiments** | Swappable providers per pipeline slot selected by manifest and compared on shared harnesses | **Built** (`gary/agent/manifests.py`: 154 registered option lambdas; `gt1dev` chains ~27 options over `gt1` over `v029`). |

**Hard constraints (non-goals):**
- **Workstation compute budget:** No AlphaStar-scale distributed RL; RL remains parked (`TODO.md:178`).
- **Offline/custom play only:** Never Battle.net ladder; no Blizzard game data or GPL code (`AGENTS.md`).
- **Honest explanations only (`ARCHITECTURE.md` §3 Principle 5):** Templates and any future narrator may cite only logged decision records—never fabricate post-hoc StarCraft stories. No LLM on the live in-game decision path.

### Constructed Illustration: Why Explainability Fails Today

*(Note: Constructed illustration matching the real `records/v1` schema in `gary/decision_log.py`—where `gt1dev` games genuinely log `layer: style, by: roll` and hundreds of `by: dice` macro/commit draws—not numbers traced to a single committed game file. Pro sample sizes reflect `data/interim/taxonomy/v2/TvZ_Z.json`.)*

| Learner Question | Typical `records/v1` Evidence Today | Best Honest Answer Today | Target Answer After Phase 1 + Army Test (Faithful to Records) |
|---|---|---|---|
| *"Why did you open this build?"* | `layer: style, choice: 1, by: roll` | *"A die rolled style 1 at the modern pros' share."* | *"On this map against unknown Zerg, I opened 1-Rax FE following pro replay card `R_142` (modern pros open this line in 62% of TvZ games on 4-player maps, `n=418`)."* |
| *"Why did you add a Factory + Siege at 4:45?"* | `macro: Factory` drawn at `p=0.05` while `Starport` was `0.55`; zeroing `decisions so far` moves it | *"It wasn't the likely choice; a die came up on a 5% option."* | *"At 4:20 my scout saw Hydralisk Den + Lair with no Spire (`P(lurker_first)=0.74`, prior `0.056` in modern TvZ, `n=150` modern / `3,150` all-era). Activated directive `PREP_VS_LURKER`: pros add Factory + Siege within 60 s in 79% of similar sightings (`n=84`; secondary context: pro win rate 51%)."* |
| *"What did you think I was doing at 5:15?"* | *(none — `belief.py` estimates army counts/supply only and is off by default; `TODO #40`)* | *"I don't form a belief about your strategy."* | *"At 5:15, seeing 2 hatcheries + Lair finishing and gas mined (3rd natural area confirmed empty at 4:50): `P(2h_muta)=0.76`, `P(3h_spire)=0.15`, `P(lurker)=0.06`, `P(other)=0.03`."* |
| *"Why did your army pull back at 9:30?"* | `commit: move` drawn at `p=0.32` while `keep` was `0.42` | *"Keeping was likelier; a die came up move."* | *(If an owned intent is built, §3.4):* *"Squad 1 exited `PUSH(enemy_natural)` into `DEFEND_HOME(main)` when 6 Mutalisks entered main vision at 9:28 (preemption rule; lease transferred cleanly)."* |
| *"Why didn't you stop my drop at 11:00?"* | `hands`/`order` records already log camera & APM refusals | *(Partially answerable today)* | *"Drop entered vision at 10:56; `DEFEND_HOME(main)` issued orders, but camera was on front fight and APM bucket refused 4 orders over 2.8 s."* |

---

## 2. Source-Grounded Diagnosis

### 2.1 What Is Working vs. Where the Current Loop Hits a Ceiling

The current `TODO.md` loop (`eval/judge.py` from 2026-11-12; `eval/pipe_table.py` from 2026-11-17) is **not** broken—in fact, `eval/judge.py` and three watched live computer games on 2026-11-12 exposed the Terran tank siege gap immediately, and `eval/pipe_table.py` (built five days later) diagnosed four of the week's five execution pipe faults. Meanwhile, `gt1dev` still carries four concrete structural gaps:

1. **Missing upper strategic state (blocks G3 & G5 completely):**
   - `gt1dev` rolls a `style` ID at 0:00 (`styleroll`) and holds no recipe card, no timing schedule, no enemy-plan belief (`TODO #40`), and no reactive branch log.
   - `gary/policy/belief.py` already computes multi-window (`30/90/180 s/ever`) fog memory and predicts per-type enemy army counts, workers, town halls, and `q50`/`q80` supply quantiles (though `predict()` currently omits workers and town halls from its returned dict), **not** the enemy's build/tech plan—and it is off by default in play (`PROGRESS.md:59`).
   - `gary/agent/selector.py` is already v0.19's implementation of `ARCHITECTURE.md` §6.8 (Beta-posterior counted table with map backoff `BORROW=20` and Thompson sampling), but it was trained only against scripted Zergs without enemy-belief context and was bypassed in `gt1dev` via `styleroll` because it over-picked style 4 (1.5% of pro games).
2. **Unleased multi-owner contention in Macro (and equal-priority overlap in Army):**
   - **Lease truth in `gary/agent/intents.py:27–30, 54–60`:** Across strict priority tiers (`3: rule:/hands:` > `2: fight/roles` > `1: army/calm`), `Leases.free()` is **preemptive**—it filters out units held by strictly higher priorities *before* the lower layer decides. (`calm.py:68` asks as `"army"`, priority 1, below `roles`'s priority 2.) However, `priority(h[0]) > p` is strict, so **equal-priority** layers (`calm` vs. `army` at priority 1; `fight` vs. `roles` at priority 2) do not exclude each other.
   - **Hidden inheritance in `gt1dev`:** `unscripted` (`manifests.py:1093–1096`) disables only `army.{static_odds, hunt, rules(except posts/raid)}`, `macro.{caps, bank_escape, supply_ahead}`, and `scv_saturation`. Because `gt1dev` inherits from `gt1` → `v029` (`manifests.py:261, 1393–1397`), **`gt1dev` still runs `"answers": True`, `rax_by`, `expand_mass`, `under-half`, and the five priority-3 Terran fight rules (`pull`, `load`, `repair`, `detect`, `reinforce`)**. (`natural_bunker` is off in both builds since `nonatbunker`, `manifests.py:849, 1224`; earlier drafts listed it as running.)
   - **No resource owner in Macro:** `macro.py` and `answers.py` make no lease calls; `posture.build`, `answers.py`, `rax_by`, `under-half`, `odds_mass`/`expand_mass`, and `MacroNet(dice)` all share one mineral/gas pool and `g.task` slot.
3. **Coherence limits of decoupled per-tick models without shared intent:**
   - The active dev stack has fewer distinct model architectures than its option list implies (`Calm` reuses `RoleModel` at `gary/policy/calm.py:5`; event models live inside `ModeModel` at `gary/policy/modes.py:177`), and models maintain local trackers (`MacroTracker`, `ArmyTracker`, `Calm.prev`/`drawn_at`, `LearnedMacro` queues). What they lack is **shared multi-second/multi-minute intent**.
   - **What the recent measurements actually show:**
     - *Calm layer (`PROGRESS.md:2217–2273`):* `CL281a` reached 1.43 short orders/min (pros 1.58), first rest 11 s, `units alone` 0.38, direction log-loss 2.669 (vs. bins' shares 2.729, uniform 2.773). `CL282a` (folded into `gt0.46dev`) hit 1.24 short orders/min, first rest 8 s (pros 8 s), `units alone` 0.41, far head 2.495; `gt0.48dev` (`HS284a`) stands at `units alone` 0.40 (pros 0.20). Later reads showed scattering was driven primarily by *which bunches get orders* (median 2 units far from the army vs. pros' 7; 89% of 1-unit orders went to already-lone units), supporting group-level command ownership rather than claiming pure direction noise.
     - *Retreats & tanks (`PROGRESS.md:99–102, 2409–2411`):* Within 2 s of a fight retreat, 37% received another retreat and **27–40%** switched to reposition, close-in, or fire; `retreatfar` (`gt0.43dev`) fixed the 3-tile destination, leaving retreat hold unbuilt (`TODO.md:59–65`). Army moves unsieging tanks mid-fight were fixed in `gt0.39dev` (`staysieged`).
     - *Exposure bias vs. parity bugs:* Separate plain observation-parity fixes (`seenall`, `eggs`, `zfullhp`, held by `tests/test_inputs.py`, where `train/macro.py:41` already imports `gary.policy.macro.encode` and parity regressions came from live `HumanInterface` vs. C++ `gary_resim` unit accounting such as workers in refineries or units in bunkers) from missing-plan drift (e.g., Hydralisk Den drawn at 1–6% in 21/24 Zerg games, or belief error doubling from 5.9 on pros to 11.7 on Gary's own games).
     - *Stale `-0.188` standing:* `gt1dev` trailing `gt1` by `-0.188 [-0.302, -0.078]` is from **2026-11-11** (predating `ModeModel` and `Calm`) and was accounted for in `PROGRESS.md:2976–3003` by the removed stop-gaps (`bank_escape -0.203`, `caps -0.109`, `static -0.062`, `scv_cap -0.047`) plus unfinished leads (`gp1dev` passed `+0.036 [-0.036, +0.109]` vs. `gp1`). Whether a deficit remains on `gt0.48dev` was an open test run in Phase 0. **Resolved (2026-11-23):** a deficit remains. `gt0.49dev` (`gt0.48dev` plus the `#64` seed fix) against `gt1` `gt0.21`, 96 paired games each against `gz1`, both `--gg 0`: **`-0.219 [-0.294, -0.141]`** by supply (critics `-0.219`, `-0.276`), no measurable change from `-0.188`; yet `gt1dev` is nearer the modern pros in every time window (all features `-0.06` to `-0.21`, every interval clear of zero; macro nearer in every window; fight nearer at 10–25 min, unresolved elsewhere) and plays the style it is told (`gt1` played standard bio in 96 of 96 games told style 4). Promotion's fidelity condition holds, its strength condition fails; `gt1` stays the playing build (`PROGRESS.md`, "gt1dev against gt1 remeasured").
4. **No stopping rule on local tells & sparse human validation:**
   - Only 4 games against a human opponent were played through 2026-10-19 (plus 3 watched computer games on 2026-11-12); ~25 changes landed under `#16` in early November without human play or comparison against `gt1` (`PROGRESS.md:1796–1799`). Without an explicit foreground priority, time box, and maintenance cap, G1 micro tells will always consume 100% of bandwidth.

### 2.2 Honest Empirical Learning Ledger

Gary's past experiments (`docs/CONTROL.md`, `docs/SELF_PLAY.md`, `docs/PROGRESS.md`) show why RL stays parked and why V1 must rely on supervised perception, counted pro frequencies, and deterministic counterfactual checks:

| Learning Experiment | Timescale | Measured Result in Gary | Honest Takeaway |
|---|---|---|---|
| `train/macro_rl.py` | 1 build click | Effect `sd=130` vs. chaos `sd=512`; **50.0% held-out** | Single-click macro RL drowns in game variance |
| `league_loop.py` roles (5 runs) | 0.5 s fights | 4 runs flat; `rl1` held once the model owned decisions in contact & passed the pipe check, then was replaced in `gt0.36dev` by `tvzmodes` because **`rl1` lacked siege, unsiege, and mines** (`manifests.py:997–999`; `PROGRESS.md` top summary still lists `rl1`) | Pipe ownership is necessary for RL, not sufficient for transfer |
| Local fight scenarios (`rl2`, `rl3`, `#53`) | 10–20 s / 120 s scenarios | Beat `rl1` on 79 held-out scenarios (`+255`, `+268` vs. `+195`), **failed 96-game transfer** (`-0.036`, `-0.013`) | **Falsifies unshaped local-reward sub-episode RL** |
| `train/commit_pairs.py` (1,004 pairs) | Commitments **locked at pro reversal hazard** (half reversed by 35–55 s) | **0.46 held-out (chance)**; constant-engage baseline matched learned scorers (`SELF_PLAY.md:507–514`) | Even locked army commitments are under-powered at 1k pairs (`MDE` limit) |
| `eval/army_effect.py` *(since deleted)* | 90 s whole-army forced attack vs. hold | Effect `sd=650` vs. chaos `sd=210` over 77 moments (`SELF_PLAY.md:488`) | Shows whole-army attack/hold *matters*; does **not** prove intermediate option choices have learnable SNR |
| `gary/agent/selector.py` (v0.19) | Whole game (per map) | Cut losses 57 → 30 of 333 against scripted Zergs—mostly by over-picking style 4 (1.5% of pro games) | **Warning:** self-play win-rate tables against weak/scripted opponents learn exploits/cheese |
| Offline supervised models (`belief`, `value`, `placement`, `stim`, `modes`, `commit`) | Offline replay datasets | Fast, reproducible, well-calibrated on held-out pros | **Proven strength** on workstation compute |

**Consequence:** RL stays **parked** (`TODO.md:178`). This plan does **not** run online leaf RL and does **not** rely on RL to pass Phases 0–2.

---

## 3. Architecture & Technical Design (Additive on Existing Seams)

This design finishes `docs/ARCHITECTURE.md` (§6.1, §6.8, §7.5, §7.6, §8) on Gary's existing provider seams rather than creating a parallel stack:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PRE-GAME (G3): strategy_compile (text -> card lookup, ambiguity shown)  │
│                or --from-replay <path> -> StrategySpec (opening_card)   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     ▼
┌─────────────────────────────────┐  ┌────────────────────────────────────┐
│ OPPONENT BELIEF (Extends        │  │ STRATEGIC TRUNK (Extends           │
│ gary/policy/belief.py, §7.5)    │  │ gary/agent/selector.py, §6.1/§6.8) │
│ • Joint P(enemy_z | sightings)  ├─►│ • Persistent StrategyState         │
│   over taxonomy/plans.py        │  │   (card, adherence, directives,    │
│ • Seen / confirmed-absent /     │  │    transition history)             │
│   unscouted state separation    │  │ • V1 Scorer: Pro conditional       │
│ • Counts + q50/q80 + workers/TH │  │   choice freq P_pro(b|belief,ctx)  │
└─────────────────────────────────┘  │   with min_n floor & printed n     │
                                     └─────────┬─────────────────┬────────┘
                                               │                 │
                       ┌───────────────────────┘                 └──────────────────────┐
                       ▼                                                                ▼
┌──────────────────────────────────────────┐   ┌──────────────────────────────────────────┐
│ MACRO EXECUTION (Single Resource Owner)  │   │ ARMY / TACTICS (Narrowed in Round Two)   │
│ • Phase 1 A/B: z-conditioned MacroNet vs │   │ • Control: current gt0.50dev             │
│   preemptive resource reserve + tech mask│   │ • Retreat hold: a pipe fix, 16 games     │
│ • Strict drills (18/20): scripted card   │   │ • Owned intent only after a 0-game read: │
│   queue (ARCHITECTURE.md:456, 471)       │   │   16×16 spatial target proposal          │
│ • Legacy rules removed ONE AT A TIME     │   │ • Keeps RoleNet/Mode/Stim/Cast/Placement │
└──────────────────────┬───────────────────┘   └────────────────────┬─────────────────────┘
                       └─────────────────────┬──────────────────────┘
                                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ HUMAN INTERFACE & ATTENTION ARBITER (Kept as-is: gary/interface.py)     │
│ + STRUCTURED TRACE (gary/decision_log.py: join IDs + plan/belief/intent)│
│ -> 5 Deterministic Templates (eval/coach.py) + 3-Part Verification (§8) │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Joint Enemy-Plan Belief (Extending `gary/policy/belief.py`)

- **Extend, don't replace:** Keep `BeliefMemory` (`30/90/180 s/ever`) and `BeliefModel`'s per-type counts + `q50`/`q80` supply quantiles; expose predicted enemy workers and town halls (already inside `out[:k]` at `belief.py:135–136`) in `predict()`.
- **Joint plan distribution, not independent soft flags:** Predict one calibrated categorical distribution `P(enemy_z | sightings, time, map)` over the existing plan library (`taxonomy/plans.py`: `{pool, hatch} × {2h, 3h} × {spire, lurker, ling_pressure, hydra, other}`), respecting Brood War's mutually exclusive early tech/gas structure. Independent binary flags fed into a downstream MLP invite soft-probability leakage (Mahinpei et al., 2021; Havasi, Parbhoo, & Doshi-Velez, 2022) and are **not** used.
- **Three-way fog visibility semantics:** Explicitly separate **seen** (with last-seen timestamp), **confirmed absent** (scout visited region at frame $t$ and observed no building/expansion), and **unscouted**—essential for explaining *"I assumed 2-hatch muta because my SCV saw no 3rd hatchery at 4:50"*.
- **Two-provider bake-off (`ARCHITECTURE.md:763`):** Implement and compare behind one slot:
  1. **Bayesian plan recognition** over tech-tree/build observations learned from replays (Synnaeve & Bessière, 2011), and
  2. **Boosted trees / calibrated lightweight NN** (matching `eval/judge.py`'s model family).
  Both must beat a **time-and-map base-rate prior** and `answers.py`'s current heuristic read on held-out per-minute Brier score and ECE.
- **Honest sample budget & distribution-shift calibration:** `data/interim/taxonomy/v2/TvZ_Z.json` contains **2,683 modern TvZ games** (18,066 across all eras): 90.8% are spire-first (plan 0 alone is 58.9%) and only **5.6% (~150 modern games)** are lurker-first (17.5% across all eras; `docs/DATA_ERAS.md`). Report per-class calibration against class base rates, account for era shift explicitly, and calibrate on **Gary's own self-play re-simulations** as well as held-out pros (closing the observed 5.9 → 11.7 supply error shift).
- **Scouting is the precondition (round two; Phase 0's finding).** The offline belief (`train/plan_belief.py`) beats the floor on the pros' held-out games and is worse than the floor on Gary's own from 6:00, because Gary does not look: its worker scout is home by about 3:00 (`answers.py:15–16`), its one scan is set for 6:30 (`answers.py:32`), and that scan cannot fire on a map with more than one enemy start (`answers.py:91` needs `army.enemy_main`, assigned only under option `watch`, `army.py:1029–1030`: all 20 scans of `RD285a` are on two maps of eight). Gary's first plan read is at a median of 7:33, when the units arrive. The "5% by 6:00 against the pros' 60%" counts a Lair or a Hive as tech (`plan_belief.py:61`), which tell no plan. So before the belief is used: fix the scan's main (a plain bug, in `gt1` too), then count, at no games, the pros' first sight of the Zerg's tech **by type** (Spire or Den apart from Lair), **by means** (their scans are commands in the replay; which unit had the building in sight; how long their first SCV stays) and, for Gary, seen **given that the building stood**. How Gary then gets scouting is §6 row 8.
- **What a look is.** `gary/policy/sightings.py` as committed counts a base as looked at when any unit is within 8 tiles of its centre and records only a town hall's presence. Before the dataset is built in full: a look comes from what was visible (the share of the base in sight, or sectors of its rim), a Comsat scan counts as a look (to verify in a scenario: whether the sweep is one of the player's units in the observation), absence is recorded for tech buildings and not only halls, the class and §4.2's `SightingState` are one shape under one name, the dataset finds the player by slot (it is wrong, and fails, in a mirror) and is built for every era the trainer reads (modern-only sightings hand the trees the era through missing values).
- **The trainer's faults, fixed before any score is quoted:** Gary's games labelled by the pros' rule (first times to 9:00, Lurker Aspect by its research, zerglings ordered by 4:00); a calibration error computed, as gate 1 names one; comparators fitted on other games than they score; the player's own supply and workers out of the inputs or flagged (a belief that reads the enemy's plan off Gary's own build explains nothing); first-seen times added (the ceiling fed the Zerg's true units is worse at 8:00 than at 6:00); the lurker egg among the types; the `--sightings` fit's categorical mask (read, not run: it would fail on the ceiling).
- **The provider test (round two):** on Gary's games where it has not looked, a provider must return the floor. The trees get the sighting states and the pros' sightings cut at random earlier times first; the Bayesian provider, where an unlooked base adds no evidence by construction, is built if they fail that test. Both are scored on Gary's games against the suite, split by looked and unlooked.
- **Tech that changes.** Beside the joint's first-tech label, the belief keeps non-exclusive flags for spire and lurker tech in play, so a Zerg that adds lurkers after mutalisks is answered (`answers.py`'s read never moves from mutalisks to lurkers, `answers.py:76–80`).

### 3.2 Persistent `StrategyState`, `strategy_compile`, & Pro-Frequency Branching (Extending `gary/agent/selector.py`)

- **Explicit `StrategyState` object:** Holds:
  - `opening_card`: concrete ordered milestones & target times/supplies extracted from a real pro replay of the chosen style or `--from-replay <path>`;
  - `adherence_mode`: `strict` (drill mode: no opportunistic switching, deterministic milestone adherence for 18/20 drills per `ARCHITECTURE.md:456, 471`) vs. `reactive` (standard sparring);
  - `active_directives`: discrete, named reactive directives (e.g., `PREP_VS_MUTA`, `PREP_VS_LURKER`, `DEFEND_EARLY_POOL`) with start frame, triggering evidence IDs, and exit condition;
  - `history`: append-only transition log of every card/directive change.
- **Pre-game `strategy_compile` slot (G3 text prompts):** Constrained pre-game lookup/compiler turning a user request (e.g., `"1-rax FE bio+tank"` or `"practice vs 2-hatch muta"`) into a validated `StrategySpec` card from the taxonomy/replay catalogue, surfacing ambiguity or out-of-catalogue requests before game start. **No LLM inside the live game loop.**
- **Explicit Departure from `ARCHITECTURE.md:194` (§6.8): Pro Conditional Choice Frequencies as V1 Scorer:**
  - `ARCHITECTURE.md:194` and §6.8 specify picking branches via **win-rate statistics**. This plan **deliberately departs** from that for V1: observational pro win rates suffer from survivor/selection bias (pros skip turrets when already winning), and self-play win rates against weak `gz1` previously taught style-4 cheese (`selector.py`, §2.2).
  - Instead, extend `gary/agent/selector.py`'s hierarchical shrinkage machinery to score branches in V1 by **pro conditional choice frequency** $P_{\text{pro}}(\text{branch} \mid \text{belief}, \text{context})$ with a written **support floor (`min_n ≥ 25` modern games after backoff, otherwise fall back to broader parent cell and print exact `n`)**.
  - **Keep three quantities strictly separated** in tables, records, and explanations:
    1. **What pros do** ($P_{\text{pro}}(\text{branch} \mid \text{belief}, \text{context})$, `n`, Wilson interval) — *V1 deciding score*;
    2. **How those pro games ended** (observational win rate) — *printed as secondary context only, never decided on*;
    3. **What the branch does for Gary** (paired-branch outcome delta from `eval/pairs.py` on Gary's own games) — *the only evidence permitted to override pro frequencies in future versions*.
  - **No CRM on pro replays:** Counterfactual Risk Minimization (Swaminathan & Joachims, 2015) requires known logging propensities and no unobserved confounding, neither of which holds in pro replays. Where logged propensities are needed later, use Gary's own `records/v1` logs (`p`, `top`) or randomized `eval/pairs.py` branches.
  - **Alternative glass-box scorers (swappable slot):** Support $\text{GA}^2\text{M}$ / EBM (Lou et al., 2013; Nori et al., 2019) for additive/pairwise branch families (e.g., turret counts, expansion timing) and depth-limited interaction trees where 3-way timing conjunctions matter. Do **not** adopt Concept Embedding Models (CEM) or an unconstrained `concept_mlp` on the live trunk: passing dense learned embeddings leaks unstated raw features, undermining G5 honesty. Keep Tier 3 leaves unconstrained on raw features and keep any unconstrained `ValueNet` **offline outside the decision path** (`ARCHITECTURE.md` §7.6).
- **Round-two consequences for the tables:** the pros' cells are those of a player who looked, so the tables are keyed on the looked state as well as the belief, or built after scouting; beliefs used to fill them are cross-fitted, never the retrospective plan label; the backoff for plans under `min_n` is written down (of the modern games, zergling pressure and hydralisks are about 0.2% each and the lurker-first styles 5.6% together, so they fall back to all eras weighted, or to the plan's parts); `PREP_VS_MUTA` and `PREP_VS_LURKER` can be active together. The dice never roll a decision under 1% (`DICE_FLOOR`, `macro.py:41`), so a directive asks for its item as a goal; a mask alone cannot make it happen.

### 3.3 Single-Owner Macro Migration (One Rule at a Time)

When the strategic trunk is active, **one owner must control macro resources and one-off tech/branch decisions** (removing the two-master conflict between `MacroNet`, `answers.py`, `rax_by`, `under-half`, and `odds_mass`/`expand_mass`). However, per `AGENTS.md`, we do **not** bundle multiple rule removals with a new layer in one opaque diff:

1. **Audit first (Phase 0):** Count how often `answers.py` actually decides in one full `gt1dev` league round's records.
2. **Log-only soak (Phase 1a):** Run `belief` + `opening_card` log-only beside `gt1dev`, tagging every macro decision as `on_card`, `off_card`, or `delayed(money | busy_building | hands)` to measure whether off-plan draws come from low-odds dice or hands/money bottlenecks.
3. **One-at-a-time rule removal (Phase 1b):** Disable conflicting legacy macro rules (`answers.py`, `rax_by`, `odds_mass`/`expand_mass`, `under-half`) **individually**, verifying each against its `AGENTS.md` measure as the trunk assumes ownership.
4. **Two-arm Macro Execution A/B (Phase 1c):** Directly settle whether neural conditioning alone holds a build card as well as preemptive masking:
   - **Arm A (AlphaStar *z*-conditioned `MacroNet`):** Condition `MacroNet` on remaining card milestones + enemy belief (Vinyals et al., 2019), with the trunk handling card/directive switches and logging why.
   - **Arm B (Preemptive Resource Reserve + Tech Mask):** Trunk holds a formal `reserved_for_milestones` mineral/gas budget and hard-masks `MacroNet`'s one-off tech/expansion/research outputs unless the active card/directive permits them (preemptive scoping in Alshiekh et al., 2018's sense).
   - **Strict drills (`adherence_mode="strict"`):** Use a deterministic milestone/scripted macro queue (`ARCHITECTURE.md:456, 471`, Churchill & Buro, 2011) if stochastic sampling cannot guarantee ≥18/20 unharassed timing runs.

**Round-two amendments to these steps:**
- **"Arm 0" before Arm A or B:** today's build scored on the card's own measure (timing error per milestone against the card of its told style) from `RD285a`'s 96 games, at no new games. The style label already reads 97–100% for styles 1 and 2 because it is the nearest cluster of each key item's first time within 8 minutes (`eval/style_adherence.py`); it cannot show what a card adds. The 40 drills and the A/B are run only if Arm 0 leaves a gap. Whether a deterministic queue is the drills' path is decided on that number too.
- **The soak's first pass costs no games:** each macro record carries its odds, its draw and the options set aside with reasons, so `on_card`/`off_card` is computed over `RD285a` first. `on_card` is defined on one-off milestones (tech buildings, add-ons, expansions, research); most macro decisions are continuous production and belong to no card.
- **Log-only means it cannot move play:** every shadow provider draws from its own stream and pins its checkpoint.
- **Switches the one-at-a-time removal needs first:** an option that turns `answers` off in TvZ (none exists), a switch for under-half (`macro.py:479`). Comsat energy joins minerals, gas and the task slot as an owned resource: the tech scan, the hunt's scans and the Detect rule each spend it without knowing of the others. `committed()` holds minerals only (`gary.py:176–188`).
- **`answers.py` first on AGENTS.md's own pending measure:** `answers` off once Gary sees, to learn whether the macro model answers alone (it already reads what was seen: in sight now and the most ever seen). If it does, the belief's job in the macro is explanation. Then one answer handed to the trunk end to end (the lurker list), judged on the time from the Zerg's tech standing to Gary's answer carried out, per plan. The Phase 0 count of 989 turret goals is of goals asked, not turrets built (a goal not carried out is asked again after 30 s).
- **Arm A's two traps:** a card input taken from each pro game's own later milestones leaks the next decision unless it is masked at random in training (as AlphaStar did with *z*); and a changed macro input turns gg off for that side until its critic is retrained (`eval/match.py:113–117`), so the arms would not play under the same `--gg`. **Arm B** integrates with `committed()` instead of adding a second reserve, which would count parked builds twice.

### 3.4 Tactical Army Layer: The Retreat Hold First, an Owned Intent Only on Evidence

Rather than jumping directly to 9 hand-authored squad options with hand-tuned thresholds (which previously mirrored `gather` and `retreatfar`), test the smallest mechanisms first. Round two narrowed the three arms first written here (the user's decision, `docs/REFOCUSReviews.md` 2.8):

- **Control:** Current `gt0.50dev` (`army.py` + `calm.py` + `roles.py`).
- **A hold on `army.py`'s commitments: not run, as it already was.** `holdtarget` (-0.011 ± 0.087) and `unitcommits` (-0.048 ± 0.064) were tried and not adopted (`manifests.py:1121–1127`); on the same measure the pros redirect 0.79 of their group orders within 30 s and `gt1dev` 0.70 (`PROGRESS.md:1213–1219`), and `SELF_PLAY.md:489–493` ends "Gary's own commitments already have that shape". The commit model already reads its commitment and its age.
- **The retreat hold: a pipe fix, judged on its own check.** Retreats seen against asked are 0.22 for the pros' 0.78, and within 2 s 37% get another retreat and 27–40% another role (`PROGRESS.md:2550–2554`; left open at `TODO.md:59–65`). A retreat held for its stretch, as a mode with the pros' exit hazard (`train/modes.py`), is judged on `eval/pipe_table.py` in 16 games, as `retreatfar` was.
- **A minimal owned intent, staged behind a 0-game read (not vetoed by it):** 1–2 persistent, unit-leased tactical intents (e.g., `DEFEND_HOME` and `PUSH_OR_PRESSURE`) with explicit lifecycle identity (`id`, `start`, `end`, `preempt`, `lease`), **retaining `ArmyNet`'s `16×16` heatmap as the spatial target proposal**. Note that past rejected relatives (`gather`, `anchor` with `home_guard`) were post-hoc interceptors bolted onto an unconditioned `commit`+`RoleNet` stack (`gather` froze `commit` and dragged every army unit to a raw center of mass), so their failure does not disprove a true top-down intent layer whose leaves are conditioned on the active intent. First, read from existing rounds: of units alone and late arrivals, the share caused by another cluster's order taking a committed unit, and the cluster key in the grouping provider that `PROGRESS.md` leaves open. That 0-game read checks one specific interference mechanism—it is **not** a veto on building a top-down tactical intent layer (3–5 modes with intent-conditioned leaves) in Phase 2 if live-game play still feels tactically incoherent or Q&A #4 remains weak after Phase 1. If built, `DEFEND_HOME` leases a local group in proportion to the threat and never calls a push home over a few zerglings.
- **Pass criteria:** Retreats seen against asked and distance gained (the retreat hold); for an owned intent, late arrivals at attacks, **Q&A #4 (*"Why did your army attack / pull back here?"*)**, and the paired score vs. `gt0.50dev`. `units alone` is not a criterion of this test: it was traced to the calm layer's moves of lone units and to having more small bunches (`PROGRESS.md:2306–2313`). No criterion on finished leads: neither arm addresses them (§6 row 10).
- **Separate offline check (0 games):** Before adding any upgrade-timing criterion (e.g., attacking on Stim/+1), measure on existing league rounds whether Gary actually mistimes attacks relative to Stim/+1 compared with pros. Settled in round two: `commit` receives no research or upgrade state (`gary/policy/army.py:135–156`), so such a criterion would need a new input and a retrained model.
- **Future leaf-coherence candidate (not in Phase 1):** If a held intent plus `RoleNet` still exhibits 2–4 s micro dithering after the retreat hold, evaluate **Action Chunking (`ACT`, Zhao et al., 2023)** as a bounded Tier 3 imitation upgrade. Do **not** run online local-reward leaf RL (`#53`).

### 3.5 Explainability & Three-Part Faithfulness Verification (`ARCHITECTURE.md` §8)

- **Trace schema extension (`gary/decision_log.py`, `records/v1`):** Add a monotonically increasing `id` and `parent_id` linking `plan_belief` → `strategy_state` / `branch_select` → `intent_event` → `lease` → `order` → `fate`, so pipe drops are visible directly in the trace.
- **Five deterministic templates first (`eval/coach.py` or `eval/why.py --ask`, no LLM in V1):**
  1. *Why this opening / strategy card?*
  2. *What did you think I was doing at minute M, and from what evidence (seen vs. confirmed-absent vs. unscouted)?*
  3. *Why did you build / tech / expand (or delay) at minute M?*
  4. *Why did your army attack / hold / pull back at minute M?*
  5. *Why did you miss a defense / supply block / timing?*
  *(Display answers linked to the exact timestamp/frame in `viewer/` to avoid the navigation cost found by Penney et al., 2018.)*
- **Three separate verification metrics (replacing single-flip "80%" kill line):**
  1. **Execution Join Integrity (automated):** Fraction of logged strategic/tactical branch decisions whose downstream leases/orders actually executed without silent override or pipe drop (directly checks the `TODO.md:15–16` failure mode).
  2. **Decision Faithfulness (1 ms in-memory, no game rollout):** Re-query the trunk on the saved input state with valid upstream belief/sighting edits to find the **minimal abductive set** of facts whose change flips the branch (handles overdetermined decisions cleanly, where single-concept flips fail).
  3. **Truth, Outcome Consequence & Human Utility:**
     - *Ground-truth belief accuracy:* compare every cited belief after the game against true opponent build (`ARCHITECTURE.md:853`) vs. base rate;
     - *Outcome counterfactual (when asked "what would have happened if X instead of Y?"):* repeated `eval/pairs.py --repeats` branches with stated horizon (Madumal et al., 2020);
     - *Blind human evaluation:* compare templated answers against answers generated from today's `gt1dev` records over ≥25 held-out moments from 5+ games on (a) blind next-branch prediction accuracy and (b) coaching usefulness rubric (user + ideally 1–2 outside BW players).

---

## 4. Codebase Inventory, Contracts, Staged Plan & Games Budget

### 4.1 Codebase Inventory (No Premature Deletions)

| Codebase Area | Action | Rationale |
|---|---|---|
| `gary/interface.py`, `gary/commands.py`, `gary/orders.py`, `gary/mapinfo.py`, `gary/terrain.py`, `gary/walls.py`, `adapters/scr_bridge/`, `viewer/` | **KEEP** | Core G2 human hands, SC:R bridge, and POV viewer (add frame-jump links for Q&As later) |
| `resim/`, `ingest/*`, `train/macro.py`, `gary/race.py`, `gary/races.py`, `gary/terran.py`, `zerg.py`, `protoss.py`, `gary/agent/executor.py`, `*_executor.py`, `gary/agent/motor.py` | **KEEP** | Replay/resim pipeline (note: `train/macro.py:41` already imports `gary.policy.macro.encode`; parity bugs live in live-vs-resim observation accounting `#50`, not duplicated encoders) and race-agnostic core |
| `gary/policy/fight.py`, `gary/policy/fight_cmd.py`, `gary/policy/plan.py`, `gary/policy/switch.py` | **KEEP (LIVE)** | Actively imported by `fight.py`, `calm.py`, `zerg_roles.py`, `posture.py`, `arbiter.py`, and `manifests.py` |
| `gary/policy/placement.py`, `stim.py`, `cast.py`, `modes.py`, `roles.py`, `value.py`, `attribution.py` | **KEEP** | Working low-level neural models, offline critic (`--gg` + Phase 3 audit), and input attribution |
| `gary/policy/belief.py` | **KEEP & EXTEND** | Add joint `P(enemy_z | seen)` over `taxonomy/plans.py` + seen/absent/unscouted memory; expose workers & town halls in `predict()` |
| `gary/agent/selector.py` | **KEEP & EXTEND** | Already v0.19's §6.8 Beta-posterior table; extend with belief/context keys and pro conditional choice frequencies (`P_pro` + `min_n`) |
| `gary/decision_log.py`, `eval/why.py`, `eval/judge.py`, `eval/pipe_table.py`, `eval/pairs.py`, `eval/style_adherence.py`, `eval/gap_windows.py` | **KEEP & EXTEND** | Add trace join `id`/`parent_id`, structured belief/strategy/intent records, 1 ms in-memory trunk counterfactual query, and `eval/coach.py` templates |
| `gary/agent/army.py`, `gary/agent/calm.py` | **FIX SEEDS & TEST** | Fix `#64` RNG seeding (`army.py:159` `game_seed`, `calm.py:41` hardcoded `Random(0)`); test persistence / minimal owned intent as §3.4 now orders them (the retreat hold first) before retiring anything |
| `gary/agent/grouping.py` | **REFACTOR IF NEEDED** | Refactor only if an owned intent / Phase 2 requires persistent squads to own hotkeys (`TypeGrouping` currently re-assigns by unit type) |
| `gary/agent/answers.py`, `gary/agent/posture.py`, `gary/agent/macro.py` legacy decoders (`odds_mass`, `expand_mass`, `under-half`, `rax_by`) | **RETIRE ONE AT A TIME ON MEASURE** | Keep in place during log-only soak; disable individually per `AGENTS.md` only as the Phase 1 trunk holds each rule's own measure |
| `gary/agent/manifests.py` | **EXTEND CLEANLY** | Register Phase 1 trunk/belief/macro options inside `gt1dev` (no `gt_ns` fork); keep every option cleanly composable and reproducible |

**Stop-Gap Accountability (`AGENTS.md`):** Every existing stop-gap (`lords`, `hunt4`/`split`, `static`/`softguard`, `caps`, `scv_saturation`, `under-half`, `bank_escape`, `mass`/`expand_mass`, `answers.py`, `early_pool` posture) keeps its `AGENTS.md` entry and exit measure. In particular, finishing won games (`hunt4`) is **not** relabeled as a permanent scripted trunk rule—it remains an explicit tracked stop-gap until a learned or explicitly measured successor replaces it.

### 4.2 Typed Contracts (`gary/agent/contracts.py`)

Contracts live behind swappable manifest slots, carry explicit identity/lifecycle state, and seed all stochastic providers from `g.game_seed` (`#64`):

```python
@dataclass(frozen=True)
class SightingState:
    seen: dict[str, tuple[int, int]]        # entity/tech -> (count, last_frame)
    confirmed_absent: dict[str, int]        # region/feature -> last_checked_frame
    unscouted: frozenset[str]               # regions/timings never checked

@dataclass(frozen=True)
class PlanBelief:
    frame: int
    plan_probs: dict[str, float]            # joint P(enemy_z | sightings) over taxonomy/plans.py
    expected_counts: dict[int, float]       # from BeliefModel
    workers_est: float
    town_halls_est: float
    supply_q50: float
    supply_q80: float
    sightings: SightingState
    record_id: int

@dataclass(frozen=True)
class Directive:
    id: str                                 # e.g., "PREP_VS_MUTA"
    params: dict[str, Any]
    started_frame: int
    exit_condition: str
    trigger_record_id: int

@dataclass
class StrategyState:
    card_id: str                            # replay/spec ID
    opening_card: list[dict[str, Any]]      # ordered milestones (item, supply/time target)
    adherence_mode: Literal["strict", "reactive"]
    active_directives: list[Directive]
    history: list[dict[str, Any]]           # transition events with record_ids

@dataclass(frozen=True)
class CandidateBranch:
    name: str
    params: dict[str, Any]

@dataclass(frozen=True)
class TacticalIntent:
    id: str                                 # persistent identity across frames
    kind: str                               # e.g., "DEFEND_HOME", "PUSH_OR_PRESSURE"
    units: tuple[int, ...]
    target: tuple[int, int] | None          # may be supplied by ArmyNet 16x16 heatmap
    params: dict[str, Any]
    started_frame: int
    end_condition: str
    preempt_by: tuple[str, ...]
    lease_id: str
    attention_hint: float | None = None     # optional arbiter/G4 hook

class PlanBeliefProvider(Protocol):
    def update(self, obs: dict, mapinfo, rng) -> PlanBelief: ...

class BranchScorerProvider(Protocol):
    # Swappable: "pro_freq_table", "ebm_ga2m", "interaction_tree"
    def score(self, belief: PlanBelief, strategy: StrategyState,
              candidates: list[CandidateBranch]) -> dict[str, dict[str, Any]]: ...

class StrategyTrunkProvider(Protocol):
    def step(self, belief: PlanBelief, current: StrategyState,
             rng) -> tuple[StrategyState, list[dict[str, Any]]]: ...
```

**Round-two amendments to the signatures above, to be written into `contracts.py` when it is created:** `StrategyTrunkProvider.step` and `BranchScorerProvider.score` also take the observation or an own-state context (units, research, economy, map, time), without which a milestone's completion, a directive's exit and the scorer's backoff cannot be computed; `PlanBeliefProvider` takes the side's slot and the enemy's race and has a `reset()` for paired branches; every provider can answer "not enough evidence" without inventing counts or odds; the evidence a decision read is identified (which observation, which sighting records); `TacticalIntent` carries the record that triggered it; `SightingState` holds, per region, when it was last looked at and how much of it was covered, so a stale look is not "never checked".

**Schema Freeze Rule:** Do **not** freeze `contracts.py` or `SightingState` until **all 6 matchups (TvZ, PvT, TvT, PvZ, ZvZ, PvP — including mirrors)** run through the **real** providers (not stubs) in `tests/test_matchups.py`, and scouting/sighting schemas cover all three races' scouting means (Terran Scans/SCVs, Protoss Probes/Observers, Zerg Overlords/Zerglings) with zero matchup-specific assumptions baked in.

### 4.3 Staged Schedule, Written Gates & Games Budget

> **Games budget (round two, in physical games; a paired round is two arms unless one is already played):** about **180 to 240** for Phase 1's unconditional steps, with up to 136 to 232 more for the card's drills and A/B and 48 to 240 for an owned army intent, each only if a 0-game read calls for it. Time is not a constraint. Steps are screened at 16 games where a fidelity measure is expected to move severalfold (`AGENTS.md`).

| Stage | Time Box | Headless Games Budget | Live / Smoke Games | Purpose & Hard Stop / Gate |
|---|---|---|---|---|
| **Phase 0: Anchor, Docs & Plumbing** | **3–5 days** | **96 paired** (`gt0.48dev` vs. `gt1`, matched `--gg`) | **3 watched** (T/Z/P) + **1 SC:R LAN** (`tools/parity.py`) | Update `TODO.md` (`## Direction`) to adopt this plan (pausing unstarted `c` items like *home at 15-20* and *PvT tanks* under the maintenance cap), fix stale `rl1` top summary in `docs/PROGRESS.md`, and note the §6.8 pro-frequency departure in `docs/ARCHITECTURE.md`. Replace stale 2026-11-11 `-0.188` baseline; validate live bridge; count `answers.py` firings in 1 league round; fix `#64` RNG seeds (`army.py:159`, `calm.py:41`). **Done 2026-11-23 (one day; results below).** |
| **Phase 1: Strategic Trunk & Q&As** *(All-matchup code & 0-game counts; TvZ-first heavy game gates; other G1 fidelity capped to watched-game regressions)* | **None (ordered steps below)** | **About 180–240** unconditional (the table "Phase 1 Order" below) | **All 6 matchups** in `tests/test_matchups.py` (real providers) + **5+ live/blind-eval games** | Scouting first; then ship race-keyed joint `P(enemy_z \| seen)`, `StrategyState` + `--from-replay` + `strategy_compile`, pro-frequency tables (`min_n`), one-at-a-time macro rule isolation, 5 templates, and 3-part verification. **Completed 2026-11-25** (results below). |
| **Army: the retreat hold, then an owned intent on evidence** | **Any time** | **16** (the retreat hold on `eval/pipe_table.py`); an owned intent only after its 0-game read: **48 screening** + up to **192** paired | Included in Phase 1 live games | Settle the retreat pipe; decide from existing rounds whether an owned intent would change anything (§3.4). |
| **Phase 2: Top-Down Tactical Intents + Early G4 Check** *(open, not started)* | **After Phase 1's gate** | Budgeted from Phase 1's and the army reads' outcomes | 2-profile sanity check | Build a small top-down tactical intent layer (3–5 event-grounded modes with intent-conditioned leaves and `ArmyNet`'s `16×16` heatmap—not a bolt-on interceptor like `gather`) if the retreat hold still leaves live army play incoherent or Q&A #4 weak (the 0-game cluster-stealing read is not a veto). Run 1 early G4 test: same recipe card under pro vs. lower `HumanProfile` *h*. |
| **Phase 3: Dynamic Symbolic Features / OOD Taxonomy** *(open, not started)* | **Deferred until Phase 1 passes** | **0 games** for ceiling audit; discovery budgeted if triggered | — | Explicitly kept on the roadmap after Phase 1. First step: **offline** 0-game held-out replay ceiling audit (`ARCHITECTURE.md` §7.6: symbolic trunk vs. unconstrained `ValueNet`/policy). If a systematic residual persists, open the residual concept discovery + phase-level OOD taxonomy loop (§5.2 #2). |

#### Phase 0 Results (2026-11-23; details in `docs/PROGRESS.md`)
The run as it was (where it departed from the row above):
- **`#64` seeds fixed first, between rounds:** the army's and the calm layer's draws from the game's seed and the side's slot, in every build (`gt0.21`, `gz0.15`, `gp0.16`, `gt0.49dev`, `gz0.32dev`, `gp0.39dev`); checked on fresh builds (same seed same first draws, another seed others), every parity game's hashes recorded again.
- **The remeasure ran on `gt0.49dev`** (`gt0.48dev` plus the seed fix) and on `gt1` `gt0.21`, as **two 96-game rounds against the same fixed opponent `gz1`**, paired game by game (12 seeds a map on the 8 ladder maps; 192 games, not 96), **both with `--gg 0`**: only the dev builds' critics can resign, so "matched `--gg`" meant gg off on both. MDE 0.11 written first. Result: **`-0.219 [-0.294, -0.141]`** by supply (this pairing's own MDE 0.119), nearer the pros than `gt1` in every window on `eval/gap_windows.py`'s marginal summary features (0.19–0.41 vs. 0.27–0.62 — a relative proxy, not pro-like live play; §2.1 item 3, line 80, resolved); not promoted.
- **`answers.py` counted** on two full rounds: 158 forced goals in 16 games against `gz1dev` (3.7% of macro decisions), 1,199 in 96 against `gz1` (3.0%; 989 mineral-line turrets against mutalisks), 653 of the model's decisions vetoed, 20 tech scans.
- **3 watched live games** (against the computer Zerg): every order through the bridge; the Terran saw no enemy fighter from 1:51 to 9:43 and lost its mech army and 20 SCVs to Hydralisk–Lurker; the Zerg sat on 11–16 drones and lost; the Protoss healthiest. The client's window doesn't follow Gary's camera (watch the POV log).
- **LAN `tools/parity.py`:** 0 mismatches in 120,471 unit comparisons, every field; the bridge's new fields (`stim`, `ammo`, `ammo_max`) agree but were only ever zero (no fight, no Reaver or Carrier): their non-zero values remain unverified.
- **Found and fixed after the remeasure:** `gt1dev` couldn't start a game outside TvZ (option `calm` had only a TvZ model): **`gt0.50dev`**, the calm layer stands aside there.
- **Phase 1 baseline:** **`gt0.50dev`** (TvZ play identical to `gt0.49dev`, the remeasured build); rounds `RD285a` / `RP285a` are the reference rounds.
- **Phase 1 begun, then stopped (2026-11-23) for the round-two review:** the enemy-plan belief offline (`train/plan_belief.py`) beats the time-and-map floor on the pros' held-out games at 4, 6 and 8 min (joint Brier `-0.096`, `-0.122`, `-0.131`), but on Gary's own games it is worse than the floor from 6:00, as Gary had seen the Zerg's tech by 6:00 in 5% of its games (pros 60%) and `gz1` plays one plan in 76% of them. The sighting states (`gary/policy/sightings.py`, `ingest/sighting_dataset.py`) are committed, checked on 12 games, not built in full and not wired into play.
- **Corrected in round two:** the 20 tech scans are all on the two maps with one enemy start, as the scan cannot fire elsewhere (§3.1); `HS284a` had two scans, not none; the 989 are turret goals asked, not turrets built; the "one plan in 76%" is 85 of 112 games of `RD285a` and `HS284a` together (`gz1` and `gz1dev`), labelled by another rule than the pros' (§3.1).

#### Phase 1 Order (Round Two)
Each step is judged on its own check before the next; new games are physical games.

| Step | What | New games |
|---|---|---|
| 1 | Plain fixes on their own checks (`AGENTS.md`, race-agnostic & mirror-safe): the scan's main known without `watch`, in one shared place (parity recorded again: it is in `gt1` too); Gary's games labelled by the pros' rule; the trainer's and the dataset's faults (§3.1, including mirror player lookup); enemy buildings recorded by tag and type, so a morph is a sighting | 0 |
| 2 | The counts (§3.1, **across all matchups with resim + taxonomy data**): pros' first sight by type and by means (Scans/SCVs, Probes/Observers, Overlords/Lings), scans with targets, first scout stay; Gary's seen given standing; `answers.py`'s goals against turrets built; Arm 0 (§3.3) | 0 |
| 3 | The sighting states rebuilt race-agnostically to what Step 2's cross-matchup counts say a look must record; a scan as a look verified in a scenario; `tests/test_matchups.py` green across all 6 matchups with real providers | 0 |
| 4 | The suite's first read: `gt1dev` with step 1 against `gz1dev` told the suite's styles, gg on. The scouting measure after the fix, each Zerg game's plan as played | 16 |
| 5 | Scouting (§6 row 8): the learned scan model; `watch` again only if step 2 shows the pros' SCV stays and is what sees the tech. Each screened on the scouting measure | 16 per option |
| 6 | The belief re-scored on the games of steps 4 and 5 (no new ones); then belief and card log-only, first over `RD285a`'s records, then a soak | 16–32 |
| 7 | `answers` off once Gary sees; then the lurker answer handed to the trunk end to end | 16–48 |
| 8 | Only if Arm 0 leaves a gap: strict drills and the macro A/B | 40 + 96–192 |
| 9 | Templates, the execution join, the blind evaluation | live and held-out games |
| 10 | Gate 4's round on the whole Phase 1 build | 96 |

**The scouting measure**, the same function for Gary and the pros of the same style on the same maps: Spire-or-Den seen by 5, 6, 7 and 8 minutes given that it stood, Lair apart; Zerg in sight at 3:00–6:00 (the pros 104 s, Gary 44 s); scans a minute and their targets; the time of the first plan read and whether it came from a building or from the units arriving; workers at 8:00 as the cost.

#### The Zerg Plans to Judge Against (Preventing `gz1dev` Overfitting)
To ensure Phase 1's opponent belief and reactive directives do not overfit to `gz1dev`'s quirks (~3× pro Lurkers, ~2× Scourge, 56% style adherence) or to the one plan `gz1` and `gz1dev` play in most games, they are judged against **`gz1dev` told a style (`--style-b`), each game labelled as played by the pros' rule**. The scripted Zergs an earlier draft budgeted were deleted in the refactor and are not rebuilt: a second Zerg to keep in parity, and scripted Zergs taught the selector its cheese (§2.2). About half the games land on the told plan, so rounds are sized for that; lurker-first is the rarest to obtain. The styles, from the catalogue's eleven:
1. Pool first, 2 hatcheries, zergling pressure (style 9). A true 9-pool is not in the catalogue; script only that, and only if the early-pool case is wanted.
2. Hatchery first, 2 hatcheries, spire first (style 1)
3. Hatchery first, 3 hatcheries, spire first (style 0, the pros' commonest)
4. Hatchery first, 3 hatcheries, lurker first (style 4), and a game where lurkers follow mutalisks

#### Pre-Written Phase 1 Acceptance Gate (Evaluated When the Steps Above Are Done)
All four conditions must be logged and reported before Phase 1 is called passed or Phase 2 opened:
1. **Scouting, then Opponent Belief Calibration:** A scouting precondition: Spire-or-Den seen by 7:00 given that it stood, within a distance of the pros' written after step 2's counts. Then the winning belief provider beats the time-and-map base-rate prior on held-out modern TvZ Brier score at 4:00, 6:00, and 8:00 (it does since 2026-11-23); on Gary's own games against the suite, labelled by the pros' rule, it is not worse than the floor where Gary has not looked and better where it has, with its calibration error reported and every comparator fitted on other games than it scores.
2. **Steering (G3):** The macro path that holds the card (today's conditioning if Arm 0 shows it does, else Arm A, Arm B or the strict-mode queue) completes **≥18/20** unharassed strict drills within a timing tolerance written before the drills, matches or improves `eval/style_adherence.py` per style over `gt0.50dev`, and runs both `--from-replay <path>` and text-prompt `strategy_compile` end-to-end.
3. **Explainability Faithfulness & Coaching Utility (G5):**
   - Execution-join integrity **≥95%** (trunk decisions trace cleanly to downstream leases/orders without silent pipe drops);
   - The 1 ms minimal abductive flip is a unit test of the trunk, not a threshold: on a deterministic trunk, reverting the triggering evidence reverts the switch by construction;
   - **Blind evaluation** over ≥25 held-out moments from ≥5 games (comparing Phase 1 templates vs. today's `gt1dev` records) shows higher blind next-branch prediction accuracy and passes the learner usefulness rubric.
4. **Strength & Fidelity Guardrail (`AGENTS.md` promotion rule):** Fidelity per window (`eval/gap_windows.py`) not measurably worse than **`gt0.50dev`** (the Phase 0 baseline), and one paired round of **96 games against `gz1` with gg off on seeds 4004–4015**, where `RD285a` is the baseline already played (the user's decision, `docs/REFOCUSReviews.md` 2.8: the games are the scarce thing, and the suite's rounds show the build against `gz1dev`). It passes by `AGENTS.md`'s rule as written: the pairing's 90% interval holds zero, **or** its loss is under the margin written first, **0.118** (the spread measured in Phase 0's pairing against `gz1`, a per-pair standard deviation of 0.466, at 96 games; an earlier wording joined the two with "and", under which the margin never binds). 48 games are not used for this guardrail: at that size the rule passes a true loss of 0.10 about half the time. `RD285a` stays the baseline only while `gz1`'s code and dice are unchanged; a change that moves every build's streams, or a resign critic retrained for `gz1` so that gg can be on, means the baseline is played again (96 more). Same `--gg` setting on both sides.

#### Phase 1 Results (completed 2026-11-25 on the user's sign-off; details in `docs/PROGRESS.md`)
Phase 1 is done. **Phases 2 and 3 are still open**, so this document stays the plan for them; it is not superseded.

**What shipped.** Everything below is folded into `docs/ARCHITECTURE.md` §6.11:
- `contracts.py` (not frozen yet: the Schema Freeze Rule above still holds);
- `SightingState` and `EnemyMain`;
- the plan belief;
- the scan sampler;
- `StrategyState` and the trunk, with the pro-frequency scorer and the `PREP_VS_LURKER` directive;
- the recipe card and its tags;
- `StrategySpec`, `strategy_compile` and `--from-replay`;
- the trace's join ids;
- the five templates (`eval/coach.py`).

They are options on `gt1dev` (`gt0.53dev`: `scansample`, `shadow`, `noanswers`, `trunk`, and `strict` for drills). They are not in `gt1`.

**Where the run departed from the plan above:**
- **Scouting:** step 5's learned scan model was not built. A sampler of the pros' scan timings and targets (`scansample`, a STOP-GAP in `AGENTS.md`) stands in, as §6 row 8 allows when the pros' timing barely depends on what they have seen.
- **The belief:** the pinned belief is the one without sighting features (step 6: the two differed by less than the games resolve). The sighting states are kept for the looked/unlooked split.
- **The macro A/B:** Arm B is strict mode only, used for drills. Normal play is step 7b's trunk (the user's decision on step 8's results).
- **`answers.py`:** off in the judged build (`noanswers`), and its lurker answer is now the trunk's directive. The rest of it has no successor, and it stays in `gt1`.
- **The `gasahead` fix:** gate 2 first missed at 17 of 20, so `gt0.53dev` added option `gasahead` (the builder sent ahead of its gas), in `gt1dev` only.

**The gate, as each condition's entry left it:**
1. **Scouting and belief.**
   - With the sampler, the Spire or Den was seen by 7:00, given that it stood, in 75% of games. The pros' figure is 67%.
   - On the pros' held-out games the belief beats the floor at 4, 6 and 8 minutes.
   - On Gary's games, where Gary looked, its tech part is near certain and right. Where Gary did not look, it is no better than the floor.
   - The joint plan stays worse than the pros' floor because of their prior over openings.
2. **Steering.**
   - 18 of 20 strict drills (`DR300a*`).
   - `--from-replay` and `strategy_compile` both ran end to end.
3. **Explainability.**
   - The execution join started 89 of 89 trunk items.
   - The minimal flip takes 0.04 ms a query.
   - The blind pack (`BE297`) was not graded. The user's review of the answers stands in its place:
     - Q1 and Q2 were faithful but written in debug jargon, now reworded in plain Brood War English.
     - Q3 (buildings drawn at 2%, 5% and 6%) and Q4 (the army model's "keep" at 86%) confirm that mid-game directives and a top-down tactical intent layer are still needed.
4. **Guardrail.**
   - `G4299a` against `RD285a`, 96 paired games against `gz1` with gg off: +0.013 [-0.044, +0.070] by supply. Every window's gap interval holds zero.
   - Style 2's Academy by 8:00 was 22% against `RD285a`'s 56% (the pros 48%) under `noanswers`.

**Open after Phase 1:**
- **`gasahead` in every build:** it is in `gt1dev` only.
- **Phase 2 (open, not started):** the inputs from gate 3 are mid-game directives and the top-down tactical intent layer (the Phase 2 row above).
- **Phase 3 (open, not started):** first the offline ceiling audit.

#### Documentation Update Schedule (Matching Findings to Repo Docs)
Docs are updated when real measurements or code land—not speculatively ahead of Step 2's counts:
- **`TODO.md`:** Update `## Direction` **before Step 1 starts** to reflect the 10-step Round 2 Phase 1 order and narrowed army plan; update item status as each step finishes.
- **`AGENTS.md`:** Add a `STOP-GAP` entry for `tech_scan` at **Step 1** (when bug-fixed and tagged), add one for a scan-timing sampler at **Step 5** only if built, and update/retire `answers.py`'s entry at **Step 7** only if its successor holds its measure.
- **`docs/PROGRESS.md`:** Update at **every step** (Step 2's 0-game counts, Step 4–5 scouting screens, the 16-game retreat hold, Arm 0, blind Q&A evaluation, and Step 10 Gate 4).
- **`docs/ARCHITECTURE.md`:** Do **not** rewrite before Gate 4 (the §6.8 pro-frequency departure note landed in Phase 0). **After Step 10 (Gate 4) passes**, fold the proven, shipped contracts (`contracts.py`, `SightingState`, `PlanBelief`, scouting provider, `StrategyState`, trace join IDs, templates) into `docs/ARCHITECTURE.md` and mark Phase 1 of `docs/REFOCUS.md` completed (done 2026-11-25, §6.11 there; the document itself stays open for Phases 2 and 3).
- **`docs/CONTROL.md`, `docs/RACES.md`, `docs/SELF_PLAY.md`:** Update only when their domain changes (`RACES.md` on version bumps; `CONTROL.md` when scouting, retreat hold, or an owned intent lands; `SELF_PLAY.md` only if RL is unparked).

---

## 5. Open Empirical Questions, Disagreements Settled by Tests & Future Directions

### 5.1 Disagreements Settled by Measurement (Not Debate)

| Question | What Decides It | When |
|---|---|---|
| Does `gt0.48dev` still trail `gt1` by `-0.188` after `ModeModel`, `Calm`, and cluster-order fixes? | **Resolved 2026-11-23:** yes, `-0.219 [-0.294, -0.141]` on `gt0.49dev`, nearer the pros in every window (§2.1) | Phase 0, done |
| How often does `answers.py` actually fire in `gt1dev` today? | **Resolved 2026-11-23:** 3.0–3.7% of macro decisions, most of them mineral-line turret goals (§4.3) | Phase 0, done |
| Does conditioning `MacroNet` on the recipe card (AlphaStar *z*) hold a requested build as reliably as preemptive resource reservation + tech masking? | Phase 1 2-arm test: 20 unharassed drills/arm + `eval/style_adherence.py` + 48–96 paired games | Phase 1 |
| Would an owned army intent change anything, now that a hold on commitments is measured as not missing? | From existing rounds: share of late arrivals caused by another cluster taking a committed unit (0 games; checks one symptom, not a veto on Phase 2 top-down intents with conditioned leaves); plus live-game army coherence and Q&A #4 (§3.4) | Before any army round / Phase 2 |
| Does Gary mistime attacks against Stim/+1 compared to pros? (`commit` sees no research state: settled in round two) | Offline audit on existing league records (0 games) | Phase 1 |
| A sampler of the pros' scan timings, or a learned scan model? | Step 2's count: does the pros' chance of a scan at a minute depend on what they have seen and on the Comsat's age | Phase 1, step 2 |
| Is `watch` worth bringing back? | Step 2's count: which unit first has the Spire or Den in sight in the pros' games, and how long their SCV stays | Phase 1, step 2 |
| How much of Gary's 5% is not looking? | The re-simulated games: per minute, the tech stood and was not seen | Phase 1, step 2 |
| Trees or a Bayesian likelihood for the belief? | Both scored on Gary's games against the suite, split by looked and unlooked | Phase 1, step 6 |
| Does the belief change a macro decision? | Offline: does it improve the likelihood of the pros' next macro choice beyond the macro model's own inputs; in play: `answers` off once Gary sees | Phase 1, steps 2 and 7 |
| Does a card add over style conditioning? | Arm 0: milestone error on `RD285a`'s 96 games | Phase 1, step 2 |
| Is a Comsat scan a look in the observation? | A scan in a scenario, then the sighting state's `look()` | Phase 1, step 3 |
| What is the prediction/value cost of a strictly symbolic trunk vs. an unconstrained model? | Offline held-out TvZ replay bake-off (`ARCHITECTURE.md` §7.6: trunk vs. unconstrained `ValueNet`/policy, 0 games) | Phase 3 Trigger |
| Is there learnable outcome SNR in intermediate tactical option choices (beyond 77-moment whole-army attack vs. hold)? | Effect-size check (`docs/SELF_PLAY.md` method) before ever training an outcome option scorer | Post-Phase 2 (only if RL unparks) |

### 5.2 SOTA Context & Future Directions (Post-Phase 1)

Every general neuro-symbolic paper cited in earlier drafts (`DreamCoder`, `LILO`, `SCoBots`, `NUDGE`, `Silver et al.`, `VisualPredicator`) was demonstrated on deterministic puzzles, Atari, or tabletop robotics—not 30-minute partially observable adversarial RTS. The closest direct precedents for Gary's components come from the **RTS / Brood War and XAI literature**:
- **Opponent modeling:** Bayesian build-tree plan recognition (Synnaeve & Bessière, 2011) and neural Brood War defogging (Synnaeve et al., 2018).
- **Build-order planning & steering:** Deterministic/search build scheduling for strict drills (Churchill & Buro, 2011; Justesen & Risi, 2017) and AlphaStar's replay-statistic *z*-conditioning (Vinyals et al., 2019).
- **Skill bands (G4):** Training/calibrating on human skill bands rather than only injecting noise into a pro model (Maia: McIlroy-Young et al., 2020), once rated lower-band replays are checked in the inventory.
- **Causal & navigable explanations (G5):** Causal contrastive explanations validated by human task-prediction in StarCraft II (Madumal et al., 2020), POV-linked foraging support (Penney et al., 2018), and human concept-transfer evaluation (Schut et al., 2023).
- **Offline policy improvement & action smoothness (if needed later):** Offline RL over human replays (AlphaStar Unplugged: Mathieu et al., 2023) and Action Chunking (`ACT`: Zhao et al., 2023) for short-horizon micro coherence.

**Future directions parked beyond Phase 1 (trigger-gated):**
1. **Attention-budgeted intents (`ARCHITECTURE.md` §6.7 + G4):** Attach `attention_hint` to active intents and log effective attention received from `Attention Arbiter` so explanations separate *"bad plan"* from *"plan starved of APM by a drop."*
2. **Offline residual concept discovery (`ARCHITECTURE.md` §7.6 + §7.7 guide mining):** Triggered only if the offline held-out replay ceiling audit finds large systematic residuals after Phase 1; pair candidate concepts with `eval/pairs.py` repeated branches (MDE-sized) before promotion.
3. **Interactive post-game trace refinement:** Capture structured user corrections on bad beliefs/branches during human sparring reviews as supervised fine-tuning records.
4. **LLM Narrator over verified templates:** Added only after Phase 1–2 templates pass blind usefulness and faithfulness checks, strictly citing record IDs.

---

## 6. Standing Repo Decisions & Explicit Departures

| Decision | Standing Repo Rule | v2.0 Policy |
|---|---|---|
| **1. Build line & macro ownership** | `gt1` vs. `gt1dev` (`AGENTS.md`); `gt1dev` inherits `answers`, `rax_by`, `under-half` | **No `gt_ns` fork and no delete list.** Build `ARCHITECTURE.md`'s upper layers on existing `gt1dev` seams. Count `answers.py` first, soak log-only, then remove conflicting macro rules **one at a time** on their `AGENTS.md` measures until the active trunk has one resource owner. |
| **2. Matchup scope** | Every matchup at once (`TODO.md`, 2026-11-12) | **Split code/0-game work from heavy game gates:** all Phase 1 code, schemas (`contracts.py`, `SightingState`), trainers, 0-game pro counts, and `tests/test_matchups.py` (exercising real providers, not stubs) cover **all 3 races and all 6 matchups including mirrors from day 1** (preventing TvZ-only tech debt like `stim.py`, `calm` crashing TvT/PvT in `a16de8f`, and `sighting_dataset.py:44` breaking mirrors). Only the **expensive headless game gates and blind human evaluation** (Steps 4–10: multi-style suite, blind Q&A study, Gate 4's 96-game round) run in **TvZ Terran first** to keep game costs bounded, with low-rate judge monitors kept on all other matchups. |
| **3. Tactical layer** | Positioning & finishing (`TODO.md` `(c)`) | **Narrowed in Phase 1, preserved for Phase 2:** the hold on commitments is not run (already measured); the retreat hold is a pipe fix judged in 16 games; the 0-game cluster-stealing read checks one narrow interference mechanism and is **not** a veto on building a true top-down tactical intent layer (3–5 modes with intent-conditioned leaves and `ArmyNet`'s `16×16` heatmap—not a bolt-on interceptor like `gather`) in Phase 2 if live army play remains incoherent or Q&A #4 stays weak; any upgrade-timing gap is measured separately before gating on it. |
| **4. Reinforcement learning** | RL parked (`TODO.md:178`); offline counterfactuals only (`AGENTS.md`) | **Remove online bounded leaf RL.** Keep RL parked; any future return uses offline methods (AWR/IQL/AlphaStar Unplugged) after effect-size SNR is measured. |
| **5. Phase 3 discovery loop** | Unstarted (`ARCHITECTURE.md` §7.6) | **Defer** until Phase 1 passes its gate; first step when triggered is an offline 0-game ceiling audit. |
| **6. Priority order & stopping rule** | `TODO.md` Direction `(a)–(f)` (G1 fidelity work) | **Phase 1 in front** as the foreground track with a pre-written gate and no time box, scouting its first build (round two); cap other G1 fidelity work to regressions caught in watched games; the army's retreat hold beside it at any time. |
| **7. V1 trunk scorer *(explicit departure from `ARCHITECTURE.md:194`)*** | `ARCHITECTURE.md` §5/§6.8 specifies win-rate statistics | **Depart to pro conditional choice frequencies** $P_{\text{pro}}(\text{branch} \mid \text{belief}, \text{context})$ with support floor `min_n` for V1; print observational win rate as non-deciding context only; allow outcome overrides only from randomized `eval/pairs.py` branches on Gary's own games. |
| **8. How Gary gets scouting (round two)** | `AGENTS.md` "Stop-gaps": a decoder turns a model's odds into a choice; a scripted rule is tagged | **The learned scan model is the target** (the pros' scans as events, on the spell-cast dataset and rule the repo has; the replacement `AGENTS.md`'s Detect entry already names). Meanwhile `tech_scan`, bug-fixed, stays and gets its `STOP-GAP` tag and entry. A sampler of the pros' timings is built only if the counts say the timing hardly depends on what was seen, and then it carries the tag. |
| **9. The guardrail round (round two)** | `AGENTS.md` promotion rule: 96 paired games against the same fixed opponent | Against `gz1` with gg off on `RD285a`'s seeds, 96 new games, margin 0.118 (§4.3 gate 4, with the condition under which the baseline is played again). |
| **10. Promotion (round two)** | `AGENTS.md`: the dev build replaces the playing build when nearer the pros and not measurably worse | **Not a target of any phase of this plan.** `gt1dev` trails `gt1` by `-0.219` through the stop-gaps `gt1` keeps and the games it does not end; nothing here builds their successors, and RL is parked. `gt1` stays the playing build; live games and the blind evaluation use the dev build by flag. |

---

## 7. References & Verification Status

Each entry states honestly how it was checked (`search-verified` = verified title, authors, venue, year, and core claims against web search / abstract records; `analogy` = structural analogy rather than direct methodological guarantee).

### Brood War, RTS & Imitation / Offline RL
1. **Churchill, D., & Buro, M. (2011).** *Build Order Optimization in StarCraft.* AIIDE 2011. (`search-verified`) — Branch-and-bound build-order scheduling; precedent for strict-mode drill execution (`ARCHITECTURE.md:456`).
2. **Justesen, N., & Risi, S. (2017).** *Continual Online Evolutionary Planning for In-Game Build Order Adaptation in StarCraft.* GECCO 2017. (`search-verified`) — Online build-order adaptation in StarCraft: Brood War.
3. **Synnaeve, G., & Bessière, P. (2011).** *A Bayesian Model for Plan Recognition in RTS Games applied to StarCraft.* AIIDE 2011 (`arXiv:1111.3735`). (`search-verified`) — Direct Brood War precedent for Bayesian opponent build-tree inference from noisy partial sightings (Phase 1 baseline provider).
4. **Synnaeve, G., Lin, Z., Gehring, J., Gant, D., Mella, V., Khalidov, V., Carion, N., & Usunier, N. (2018).** *Forward Modeling for Partial Observation Strategy Games — A StarCraft Defogger.* NeurIPS 2018 (`arXiv:1812.00054`). (`search-verified`) — Neural hidden/future state estimation from partial Brood War observations.
5. **Vinyals, O., Babuschkin, I., Czarnecki, W. M., Mathieu, M., Dudzik, A., Chung, J., Choi, D. H., Powell, R., Ewalds, T., Georgiev, P., et al. (2019).** *Grandmaster level in StarCraft II using multi-agent reinforcement learning.* Nature 575, 350–354. (`search-verified`) — Replay-statistic *z*-conditioning (Phase 1 Macro Arm A baseline) and pure-neural scale contrast.
6. **Mathieu, M., Ozair, S., Srinivasan, S., Gulcehre, C., Zhang, S., et al. (2023).** *AlphaStar Unplugged: Large-Scale Offline Reinforcement Learning.* `arXiv:2308.03526`. (`search-verified`) — Offline RL benchmark over human StarCraft II replays; reference point if Gary later unparks offline RL.
7. **McIlroy-Young, R., Sen, S., Kleinberg, J., & Anderson, A. (2020).** *Aligning Superhuman AI with Human Behavior: Chess as a Model System* (`Maia`). KDD 2020 (`arXiv:2006.01855`). (`search-verified`) — Demonstrates predicting human decisions per skill band rather than adding noise to a pro policy (future G4 design).
8. **Ross, S., & Bagnell, D. (2010)** / **Ross, S., Gordon, G. J., & Bagnell, J. A. (2011).** *Efficient Reductions for Imitation Learning* (AISTATS 2010) and *A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning* (`DAgger`, AISTATS 2011, `arXiv:1011.0686`). (`search-verified`) — Establishes compounding covariate shift in behavioral cloning (note: DAgger's own remedy requires an interactive expert oracle unavailable for pro replays).
9. **Zhao, T. Z., Kumar, V., Levine, S., & Finn, C. (2023).** *Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware* (`ACT`). RSS 2023 (`arXiv:2304.13705`). (`search-verified`) — Action chunking over short sequences to reduce per-step imitation compounding error (candidate Tier 3 leaf direction if held intents still dither).

### Explainability, Glass-Box Models & Concept Bottlenecks
10. **Madumal, P., Miller, T., Sonenberg, L., & Vetere, F. (2020).** *Explainable Reinforcement Learning through a Causal Lens.* AAAI 2020. (`search-verified`) — Causal contrastive ("why X instead of Y?") explanations validated in a 120-participant StarCraft II study on task prediction, satisfaction, and trust.
11. **Penney, S., Dodge, J., Hilderbrand, C., Anderson, A., Simpson, L., & Burnett, M. (2018).** *Toward Foraging for Understanding of StarCraft Agents: An Empirical Study.* CHI 2018 (`arXiv:1711.08019`). (`search-verified`) — Shows experienced StarCraft players face high information-foraging costs inspecting agents, motivating timestamp/POV-linked explanations.
12. **Schut, L., Tomasev, N., McGrath, T., Hassabis, D., Paquet, U., & Kim, B. (2023).** *Bridging the Human-AI Knowledge Gap: Concept Discovery and Transfer in AlphaZero.* `arXiv:2310.16410`. (`search-verified`) — Evaluates explanations by whether human players actually improve from them.
13. **Rudin, C. (2019).** *Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead.* Nature Machine Intelligence 1, 206–215. (`search-verified`) — Motivates inherently inspectable strategic branch decisions over post-hoc input perturbation alone.
14. **Lou, Y., Caruana, R., Gehrke, J., & Hooker, G. (2013)** & **Nori, H., Jenkins, S., Koch, P., & Caruana, R. (2019).** *Accurate Intelligible Models with Pairwise Interactions* (KDD 2013) and *InterpretML: A Unified Framework for Machine Learning Interpretability* (`arXiv:1909.09223`). (`search-verified`) — Introduces $\text{GA}^2\text{M}$ and EBM (swappable glass-box branch scorer for additive/pairwise features; note ≥3-way conjunctions require trees).
15. **Koh, P. W., Nguyen, T., Tang, Y. S., Mussmann, S., Pierson, E., Kim, B., & Liang, P. (2020).** *Concept Bottleneck Models.* ICML 2020 (`arXiv:2007.04612`). (`search-verified`) — Concept-level transparency and test-time intervention (static classification; adapted with care to temporal partial-observability beliefs).
16. **Mahinpei, A., Clark, J., Lage, I., Doshi-Velez, F., & Pan, W. (2021)** & **Havasi, M., Parbhoo, S., & Doshi-Velez, F. (2022).** *Promises and Pitfalls of Black-Box Concept Learning Models* (`arXiv:2106.13314`) and *Addressing Leakage in Concept Bottleneck Models* (NeurIPS 2022). (`search-verified`) — Demonstrates soft-probability leakage when passing continuous concept probabilities into learned downstream classifiers, motivating discrete/joint plan beliefs and dropping `concept_mlp`.
17. **Marconato, E., Teso, S., Vergari, A., & Passerini, A. (2023).** *Not All Neuro-Symbolic Concepts Are Created Equal: Analysis and Mitigation of Reasoning Shortcuts.* NeurIPS 2023 (`arXiv:2305.19951`). (`search-verified`) — Motivates direct hindsight supervision of belief/concept extractors from re-simulated ground truth.

### Options, Shielding Terminology & Neuro-Symbolic Analogies
18. **Sutton, R. S., Precup, D., & Singh, S. (1999).** *Between MDPs and semi-MDPs: A framework for temporal abstraction in reinforcement learning.* Artificial Intelligence 112, 181–211. (`search-verified`) — Foundational options framework $(I_\omega, \pi_\omega, \beta_\omega)$.
19. **Bacon, P.-L., Harb, J., & Precup, D. (2017)** & **Harb, J., Bacon, P.-L., Klissarov, M., & Precup, D. (2018).** *The Option-Critic Architecture* (AAAI 2017, `arXiv:1609.05140`) and *When Waiting is not an Option: Learning Options with a Deliberation Cost* (AAAI 2018, `arXiv:1709.04571`). (`search-verified`) — Option termination and explicit deliberation costs to prevent rapid switching (Arm 2/Arm 3 persistence design).
20. **Alshiekh, M., Bloem, R., Ehlers, R., Könighofer, B., Niekum, S., & Topcu, U. (2018).** *Safe Reinforcement Learning via Shielding.* AAAI 2018 (`arXiv:1708.08611`). (`search-verified`) — Provides the preemptive-vs-post-posed shielding terminology used for macro action masking (note: Alshiekh et al. prove RL convergence is preserved under both placements when actions are properly credited; Gary's past RL failures came from silent non-execution / unasked decisions and variance, documented in `docs/SELF_PLAY.md`).
21. **Swaminathan, A., & Joachims, T. (2015).** *Batch Learning from Logged Bandit Feedback through Counterfactual Risk Minimization.* ICML / JMLR 2015 (`arXiv:1502.02362`). (`search-verified`) — Cited specifically to note why logged-bandit propensity methods do **not** apply to observational pro replays (no logged propensities, unobserved confounding) and belong only where logging propensities are recorded (`records/v1` / paired branches).
22. **Kautz, H. (2022)** (*The Third AI Summer*, AI Magazine), **Silver, T., et al. (2022)** (*Learning Neuro-Symbolic Skills for Bilevel Planning*, CoRL 2022, `arXiv:2206.10680`), **Castellano Ontiveros, R., Giannini, F., Gori, M., Marra, G., & Diligenti, M. (2025)** (*Grounding Methods for Neural-Symbolic AI*, IJCAI 2025, `arXiv:2507.08216`), **Ellis, K., et al. (2021)** (*DreamCoder*, PLDI 2021, `arXiv:2006.08381`), **Grand, G., et al. (2024)** (*LILO*, ICLR 2024, `arXiv:2310.19791`), and **Liang, Y., et al. (2025)** (*VisualPredicator*, `arXiv:2410.23156`). (`search-verified`, **analogy only**) — High-level framing analogies for neuro-symbolic composition, relational aggregation, and future offline library growth; none operate at StarCraft: Brood War scale.
