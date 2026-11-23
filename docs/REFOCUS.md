# Gary — Neuro-Symbolic Refocus & Implementation Plan (RFC)

Status: **Draft v1.1 for Multi-Agent Adversarial Review** (2026-11-22)  
Scope: Standalone architectural refocus plan synthesizing codebase audits, empirical findings from `docs/PROGRESS.md`, `docs/CONTROL.md`, `docs/SELF_PLAY.md`, `TODO.md`, and `AGENTS.md`, record inspection, and verified neuro-symbolic AI/RL literature.  
Audience: Project owner and reviewing AI agents debating pros, cons, risks, and implementation scope before code changes begin.

---

## Executive Summary

Gary has built an unusually strong foundation for a StarCraft: Brood War AI: a genuine single-pair-of-human-hands interface (`gary/interface.py`), a 1:1 offline StarCraft: Remastered bridge (`adapters/scr_bridge/`), a 92k-replay pipeline with modern SC:R re-simulation (`resim/`, `ingest/`), deterministic branching games (`eval/pairs.py`), unified decision records (`gary/decision_log.py`, `eval/why.py`), and a race-agnostic agent core (`gary/race.py`, `gary/agent/executor.py`).

**However, the current development trajectory is unlikely to reach Gary's core product goals.** Over October–November 2026, Gary quietly inverted its intended neuro-symbolic architecture:
1. In the playing builds (`gt1`, `gz1`), hand-coded symbolic **stop-gaps sat at the leaves and side-channels** (`RoleAhead`, `PullRule`, `LoadRule`, `hunt4`, `caps`, `bank_escape`, `answers.py`), overriding neural outputs and sequestering units—which broke credit assignment and made reinforcement learning (RL) impossible.
2. In the dev builds (`gt1dev`, `gz1dev`, `gp1dev`), removing those leaf stop-gaps left **no symbolic strategic or tactical trunk**. Instead, Gary became a stack of ~10 independent, stateless behavior-cloning (BC) models (`MacroNet`, `ArmyNet/commit`, `CalmNet`, `CalmFarNet`, `RoleNet`, `ModeModel`, `EventModel`, `StimModel`, `CastModel`, `PlacementModel`) glued together by ~30 manifest flags and stochastic decoders.
3. Because the active dev agent holds only a static style integer rolled at 0:00 and samples per-tick marginal odds, it suffers from compounding drift, cannot learn from full-game RL at workstation compute, and **cannot answer "why did you make that strategic choice?" in a way useful to someone learning StarCraft**.

**This plan proposes a targeted refocus—not a rewrite:**
- **Keep** the hard-won infrastructure (human hands, SC:R bridge, replay/resim pipeline, deterministic branching, race-agnostic executor, and useful low-level neural perception/micro models).
- **Flip the neuro-symbolic stack right-side up** into a modular **Neuro-Symbolic Sandwich**:
  `NN Perception (Concept Bottleneck)` → `Factored Symbolic Strategic & Tactical Trunk (with Learned Concept-Conditioned Scoring)` → `Goal-Conditioned NN Leaf Executors (Exclusive Unit Ownership, Zero Leaf Stop-Gaps)` → `Human Interface & Attention Arbiter`.
- **Add an offline Neural → Symbolic Discovery Loop** (phase-level OOD novelty detection + `ValueNet` residual concept invention + human/LLM library curation) so symbolic structure never freezes the meta or prevents hybrid builds.
- **Prove the full loop on one matchup first (TvZ, Terran)**, gated by live human sparring games and counterfactual-verified learner Q&As, while keeping every component behind versioned swappable contracts so competing providers can be benchmarked empirically.

---

## 1. Context & Design Goals

From `docs/ARCHITECTURE.md` (§1), Gary's purpose is to be a **sparring partner and training tool** for aspiring and strong StarCraft: Brood War players—not a superhuman tournament bot.

| Goal | Requirement | Current Standing (2026-11-22) |
|---|---|---|
| **G1. Real human-like opponent** | Coherent macro, timing, adaptation, and micro that feels like a real player rather than a script or superhuman bot | Partial: plays full 3-race games, but `eval/humanlike.py` separates Gary from pros at AUC 0.99+; live games expose glaring strategic/tactical incoherence |
| **G2. Human hands in the action space** | Single camera, 12-unit selection, burst APM, reaction delay, hit-testing, fog memory, hidden enemy HP | **Built and strong** (`gary/interface.py`, 1:1 in OpenBW and SC:R) |
| **G3. Steerable** | Prompt or replay compiles into a `StrategySpec` (*z*) followed reliably ("practice vs. 2-hatch muta 20 times") | Weak: only a static coarse `style` integer (`--style`) fixed at 0:00. Told a style, Terran holds the coarse label (100% in October readings) while inner milestones drift (Factory by 8:00 in 59% vs. pros' 88%; Starport in 10% vs. 55%); Zerg drops the style itself (50% and 17% on styles 0 and 4). No recipe card, no replay-to-plan, no prompt compiler |
| **G4. Adjustable skill** | One system, multiple human skill bands via `HumanProfile` (*h*) | Unbuilt beyond partial pro-speed hand timings |
| **G5. Faithfully explainable for learners** | Queryable causal trace answering *why* a strategic/tactical decision was made, what Gary believed, what alternatives lost, and what hand constraint intervened | **Blocked architecturally**: `eval/why.py` logs model odds, dice rolls, and feature-ablation deltas useful for debugging, not coaching |
| **G6. Modular for experiments** | Swappable providers per pipeline slot selected by manifest and compared on shared harnesses | **Built** (`gary/agent/manifests.py`), though manifests have grown into 30-flag option chains |

**Hard constraints (non-goals):**
- **Workstation compute budget:** Solutions cannot require AlphaStar-scale distributed RL (Vinyals et al., 2019).
- **Offline/custom play only:** Never Battle.net ladder; no Blizzard data or GPL code.
- **Honest explanations only (`ARCHITECTURE.md` §3 Principle 5):** An LLM narrator may only verbalize what the decision records actually hold—never invent post-hoc StarCraft stories.

### Concrete Illustration: Why Explainability Fails Today

From a representative dev-build game's decision records (`records/v1` schema in `gary/decision_log.py`, queried via `eval/why.py` and `gary/policy/attribution.py`), here is what the most honest possible narrator can say today vs. what a Brood War learner actually needs:

| Learner Question | Typical Record Evidence (`eval/why.py` + `attribution.py`) | Best Honest Answer Today | Target Answer After Refocus (Faithful to Records) |
|---|---|---|---|
| *"Why did you open this build?"* | `layer: style, choice: 3, by: roll` | *"A die rolled style 3 at the modern pros' share."* | *"Map is Fighting Spirit; against unknown Zerg I opened 1-Rax FE into Bio+Tank (pro win rate 54%, n=312; alternative 1-1-1 is 47%, n=98)."* |
| *"Why did you build a second Factory at 3:31?"* | First Factory at `p=0.80`; second by dice at `p=0.047` while Starport was `0.549`; zeroing `decisions so far` raises it to `0.80` | *"It wasn't the likely choice; a die came up on a 5% option."* | *"My opponent model puts 76% on 3-Hatch Lurker after seeing Hydralisk Den + Lair at 4:40 with no Spire; switching active tech target from pure Bio to `{bio: 0.6, tank: 0.4}` to get Siege Tanks before Lurkers hit."* |
| *"Why did you attack at 10:15?"* | `commit: engage` drawn at `0.32` while `keep` was `0.42`; zeroing `money` moves it to `0.36` | *"Keeping was likelier; a die came up engage."* | *"Stim and +1 Attack finished (timing window active), my belief estimates Zerg has ~42 drones and <18 army supply after a fast 3rd, and squad regroup completed → initiated `TIMING_PUSH(enemy_natural)`."* |
| *"What did you think I was doing?"* | *(none — no opponent plan belief runs in play; TODO #40)* | *"I don't form a belief about your strategy."* | *"At 5:15, seeing 2 hatcheries + Lair finishing and 100 gas mined puts 78% on 2-Hatch Muta (16% 3-Hatch Spire, 6% Lurker)."* |
| *"Why didn't you stop my drop at 11:00?"* | Arbiter/hands trace logs camera location & APM saturation | *(Already partially answerable from hands trace!)* | *"Detected drop on minimap at 10:56, triggered `DEFEND(main)`, but my camera was on the front fight and APM bucket was empty for 2.8 s."* |

**Core insight:** Building an LLM narrator on top of today's records would produce *faithful nonsense*. Explainability is not a missing UI layer at Phase 5—it is a structural property of whether the agent holds explicit strategic beliefs, plans, and options.

---

## 2. Diagnosis: Why the Current Path Cannot Meet the Goals

### 2.1 The Inverted Neuro-Symbolic Stack (Why Leaf Stop-Gaps Killed RL)

`ARCHITECTURE.md` (§3 Principle 4) envisioned *"neural for skill and inference, symbolic for structure and decisions of record."* In practice, Gary evolved upside down:
- **Messy leaves had symbolic overrides:** In `gt1`, `RoleAhead` hand-coded in-contact micro, `PullRule`/`LoadRule`/`RepairRule`/`ReinforceRule`/`DetectRule` held higher lease priority (`intents.py`: priority 3 vs. neural fight priority 2 vs. army priority 1), `hunt4` and `static` overrode army engagements, and `caps`/`bank_escape`/`answers.py` overrode `MacroNet`.
- **Consequence for RL:** As observed empirically in `docs/SELF_PLAY.md` ("Learning beyond imitation"), neural outputs frequently never reached the units or were overwritten mid-execution. In the safe-RL shielding literature, Alshiekh et al. (2018) distinguish **preemptive shielding** (constraining the legal action/goal space *before* the policy chooses) from **post-posed overrides** (silently overwriting the policy's action *after* it chooses). Post-posed overrides break on-policy credit assignment and distort state-action attribution whenever the learner isn't cleanly separated from the overrider.
- **Consequence for micro:** Hand-coding messy spatial/continuous behaviors (stutter-step, kiting, focus fire, splitting) is both brittle and plays against the exact strength of neural networks.

### 2.2 Removing Stop-Gaps Left a Vacuum: Fragmented Marginal Behavior Cloning

When `gt1dev`, `gz1dev`, and `gp1dev` rightly stripped out leaf stop-gaps (`unscripted`, `noalarm`, `styleroll`), nothing symbolic was built at the trunk to take over long-horizon coherence. Today `gt1dev` (`gary/agent/manifests.py`) stacks ~30 options across ~10 decoupled supervised models with no shared latent plan:

1. **Compounding covariate shift and decoder whack-a-mole:** Pure behavioral cloning suffers from quadratic compounding error once closed-loop execution drifts off the expert state distribution (Ross, Gordon, & Bagnell, 2011). Gary's history in `docs/PROGRESS.md` reflects this directly: `belief.py` error doubles on Gary's own games (11.7 supply error vs. 5.9 on pros); off-plan low-probability draws corrupt the model's own decision history (e.g., a 1–6% Hydralisk Den drawn in 21 of 24 Zerg games made the model abandon Mutalisks, and the 4.7% second Factory above is the same class of event); and `MacroNet` required a cascade of exposure-bias patches (`dice`, `mass`, `expand_mass`, `parkmany`, `coming`, `comingbuild`, `savecoming`, `queued_builds`, `tech_min_p`, `gaswaits`, `ownhist`, `pendown`, `builtcount`, `unitcount`). Replacing `selector.py` with `styleroll` had a valid tactical reason (the old table trained on scripted Zergs over-picked cheesy style 4, 1.5% of pro games), but rolling a die discarded strategic reasoning along with the bias instead of counting outcomes from pro replays as `ARCHITECTURE.md` §6.8 designed.
2. **Marginal matching ≠ coherent behavior (the `CalmNet` proof):** Because stateless per-tick classifiers marginalize over unobserved human intent, matching 1D marginal action rates produces incoherent noise. In `docs/PROGRESS.md` (2026-11-19), `CalmNet` matched the pros' short-order rate out of contact (1.43 vs. 1.58/min) and new-unit rest time (8 s vs. 8 s), **while its direction head achieved log-loss 2.67 vs. uniform 2.77**—nearly random Brownian motion that scattered units (`units alone` rose from 0.29 to 0.41, pros 0.20).
3. **Uncoordinated army tug-of-war:** Four separate systems act on the same army without a shared squad goal: `ArmyNet/commit` (16×16 grid, 5 s), `CalmNet`/`CalmFarNet` (out of contact >12 tiles), `RoleNet` (within 12 tiles, 0.5 s Markov draws), and `ModeModel`/`EventModel`/`StimModel`/`CastModel`. Result: army moves unsieged tanks mid-fight, 37–40% of retreats were cancelled by the next fight turn within 2 s, units left rallies alone 49% of the time (pros 21%), and `gt1dev` trails `gt1` by `-0.188 [-0.302, -0.078]` in paired play.
4. **Proxy optimization without a stopping rule:** "Would a pro do this here?" across every layer, race, and matchup has no natural stopping point (`PROGRESS.md` notes that a retrained humanlikeness classifier always finds the next tell). Five days on tank siege moved no top-level measure (`TODO.md`), ~25 consecutive changes landed without human play or comparison against the playing builds (`PROGRESS.md`, 2026-11-11), no single top-level trend series tracks progress across the past month, and months of headless `gap_windows.py` / `pipe_table.py` rounds missed that Terran tanks *never sieged against Zerg*—spotted immediately in three watched live games (`TODO.md`, 2026-11-12). Only four human games were played in seven weeks (last recorded on 2026-10-19).
5. **The "fidelity must come first" counter-case is partly backwards:** A natural objection is *"a bot that plays poorly isn't worth explaining, so tactical fidelity must come before strategy/explainability."* That order fails on two counts: (a) strategic reasoning (plan, enemy-plan belief, counted pro tables) is computed from sightings and the replay database and is valid whether or not tanks siege perfectly; and (b) holding an explicit plan state in play is predicted to *eliminate* whole classes of off-plan tech draws and decoder patches directly, rather than fighting them one symptom at a time.

### 2.3 Empirical RL Ledger: Single-Tick Signal Drowns, Temporally Extended Signal Holds

Gary's own experiments (`docs/CONTROL.md` step 7, `docs/SELF_PLAY.md`) already revealed where learning works and where it fails on workstation compute:

| Learning Target | Timescale | Empirical Result in Gary | Takeaway |
|---|---|---|---|
| Macro single-decision branch (`macro_rl.py`) | 1 build click | Effect `sd=130` vs. chaos `sd=512`; **50.0% held-out (noise)** | Single-tick macro RL is hopeless at this compute |
| Per-unit fight roles (`league_loop.py`, 5 runs, ~4k pairs) | 0.5 s | 4 runs flat; the 1 small gain (`rl1`) was replaced in `gt0.36dev` by a relabeled imitation model lacking siege/mines (`manifests.py`, though `PROGRESS.md`'s top summary still lists `rl1`) | Unscoped per-tick micro RL fails when armies/rules interfere |
| Commit paired branches (`commit_pairs.py`, 1,004 pairs) | 5 s grid draw | **0.46 held-out (chance)** even with locked arms + critic | Perturbing 1 grid tick while other layers roll dice drowns in noise |
| **Whole-army coherent intent (`eval/army_effect.py`)** | **90 s held option** | **Effect `sd=650` vs. chaos `sd=210` (3× SNR, 62% > 2 SE)** | **Temporally extended options have strong learnable signal** |
| **Per-game strategy choice (`selector.py`)** | **Whole game** | **Losses cut 57 → 30 of 333** | **Strategic-level outcome learning works cleanly** |
| **Offline supervised perception/prediction** (`belief`, `value`, `placement`, `stim`, `modes`, `commit`) | Offline dataset | **Reliable, fast, well-calibrated on held-out pros** | **Supervised neural perception is a proven strength here** |

### 2.4 Scope Multiplier & Code Duplication

Scaling an unfinished paradigm to 3 races × 6 matchups × 2 build lines (`gt1`/`gt1dev`, `gz1`/`gz1dev`, `gp1`/`gp1dev`) multiplied validation and maintenance costs by ~6× before proving G3 or G5 in a single matchup: one hands fix bumps six versions and re-records parity, 96 paired games only resolve 0.06–0.14 of paired score (`AGENTS.md`), and evaluation tooling has grown to 46 scripts in `eval/`. Simultaneously, feature calculation is duplicated in separate code (`ingest/macro_dataset.py` imports nothing from `gary/`), creating an ongoing input-parity tax (`tests/test_inputs.py`) that a single shared reader would eliminate.

---

## 3. Proposed Refocus: Six Integrated Solutions

The refocus establishes a strict, principled division of labor across the pipeline, keeping every boundary behind a versioned, swappable provider contract.

```
                         ┌──────────────────────────────────────────────────────┐
                         │   OFFLINE NEURAL → SYMBOLIC DISCOVERY LOOP (Sol. 5)  │
                         │  Pro replays + Self-play → Trajectory OOD Novelty +  │
                         │  ValueNet Residual Analysis → Curated Concept/Option │
                         │  Library (Factored Concepts, Phase Graphs, Cards)    │
                         └─────────────────────────┬────────────────────────────┘
                                                   │ versioned concepts & options
                                                   ▼
┌──────────────────────────────┐     ┌────────────────────────────────────────────┐
│ TIER 1: NN PERCEPTION (Sol.2)│     │ TIER 2: SYMBOLIC TRUNK + LEARNED SCORING   │
│ (Supervised from Resim)      │     │         (Sol. 1 & Sol. 3)                  │
│ Raw fogged obs → Calibrated  ├────►│ • Factored StrategyState (opening card,    │
│ named concepts & relations:  │only │   tech mix, posture, phase transitions)    │
│ • P(enemy opening/tech/eco)  │named│ • Learned Branch Scorer (Counted Table /   │
│ • Threat ETAs & relations    │con- │   EBM / Concept-MLP — strict bottleneck)   │
│ • Map/choke/exposure facts   │cepts│ • Persistent Squad Options (STAGE, REGROUP,│
└──────────────────────────────┘     │   PUSH, CONTAIN, HARASS, DEFEND, DISENGAGE)│
                                     └─────────────────────┬──────────────────────┘
                                                           │ active option + exclusive unit lease
                                                           ▼
┌──────────────────────────────┐     ┌────────────────────────────────────────────┐
│ EXPLAINABILITY (Sol. 6)      │◄────┤ TIER 3: GOAL-CONDITIONED NN LEAVES (Sol. 4)│
│ Structured records of        │     │ (Zero leaf stop-gaps stealing units!)      │
│ beliefs, plan transitions,   │     │ • Option-conditioned RoleNet / micro skills│
│ concept scores, alternatives │     │ • Mode/Stim/Cast models scoped to option   │
│ & arbiter constraints →      │     │ • Plan-conditioned MacroNet + PlacementNN  │
│ Counterfactual-tested Q&As   │     └─────────────────────┬──────────────────────┘
└──────────────────────────────┘                           │ candidate actions
                                                           ▼
                                     ┌────────────────────────────────────────────┐
                                     │ TIER 4: HUMAN HANDS & ARBITER (Kept as-is) │
                                     │ Attention Arbiter (shares from Posture + h)│
                                     │ HumanInterface (camera, 12-box, APM, Fitts)│
                                     └────────────────────────────────────────────┘
```

---

### Solution 1: Flip to the "Neuro-Symbolic Sandwich" with Strict Ownership Boundaries

**Design:** Place neural networks where perception and messy continuous control live (bottom-up perception and top-down leaf skills), and place explicit symbolic structures in the strategic/tactical trunk—with **no symbolic leaf stop-gaps allowed to override or sequester units leased to an active NN skill**. Symbolic preemption happens only at explicit **option boundaries** (initiation/termination/interruption of a named option), never by stealthily intercepting clicks downstream.

**Literature Grounding:**
- **Kautz (2022)** (*The Third AI Summer*, AI Magazine) formalizes neuro-symbolic architectures; this design combines Kautz's `Neuro → Symbolic` (neural perception extracting structured concepts) with `Symbolic[Neuro]` / `Neuro | Symbolic` (symbolic strategic/option control invoking neural evaluators and neural skill subroutines).
- **Silver et al. (2022)** (*Learning Neuro-Symbolic Skills for Bilevel Planning*, CoRL 2022, `arXiv:2206.10680`) demonstrate in continuous long-horizon robotics that pairing high-level symbolic operators/preconditions with learned low-level parameterized neural skills yields compositional long-horizon generalization that neither flat RL nor pure scripting achieves.
- **Alshiekh et al. (2018)** (*Safe Reinforcement Learning via Shielding*, AAAI 2018, `arXiv:1708.08611`) formalize **preemptive** (scoping legal choices *before* policy selection) vs. **post-posed** (overwriting choices *after* selection) intervention. Gary's old stop-gaps acted as uncoordinated post-posed overrides; moving constraints to preemptive option scoping restores clean policy-execution alignment.
- **Rudin (2019)** (*Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead*, Nature Machine Intelligence) argues that post-hoc explanations of black boxes are structurally unfaithful and that decision accountability requires inherently interpretable structure at the decision boundary itself.

**Known Strengths, Limits, and Risks:**
- *Strengths:* Directly aligns each subproblem with its inductive bias; makes strategic state inspectable and steerable by construction; restores exclusive unit ownership so NN micro skills can actually learn.
- *Limits:* Adds interface contracts between tiers; any error at a tier boundary (e.g., bad concept definition or poorly scoped option) caps downstream quality.
- *Risks:* **Inter-level blame ambiguity** (when a push fails, was Perception wrong, was the Trunk wrong to push, or did the NN Leaf micro poorly?) and **engineering complexity** if contracts are over-designed before validating on one matchup.

**Alternatives Considered & Why Not Picked:**
1. *End-to-end deep RL (e.g., AlphaStar, Vinyals et al., 2019; Pluto):* Requires orders-of-magnitude more compute than a workstation, sacrifices G5 (faithfully explainable strategy), and makes fine-grained steering (G3) brittle.
2. *Pure programmatic/logic policies down to leaves (`VIPER`, Bastani, Pu, & Solar-Lezama, 2018, `arXiv:1805.08328`; `NUDGE`, Delfosse et al., 2023, `arXiv:2306.01439`):* Great for discrete low-dimensional domains, but cannot express fluid continuous spatial micro (stutter-stepping, splitting vs. splash, kiting) in Brood War.
3. *Keeping leaf stop-gaps (`gt1` paradigm):* Empirically proven in Gary to kill NN credit assignment and block RL.

---

### Solution 2: Strict Concept Bottleneck Perception (Opponent Model + Relational Predicates)

**Design:** Build a dedicated **Concept Perception Layer** trained via supervised learning on fog-filtered pro re-simulations (where Gary's pipeline already excels) plus deterministic geometric/relational extractors:
- **Factored Opponent Model (`P(enemy_concepts | seen)`):** Instead of predicting only raw enemy army supply (`gary/policy/belief.py`), predict calibrated probability distributions over:
  - *Enemy opening & active tech lines* (multi-label, e.g., `early_pool`, `fast_3rd_hatch`, `spire_muta`, `lurker_tech`, `hive_tech`)
  - *Estimated hidden economy & army* (`enemy_workers`, `enemy_bases`, `enemy_army_supply` with uncertainty intervals)
  - *Imminent threat windows* (`P(ling_hit_within_45s)`, `P(muta_hit_within_60s)`, `P(lurker_fielded)`)
- **Relational Tactical Concepts:** Not just flat counts, but object/region relations (e.g., `army_advantage_at_front`, `my_army_closer_to_natural_than_enemy`, `base_mineral_line_air_exposed`, `timing_window_active[stim_+1]`, `enemy_natural_static_heavy`).
- **Strict Bottleneck Rule at Runtime:** The Strategic Trunk's branch scorer receives **only** these named symbolic concepts and calibrated probabilities—no raw hidden-layer bypass vectors.

**Literature Grounding:**
- **Koh et al. (2020)** (*Concept Bottleneck Models*, ICML 2020, `arXiv:2007.04612`) establish that forcing predictions through supervised human-named concepts enables both inherent transparency and **test-time human intervention** (manually correcting a concept cleanly updates downstream decisions).
- **Delfosse et al. (2024)** (*Interpretable Concept Bottlenecks to Align Reinforcement Learning Agents* — `SCoBots`, NeurIPS 2024, `arXiv:2401.05821`) extend CBMs to RL using **successive and relational concept layers**, showing that relational concepts (beyond raw object counts) are essential for sequential control and expose subtle reward/goal misalignments.
- **Mahinpei et al. (2021)** (*Promises and Pitfalls of Black-Box Concept Learning Models*, ICML XAI Workshop, `arXiv:2106.13314`) and **Havasi, Parbhoo, & Doshi-Velez (2022)** (*Addressing Leakage in Concept Bottleneck Models*, NeurIPS 2022) prove that **concept leakage** occurs whenever soft concept probabilities or residual shortcuts smuggle unmodeled raw features past the bottleneck—destroying concept semantics and breaking interventions. They identify *insufficient concept sets* and *inexpressive concept predictors* as the root causes.
- **Marconato et al. (2023)** (*Not All Neuro-Symbolic Concepts Are Created Equal: Analysis and Mitigation of Reasoning Shortcuts*, NeurIPS 2023, `arXiv:2305.19951`) show that jointly trained NeSy systems frequently converge to **reasoning shortcuts**—achieving high task accuracy by mapping concepts to unintended semantics. Training concept extractors with **direct hindsight supervision from re-simulated ground truth** (rather than purely weak end-to-end game-outcome supervision) directly mitigates reasoning shortcuts.

**Known Strengths, Limits, and Risks:**
- *Strengths:* Free, abundant ground-truth supervision from 19k+ modern re-simulated games; calibrated beliefs immediately unlock *"What did you think I was doing?"*; direct supervision prevents reasoning shortcuts; enables true human intervention for coaching/drills.
- *Limits:* **Accuracy-faithfulness tradeoff:** if key Brood War concepts are missing from the vocabulary, a strict bottleneck will underperform an unconstrained neural policy until those concepts are added.
- *Risks:* **Distribution shift on Gary's own games** (already observed in `belief.py`: 5.9 error on pros vs. 11.7 on Gary's league games—requires calibrating/augmenting on Gary's own self-play re-simulations too); **soft-probability leakage** if downstream neural branch scorers overfit calibration artifacts of `P(concept)`.

**Alternatives Considered & Why Not Picked:**
1. *Post-hoc feature ablation on flat networks (`gary/policy/attribution.py`):* Zeroing correlated columns (`decided`, `money`) creates out-of-distribution inputs, yields correlation rather than strategic cause, and cannot answer opponent-belief questions (Rudin, 2019).
2. *Live Side-Channel / Residual CBMs (Havasi et al., 2022):* Allowing a raw neural bypass into the live branch scorer recovers accuracy at the cost of unexplainable decisions whenever the side-channel dominates. **Compromise:** Keep an unconstrained `ValueNet` *offline* to detect missing concepts (Solution 5), and support a side-channel scorer as an **experimental manifest option** solely to measure the exact Elo cost of the strict bottleneck.

---

### Solution 3: Factored Compositional Strategy + Persistent Tactical Options (Solving Explosion & Rigidity)

**Design:** Address three coupled problems simultaneously—combinatorial explosion, rigid whole-game build buckets ("Bio vs. Mech" missing hybrids & transitions), and uncoordinated 4-way army control:

1. **Factored, Phase-Level `StrategyState` (Replacing Static `style` IDs):**
   - **Non-parametric anchor (`opening_card`):** A real pro replay's build milestones & timings (e.g., from the chosen style or user-supplied replay) giving crisp G3 drill steerability and concrete "on-plan / late-by-15s" accounting.
   - **Composable multi-label tech & posture state (not mutually exclusive enums):**
     - `active_tech_lines`: soft weights / multi-hot set (e.g., `{bio: 0.65, tank: 0.35, starport: 0.2}`) — natively represents Bio+Tank hybrids, 1-1-1, Vulture-Bio, and mid-game Bio → Mech switches without enumerating $N$ rigid build buckets.
     - `posture`: `{greedy, standard, timing_pressure, defensive, all_in}`.
     - `active_directives`: reusable sub-plan DAG nodes triggered by beliefs/facts (e.g., `PREP_VS_MUTA(turrets_per_base=2)`, `DEFEND_EARLY_POOL`, `TECH_TRANSITION(siege_tanks)`, `TAKE_EXPANSION(third)`).
   - **Phase transitions:** Strategy is a **trajectory** (`Opening → Midgame → Lategame`), logging every branch/transition event with its triggering concepts and alternatives.

2. **Persistent Squad-Level Tactical Options (Replacing `Commit` + `Calm` + `Hunt4`):**
   - Lift army decisions from 200 individual units and 5 s 16×16 grid dice rolls to **1–4 named squads** holding temporally extended **Options** (`STAGE`, `REGROUP`, `TIMING_PUSH`, `CONTAIN`, `HARASS`, `DEFEND`, `DISENGAGE`, `SCOUT`, `CLEAR_FINISH`).
   - Each option specifies:
     - **Initiation preconditions** (over named concepts),
     - **Target / parameters** (base, choke, region),
     - **Termination & preemption predicates** (e.g., `REGROUP` ends when ≥80% squad gathered or 15 s elapsed; `DISENGAGE` holds until ≥6 tiles clear of threat so `RoleNet` stops cancelling retreats after 0.5 s; `DEFEND(main)` preempts `STAGE`),
     - **Exclusive unit lease** passed down to the Tier 3 NN leaf executor.

3. **Learned Concept-Conditioned Branch Scoring (Avoiding $O(V^d)$ Table Explosion):**
   - Never enumerate a flat Cartesian lookup table over `map × spawn × build × enemy × phase`.
   - Score candidate strategic branches / squad options using **swappable glass-box or concept-bottleneck scorers** taking only the named concepts:
     - *Provider A (V1 baseline):* **Counted Pro & Self-Play Tables with hierarchical Bayesian shrinkage** (including sighting-to-response tables, e.g., *"after seeing Spire, pros build ≥1 turret/base within 60 s in p% (n)"*—converting `answers.py` from an ad-hoc stop-gap into a data-counted, printable branch rule).
     - *Provider B:* **Explainable Boosting Machines (EBM / $\text{GA}^2\text{M}$)** — additive + pairwise-interaction boosted models over named concepts that generalize across unseen feature combinations while exposing exact per-concept additive logit contributions.
     - *Provider C:* **Concept-Only Small MLP / Contextual Bandit** — updated offline via counterfactual risk minimization / propensity-weighted or paired-branch outcomes at the option/game timescale (where SNR is 3× higher than single ticks).

**Literature Grounding:**
- **Sutton, Precup, & Singh (1999)** (*Between MDPs and semi-MDPs: A framework for temporal abstraction in reinforcement learning*, Artificial Intelligence) formalize **Options** $(I_\omega, \pi_\omega, \beta_\omega)$ as temporally extended macro-actions over semi-MDPs, reducing horizon length and improving credit assignment.
- **Bacon, Harb, & Precup (2017)** (*The Option-Critic Architecture*, AAAI 2017, `arXiv:1609.05140`) formalize option termination gradients (an option terminates when switching beats continuing), grounding why explicit termination/persistence stops the 0.5 s flip-flopping seen in Gary's retreats and tank sieges.
- **Ontiveros et al. (2025)** (*Grounding Methods for Neural-Symbolic AI*, IJCAI 2025, `arXiv:2507.08216`) analyze the **grounding bottleneck** ($O(E^k)$ combinatorial explosion under exhaustive grounding) and show that **lifted / parameterized grounding** (reasoning over abstract groups/classes and instantiating lazily per query) keeps neuro-symbolic inference tractable. Operating on 1–4 squads and 2–5 bases instead of 200 units is relational lifting by design.
- **Nori et al. (2019)** (*InterpretML: A Unified Framework for Machine Learning Interpretability*, `arXiv:1909.09223`) introduce **Explainable Boosting Machines ($\text{GA}^2\text{M}$)**, showing glass-box additive models with pairwise interactions match boosted-tree accuracy while giving exact, faithful per-feature attributions without flat table explosion.
- **Swaminathan & Joachims (2015)** (*Batch Learning from Logged Bandit Feedback through Counterfactual Risk Minimization*, JMLR / ICML 2015) establish propensity-weighted offline policy evaluation and variance regularization for learning from **confounded observational logs**—directly addressing `ARCHITECTURE.md` §6.8's confounding warning on pro replay win rates.

**Known Strengths, Limits, and Risks:**
- *Strengths:* Eliminates both grounding explosion ($O(E^k)$) and Cartesian table explosion ($O(V^d)$); supports hybrid builds and mid-game transitions natively; directly produces teachable strategic and tactical explanations; elevates army decisions to the 30–90 s timescale where `eval/army_effect.py` proved 3× SNR.
- *Limits:* Requires defining a clean, compact initial vocabulary of factored concepts and ~8–9 squad options; replay win-rate tables remain observationally confounded until validated via self-play interventions.
- *Risks:* **Option design brittleness** (poorly chosen termination thresholds can make squads sluggish or indecisive); **over-engineering V1** if factored strategy and squad options are built simultaneously rather than staged (Phase 1 strategy slice → Phase 2 squad options).

**Alternatives Considered & Why Not Picked:**
1. *Flat decision trees or unfactored lookup tables:* Explodes as $O(V^d)$ with every added context feature, leaving most cells empty.
2. *Whole-game mutually exclusive build enums (`Bio` vs. `Mech`):* Cannot represent hybrids, mid-game switches, or new seasonal meta builds cleanly.
3. *Joint online Option-Critic RL (Bacon et al., 2017):* Suffers from severe multi-level non-stationarity and option collapse at workstation compute (see Solution 4).

---

### Solution 4: Goal-Conditioned Neural Leaf Executors & Bilevel Training (Unblocking Learning)

**Design:** Keep neural networks as the **sole owners of messy low-level execution**, conditioned explicitly on the active symbolic goal/option from Tier 2:
- **Micro / Fight Leaves:** Condition `RoleNet` (and `ModeModel`/`StimModel`/`CastModel`) on the squad's active `Option` (`TIMING_PUSH`, `CONTAIN`, `DISENGAGE`, `HARASS`, `DEFEND`, `STAGE`). While a squad is leased to an option, **no leaf stop-gap steals its units or vetoes its orders.**
- **Macro Execution Leaf:** Condition `MacroNet` on the active `StrategyState` (or let a clean preemptive milestone scheduler emit high-priority tech/branch milestones while `MacroNet` + `PlacementModel` handle continuous unit/supply/expansion flow without conflicting side-overrides like `bank_escape` or `caps`).
- **Handling Unlearned Micro Skills During Transition (No Silent Hijacks):** Jobs that no NN currently outputs (e.g., loading bunkers, repairing turrets, pulling workers against early lings, scanning cloaked lurkers) are refactored into **explicit, bounded leaf-skill providers occupying their own named options** (e.g., `DEFEND_WORKER_PULL`, `GARRISON_BUNKER`, `REPAIR_DEFENSE`)—so unit leases are explicit, visible in the trace, and **each skill can be swapped 1-for-1 for a learned NN provider** when trained, without ever interfering with `RoleNet`'s leased combat units.
- **Bilevel / Alternating Training Protocol:**
  - Never train Tier 2 (Trunk) and Tier 3 (Leaves) jointly via online RL.
  - **Leaf training:** Freeze the Trunk. Train each NN leaf skill via supervised imitation on option-filtered pro replays, optionally followed by **bounded local skill RL** on 15–45 s sub-episodes with option-specific rewards (e.g., `DISENGAGE` rewarded for survival + distance gained; `HARASS` for worker damage per unit lost; `ENGAGE` for local fight trade) where the leaf has 100% unit control.
  - **Trunk training:** Freeze the Leaves. Update branch scorers via offline counterfactuals / paired option branches / game-level outcomes.

**Literature Grounding:**
- **Levy et al. (2019)** (*Learning Multi-Level Hierarchies with Hindsight* — `HAC`, ICLR 2019, `arXiv:1712.00948`) formally analyze **multi-level non-stationarity in HRL**: when lower-level policies update concurrently with higher-level policies, the high-level transition function $T_{i|\pi_{i-1}}$ shifts continuously, destabilizing learning. Decoupling levels via bilevel/alternating training (and hindsight goal relabeling when lower levels achieve alternative outcomes) directly resolves this instability.
- **Silver et al. (2022)** (`arXiv:2206.10680`) similarly separate low-level skill acquisition from high-level bilevel planning using explicit skill contracts.
- **Ross, Gordon, & Bagnell (2011)** (`DAgger`, AISTATS 2011) show that closed-loop covariate shift in BC is reduced when policies are trained on states visited under their own rollouts—which becomes tractable once rollouts are bounded to 15–45 s option episodes.

**Known Strengths, Limits, and Risks:**
- *Strengths:* Fixes the exact broken-pipe problem that killed RL in `gt1`; reduces micro RL horizon from 30 minutes to 15–45 s localized objectives; preserves playability during migration via explicit, swappable option-scoped skill slots.
- *Limits:* Goal-conditioning `RoleNet` and `MacroNet` requires relabeling pro replay datasets with inferred option/phase tags (a noisy offline labeling step).
- *Risks:* **Option-label noise** in pro replays (e.g., distinguishing pro `CONTAIN` from `TIMING_PUSH` heuristically) could dilute goal-conditioned imitation; **bounded skill RL may still face high variance** under human-hand noise (camera/click scatter)—this must be tested empirically with pipe checks before scaling compute.

**Alternatives Considered & Why Not Picked:**
1. *Unconditioned `RoleNet` + `CalmNet` + `Commit` (status quo):* Marginalizes over conflicting goals, producing scattered moves and cancelled retreats.
2. *Simultaneous end-to-end hierarchical RL across all tiers:* Known to suffer from non-stationarity (Levy et al., 2019) and empirically failed across 10+ runs in Gary's compute regime.

---

### Solution 5: Offline Neural → Symbolic Knowledge Induction Loop

**Design:** Ensure the symbolic vocabulary is **living, not frozen**, so new seasonal builds, hybrids, and hidden tactical contexts can flow from neural models into the symbolic library:
1. **Phase-Level Trajectory Embeddings + OOD Novelty Detection:** Replace `taxonomy/label_all.py`'s frozen 0–8 min kNN projection with a sequence encoder over sliding game phases (opening 0–4 min, midgame 4–10 min, lategame 10+ min). New replay packs are scored against existing cluster densities; **out-of-distribution (OOD) pockets are explicitly flagged as `"novel/unclassified"`** rather than silently forced into old buckets. When enough replays accumulate in a novel pocket, the pipeline emits a cluster card + distilled rule + LLM-proposed name for human review.
2. **Residual-Driven Concept Invention (`ARCHITECTURE.md` §7.6):** Periodically compare an **unconstrained offline `ValueNet`** (or unconstrained policy trained on new replays) against the **concept-only Trunk model**. Identify game states with large systematic residuals (`V_unconstrained - V_concepts`). Cluster high-residual states in neural latent space, compute feature attributions, and have an LLM + human inspect example replays inside vs. outside the cluster to propose a missing relational concept (e.g., `cross_spawn`, `cliff_exposed_natural`, `valkyrie_bio_hybrid`). **Strict promotion gate:** a candidate concept enters the symbolic library *only* if adding it reduces held-out prediction residuals after multiple-comparison correction.
3. **Curated Library Compression & Documentation (Offline Wake-Sleep):** Mine recurring multi-step build blocks and tactical patterns across winning pro games and compress them into named reusable modules in the strategy library (with auto-generated + human-reviewed descriptions), then retrain the Concept Perception NNs to recognize them.

**Literature Grounding:**
- **Ellis et al. (2021)** (*DreamCoder: Bootstrapping Inductive Program Synthesis with Wake-Sleep Library Learning*, PLDI 2021, `arXiv:2006.08381`) introduce the wake-sleep cycle alternating between task execution (wake), library compression of recurring abstractions (sleep-abstraction), and retraining a neural recognition model to invoke them (sleep-dreaming).
- **Grand et al. (2024)** (*LILO: Learning Interpretable Libraries by Compressing and Documenting Code*, ICLR 2024, `arXiv:2310.19791`) combine symbolic compression with LLM-driven auto-documentation (`AutoDoc`), showing that naming and documenting discovered abstractions makes them usable by both humans and neural synthesizers.
- **Liang et al. (2025)** (*VisualPredicator: Learning Abstract World Models with Neuro-Symbolic Predicates for Robot Planning*, ICLR 2025 Spotlight, `arXiv:2410.23156`) demonstrate neuro-symbolic predicate invention from sensory trajectories for planning, showing improved OOD generalization over flat hierarchical RL.

**Known Strengths, Limits, and Risks:**
- *Strengths:* Directly answers the "new builds invented every season" problem; prevents symbol bloat by promoting only concepts that measurably shrink residuals; keeps humans in control of explanation quality.
- *Limits:* **Not fully autonomous.** Unlike DreamCoder/LILO (which have exact deterministic program verifiers), Brood War has noisy, confounded outcomes; automated predicate invention without human/statistical gating will invent spurious correlations.
- *Risks:* **Overfitting residuals** to a small replay pack or to quirks of Gary-vs-Gary self-play rather than real human StarCraft; **maintenance burden** if the concept vocabulary churns faster than models can be retrained.

**Alternatives Considered & Why Not Picked:**
1. *Static hand-authored taxonomy (`plans.py` + frozen kNN in `label_all.py`):* Blind to seasonal meta shifts and mid-game transitions.
2. *Pure unsupervised clustering on raw timings (`discover.py` alone):* Empirically unstable on Zerg (2 to 23 clusters, two-thirds unclustered) and blind to strategic outcomes.
3. *Fully autonomous online symbol invention:* Beyond current SOTA in noisy adversarial RTS (see Section 5).

---

### Solution 6: Counterfactual-Verified Coaching Explainability Built *Now* (Not Deferred to P5)

**Design:** Move explainability from "Phase 5 after everything else is finished" to a **Phase 1 architectural forcing function**:
- Extend `gary/decision_log.py` with structured record types matching `ARCHITECTURE.md` §6.5: `concept_belief`, `strategy_state`, `branch_select` (concept contributions + alternative scores + replay `n`/CI), `option_event` (start/continue/terminate/preempt + reason), alongside existing `arbiter`/`hands`/`order` constraint records.
- Build **five deterministic explanation templates first** (zero LLM hallucination risk) answering:
  1. *Why this opening / strategy plan?*
  2. *What did you think I was doing at minute M, and from what evidence?*
  3. *Why did you build/tech/expand (or hold back) at minute M?*
  4. *Why did you push / hold / retreat / harass at minute M?*
  5. *Why did you miss a defense / supply block / timing?*
- **Automated Faithfulness Test (`ARCHITECTURE.md` §8):** Leverage Gary's deterministic branching engine (`eval/pairs.py`) as a **counterfactual verifier**: if an explanation cites concept/fact $F$ as decisive at frame $t$, replay frame $t$ with $F$ intervened/flipped and verify that the trunk's chosen branch actually changes.
- Add an optional **LLM Narrator provider** on top of the verified templates only after the templated answers pass faithfulness and human coaching utility checks.

**Literature Grounding:**
- **Rudin (2019)** (inherent interpretability over post-hoc rationalization); **Koh et al. (2020)** (intervention accuracy as the gold standard of concept faithfulness).

**Known Strengths, Limits, and Risks:**
- *Strengths:* Prevents silent drift away from G5; turns explainability into an automated CI-like check via counterfactual replays; templates eliminate LLM fabrication risk in V1.
- *Limits:* Deterministic templates are terse and cover a bounded set of question types until a grounded LLM narrator is layered on top; explanations can only be as insightful as the concepts in Tier 1–2.
- *Risks:* **False sense of completeness** if templates pass counterfactual tests on trivial concepts (e.g., citing a tautological fact like *"I built a depot because I was supply-blocked"*) rather than strategic concepts useful to a learner—which is why human sparring review of the answers is a mandatory Phase 1 gate.

**Alternatives Considered & Why Not Picked:**
- *Waiting for "complete records" before building explanations:* Current `records/v1` logs (`gary/decision_log.py`) are already complete for what the layers do—they lack *strategic reasons*, not log fields.
- *Prompting an LLM over raw replay summaries:* Violates Principle 5 ("records, not stories"); hallucinates plausible StarCraft prose unrelated to actual decision causality.

---

## 4. Implementation Plan in the Current Gary Codebase

### 4.1 Keep / Refactor / Delete & Rebuild Inventory

| Codebase Area | Action | Rationale & Specific Details |
|---|---|---|
| `gary/interface.py`, `gary/commands.py`, `gary/orders.py`, `gary/mapinfo.py`, `gary/terrain.py`, `gary/walls.py` | **KEEP** | Core G2 human hands & map geometry; battle-tested and 1:1 with SC:R |
| `adapters/scr_bridge/`, `viewer/` | **KEEP** | Live Remastered play and POV debugging; add concept/option overlays to `viewer/` later |
| `resim/`, `ingest/inventory.py`, `ingest/cmdcache.py`, `ingest/build_orders.py`, `ingest/ladder_maps.py` | **KEEP** | 92k replay & modern SC:R re-simulation pipeline is a core asset |
| `gary/race.py`, `gary/races.py`, `gary/terran.py`, `gary/zerg.py`, `gary/protoss.py`, `gary/agent/executor.py`, `*_executor.py`, `gary/agent/motor.py`, `gary/agent/grouping.py` | **KEEP** | Race-agnostic execution substrate; stop polishing Protoss/Zerg edge cases during Phase 1–2, but keep `tests/test_matchups.py` and `tests/test_live.py` green |
| `eval/match.py`, `eval/pairs.py`, `eval/paired.py`, `eval/league.py`, `eval/why.py`, `eval/monitor.py`, `gary/decision_log.py` | **KEEP & EXTEND** | Add structured `concept_belief`, `strategy_state`, `branch_select`, `option_event` record types; add counterfactual intervention runner to `eval/pairs.py`; add template Q&A CLI (`eval/coach.py` or `eval/why.py --ask`) |
| `gary/policy/placement.py`, `gary/policy/stim.py`, `gary/policy/cast.py`, `gary/policy/modes.py`, `gary/policy/value.py` | **KEEP & RE-SCOPE** | Keep `PlacementModel` + `ProTiles` as clean neural spatial skills; keep `ValueNet` for offline residual discovery & `--gg`; scope `ModeModel`/`StimModel`/`CastModel` strictly inside active squad options |
| `gary/policy/belief.py` | **REFACTOR / UPGRADE** | Expand from raw enemy-supply regressor into full `ConceptPerceptionProvider` predicting factored `enemy_opening`, `enemy_tech_lines`, `threat_timings`, and `enemy_eco_army` with calibration checks; wire into play by default |
| `gary/agent/manifests.py`, `gary/agent/gary.py` | **REFACTOR** | Introduce clean typed slot contracts for the 4 tiers (`perception`, `strategy`, `tactics`, `skills`, `arbiter`); stop chaining 30+ flat option flags; create a clean `gt_ns` manifest line while keeping legacy `gt1` reproducible for A/B comparison |
| `gary/agent/intents.py`, `gary/agent/arbiter.py` | **REFACTOR** | Separate **Tactical Squad Options** (persistent, 10–60 s, owning unit leases & attention hints) from low-level motor commands; allow active Posture + `HumanProfile` (*h*) to set arbiter attention shares (`ARCHITECTURE.md` §6.7) |
| `gary/policy/macro.py`, `gary/agent/macro.py` | **REFACTOR** | Extract a **single shared feature/concept encoder** used by both `ingest/` and `gary/` (eliminating duplicated feature logic); accept `StrategyState` (recipe-card milestones + factored tech/posture targets) instead of a single static `style` ID |
| `gary/policy/roles.py`, `gary/agent/roles.py`, `gary/agent/fight.py` | **REFACTOR** | Condition `RoleNet` on the active Squad Option; move unlearned rules (`PullRule`, `LoadRule`, `RepairRule`, `DetectRule`) into explicit option-scoped leaf-skill slots rather than silent priority-3 hijacks |
| `taxonomy/discover.py`, `taxonomy/plans.py`, `taxonomy/label_all.py`, `gary/styles.py` | **REFACTOR (Phase 3)** | Upgrade to phase-level trajectory embeddings + OOD novelty flag + residual-driven concept cards; keep `v2` catalogue backward-compatible during Phase 1–2 |
| `gary/agent/posture.py`, `gary/agent/answers.py`, `gary/agent/selector.py` | **RETIRE & REBUILD** | Replace ad-hoc hardcoded `EarlyPoolPostureV1..V6`, hardcoded `LURKER_ANSWER`/`MUTA_ANSWER`, and old 1.16 map-only `StrategySelector` with the unified **Tier 2 Symbolic Strategy Trunk** (factored `StrategyState` + counted pro/self-play tables + swappable glass-box branch scorers) |
| `gary/agent/calm.py`, `gary/policy/calm.py` | **DELETE / RETIRE (Phase 2)** | Out-of-contact positioning belongs to persistent Squad Options (`STAGE`, `REGROUP`), not random-direction local jitter |
| `gary/agent/army.py` (`commit` 5 s grid dice, `hunt4`, `static` overrides) & `gary/agent/army_rules.py` | **REBUILD (Phase 2)** | Replace uncoordinated 5 s grid dice + side-override `hunt4` with **Tier 2 Squad Tactical Options** (keep `ArmyNet`'s spatial heatmaps optionally as a *target-location scorer* provider inside an option!) |
| Legacy dead/superseded scripts (`gary/policy/fight_cmd.py`, `gary/policy/fight.py`, `gary/policy/switch.py`, `gary/policy/plan.py`, `v02`–`v028` manifest clutter) | **ARCHIVE / PRUNE** | Clean out unused prototypes once parity tests are scoped to active manifests |

### 4.2 Modularity & Plug-and-Play Contracts

Every tier boundary stays a typed protocol in `gary/agent/contracts.py` (selected via `gary/agent/manifests.py`) so no single architectural bet is hardcoded:

```python
class ConceptPerceptionProvider(Protocol):
    """Tier 1: Raw fogged obs -> calibrated named concepts & relational facts."""
    def update(self, obs: dict, mapinfo) -> ConceptState: ...

class StrategyTrunkProvider(Protocol):
    """Tier 2a: ConceptState -> factored StrategyState (opening card, tech mix, posture, directives) + trace."""
    def step(self, concepts: ConceptState, current: StrategyState) -> tuple[StrategyState, list[TraceRecord]]: ...

class BranchScorerProvider(Protocol):
    """Plug-in scorer inside Tier 2a/2b: evaluates legal branches strictly from ConceptState."""
    # Swappable providers: "counted_table", "ebm_ga2m", "concept_mlp", "side_channel_ablation"
    def score(self, concepts: ConceptState, options: list[str]) -> dict[str, BranchScore]: ...

class TacticalOptionProvider(Protocol):
    """Tier 2b: ConceptState + StrategyState -> persistent SquadOptions with unit leases & termination."""
    def step(self, concepts: ConceptState, strategy: StrategyState, squads: list[Squad]) -> list[SquadOption]: ...

class LeafSkillProvider(Protocol):
    """Tier 3: Executes one SquadOption over its leased units -> candidate HumanActions (no side-overrides)."""
    # Swappable providers: "role_net_cond", "role_net_rl", "bounded_rule_skill"
    def act(self, option: SquadOption, obs: dict, hands: InterfaceState) -> list[Candidate]: ...
```

This directly guarantees **experimental falsifiability**: e.g., to test whether a strict concept bottleneck loses strength vs. a leaky neural network, you swap `BranchScorerProvider` between `ebm_ga2m` (strict concepts) and `side_channel_ablation` (concepts + raw `ValueNet` embedding) on the exact same manifest, seeds, and opponent.

### 4.3 Staged Implementation Roadmap (TvZ Terran Vertical Slice First)

> **Scope discipline:** Pause tuning PvT, PvZ, PvP, ZvZ, and TvT edge cases until TvZ passes Phase 1 and Phase 2 acceptance gates. Keep `tests/test_matchups.py` and `tests/test_live.py` green so the race-agnostic core does not rot.

#### Phase 0 — Plumbing & Clean Slate (1 week)
- Unify feature/concept extraction into one shared module imported by both `ingest/` and `gary/` (for the new concept and strategy pipelines).
- Define `gary/agent/contracts.py` (`ConceptState`, `StrategyState`, `SquadOption`, `BranchScore`) and register the new `gt_ns` manifest line in `gary/agent/manifests.py`.
- Reconcile standing repo rules with the user (see Section 6.2).

#### Phase 1 — TvZ Strategic Vertical Slice: Prove G3 + G5 Fast (2 weeks)
1. **Supervised Factored Opponent Concept Model (TvZ Terran):** Train boosted trees / lightweight NN on fog-filtered modern TvZ resim to output calibrated `P(enemy_opening)`, `P(enemy_tech_lines: spire/lurker/fast_3rd/early_pool)`, `E[enemy_workers, enemy_army]`, and `P(imminent_threat)`. Gate: held-out Brier score / ECE calibration curve per minute (2:00–12:00) + calibration check on Gary-vs-Gary games.
2. **Factored `StrategyState` + Replay Recipe Card:** Sample a real pro TvZ game of the chosen build (or accept `--from-replay <path>`, directly delivering G3's *"play the build from this replay"*) as the concrete opening timing anchor, paired with factored `active_tech_lines` and `posture`. First run **log-only** alongside `MacroNet`—marking every decision on-card, off-card, or late-and-by-what (money, busy building, hands: already recorded)—then let the Strategy Trunk hold one-off tech, expansion, and reactive defense milestones in place of `odds_mass`/`tech_min_p`/`answers.py`, driven by **counted pro matchup and sighting tables** (e.g., *"after first seeing a Spire, pros build a turret within 60 s in p% (n)"*, turning ad-hoc answers into printable data-counted rules).
3. **Five Templated Learner Q&As + Counterfactual Replay Verifier:** Implement `eval/coach.py` over the structured decision records (no LLM yet). Verify via `eval/pairs.py` counterfactual replay: removing or flipping the cited concept/fact changes the trunk's chosen branch.
4. **Acceptance Gate:** Play **3 live TvZ games** (human vs. `gt_ns`) and inspect the 5 Q&As per game. Must pass counterfactual faithfulness, hold belief calibration, and feel meaningfully more coherent/teachable than `gt1dev`. If answers are still unhelpful, we learn that in 2 weeks rather than at P5.

#### Phase 2 — Tactical Squad Options & Clean NN Leaf Ownership (2–3 weeks)
1. **Persistent Squad Options:** Implement `TacticalOptionProvider` (`STAGE`, `REGROUP`, `TIMING_PUSH`, `CONTAIN`, `HARASS`, `DEFEND`, `DISENGAGE`, `SCOUT`, `CLEAR_FINISH`) using `BranchScorerProvider` (`counted_table` / `ebm_ga2m`) over relational tactical concepts. Retire `calm.py`, `hunt4`, and uncoordinated 5 s `commit` grid draws.
2. **Goal-Conditioned NN Leaves:**
   - Condition `RoleNet` (and `ModeModel`/`StimModel`) on the active Squad Option; enforce exclusive unit leases (no priority-3 rule hijacks).
   - Wrap remaining unlearned micro jobs (`Pull`, `Load`, `Repair`, `Detect`) as explicit, isolated option-scoped leaf skills (`bounded_rule_skill`) so they are traceable and replaceable 1-for-1.
3. **Bilevel Verification & Bounded Leaf RL Pilot:**
   - Freeze Tier 2 Trunk. Run the pipe check (`train/roles_rl.py --pipe`) on option-leased units (verify shifted logits cleanly move execution and local reward with zero stop-gap interference).
   - Run one **bounded local skill RL test** (e.g., 20 s `ENGAGE` or `DISENGAGE` sub-episodes) to test whether clean unit ownership + bounded horizons finally unlock leaf RL gains on workstation compute.
4. **Acceptance Gate:** `gt_ns` closes won games cleanly without `--gg`, matches or beats `gt1` in 96 paired TvZ games (or falls within pre-written MDE while decisively winning on human live-game feel), and passes Q&A #4 (*"Why did you attack/hold/retreat?"*) in 3 live human games.

#### Phase 3 — Offline Neural → Symbolic Discovery Loop & Ceiling Audit (2 weeks)
1. **Measure the Faithfulness vs. Strength Ceiling:** Train `ebm_ga2m` (strict concepts) vs. `side_channel_ablation` (concepts + unconstrained `ValueNet` representation) on held-out TvZ replays and self-play paired branches. Quantify the exact residual gap!
2. **First Residual-Driven Concept Invention Pass (`ARCHITECTURE.md` §7.6):** Cluster top residual games/moments, inspect with LLM + human review, implement 2–3 newly discovered relational concepts, and verify they shrink held-out residuals.
3. **Phase-Level OOD Novelty Detector (`taxonomy/` v3):** Train a lightweight trajectory encoder on sliding phases; verify that holding out one known modern build (e.g., 1-1-1 or 3-hatch lurker) triggers the OOD novelty alert instead of silently merging into another cluster.

#### Phase 4 — Skill Slider (*h*), LLM Narrator, and Multi-Race Scaling
- Fit `HumanProfile` (*h*) across lower rating bands (APM, reaction delay, arbiter macro/micro shares, concept-noise/lapse rates) so G4 works.
- Layer an optional LLM Narrator strictly citing verified record IDs over Phase 1–2 templates.
- Port the exact same contracts (`ConceptState`, `StrategyState`, `SquadOption`) to Zerg (`gz_ns`) and Protoss (`gp_ns`) using race-keyed tables and data.

---

## 5. Honest SOTA Limits, Open Research Questions & Candidate Novel Solutions

### 5.1 Brutal Honesty: Where Published SOTA Stops vs. Where Gary Lives

Reviewing agents should **not** assume the cited literature has solved StarCraft scale. Every major neuro-symbolic paper cited in Section 3 was demonstrated on vastly simpler environments:

| Literature Family | Verified Benchmarks in Published Papers | Gap to Full-Game StarCraft: Brood War |
|---|---|---|
| `DreamCoder` (Ellis et al., 2021) / `LILO` (Grand et al., 2024) | List processing, regexes, Logo graphics, ARC-like puzzles | Deterministic worlds with exact pass/fail verifiers; BW has 30-min noisy, confounded, adversarial outcomes |
| `SCoBots` (Delfosse et al., 2024) / `NUDGE` (Delfosse et al., 2023) | Atari (*Pong*, *Seaquest*, *Kangaroo*) | Fully observable 2D arcade, tiny object counts, no tech trees or hidden adversarial plans |
| `Silver et al. (2022)` / `VisualPredicator` (Liang et al., 2025) | Tabletop robotics (4–10 blocks, kitchen pick-and-place) | Single-agent, 5–20 step horizons, crisp boolean postconditions (`Holding(A)`), no real-time multi-front attention bottleneck |
| `AlphaStar` (Vinyals et al., 2019) | Full-game SC2 (Grandmaster) | Pure black-box neural + massive distributed TPU league; fails G5 (explainability) and workstation compute |

**Implication:** Building Gary is **not** pet-project engineering—it is a genuine stress test of whether the Neuro-Symbolic Sandwich scales to real-time, partially observable, adversarial, continuous-control systems.

### 5.2 Five Open Questions We Must Answer Empirically

1. **Q1 (Faithfulness vs. Strength Ceiling):** How large is the performance gap between a strict 30–60 concept bottleneck and an unconstrained neural evaluator in Brood War? Does the residual flatten after ~40 relational concepts, or does BW contain irreducible tacit spatial intuition that caps a strict bottleneck well below strong human play?
2. **Q2 (Soft Concept Leakage in Sequential Play):** When Perception outputs continuous probabilities (`P(2h_muta) = 0.62`), can downstream learned branch scorers (`ebm_ga2m`, `concept_mlp`) remain genuinely faithful under intervention, or do they exploit subtle calibration correlations as hidden leakage (Havasi et al., 2022; Marconato et al., 2023)?
3. **Q3 (Interruptible Multi-Front Options under Shared Human Hands):** How should concurrent squad options (`TIMING_PUSH` at front + `DEFEND` drop in main + `MACRO` at home) share a single camera/APM bottleneck (`Attention Arbiter`) so that human-like mistakes emerge without corrupting option-level credit assignment?
4. **Q4 (Causal vs. Confounded Strategy Selection):** Pro replay win rates are heavily confounded (pros choose an all-in *because* they read a winning state). How accurately can propensity weighting (Swaminathan & Joachims, 2015) + limited workstation self-play interventions separate causal counter-play from observational bias?
5. **Q5 (Bounded Leaf RL Viability):** Once leaf stop-gaps are removed and options isolate 15–45 s localized goals, does RL over NN micro leaves (`RoleNet`) actually beat imitation + rules under human-hand noise, or does human-interface stochasticity still swamp local policy gradients?

### 5.3 Where Novel Solutions May Be Needed (Candidate Directions Beyond Literature)

If/when off-the-shelf methods hit walls on Q1–Q5, four candidate novel mechanisms fit Gary's unique capabilities:

1. **Counterfactual-Replay-Verified Concept Discovery (Addressing Q4 & DreamCoder's Verifier Gap):**
   - Unlike standard observational datasets, Gary has a **deterministic branching OpenBW simulator** (`eval/pairs.py`). When offline residual clustering + LLM inspection proposes a candidate causal concept/rule (*"against Nexus-first on cross spawn, switching to 2-Fac Vulture beats standard bio"*), Gary can automatically run **targeted paired counterfactual branches** on 30–50 matching game states—turning observational hypotheses into cheap *interventional causal verification* before promoting a concept to the symbolic library.
2. **Anchor-and-Delta Dual Strategy Representation (Addressing Q1 & New Meta Builds):**
   - Represent any build as `(exemplar_trajectory_anchor, factored_symbolic_deltas)`—a real pro replay supplies the concrete fine-grained timings (handling arbitrary novel seasonal builds immediately), while the factored symbolic layer expresses *deviations and transitions* relative to that anchor (`+2 turrets because P(muta) > 0.7`, `+Siege Tank transition because Lurker scouted`). This preserves 100% expressiveness for new builds while keeping explanations crisp (*"Following replay X's 1-Rax FE, except I added 2 turrets early because..."*).
3. **Attention-Budgeted Semi-MDP Options (Addressing Q3):**
   - Extend classical options $(I_\omega, \pi_\omega, \beta_\omega)$ with an **attention-share request** $a_\omega \in [0, 1]$ handed to the `Attention Arbiter` (modulated by `HumanProfile` *h*), and log **effective attention received** per option execution. Option-level credit assignment and explanations explicitly separate *"bad option choice"* from *"good option starved of APM by a simultaneous drop."*
4. **Intervention-Driven Interactive Refinement (Addressing Q1 & G5 Together):**
   - During post-game human sparring reviews, when a player challenges Gary's trace (*"No, seeing a 3:10 Lair with 2 hatcheries means 2-hatch muta, not 3-hatch lurker"* or *"You should have disengaged here"*), capture the human correction as a structured **concept or branch preference record** (`annotate/`), directly fine-tuning the Perception calibrator or Branch Scorer on high-leverage real-game errors without full RL retraining.

---

## 6. Adversarial Multi-Agent Review Kit

This section is explicitly structured so multiple reviewing agents can debate, red-team, and refine this plan before implementation starts.

### 6.1 Falsifiable Hypotheses & Kill Criteria

| Core Bet | Verification Test | Kill / Pivot Trigger | Fallback Action |
|---|---|---|---|
| **H1 (Phase 1):** Factored Opponent Model + Recipe Card + Counted Tables produce genuinely useful learner coaching answers | 3 live human TvZ games + 5 Q&As evaluated by the user + counterfactual replay check | Counterfactual consistency < 80%, OR user judges answers still unhelpful/generic after Phase 1 (2–3 weeks) | Inspect whether failure is in concept granularity (add relational concepts) or recipe-card adherence (tighten strict-mode macro execution) |
| **H2 (Phase 2):** Persistent Squad Options + conditioned NN leaves eliminate army tug-of-war without leaf stop-gaps | 96 paired TvZ games vs. `gt1` + 3 live games + `pipe_table.py` | `gt_ns` trails `gt1` by > 0.10 paired score AND feels worse in live games after option tuning | Keep symbolic options for strategic timing/regrouping, but use `ArmyNet` heatmaps as a continuous target proposal inside `TIMING_PUSH`/`CONTAIN` |
| **H3 (Phase 2):** Removing leaf stop-gaps + bounding horizon to 15–45 s options unlocks positive leaf RL signal | Pipe check + held-out option-episode A/B pairs (MDE written upfront) | Shifted logits move commands, yet 2 bounded RL runs end at chance on held-out episodes | Accept that workstation RL stays at **Tier 2 (options/strategy)** only; keep Tier 3 leaves purely supervised + `DAgger`-style filtered imitation |
| **H4 (Phase 3):** Strict concept bottleneck stays close to unconstrained neural strength | Held-out TvZ replay prediction + 96 paired games: `ebm_ga2m` (strict) vs. `side_channel_ablation` | Strict concept bottleneck loses > 0.12 paired score even after 2 residual concept-invention iterations | Adopt a **calibrated hybrid** where strict concepts own *strategic branches* (build/tech/expand/push-or-hold) while continuous spatial features assist *where* to execute |

### 6.2 Standing Repo Decisions to Reopen

| Standing Rule | Recorded Rationale | Proposed Change in Refocus |
|---|---|---|
| **Work every matchup at once** (`TODO.md`, 2026-11-12) | One matchup hides bugs others expose | Keep race-agnostic code & `test_matchups.py`; build & prove Phase 1–3 in **TvZ Terran only** first |
| **All symbolic rules are "stop-gap debt"** (`AGENTS.md`) | Decisions should eventually be learned | Replace binary with a **3-way classification**: (1) *Leaf overrides* = debt (eliminate); (2) *Data-counted symbolic trunk rules & option contracts* = core architecture (keep & grow); (3) *Temporary option-scoped rule skills* = tracked for 1-for-1 NN leaf replacement |
| **Fidelity before wins** (`AGENTS.md`) | Prevent abandoning pro-like changes due to execution bugs | Keep as a guardrail against discarding valid fidelity fixes, **add a stopping rule**: marginal gap metrics (`gap_windows.py`, `pipe_table.py`) are anomaly detectors, not the work queue; prioritize faults seen in live/watched games or blocking coaching Q&As |
| **Narrator waits for "complete records"** (`ARCHITECTURE.md` §8) | Prevent hallucinated reasons | Build templated Q&As + counterfactual replay verifier **in Phase 1** as the architectural compass |
| **Two builds per race (`gt1` vs. `gt1dev`)** | Dev build judges learning without stop-gaps | Freeze `gt1` as baseline; stop adding marginal BC patches to `gt1dev`; build the refocused architecture cleanly as `gt_ns` |
| **Headless rounds as primary loop** | Need paired statistical power | Run **≥1 live human or watched game per milestone** before running 48/96-game headless rounds |

### 6.3 Shared Evaluation Rubric

Proposals and revisions should be evaluated against six criteria:
1. **Coaching Utility (G5):** Would a D/C/B-rank Brood War learner actually learn StarCraft from Gary's post-game answers, and are those answers counterfactually faithful?
2. **Coherence & Sparring Feel (G1):** Does it eliminate visible bot-like incoherence (scattered rallies, cancelled retreats, ignoring scouted tech, failing to finish won games)?
3. **Steerability & Intervenability (G3):** Can a user request a specific build, replay, or adaptive branch reliably?
4. **Learnability / Pipe Cleanliness:** Does it preserve exclusive unit control and clean credit assignment for future NN/RL improvements?
5. **Time-to-Falsifiable-Signal:** How quickly (in weeks, on workstation compute) can the core riskiest assumption be tested and either validated or killed?
6. **Modularity (G6):** Can individual components (perception, branch scorer, option policy, leaf skills) be swapped and A/B tested via manifest without rewrites?

---

## 7. Verified References

Every citation below was verified directly against published proceedings / arXiv records for exact authorship, venue, and supported claims:

1. **Alshiekh, M., Bloem, R., Ehlers, R., Könighofer, B., Niekum, S., & Topcu, U. (2018).** *Safe Reinforcement Learning via Shielding.* AAAI 2018 (`arXiv:1708.08611`). — Formalizes preemptive vs. post-posed runtime shielding; grounds why post-posed leaf overrides distort policy-execution alignment compared to preemptive option scoping.
2. **Bacon, P.-L., Harb, J., & Precup, D. (2017).** *The Option-Critic Architecture.* AAAI 2017 (`arXiv:1609.05140`). — Formalizes option initiation, intra-option policies, and termination gradients; grounds option persistence/termination design.
3. **Bastani, O., Pu, Y., & Solar-Lezama, A. (2018).** *Verifiable Reinforcement Learning via Policy Extraction* (`VIPER`). NeurIPS 2018 (`arXiv:1805.08328`). — Policy extraction into decision trees; cited as an alternative programmatic-policy paradigm suited to discrete trunks but insufficient for continuous BW micro leaves.
4. **Delfosse, Q., Shindo, H., Dhami, D. S., & Kersting, K. (2023).** *Interpretable and Explainable Logical Policies via Neurally Guided Symbolic Abstraction* (`NUDGE`). NeurIPS 2023 (`arXiv:2306.01439`). — Neurally guided differentiable logic policies on Atari; cited as an alternative pure-logic paradigm and SOTA scope benchmark.
5. **Delfosse, Q., Sztwiertnia, S., Rothermel, M., Stammer, W., & Kersting, K. (2024).** *Interpretable Concept Bottlenecks to Align Reinforcement Learning Agents* (`SCoBots`). NeurIPS 2024 (`arXiv:2401.05821`). — Introduces successive and relational concept bottlenecks in RL to enable human inspection, pruning, and alignment; evaluated on Atari.
6. **Ellis, K., Wong, C., Nye, M., Sablé-Meyer, M., Cary, L., Morales, L., Hewitt, L., Solar-Lezama, A., & Tenenbaum, J. B. (2021).** *DreamCoder: Bootstrapping Inductive Program Synthesis with Wake-Sleep Library Learning.* PLDI 2021 (`arXiv:2006.08381`). — Wake-sleep abstraction compression + neural recognition model; motivates offline library growth while highlighting its exact-verifier assumption.
7. **Grand, G., Wong, L., Bowers, M., Olausson, T. X., Liu, M., Tenenbaum, J. B., & Andreas, J. (2024).** *LILO: Learning Interpretable Libraries by Compressing and Documenting Code.* ICLR 2024 (`arXiv:2310.19791`). — Combines symbolic abstraction compression (`Stitch`) with LLM auto-documentation (`AutoDoc`) to build human-readable concept libraries.
8. **Havasi, M., Parbhoo, S., & Doshi-Velez, F. (2022).** *Addressing Leakage in Concept Bottleneck Models.* NeurIPS 2022 (OpenReview `tglniD_fn9`). — Diagnoses concept leakage and broken interventions from insufficient concept sets and soft probability encoding; introduces Side-Channel CBMs (used here as our offline/ablation benchmark for measuring the strength ceiling).
9. **Kautz, H. (2022).** *The Third AI Summer.* AI Magazine, 2022 (AAAI Robert S. Engelmore Memorial Lecture). — Canonical taxonomy of neuro-symbolic integration patterns (`Neuro → Symbolic`, `Symbolic[Neuro]`, `Neuro | Symbolic`, etc.).
10. **Koh, P. W., Nguyen, T., Tang, Y. S., Mussmann, S., Pierson, E., Kim, B., & Liang, P. (2020).** *Concept Bottleneck Models.* ICML 2020 (`arXiv:2007.04612`). — Foundational CBM formulation establishing concept-level transparency and test-time human intervention.
11. **Levy, A., Konidaris, G., Platt, R., & Saenko, K. (2019).** *Learning Multi-Level Hierarchies with Hindsight* (`HAC`). ICLR 2019 (`arXiv:1712.00948`). — Analyzes multi-level non-stationarity in hierarchical RL when lower and higher policies co-adapt; grounds staged/bilevel training and hindsight goal relabeling.
12. **Liang, Y., Kumar, N., Tang, H., Weller, A., Tenenbaum, J. B., Silver, T., Henriques, J. F., & Ellis, K. (2025).** *VisualPredicator: Learning Abstract World Models with Neuro-Symbolic Predicates for Robot Planning.* ICLR 2025 Spotlight (`arXiv:2410.23156`). — Neuro-symbolic predicate invention for abstract world models in robotics planning; illustrates both modern predicate-invention direction and current tabletop-scale SOTA limits.
13. **Mahinpei, A., Clark, J., Lage, I., Doshi-Velez, F., & Pan, W. (2021).** *Promises and Pitfalls of Black-Box Concept Learning Models.* ICML 2021 Workshop on Explainable AI (`arXiv:2106.13314`). — Demonstrates how soft concept representations leak non-concept information, undermining faithfulness.
14. **Marconato, E., Teso, S., Vergari, A., & Passerini, A. (2023).** *Not All Neuro-Symbolic Concepts Are Created Equal: Analysis and Mitigation of Reasoning Shortcuts.* NeurIPS 2023 (`arXiv:2305.19951`). — Formalizes reasoning shortcuts (high accuracy via corrupted concept semantics); motivates direct hindsight supervision of Gary's concept extractors from re-simulated ground truth.
15. **Nori, H., Jenkins, S., Koch, P., & Caruana, R. (2019).** *InterpretML: A Unified Framework for Machine Learning Interpretability.* (`arXiv:1909.09223`). — Introduces Explainable Boosting Machines ($\text{GA}^2\text{M}$), glass-box additive + pairwise interaction models avoiding flat Cartesian table explosion while maintaining exact feature attribution.
16. **Ontiveros, R. C., Giannini, F., Gori, M., Marra, G., & Diligenti, M. (2025).** *Grounding Methods for Neural-Symbolic AI.* IJCAI 2025 (`arXiv:2507.08216`). — Formalizes the combinatorial grounding bottleneck in NeSy systems and parameterized/lifted grounding trade-offs.
17. **Ross, S., Gordon, G. J., & Bagnell, J. A. (2011).** *A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning.* AISTATS 2011 (`DAgger`). — Establishes compounding covariate shift in behavioral cloning and why closed-loop state coverage matters.
18. **Rudin, C. (2019).** *Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead.* Nature Machine Intelligence, May 2019. — Argues against post-hoc black-box explanations in favor of inherently interpretable decision models.
19. **Silver, T., Athalye, A., Tenenbaum, J. B., Lozano-Pérez, T., & Kaelbling, L. P. (2022).** *Learning Neuro-Symbolic Skills for Bilevel Planning.* CoRL 2022 (`arXiv:2206.10680`). — Combines symbolic operators with learned continuous low-level skills for long-horizon robotics planning.
20. **Sutton, R. S., Precup, D., & Singh, S. (1999).** *Between MDPs and semi-MDPs: A framework for temporal abstraction in reinforcement learning.* Artificial Intelligence, 1999. — Foundational formalization of temporally extended options and semi-MDPs.
21. **Swaminathan, A., & Joachims, T. (2015).** *Batch Learning from Logged Bandit Feedback through Counterfactual Risk Minimization.* JMLR / ICML 2015. — Propensity-weighted off-policy learning and variance regularization for confounded logged outcomes.
22. **Vinyals, O., Silver, D., & the DeepMind AlphaStar Team (2019).** *Grandmaster level in StarCraft II using multi-agent reinforcement learning.* Nature, November 2019. — Demonstrates full-game StarCraft mastery via black-box multi-agent deep RL with massive league compute; serves as the pure-neural contrast point.
