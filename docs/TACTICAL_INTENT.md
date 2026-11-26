# TacticalIntent v0 — the 0-game read and the design (Phase 2, docs/REFOCUS.md §3.4)

Status: offline results and a design for review (2026-11-26). Nothing here is wired into play; no game has been played
for it. The numbers come from `eval/alone.py` (replays re-simulated, joined with the game records) and
`train/tactical_intent.py` (the labeller and the model, on the army dataset's commitment ticks).

## 1. What leaves Gary's army incoherent (0 games)

**Sources:**
- Gary: gate 4's 96 games (`G4299a`, `gt0.53dev`, against `gz1`, 30 minutes).
- The pros: 60 modern TvZ pro games, re-simulated through the same code.
- The two live LAN games of 2026-11-25.

**Definitions** (`eval/alone.py`):
- A unit is *alone* when no other Terran fighter is within 6 tiles at its last look. This is `gary/agent/sightings.py`'s
  measure.
- A *late arrival* is `eval/attacks.py`'s.

| | Gary (G4299a) | Pros | Live game 1 | Live game 2 |
|---|---|---|---|---|
| Fighter deaths alone | **21%** of 10,395 (games' mean 0.25) | **9%** of 6,913 (games' mean 0.10) | 10 of 10 | 14 of 27 (replay; the records count 13 of 19) |
| ...outnumbered there (Zerg supply within 8 tiles above own) | 78% | 73% | | 79% |
| Fighter samples alone, 5–20 min | 0.076 | 0.042 | | 0.65 |
| Ground samples in no cluster the commit model asks (< 4 supply) | 0.127 | 0.074 | | 0.69 |
| Attacks a game | 4.9 | 3.4 | | |
| The army's share at an attack (median) | **0.30** | **0.50** | | |
| Late arrivals per fighter there | **0.128** | **0.052** | | |
| Late arrivals produced after the attack began | 14% | 28% | | |

The older figures in the brief (48% alone, 0.27 late arrivals) are from earlier builds and other measures. On today's
build and one definition the gap is 21% against 9% and 0.13 against 0.05. The pros' side has no bunker exclusion (no
records: a marine loaded into a bunker and never seen again counts as a death), which inflates their deaths a little,
so the gap is if anything wider.

**Units dying alone in gate 4 (2,207), by what left each one alone.** A unit was either left alone in its last 10 s,
or was alone already and was brought there by its last order 10–90 s before (the roles' orders aside):

| Cause | Share of deaths alone | The brief's bucket |
|---|---|---|
| Left alone: its neighbours died first (a fight lost) | 29% | — (the fight itself) |
| Left alone: its neighbours were moved off by the role layer (per-unit roles split the group) | 15% | (e) |
| Left alone: its neighbours moved off with no order, or by other layers | 10% | — |
| Alone already: a commit order brought it | 15% | (f) |
| ...of which the commit order moved a straggler (the unit now in no asked cluster) | 9% | (f) |
| Alone already: no order, while in a cluster the commit model asks and kept | 8% | (b) |
| Alone already: the calm layer moved it | 8% | (c) |
| Alone already: no order, never in an asked cluster (under 4 supply) | 6% | (a) |
| Alone already: the reinforce rule sent it | 2% | (d) |
| Unknown (no look 10 s before) | 8% | — |

**By the last order before death** (the record of who held the unit): the role layer 81%, the reinforce rule 4%,
commit orders swept or re-taken 4%, everything else 2% or less. The role layer holds nearly every unit in contact, so
this says who was fighting, not what made the unit alone. Of the deaths alone held by `CLOSE_IN`, 92% had two or more
enemies near.

The pros' split is much the same (left alone 58%, alone already 31%, unknown 11%). Gary simply has more of both:
- Left alone: 11% of all deaths against the pros' 5%.
- Alone already: 8% against 3%.

**The brief's hypotheses, measured:**
- **(a) commit's under-4-supply cutoff:** 6% of deaths alone. The ground units in no asked cluster are 0.127 of
  samples against the pros' 0.074.
- **(b) commit drawing keep:** not the defect. Gate 4's commit model keeps 57% of its questions; the pros' clusters
  keep 72% (army dataset v5, from 5:00). With no commitment in force, Gary keeps 82% and the pros 93%. Live game 2's
  "keep 6 of 6 at 93–97%" was asked only about clusters with no commitment, which is the pros' case. In 8% of deaths
  alone the unit sat in a kept cluster without an order.
- **(c) the calm layer:** 8%.
- **(d) the reinforce rule:** 2–4%. Small, but 87% of those deaths were outnumbered.
- **(e) the roles:** the second-largest mechanism. Per-unit roles split groups (15% of deaths alone), and `CLOSE_IN`
  sends outnumbered units in.
- **(f) cluster stealing and stragglers:** 15% brought by a commit order, 9% of them stragglers swept from elsewhere.
  Separately, 46% of late arrivals were sent by a cluster's own `commit engage`: each cluster decides alone, so the
  army arrives cluster by cluster.

**The largest single cause** is fights taken outnumbered (29% left alone as the others died, 78% outnumbered). It goes
with attacks made with 30% of the army where the pros bring 50%. That is a top-down decision (who goes, and when the
group is together), which no leaf owns today.

**The live games are another problem.** Gary's army in the macro's records:
- Game 1: 0–2 units at every minute, and the commit model was never asked.
- Game 2: 2–5 units at 4–14 minutes; the commit model was asked 6 times, all after 10:18.
- Gate 4: a median 11 units at 8:00 and 17 at 10:00.

The macro's count leaves out marines inside bunkers. Game 2's replay, re-simulated, agrees: 2–4 fighters in view from
4:30 to 14:30, with 1–2 bunkers whose marines the count can't see. Game 1 left no replay.

With so few units every death is likely alone and no tactical layer can gather an army. Game 2's poverty is partly
diagnosed already, and fixed in `gt0.54dev`:
- its card's reserve held money from 10:26 to 14:48;
- the turret flood took 14 turrets;
- Comsat and upgrades were masked.

Game 1 played style 2 with no card and is not diagnosed. What starved production there (the hands over LAN, the
human's raids, the style-2 macro) is its own 0-game read, before any live verdict on the intent layer.

## 2. The intents, event-grounded (train/tactical_intent.py)

**The data.** The labeller reads the pros' army dataset (v5): every 5 s, each army cluster with the next 5 s's order
(keep, engage or move, and its cell), the commitment in force, and the 16×16 grids of own and enemy army, buildings
and losses. One intent per tick is given to the player's main ground cluster. The rules, written before reading:

| Kind | Event |
|---|---|
| `DEFEND_BASE` | Enemy fighters at or next to a home cell (in sight, seen in 30 s, or own losses there), and the cluster is sent within a cell of that cell, or stands within 2 cells of it |
| `ATTACK` | Sent or committed to a cell next to known enemy presence (the dataset's engage), not a home cell |
| `RETREAT` | Moved 2 or more cells nearer its main, from enemy fighters within 2 cells or fresh losses |
| `GATHER` | Any other move: staging, joining, back home calm, taking a position |
| `HOLD` | No commitment in force and no new order |

**The pros: 2,422 modern TvZ games, 298,704 ticks.**

| | DEFEND_BASE | ATTACK | RETREAT | GATHER | HOLD |
|---|---|---|---|---|---|
| Pros, share of ticks | 25.0% | 36.4% | 3.2% | 28.5% | 6.9% |
| Gary G4299a (96 games, 22,989 ticks) | 15.7% | 43.3% | 1.2% | 27.6% | 12.1% |
| Pros, hold median / p75 (s) | 20 / 40 | 20 / 40 | 5 / 10 | 15 / 30 | 15 / 35 |
| Gary, hold median / p75 (s) | 20 / 35 | 25 / 61 | 10 / 10 | 20 / 40 | 25 / 45 |
| Pros, episodes a game | 4.8 | 7.2 | 2.1 | 7.6 | 1.5 |
| Gary, episodes a game | 6.5 | 11.9 | 1.5 | 10.4 | 3.5 |

**By time.** The pros defend most at 5–10 minutes (34% of ticks; Gary 18%) and attack most after 10 (46–52%).
Gary holds at 20+ minutes in 16% of ticks against the pros' 4%. The commonest switches are the same for both:
- GATHER→ATTACK: pros 21%, Gary 22%.
- ATTACK→GATHER: pros 18%, Gary 19%.

Live game 2 had 48 main-cluster ticks in 15 minutes (the army was mostly under 4 supply), 94% of them `DEFEND_BASE`.

**What this says.** Gary's *choice* of intent, read from its main cluster, is near the pros' mix. Its defects are in
carrying the intent out:
- the share of the army that goes;
- units left out or swept in;
- groups split in contact.

So an intent layer that only picked kinds would change little. It has to own *who is in the intent* and *when it
moves*.

**The sanity checks.**
- **Against an independent event:** in the 60 re-simulated pro games, eval/attacks.py detects an attack when 3 or
  more fighters reach a Zerg building. 80% of those attacks (163 of 203) fall within 15 s of an `ATTACK` tick. The
  other way, 36% of `ATTACK` episodes of 10 s or more meet a detected attack. The rest engage the Zerg army or a unit
  away from its buildings: the dataset's engage is "next to enemy presence", not "at a building".
- **The tracked destination:** on Gary's v6 ticks (which carry the commitment's real target, `tick_ctarget`), the
  labeller's destination for a kept commitment is within a cell of it in 75% of 14,008 ticks; none was tracked in 3%.
- **A deviation from the written rule:** the code gives `HOLD` whenever no destination is tracked. In 9% of the pros'
  `HOLD` ticks and 11% of Gary's, a commitment was still in force (its order before the main cluster was tracked).
  To fix in the labeller's next version: label such ticks by the commitment's kind.
- **By hand:** 15 sampled held-out moments, three of each kind, read as their labels. One `GATHER` moment had losses
  at home: the main cluster was elsewhere, as another cluster defended.
- **Threat size:** in the 41 games dumped for reading, 34% of `DEFEND_BASE` ticks had no enemy fighter on a home cell
  itself (the threat was next to one, or was a loss there), and 12% had at most 2 supply of enemy (the "two
  zerglings" case).
- **Dataset versions:** the pros' ticks are army dataset v5, Gary's are v6, where the flyers are clustered apart. The
  main *ground* cluster is labelled in both, so the comparison holds for the ground army. Gary's flyers (wraiths,
  vessels) are outside it.

**Contract mapping** (`gary/agent/contracts.py` `TacticalIntent`; race-agnostic: the kinds read only army, buildings
and losses):

| Field | Content |
|---|---|
| `kind` | One of the five above |
| `units` / `lease_id` | The leased group: the clusters and units it owns |
| `target` | A cell from `ArmyNet`'s 16×16 heatmap, restricted to the kind's side: enemy-presence cells for `ATTACK`, threatened home cells for `DEFEND_BASE`, cells nearer the main for `RETREAT`, the rest for `GATHER`, none for `HOLD` |
| `started_frame` | When it began |
| `end_condition` | The kind's: the target reached and its hold done; the threat gone for 10 s; ... |
| `preempt_by` | `DEFEND_BASE` over `GATHER` and `HOLD` (for the detachment only); `RETREAT` over `ATTACK` |
| `trigger_record_id` | The records' decision line |

## 3. The offline model P(intent | state, belief)

**The setup.**
- **Data:** the pros' ticks, 80/20 by game: 1,951 games to train, 469 held out (55,162 ticks).
- **Inputs:** the state at the tick, and the intent of the tick before with how long it has held.
- **Belief inputs:** the cross-fitted plan belief at the tick (P(spire first), P(lurker first)). It exists only at
  2:30–10:00, which is 57% of the held-out ticks.
- **Model:** sklearn gradient-boosted trees.

| Held-out pros | Log-loss | Brier | Accuracy | ECE |
|---|---|---|---|---|
| Time and map (minute bucket × map) | 1.279 | 0.685 | 0.411 | 0.010 |
| The tick before (persistence) | 0.631 | 0.302 | 0.823 | 0.003 |
| **Model** | **0.472** | **0.247** | **0.845** | **0.005** |

**Most of that is the labeller's own rule.** `HOLD` and a standing `DEFEND_BASE` are set by fields that are also
inputs: the commitment, the threatened cells and the cluster's distance to them. So the honest score is where the pro
gave a new order in the next 5 s (`tick_label` not keep), 17,982 held-out ticks:

| Held-out pros, ticks with a new order | Log-loss | Accuracy |
|---|---|---|
| Time and map | 1.266 | 0.401 |
| **Model** | **1.028** | **0.589** |

On the 37,180 ticks with no new order, the model scores 0.203 (accuracy 0.969), largely by definition. **It beats the
baseline where the decision is made, by less than the table above suggests.**

**Calibration.** When the model's confidence is 0.9–1.0 (43% of ticks) it is right 0.95 of the time. At 0.8–0.9 (29%)
it is right 0.85, at 0.6–0.8 (22%) 0.72, and at 0.4–0.6 (6%) 0.54. Recall by intent:

| Intent | Recall | Mean P |
|---|---|---|
| HOLD | 0.98 | 0.91 |
| DEFEND_BASE | 0.90 | 0.82 |
| ATTACK | 0.85 | 0.76 |
| GATHER | 0.81 | 0.71 |
| RETREAT | 0.45 | 0.35 |

**The switches.** On the 18% of ticks where the intent changes, the single model is worse than the baseline (log-loss
1.90 against 1.45): it leans on persistence. Split into two heads, it beats it:
- **Hazard head** (does the intent change in the next 5 s): AUC 0.784, log-loss 0.374 against 0.467 for a constant.
- **Next-intent head**, given a switch, with the intent before as an input: log-loss **0.564**, accuracy **0.745**;
  time-only baseline 1.358 and 0.358. On the switches with a new order (7,874), 0.585 against 1.292, accuracy 0.730.

The design uses the two heads, decoded as the pros' modes are: hold the current intent at the pros' hazard, then
draw the next one.

**The belief adds nothing measurable:** 0.469 without it, 0.472 with it; on switches, 0.565 and 0.564. The inputs stay
(the contract carries the belief, and a later directive may read it), but no claim rests on them.

## 4. How the leaves obey the intent (the design; nothing wired yet)

**The principle.** The intent layer owns the decision of what the army does and with whom. The leaves keep their
decisions inside it, conditioned on it, instead of a rule overriding them afterwards.
- `gather` and `anchor` failed as interceptors: they froze `commit` and pulled every unit to a raw centre of mass.
- Here, every leaf reads the active intent of the group its unit is leased to. Where the leaf is learned, the intent
  is a model input, trained on the pros' labelled ticks. The labels exist for every pro army tick, joined by
  (game, frame).

**The provider** (`gary/agent/tactical.py`, option `intent`; source `intent` in `intents.py`):
- **Asked:** every 5 s.
- **Groups:** one main intent over the army, plus at most two detachments.
- **Lease priority:** over the army layer and calm, under the rules and the roles in contact. Units in contact are
  steered through the roles' conditioning, not over them.
- **Records:** every start and end is a decision line, with its record id, kind, target, units and trigger.

**`DEFEND_BASE`'s size, measured on the pros** (800 games, every cluster at each moment with enemy fighters at or next
to a home cell; defending means sent within a cell of the threat, or standing within 2 cells of it):

| Enemy supply at home | Moments | No cluster defends | Supply defending (median) | Its ratio to the threat (median) | Share of the army |
|---|---|---|---|---|---|
| 0–2 (two zerglings) | 7,431 | 32% | 6 | 9.0 | 0.17 |
| 2–6 | 6,537 | 27% | 7 | 2.2 | 0.26 |
| 6–12 | 4,945 | 27% | 8 | 1.2 | 0.21 |
| 12 or more | 37,598 | 19% | 13 | 0.3 | 0.27 |

The pros send a small detachment whatever the threat: about 6–8 supply, a fifth to a quarter of the army. It grows
slowly with large threats, and in a fifth to a third of the moments nobody goes. They don't size it to 1.5× the
threat. Against two zerglings they send 6 supply (17% of the army), or nothing.

The largest band is inflated by the "seen in 30 s" memory counting a passing army.

So the detachment's size should be learned, not set:
- a model of the defending supply given the threat, the army, the static defense and the minute, fitted on these
  moments;
- its median as the lease's size, nearest units first;
- the main intent carries on with the rest.

The end condition (no enemy at the base for some seconds) should be read from the pros' `DEFEND_BASE` hold lengths
(median 20 s, p75 40 s), not set at 10 s.

**Open decision for the user:** learn the sizing as above, or start from a scripted rule tagged as a stop-gap with its
`AGENTS.md` entry.

**The leaves:**

| Leaf | What it does under the intent | How it is conditioned | Its 0-game check first |
|---|---|---|---|
| **`commit`** | Decides per cluster *whether now*: keep, or go to the intent's target. Its destination is the intent's cell, not a fresh draw per cluster, so the clusters of one intent go to one place. | Retrained (`train/commit.py`) with the intent's kind and target as inputs, from the same army ticks (the pros' label is in the row). Two ways, an **open decision for the user**: (i) conditioning only, the intent as an input and no mask, so `commit` may still disagree, and the pipe check measures how often; (ii) a kind mask, the head allowed only the intent's kinds (`ATTACK`: engage or keep; `GATHER`, `RETREAT`: move or keep; `HOLD`: keep; `DEFEND_BASE`: engage toward the threat or keep). The mask is a veto of the model's other kinds, so it is a stop-gap in `AGENTS.md`'s sense. Recommended: (i) first, with the mask only if the pipe check shows `commit` ignoring the intent. | Held-out log-loss of the kind head with the intent against without; P(engage \| ATTACK) against the pros' |
| **The gather before `ATTACK`** | An `ATTACK` starts from `GATHER` at a staging cell. Clusters leased to it keep until the intent's group holds its share of the army there, a learned stopping point. This is the decision that brings 0.50 of the army, not 0.30. | The share at which the pros go, from their ticks: the army's share within 2 cells of the staging cell at the GATHER→ATTACK switch | The pros' share at the switch; Gary's at its attacks |
| **`calm`** | Moves only units of an intent's group, around the group's middle. A unit alone (more than 6 tiles from any friend) and in no group is sent to join its intent's group instead of a calm hop. | Later, the calm model with the intent as input; v0 routes | The share of calm orders to lone units (56% of the calm layer's orders went to one unit, HS284a) |
| **`roles`** (`RoleNet`) | Micro in contact, conditioned on the intent: in `RETREAT`, close-in should vanish; in `DEFEND_BASE`, fire and close-in near the threat. | The intent's kind as an extra input token, retrained (`train/roles.py`) on the pros' fights joined to their intent by frame. No hand veto. | The pros' role shares by intent; the model's held-out log-loss with and without; `CLOSE_IN` when outnumbered, the pros' against Gary's |
| **The reinforce rule** | Subsumed. A new unit is leased to an intent at birth. A `DEFEND_BASE` detachment at its base takes it if the detachment is short; otherwise it walks to its intent's group. It is never attack-moved alone into a fight. | Membership, not a model | The rule's measure in `AGENTS.md`: deaths with no friend within 6 tiles, against the pros' |
| **`grouping`** | Keys follow intents: key 1 the main intent's group, keys 2–3 the detachments, so an intent's order is one key and one click. Today a commit order is three orders, one per key or box. | Scripted, as the provider slot is (a learned grouping later) | Orders per intent decision; the share of the group in the order |

**Stop-gaps or not** (`AGENTS.md`):
- **The lease routing** is a decoder of the intent model's choice: who is in the group that the model decided on.
- **The commit mask and a scripted detachment size** would be stop-gaps, each with its entry, if chosen over the
  learned versions above.
- **The intent model's own decision** (the kind, the switch, the target) is learned.
- **The reinforce rule's entry** goes when the intent's membership holds its measure with the rule off.

**`eval/coach.py` Q4** will cite the intent first, in plain Brood War English, then the leaves inside it. For example
(its numbers illustrative):

> At 9:12 most of the army, 18 of 24 units, was gathering at the natural's front: it had been since 8:58, after the
> Zerg's attack on the third base was beaten off. In this situation the pros gather 61% of the time and attack 22%.
> Six units were defending the main against four zerglings. At 9:30, with 70% of the army at the gathering point, it
> attacked the hatchery at the Zerg's third. 15 units went in together, and 2 marines arrived 20 s late.

Each figure is linked to its record. Q4 cites:
- the intent's start, its kind and its target in tiles;
- the share of the army leased;
- the trigger;
- the pros' odds from the model;
- the detachments;
- the leaves' decisions inside it;
- the deaths alone with the intent their unit was leased to.

## 5. The checks once approved (written before any game)

**1. The in-memory pipe check** (`tests/test_intent_pipe.py`, about a minute; the paired-branch deep copy of
`tests/test_pairs.py`).
- **The run:** one headless game of `gt1dev+intent` to 12:00. At every 30 s from 5:00, deep-copy Gary once per kind,
  force that intent for 10 s on the copy, and collect the hands' orders.
- **It passes when:**
  1. At least 90% of the leased units' orders in a forced intent point to its target's side (enemy presence for
     `ATTACK`, the threatened base for `DEFEND_BASE`, toward the main for `RETREAT`; none for `HOLD`).
  2. The five arms' orders differ pairwise in at least 80% of the moments.
  3. No lease conflict on a leased unit outside contact.
  4. A forced `DEFEND_BASE` against 2 zerglings leases about the pros' detachment (6 supply, the fitted median) and
     leaves the main intent's units on their orders.
  5. The retrained `commit` and `roles` models' outputs move with the intent input at those moments: the kind head's
     odds move toward the intent's kinds, and `CLOSE_IN` falls under `RETREAT`.

**2. The 16-game screening round** (`gt1dev+intent` against `gt1dev`, both against `gz1`, paired seeds; the ladder
maps, 8 maps × 2 seeds from 4004, 30 minutes, `--gg 0` as gate 4, so no game ends before its attacks; the baseline replayed with the same code and
opponent). The minimum detectable effects use the per-game spread in G4299a (80% power, 5% two-sided, two arms of 16):

| Measure (`eval/alone.py`) | gt1dev now | Pros | MDE at 16 games | Expected | Read as |
|---|---|---|---|---|---|
| Deaths alone (games' mean) | 0.25 | 0.10 | 0.14 | 0.25 → 0.14 or lower | Judged |
| The army's share at attacks | 0.36 | 0.55 | 0.15 | → 0.45 or higher | Judged |
| Late arrivals per fighter there | 0.13 | 0.06 | 0.12 | toward 0.06 | Direction only (48 games to resolve) |
| Intent shares and hold lengths (`train/tactical_intent.py --gary`) | above | above | | per kind nearer the pros (`RETREAT` 1.2% → 3%; `HOLD` at 20+ min 16% → under 8%) | Fidelity, read |
| Q4 answers at 3 moments of 4 games | | | | the intent cited, faithful to the records | Read by the user |
| Paired score (`eval/paired.py`) | | | about 0.2 | not measurably worse | Read, not judged; 48 then 96 per `AGENTS.md` |

## 6. Order of work once approved

1. **Labels into the data.** Join the labeller's intents into the commit and role datasets, then retrain `commit` and
   `roles` with the intent input. The 0-game checks are in the table above.
2. **The provider.** The two-headed intent model (hazard and next intent), its decoder at the pros' hazard,
   `ArmyNet`'s heatmap restricted by kind, the leases, and `DEFEND_BASE`'s detachment sized by a model fitted on the pros' defending moments (or the user's chosen stop-gap). `tests/test_intent_pipe.py`.
3. **The leaves' routing.** Calm, reinforce and grouping. `tests/test_smoke_game.py`, `tests/test_pairs.py`,
   `tests/test_inputs.py`, `tests/test_live.py`.
4. **Coach Q4** on the intent records.
5. **The 16-game screen**, then 48 and 96 per `AGENTS.md`. Separately: the live army-size read (section 1) before any
   live verdict.
