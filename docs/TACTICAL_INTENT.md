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

## 7. Steps 1–3 done (2026-11-26; 0 games)

**The user's decisions:**
- The defence's size is learned (no scripted stop-gap).
- `commit` takes the intent as an input only, with no kind mask.
- Live game 1 gets a quick 0-game read.

**Live game 1, 0:00–3:55, against gate 4's 32 style-2 games** (the medians):
- **Workers:** 7, 11, 15 and 18 at 1, 2, 3 and 3:55 minutes; gate 4's 7, 11, 15 and 19.
- **SCVs ordered:** 18 against 18.
- **Marines:** 1 against 1.5.
- **Depots:** 2 against 2.
- **The Factory:** 3:11 against 2:58.
- **The Command Center:** 3:55 against 3:44.
- **The bank:** 190 minerals at 2:00 (gate 4 52), from the Barracks' two failed placements.

Nothing beyond those retries slowed it over LAN. The army's poverty came after the zerglings at 4:00.

**The labeller's fix.** A kept commitment whose destination is unknown is labelled by its kind. The pros' `HOLD` ticks
with a commitment in force went from 9% to 0%. The shares moved little:

| DEFEND_BASE | ATTACK | RETREAT | GATHER | HOLD |
|---|---|---|---|---|
| 25.0% | 36.6% | 3.2% | 29.0% | 6.2% |

The labeller and the numbers live in `gary/policy/tactical.py`, shared by the data and play. Every number comes from
the army tracker's own 16×16 grid, the economy and the commitment, so play reads what the data counted.

### The intent model

`train/tactical_intent.py --train` writes `runs/intent/TvZ_T_20261126-022348`. Held out: 469 games, 55,162 ticks.

| | Model (log-loss, accuracy) | Time and map |
|---|---|---|
| All ticks (the hazard and the next head combined) | 0.358, 0.866 | 1.271, 0.409 |
| Ticks with a new order (the honest score) | **0.786, 0.646** | 1.258, 0.401 |
| The next head, given a switch | **0.412, 0.820** | 1.441, 0.320 |
| The next head, a switch with a new order | **0.438, 0.809** | 1.398, 0.338 |

**The switch hazard:** AUC 0.894. At confidence 0.9 or more (52% of ticks) the model is right 0.978 of the time; at
0.8–0.9, 0.877; at 0.6–0.8, 0.717.

**The army's cohesion** (the share of the own army within 2 cells of the cluster and of its destination, the share in
the cluster, the clusters). The next head on switches with a new order scores 0.438 with these numbers and 0.463
without them. For GATHER→ATTACK, the next head's AUC among the switches out of GATHER is 0.939 with them and 0.931
without. So the launch is learned from them inside the heads, with no hand threshold, though they add little the other
numbers didn't already carry.

### The defence's size

A median regression on the pros' threatened moments; held out, 29,345 of them.
- **Error:** 7.3 supply against 9.6 for a constant.
- **By the threat's supply:**

| Threat (supply) | Pros' median | Model's median |
|---|---|---|
| 0–2 | 5.0 | 7.7 |
| 2–6 | 6.0 | 7.7 |
| 6–12 | 8.0 | 9.4 |
| 12 or more | 13.0 | 14.4 |

- **A small army early (6 supply or less, by 4:30; 620 moments):** an army of 5, the pros send 4 (median) and the model
  says 5. In 54% of those moments the size is above the whole army, so nearest units up to the size take everything
  there, as asked.

### The commit model with the intent

`runs/commit_intent/TvZ_T_intent`, fine-tuned 2 epochs from the deployed one on the modern games. Its control is
`TvZ_T_control`, the same without the intent.

| Held out (47,819 ticks) | Control | Intent |
|---|---|---|
| Order vs keep, AUC | 0.774 | 0.806 |
| Engage vs move, AUC | 0.769 | 0.991 |
| Destination in the top 5 | 0.340 | 0.378 |

Engage against move is near-certain given the intent, partly by definition: the intent's kind is the order's.

What the pros do under each intent, against the model:

| Intent | Pros: keep / engage / move | Model: keep / engage / move |
|---|---|---|
| ATTACK | 0.68 / 0.32 / 0.00 | 0.72 / 0.28 / 0.01 |
| RETREAT | 0.35 / 0.00 / 0.65 | 0.37 / 0.00 / 0.63 |
| GATHER | 0.70 / 0.00 / 0.30 | 0.68 / 0.01 / 0.32 |
| DEFEND_BASE | 0.82 / 0.16 / 0.03 | 0.84 / 0.14 / 0.02 |
| HOLD | 1.00 / 0 / 0 | 0.99 / 0.01 / 0.00 |

### The role model with the intent: a negative result

`runs/roles_intent/intent`, trained as the deployed one (`--decisions --move --attended --budget --again`) with the
intent one-hot on every unit. Its control is `runs/roles_intent/control`, the same without it.
- **Accuracy (held out):** 0.482, against the control's 0.496. On 6,000 sampled held-out snapshots, 0.560 against
  0.582.
- **The pros' close-in does not fall under a retreat:**

| Intent | Pros' close-in, all | Pros' close-in, outnumbered | Control's close-in (outnumbered) | Intent model's close-in (outnumbered) |
|---|---|---|---|---|
| ATTACK | 0.049 | 0.050 | 0.064 | 0.073 |
| RETREAT | 0.078 | 0.138 | 0.084 | 0.124 |

A retreat in contact means units close in to cover it. The intent model follows that a little, and the control
doesn't.

**The decision:** `gt1dev+intent` keeps the deployed role model. The intent role model is option `intentroles`, for the
record.

### Play

**`gary/agent/tactical.py`, option `intent`.** The intent is decided on its own 5-s clock in the arbiter's turn
(`look`), whoever has the hands: in an army turn it never ran while a fight held the hands. The provider:
- holds the intent at the hazard, then draws the next one (the game's seed and the side's);
- picks the target from the commit model's destination odds on the intent's side;
- makes a switch an event: the main cluster is asked at once;
- sizes and leases a `DEFEND_BASE` detachment, nearest ground units first, and ends it after 20 s quiet;
- sends lone units, out of contact, to their group (never a sieged tank).

**The leaves:**
- **`commit`:** takes the cluster's intent as an input and the intent's target as its destination when it is 2 or more
  cells away. A cluster with detachment units orders only the main intent's.
- **Under `HOLD`, with option `intentholdclear` only:** the commitment input reads none, as the data labels `HOLD`, so
  an old commitment doesn't carry into the intent's input. It is a rule over an input, so it is the user's call (below).
- **The calm layer:** leaves lone units to the intent layer, and stops its far sends.
- **The reinforce rule:** hands new units to a short detachment, else to their group; never alone into a fight.
- **The control groups:** follow the intent's groups, one type of a group on a key, flyers apart.
- **Its orders:** carry their own source, `intent`.
- **Coach Q4:** cites the active intent (its kind, start, group, target, the threat, the model's odds at the switch)
  and the detachments, in plain words.

**Two fixes before the final pipe run.**
- **Feature parity** (one game of `gt1dev+intent`, its replay rebuilt by the army dataset's builder and labelled, 84
  decisions paired with ticks): the cluster's position was its top-left unit in play. The data's channel 8 holds the
  cluster at its centre cell alone; play's holds every unit's cell. Read as the densest cell, `d_main` matches 81% of
  pairs (was 48%), `d_enemy_bld` 77% (24%), the cohesion share 93% (66%). The rest match 85–99%, except the "enemy army
  seen in 30 s" memory: 48% off by more than 2 supply, the difference `tests/test_inputs.py` lists as intended for the
  army model.
- **The detachments capped at two** (§4 says at most two; nothing enforced it).

**`tests/test_intent_pipe.py`, final** (one headless game to 12:00, a deep copy per intent at each minute from 6:00, 15 s
each with the intent forced, 35 arms over 7 moments):

| Criterion | Result |
|---|---|
| 1. The forced intent's units' commit and intent orders to its target, 90% or more | **83% of 87 over all arms. After a real switch: 56 of 58 (97%)** (ATTACK 21/23, RETREAT 29/29, GATHER 5/5, DEFEND_BASE 1/1). The misses are the test's own: 10 are a forced GATHER on a main already gathering (no switch, its old target kept) and 3 a question before the switch |
| 2. The arms' orders differ pairwise in 80% of the moments or more | **4 of 7: fail.** At the other 3 the arms gave no or the same commit questions (a fight held the hands) |
| 3. No intent order over a fight's or a rule's units | **0: pass.** Its 9 lease conflicts were all over the army layer's own moves |
| 4. The defence's size about the pros' | **Pass** on made-up states: 7.6 supply against a threat of 1 in an army of 30 (the pros' median 5); 5 of an army of 5 at 4:00 |
| 5. The commit model's odds follow the intent | **Pass**, see Decision 2 below |

**Decision 2's evidence, the kind taken.** The main cluster's questions after the switch with the forced intent as
input (45; 11 more where the main already had it):

| Forced | keep / engage / move |
|---|---|
| ATTACK | 2 / 9 / 0 |
| RETREAT | 1 / 0 / 12 |
| GATHER | 1 / 0 / 9 |
| DEFEND_BASE | 4 / 7 / 0 |
| HOLD | 6 / 4 / 0 |

Every intent but HOLD is obeyed through the input alone. HOLD is not, where a commitment is in force: the data's HOLD
never has one. The offline odds say the same (keep 0.54, engage 0.44 under HOLD). Criterion 5's "keep largest under
HOLD" passed by a hair.

Option `intentholdclear` (not in `intent`) makes the commit model read no commitment under HOLD. With it the HOLD arms
took 9 / 1 / 0 (keep / engage / move), against 5 / 4 / 1 without it, in the run before the centre fix. It is a rule over
an input, so the user's call, as a mask would be.

**The unforced main line** (the same game, its own intents from 6:00 to 12:00):

| Intent | Share of time | Hold median (s) | The pros' hold median (s) |
|---|---|---|---|
| GATHER | 72% | 40 | 15 |
| ATTACK | 22% | 27 | 20 |
| DEFEND_BASE | 6% | 14 | 20 |
| RETREAT | 0% | | 5 |
| HOLD | 0% | | 15 |

It switches 1.65 times a minute. The labeller on the same game's replay saw GATHER 65, ATTACK 15 and DEFEND_BASE 9 of 89
ticks.

**The detachments in that game:**

| Minute | Units | Supply | Enemy supply at home | Army supply |
|---|---|---|---|---|
| 7 | 20 | 20 | 32 | 24 |
| 8 | 9 | 9 | 22 | 29 |
| 8 | 6 | 6 | 0 (losses only) | 28 |
| 10 | 9 | 9 | 5.5 | 29 |

- **At most two at once.** While any was active they held half the army's supply on average, and at peak all of it:
  the 32-supply attack at 7:00 took 20 of 24.
- **The pros' detachments are a fifth to a quarter of their army.** Gary's army is small at 7–8 minutes (24–29
  supply), and the sizer works in supply, not share.
- **A threat of losses alone still detached 6.** The sizer's median never says "nobody", where the pros send no one in
  19–32% of threatened moments.
- **Open, the user's call:**
  - the size as a share of the army, or with a model of whether anyone goes;
  - the main itself switching to DEFEND_BASE on a large threat (it did, 6% of the time), not a detachment;
  - as now.

**The specialists:**
- 0 orders to sieged tanks in the arms, 0 tanks unsieged.
- All 18 control-group keys held one unit type, and no key mixed flyers with ground units.

**Coverage.** `tests/test_matchups.py` with `GARY_TEST_T=gt1dev+intent`: all six matchups play (the layer stands aside
where there is no intent model: every matchup but TvZ).

**About the role model's result.** The control and the deployed model share one recipe (0.496 and 0.482 held out), so
the intent model's 0.482 is no gain rather than worse.

**The regression tests:**
- `test_parity` (gt1, gz1, gp1 unchanged), `test_smoke_game`, `test_pairs`, `test_live`, `test_card_macro`,
  `test_trunk_faithful` and `test_matchups` pass.
- `tests/test_inputs.py` fails only #67's five blocks, unchanged.

## 8. The user's calls, applied (2026-11-26; 0 games)

**The calls:**
- `HOLD` clears the commitment input, folded into `intent`: the pros' `HOLD` ticks have none, so this is input
  parity with the labeller, not a mask. Option `intentholdclear` is gone. No kind mask on any intent.
- The defence is a hurdle: a learned P(anyone defends | state) on the same threatened moments, then the size given a
  defence. No detachment while the main is `DEFEND_BASE`. A size of half the main's supply or more switches the main
  itself to `DEFEND_BASE`, rather than carving most of it off.
- Criterion 2 is accepted at 4 of 7 and is now read over army-active moments. A forced intent is always a fresh one,
  with its own target.

**A correction to §4's premise.** The pros' detachments are not "a fifth to a quarter of the army".
- §4's table was computed some other way. On 200 games with the sizer's own definition (12,933 threatened moments),
  nobody defends in 23%.
- Given a defence, the median force is **0.92 of the army** (quartiles 0.52–1.00):

| Minute | Army (median) | Sent (median) | Share (median) | Share under half |
|---|---|---|---|---|
| 0–6 | 7 | 7 | 1.00 | 2% |
| 6–10 | 16 | 13 | 1.00 | 14% |
| 10–15 | 31 | 17 | 0.78 | 36% |
| 15+ | 65 | 30 | 0.50 | 50% |

So the half-the-army rule matches the pros: their defences are mostly the whole army, and a true detachment (under
half) is 24% of them, mostly after 10 minutes.

**The model** (`runs/intent/TvZ_T_20261126-092552`; the hazard and next heads unchanged, AUC 0.894, 0.438):
- **Does anyone go,** held out (29,345 moments): AUC 0.746; nobody 22.7% against the pros' 23.0%.

| Threat | Pros: nobody | Model: nobody |
|---|---|---|
| 0–2 supply | 35.9% | 33.4% |
| 2–6 | 27.7% | 28.2% |
| 6–12 | 23.3% | 26.6% |
| 12+ | 19.0% | 18.6% |
| Losses only, no enemy seen | 45.0% | 41.2% |

- **The size given a defence:** off by 4.66 supply, against 9.06 for a constant. Pros' median against the model's, by
  threat band: 9/10, 9/10, 11/12, 15/16.
- **A small army early** (6 supply or less, by 4:30): nobody 18.4% against the model's 16.2%; the size 5 against 5.

**In play** (`gary/agent/tactical.py`):
- Whether anyone goes is drawn once per threat (the game's seed and the side's), and drawn again only if the threat
  doubles. A threat nobody went to is forgotten 20 s after it ends.
- A size of half the main's ground supply or more switches the main to `DEFEND_BASE`, toward the threat.
- Coach Q4 cites all three outcomes: nobody went, a detachment, or the whole group.

**One more leaf fix.** A cluster already within 2 cells of its intent's target drew its own cell 4–9 cells away (4 of
41 of the main's orders in the arms). The labeller would call that a different intent (`DEFEND_BASE` is within a cell
of the threat, `GATHER` any other move), so leaving is the intent model's switch to make, not this order's. Now, at the
target, the commit model's cell is drawn among those within 2 cells of it. This restricts where it goes, not the kind.

**`tests/test_intent_pipe.py`, again** (35 arms over 7 moments):

| Criterion | Result |
|---|---|
| 1. Orders after the switch to the target | **100% of 93: pass** (before the switch, 6 more, not counted; the join's and the detachments' orders excluded, the test judging a unit by its intent when ordered) |
| 2. Arms differ, army-active moments | **4 of 5: pass** (all moments 4 of 7) |
| 3. Intent orders over a fight's or a rule's units | **0: pass** |
| 4. The defence | **Pass.** P(anyone defends) 0.69–0.74 against threats of 1–20 supply with an army of 30; 0.71 on losses alone; size given a defence 11–12 (the pros' 9–15). 2 supply against an army of 5 at 4:00: P 0.93, size 4.9, so the main defends |
| 5. The commit model follows the input | **Pass.** Keep / engage / move offline: `HOLD` 0.42 / 0.57 / 0.01 with no commitment, the largest keep of the five but not above its engage at these moments |

- **The main's kind after the switch** (keep / engage / move): `DEFEND_BASE` 6/4/0, `ATTACK` 4/6/0, `RETREAT` 2/0/8,
  `GATHER` 2/2/7, `HOLD` 8/3/0.
- **Specialists:** 0 orders to sieged tanks, 0 unsieged, 16 of 16 keys one type, flyers apart.
- **The unforced main line:**
  - shares `GATHER` 50%, `ATTACK` 29%, `DEFEND_BASE` 21%;
  - 1.92 switches a minute;
  - one detachment (14 of 34 supply);
  - the main defended twice;
  - nobody went five times, two of those against 76–80 supply (P 0.54 and 0.76): the "seen in 30 s" memory inflates
    the threat, as in §4.

**Regression tests:**
- Parity (gt1, gz1, gp1 unchanged), smoke, pairs and live pass.
- `tests/test_matchups.py` with `gt1dev+intent` plays all six matchups.

## 9. The 16-game screen (2026-11-26; IN303a against IB303a)

**The round.** `gt1dev+intent` (IN303a) and `gt1dev` replayed on the same code (IB303a), both against `gz1`. The 8
ladder maps × 2 seeds from 4004, 30 minutes, `--gg 0`, paired by map and seed. The measures are §5's, from
`eval/alone.py`, `eval/paired.py`, `eval/gap_windows.py`, `train/tactical_intent.py --gary` and the records.

| Measure | Baseline (IB303a) | Intent (IN303a) | Paired difference, 90% | Expected (§5) | Read |
|---|---|---|---|---|---|
| Deaths alone (games' mean) | 0.194 | 0.186 | −0.008 [−0.046, +0.031] | 0.25 → 0.14 | **No change** |
| The army's share at attacks (games' median) | 0.275 | 0.422 | **+0.149 [+0.081, +0.216]** | → 0.45 | **Moved, as expected** |
| Late arrivals per fighter there | 0.117 | 0.158 | +0.018 [−0.040, +0.081] | toward 0.06 | Direction only: none |
| Attacks a game | 4.7 | 3.8 | | | Fewer, larger |
| Fighters alone, 5–20 min samples | 0.070 | 0.055 | | | Down |
| Ground fighters in no asked cluster | 0.131 | 0.085 | | | Down |
| Paired score by supply | | | −0.109 [−0.281, +0.062] | not measurably worse | Read, not judged (16 games resolve about 0.2) |
| Gap, all windows | 0.416 | 0.424 | +0.008 [−0.063, +0.080] | | Same. 5–10 min +0.036 [−0.011, +0.073]; 25–30 min −0.111 [−0.202, −0.013] (intent nearer the pros) |

Results: the intent build won 3, lost 2 and had 11 at time; the baseline won 4, lost 1 and had 11 at time.

**Deaths alone are the roles' doing.**
- 88% of the intent build's alone deaths had the role model's order last (baseline 84%), 78% of them outnumbered.
- What left them alone: neighbours died (31%), and neighbours moved off by the roles (19%).
- The intent layer steers the army out of contact. The units that die alone die in contact, where the role model
  decides, and the role model doesn't read the intent (§7: no gain offline). So this measure needs the fight layer,
  not this one.

**Intent shares** (the labeller over each round's replays; the pros' in §2):

| | DEFEND_BASE | ATTACK | RETREAT | GATHER | HOLD | HOLD at 20+ min |
|---|---|---|---|---|---|---|
| Pros | 25.0% | 36.6% | 3.2% | 29.0% | 6.2% | 3% |
| Baseline | 19.2% | 40.7% | 1.3% | 28.9% | 9.9% | 13% |
| Intent | 20.0% | 40.0% | 1.4% | 30.0% | 8.7% | 15% |

The labelled shares hardly moved: `RETREAT` stays at 1.4% (expected 3%), and late `HOLD` at 15% (expected under 8%).

**The layer's own decisions** (its records, 16 games):
- **Time shares:** `DEFEND_BASE` 27%, `ATTACK` 35%, `RETREAT` 1.6%, `GATHER` 36%, `HOLD` 0.9%.
- **Switches:** 2.54 a minute.
- **Hold medians:** 10–16 s, against the pros' 15–20 s. The p90 is about a minute, with a long tail: one `ATTACK`
  held 7 minutes.
- **The defence:**
  - 101 times the main itself defended (threat median 13 supply);
  - 46 detachments (median 31 supply, late armies);
  - 64 times nobody went (threat median 6; 15 of them against more than 20 supply, the "seen in 30 s" memory
    included).

**A deviation found: `GATHER` makes the commit model move, not keep.**
- Under `GATHER`, `commit` gave keep / engage / move 363 / 17 / 607: 62% moves. The pros' and the model's offline odds
  are 30% moves (§7).
- 269 of the moves were at the target, shuffling within 2 cells of it every few seconds (Q4, KnockOut 14:45–14:58).
- A likely reason: play reaches `GATHER` with the old commitment still in force, a state the data never holds,
  because the labeller labels `GATHER` from a move commitment.
- The other kinds are near the pros':
  - `ATTACK` engages 47% of its decisions (pros 32%);
  - `DEFEND_BASE` 30% (pros 16%);
  - `RETREAT` moves 77% (pros 65%);
  - `HOLD` keeps 100%.

**Coach Q4.** 12 answers at 7, 11 and 15 minutes of 4 games are in `runs/league/IN303a/q4_review.txt` (not in the
repository). Each cites the intent in force, its target, the model's odds at the switch, the defence (detachment,
the whole group, or nobody) and the commit decisions behind it. A bug the read found: when the main itself defended,
Q4 also printed it as a detachment ("None supply"). It is fixed in `eval/coach.py`.

## 10. Before the 48: the user's three checks (2026-11-26; 0 games)

**"Nobody went" against more than 20 supply (IN303a's 15).**
- The replays' commitment ticks separate Zerg in sight at the threat from Zerg only remembered (seen in 30 s):
  - 10 of the 15 had 8 or more supply in sight, and 9 were followed by losses at home within a minute (up to 110 loss
    units, Odyssey 21:12);
  - about 3 were ghosts: nothing in sight and no losses.
- The main army defended soon after:
  - 14 of the 15 were followed by a defence within 2 minutes, at 5–31 s in 12 of them, 51 and 109 s in two;
  - over all 64 "nobody" draws, a defence followed within 2 minutes in 55, median 21 s.
- **The fix:** the draw is now made again when Gary's losses at home grow since it (`loss_home`, a model input), as
  well as when the threat doubles. In the pipe check's game it did not fire (the same five draws as before).

**ATTACK held 10:00 to past 15:00 (Attitude seed 4004).** Not a bug.
- The game replayed with the same seed and code reproduced it exactly.
- The layer decided every 5 s: 62 ticks, switch odds median 0.008, at most 0.24 (P of no switch in all of them 0.22).
- The army sat at its target in contact, its engage commitment renewed every 17–83 s. The labeller would call each of
  those ticks ATTACK too, so the model's hazard is right for the state. The state is self-fed: orders at the target
  keep the commitment fresh, the shape GATHER's hops have.

**GATHER's hops: item 1 as specified does not fix them, and the cause is elsewhere.**
- **As specified** (the commitment input read as a move to the target on entering GATHER): it never fired. At the
  gather point the commitment was already a move near the target. The replayed KnockOut seed 4005 matched the round's
  records exactly: 69 moves, 43 of them hops.
- **Two variants, tried and reverted:**
  - the move aged from the intent's start;
  - the same shared with the intent model, gone after 120 s, with the GATHER target 2+ cells away.

  They gave 18 of 50 and 40 of 94 hops on games that part after their first changed decision: game path, not effect.
- **At a fixed state** (59 questions of the main at its GATHER target, the same grid with the commitment input
  varied), P(move):

| Commitment input | none | engage 5 s | move 5 s | move 30 s | move 60 s | move 120 s |
|---|---|---|---|---|---|---|
| P(move), median | 0.88 | 0.98 | 0.92 | 0.84 | 0.76 | 0.72 |

  No commitment input brings it near the pros'. The real one at those questions was a move, 5 s median: Gary's own last
  hop.
- **The pros at their gather point** (3,904 GATHER ticks within 2 cells of the destination, 300 games):
  - a new move order on 36% of ticks (41% away from it);
  - that move goes a median 3 cells from the cluster;
  - 60% of those moves leave the old destination's 2 cells.
- **The labeller:** a move from a GATHER cluster to any cell that isn't a threat or a retreat is GATHER with a new
  destination. In the data, GATHER re-targets as it goes.
- **So two things make the hops:**
  - **The §8 clamp.** It is wrong for GATHER and ATTACK, whose moves the labeller keeps in the same intent with a new
    destination, and right only for DEFEND_BASE. It squeezes every drawn move into a 2-cell hop; 60% of the pros' leave.
  - **The commit model's move odds in Gary's states.** 0.72–0.98 at the gather point, where the pros move on 36% of
    ticks, and the same model scores the pros' own GATHER ticks at 0.32 (§7). The high odds come from Gary's states,
    not the commitment input. Which inputs drive them is open.

**The 48 is not launched:** item 1 is not clean, and the clamp is the user's call.

## 11. What drove GATHER's move odds, Option 1, and the 48 (2026-11-26)

**The user's calls.** Option 1: the 2-cell clamp only for DEFEND_BASE; GATHER's move and ATTACK's engage at the target
move the intent's target, as the labeller carries them. First a 0-game check of which input drives the commit model's
P(move) at Gary's gather points.

**The check (0 games).** The commit model's inputs were captured at the 59 questions of the KnockOut seed 4005 replay
(the main under GATHER within 2 cells of its target) and compared with 2,616 pros' GATHER-at-target rows (196 modern
TvZ games of the v5 army dataset, built as train/commit.py builds them):
- P(move): Gary 0.92 median (0.80 mean); the pros' rows 0.38 (0.41), the pros moved on 0.37 of them.
- Each input group swapped between the two sets (mean P(move), Gary's rows with the pros' group / the pros' with
  Gary's): every number group and every other map channel within 0.07 of the base. **Channel 8, the group: 0.80 to
  0.46, and the pros' 0.41 to 0.73.**
- Channel 8 in the data holds the cluster's whole supply in one cell: an order's at the selection's centre, a
  commitment tick's at the cluster's densest cell (ingest/army_dataset.py). Every pros' row has it in exactly 1 cell.
  Play put each unit's supply in its own cell: 4 cells median at Gary's gather points. A play-against-training
  mismatch, in every build: tests/test_inputs.py reads the army's inputs with an empty group, so it never compared it.
  §7's fix read the cluster's position as its densest cell; the channel itself stayed spread.
- Gary's same 59 inputs with channel 8 in its densest cell: P(move) 0.56 median (0.54 mean).

**The fix** (`ArmyTracker.inputs`, `densest`): the group's supply in one cell, the mean position's for an order
question, the densest cell for a commitment question (army.py `_committed`, the intent layer's read). A model's input
counted as its data counts it: it changes every build that uses the army or commit model (gt1, gz1, gp1 and the dev
builds); the parity hashes are recorded again with it. tests/test_inputs.py passes (214 moments), every matchup plays.
IB303a, the screen's baseline, ran without it, so the 48's baseline is replayed. Through the real code path (KnockOut
seed 4005 replayed on the fixed code to 15:30, every commit question of the main at its GATHER target captured at the
model): 5 such questions (59 before: the hops are gone), each with channel 8 in exactly one cell holding the group's
supply as the numbers give it, P(move) 0.47 median. (tests/test_inputs.py reads the army with an empty group, so its
pass says nothing of channel 8.)

**Option 1** (`army.py`, `Tactical.retarget`): at the intent's target, GATHER's move and ATTACK's engage draw their cell
as any commit order does, and the drawn cell becomes the main's target (the intent and its clock unchanged);
DEFEND_BASE keeps the clamp. tests/test_intent_pipe.py's criterion 1 now compares each order with the target in force
when it was given.

**The pipe check with both** (one game, KnockOut seed 4004, 7 moments): criterion 1 96% of 96 (pass; an order that moved
the target counts as a hit by construction, 2 of the 96); **criterion 2 fails: 4 of 7, all 7 army-active** (the user's
4 of 7 was accepted when the misses were fights holding the hands; the commit message of 5457ef2 called this one
accepted, wrongly). The three misses, read arm by arm: at 6:00 all five arms keep; at 9:00 and 12:00 DEFEND_BASE,
ATTACK and HOLD keep while RETREAT and GATHER move to their targets. No two arms that acted sent the same order: the
intent reaches the army when the commit model acts, and the misses are its keep draws (its keep odds rose with the
channel-8 fix). Criteria 3-5 pass; sieged tanks and keys clean. P(move) at the gather points, 0.56 against the pros'
0.38, is still open. The unforced main
under GATHER: keep / engage / move 31 / 1 / 14 (moves 30%; the screen's 62%, the pros' 30%), 6 re-targets
(the hop counter read 0, but it matches the clamp's "near the intent's target", which only DEFEND_BASE gives after
Option 1: it could not see GATHER's hops; §12 counts them from the re-targets). One game: a rate, not a measure.

**The 48 (written before it runs).** IN304a (`gt1dev+intent`) against IB304a (`gt1dev`, replayed on the same code), both
against gz1, the ladder maps, seeds 4004-4009 (8 maps x 6 = 48 games each), 30 minutes, `--gg 0`, paired by map and
seed.
- **Paired score.** 48 paired games resolve about 0.10-0.15 (90% interval +-0.07 to +-0.12: the screen's +-0.17 on 16
  games, scaled; AGENTS.md's 0.06-0.14 for 96). A difference under 0.10 is not resolved; if the interval holds zero
  and the point is within 0.10, the second 48 (`--first 4010`) runs, per AGENTS.md.
- **Army share at attacks** (eval/alone.py): the screen's +0.149 [+0.081, +0.216] on 16; 48 resolve about +-0.04, so
  the expected rise shows or doesn't.
- **Ground fighters in no asked cluster** (13% to 9% on the screen): resolves a change of about 3 points.
- **Gap per window** (eval/gap_windows.py): all windows about +-0.04 at 48; per window wider.
- **Intent fidelity**: GATHER's commit moves per question against the pros' 30%, hops at the target, intent shares
  and hold lengths against the pros' (§5), and Coach Q4 at three moments of four games.
- Deaths alone are not judged here (the fight layer's, TODO).

## 12. The first 48 (2026-11-26; IN304a against IB304a)

**The round.** As written in §11: `gt1dev+intent` (IN304a) against `gt1dev` (IB304a), both on the channel-8 fix,
against gz1, the 8 ladder maps x seeds 4004-4009, 30 minutes, `--gg 0`, 48 paired games. Measured with
`eval/paired.py`, `eval/gap_windows.py`, `eval/alone.py` (paired by map and seed, bootstrap over games),
`train/tactical_intent.py --gary` and the records.

| Measure | Baseline (IB304a) | Intent (IN304a) | Paired difference, 90% | The screen's (§9) | Read |
|---|---|---|---|---|---|
| Paired score by supply | 0.505 | 0.500 | -0.005 [-0.078, +0.062] | -0.109 [-0.281, +0.062] | Not resolved: the second 48 runs |
| The army's share at attacks (games' mean of medians) | 0.281 | 0.282 | +0.001 [-0.044, +0.047] | **+0.149 [+0.081, +0.216]** | **The screen's gain is gone** |
| Late arrivals per fighter there | 0.111 | 0.108 | -0.017 [-0.056, +0.022] | +0.018 | None |
| Attacks a game | 4.3 | 3.2 | **-1.1 [-1.8, -0.5]** | -0.9 | Fewer, as on the screen |
| Ground fighters in no asked cluster (5-20 min) | 0.119 | 0.112 | -0.008 [-0.045, +0.033] | -0.050 [-0.079, -0.021] | The screen's drop is gone |
| Deaths alone | 0.203 | 0.198 | -0.004 [-0.039, +0.031] | -0.008 | None (the fight layer's) |
| Gap, all windows | 0.491 | 0.510 | +0.019 [-0.030, +0.058] | +0.008 | Same; no window resolved (0-5 min -0.027, 20-25 +0.022) |

Results: the intent build won 2, lost 6 and had 40 at time; the baseline won 3, lost 6 and had 39 at time.

**The screen's gain went with the code change, not the seeds.**
- On the screen's starts (seeds 4004-4005; 13 paired games with attacks in both) the paired difference is -0.060
  (intent 0.277, baseline 0.338), against the screen's +0.149 on 15 (0.422 against 0.275). The baseline rose there
  too, so the same starts are a check of direction, not a measure.
- The baseline's own share over all 48 is unchanged (0.281; the screen's 0.275), so the intent build lost it.
- Under IN303a the attacks a commit move began carried 0.63 of the army (median) and a commit engage's 0.54; under
  IN304a they carry 0.42 and 0.33.
- Two things changed between the screen and the 48: the channel-8 fix (the commit model keeps more: GATHER moves 62% to
  34% of its questions) and Option 1 (the gather point follows the commit model's draws instead of the clamp holding
  the army near it).
- **The records separate them (0 games).** Under IN304a the main gets far fewer orders within an intent's spell: an
  ATTACK spell sends 0.20 commit orders for the main (IN303a 1.09), 89% of them none (71%); GATHER 0.81 (1.77), 74%
  none (63%); DEFEND_BASE 0.13 (0.56), 91% none (73%). The commit model keeps on most questions since the channel-8
  fix, and the spells are short (10-11 s median), so most intents end before the main is sent anywhere; Option 1 acts
  only at the target, after an order has gone. The main's share of the army on entering ATTACK hardly moved (0.62
  median, IN303a 0.67). So the screen's share at attacks rode on the commit model's spread group channel, which made
  it move: the channel-8 fix took it, not Option 1. (Overstated: the second 48 on the same code moved the share +0.107,
  §13.) A switch of intent sends nothing by itself; in the pros' data an
  intent begins with an order (the labeller labels it from a commitment), a state Gary now rarely holds.

**Intent fidelity.**
- The commit model under GATHER: keep / engage / move 1,961 / 12 / 1,035, moves 34% (the pros' 30%; the screen's
  62%). 307 GATHER re-targets, 90 of them within 2 cells of the cluster (29%; the pros' moves at their gather point
  stay within 2 cells 40% of the time, §10). The other intents' kinds: DEFEND_BASE engages 7% (the pros 16%), ATTACK
  16% (32%), RETREAT moves 32% (65%), HOLD keeps 95%.
- The layer's time shares: DEFEND_BASE 27%, ATTACK 27%, RETREAT 1.1%, GATHER 41%, HOLD 3.4%; 3.09 switches a minute
  (the screen's 2.54); hold medians 10-11 s (the pros' 15-20 s), HOLD's 71 s.
- The labeller over the replays (shares of main-cluster ticks):

| | DEFEND_BASE | ATTACK | RETREAT | GATHER | HOLD |
|---|---|---|---|---|---|
| Pros | 25.0% | 36.6% | 3.2% | 29.0% | 6.2% |
| Baseline (IB304a) | 22.9% | 33.0% | 0.8% | 27.8% | 15.5% |
| Intent (IN304a) | 20.2% | 27.6% | 0.6% | 38.2% | 13.3% |

  GATHER moved away from the pros' (38% against 29%), ATTACK too (28% against 37%); HOLD a little nearer.
- The defence: the main defended 332 times (threat median 17.5 supply), 201 detachments (median 28 supply), nobody
  went 190 times (threat median 5; 35 of them against more than 20 supply).
- **Coach Q4** at 7, 11 and 15 minutes of four games (Attitude 4004, KnockOut 4005, Odyssey 4007, Radeon 4009): each of
  the 12 opens on the intent in force, its target and the model's odds at the switch (two read in full, the rest by
  that line). One GATHER held 8:18 to past 11:00 with 20 supply of Zerg at Gary's bases (Odyssey 4007).
- **Hops:** GATHER's re-targets landing within 2 cells of the cluster: 90 in 48 games (1.9 a game; the screen's
  shuffles 269 in 16, 17 a game), 29% of its 307 re-targets (the pros' moves at their gather point stay within 2
  cells 40% of the time, §10).

**Read.** Not measurably worse in score or gap, nearer the pros on GATHER's commit kinds, but the measure the layer
was built for (the army's share at attacks, §5) no longer moves, and the labelled shares drift toward GATHER. The cause is
in the records: since the channel-8 fix the commit model keeps through most intent spells, so the intent rarely reaches
the main. The second 48 (IN304b against IB304b, `--first 4010`) started per AGENTS.md; it measures this build, which
the cause may change (the user's call).

## 13. The second 48 and the 96 (2026-11-26; IN304b against IB304b, seeds 4010-4015)

**The round.** The same code and arms as §12, seeds 4010-4015 (`--first 4010`), run per AGENTS.md for a close 48.
The intent build won 0, lost 10, 38 at time; the baseline won 4, lost 9, 35 at time.

| Measure | Second 48 (B - A) | All 96 (B - A) | Baseline / intent over 96 |
|---|---|---|---|
| Paired score by supply | | -0.034 [-0.089, +0.018] (MDE at 96: 0.083) | 0.497 / 0.464 |
| The army's share at attacks | **+0.107 [+0.044, +0.169]** | **+0.051 [+0.012, +0.090]** | 0.289 / 0.340 (pros' target 0.45, §5) |
| Ground fighters in no asked cluster | -0.048 [-0.072, -0.025] | **-0.028 [-0.050, -0.004]** | 0.123 / 0.095 |
| Fighters alone, 5-20 min samples | -0.049 [-0.076, -0.024] | -0.023 [-0.042, -0.003] | 0.111 / 0.089 |
| Late arrivals per fighter | -0.015 [-0.039, +0.011] | -0.016 [-0.039, +0.008] | 0.093 / 0.084 |
| Deaths alone | -0.019 [-0.048, +0.013] | -0.011 [-0.035, +0.012] | 0.226 / 0.214 |
| Attacks a game | -0.6 [-1.3, +0.1] | -0.9 [-1.3, -0.4] | 4.2 / 3.3 |
| Gap, all windows | | -0.007 [-0.049, +0.031]; no window resolved | 0.465 / 0.458 |

**The halves disagree on the share** (+0.001 and +0.107 on the same code, each about +-0.06), so §12's "the gain is
gone" was a half's noise read as a verdict. Over 96 the intent build moves the army's share at attacks and the
fighters in no asked cluster, about a third of the screen's +0.149 and half of its -0.050, with no measurable cost in
score or gap.

**The records per spell, all three intent rounds** (commit orders sent for the main within an intent's spell):

| | ATTACK | GATHER | DEFEND_BASE | Share at attacks (B - A) |
|---|---|---|---|---|
| IN303a (the screen, before the channel-8 fix) | 1.09 (71% none) | 1.77 (63%) | 0.56 (73%) | +0.149 |
| IN304a | 0.20 (89%) | 0.81 (74%) | 0.13 (91%) | +0.001 |
| IN304b | 0.42 (81%) | 1.14 (70%) | 0.11 (92%) | +0.107 |

The orders an intent's spell gets follow the share across the three rounds, and most spells still end with no order
for the main: the intent reaches the army only through the commit model's non-keep draws. That stands as §12 found it;
only its verdict on the share was wrong.

**Intent fidelity over the 96.**
- Labelled shares (main-cluster ticks): intent GATHER 38.2% / 32.7% (the halves), ATTACK 27.6% / 34.5%; baseline
  GATHER 27.8% / 30.9%, ATTACK 33.0% / 36.3%; the pros' 29.0% and 36.6%. The intent build gathers more than the pros.
- The layer, second half: DEFEND_BASE 24%, ATTACK 33%, RETREAT 1.3%, GATHER 36%, HOLD 5.4%; 2.79 switches a minute;
  hold medians 10-11 s (the pros' 15-20 s). GATHER's commit moves 36% (the pros' 30%); 89 hops in 48 games (1.9 a game,
  as in the first half).
- The defence: the main defended 277 times, 171 detachments (median 30 supply), nobody went 188 times (56 of them
  against more than 20 supply, the first half's 35).

**Read.** By the promotion rule's shape (for an option: not measurably worse in 96, nearer the pros on its fidelity
measure): not measurably worse in score (interval holds zero, under the MDE) or gap, and the army's share at attacks
and the fighters outside asked clusters move toward the pros' (0.289 to 0.340 against their 0.45; 0.123 to 0.095
against their 0.085). Against it: GATHER labelled about 6 points over the pros' and ATTACK 5 under, holds half the
pros' length, nobody going against 20+ supply, and most intents never reaching the main. Folded into gt1dev on the
user's call (gt0.55dev, §14).

## 14. Folded into gt1dev (2026-11-26; gt0.55dev; 0 games)

**The user's call** on §13: option `intent` folded into `gt1dev`, version gt0.55dev. The manifest is `gt1dev+intent` as
IN304a+b played it, byte for byte (the built manifests compared: equal, the version aside; `gt1`, `gz1`, `gp1`, `gz1dev`
and `gp1dev` unchanged). `gt1dev+intent` still builds, the same manifest (the option is now idempotent). The layer
plays TvZ only: in the other matchups there is no intent model, and it stands aside.

**The checks, on the fold:**
- tests/test_intent_pipe.py (now on `gt1dev`): as §11 found it on `gt1dev+intent`. Criterion 1 96% of 96 (pass),
  criterion 2 4 of 7 (fails, the keep draws read in §11), criteria 3-5 pass.
- tests/test_smoke_game.py, tests/test_pairs.py, tests/test_live.py (each race's dev build through the live launcher),
  tests/test_matchups.py (the playing builds, and `GARY_TEST_T=gt1dev GARY_TEST_Z=gz1dev`: all six matchups) pass.
- tests/test_parity.py passes without recording again: its games play `gt1`, `gz1` and `gp1`, which did not change.
- tests/test_inputs.py fails on the fold and on the code before it, both on #67's lines.
  - Before the fold: the Terran's macro and critic "decided" off at 25% of 107 moments, and the Zerg's placement
    `workers_lost` at 40% of 5.
  - On the fold: the Zerg's placement `minute` off at 60% of 5. The Terran's "decided" is at 12%, under the bar.
  - The Terran's change changes the game the test plays, so which of #67's lines cross the bar moves. No new kind of
    difference appears.

## 15. Why most intents send the main nothing, and the threats nobody went to (2026-11-26; 0 games)

Read on IN304a+b's records (96 games), their saved commit-model inputs (each record's `rl` row; re-queried, the odds
within 0.001 of the recorded), the replays' re-simulated ticks, and 300 modern pros' TvZ games (37,195 main-cluster
ticks, the labeller of §2). No scripted order on a switch was tried. The requested read was what the commit model
would do if a switch cleared the old commitment.

### Check 1: entering an intent

**Most spells never ask the main.** Of the main's intent spells, these got no commit question for the main at all:
DEFEND_BASE 60% of 1,576, ATTACK 65% of 2,151, RETREAT 62% of 208, GATHER 58% of 2,329.
- In those spells no cluster was asked, and 77-91% of them had a fight.
- The arbiter gives the army layer only units more than 12 tiles from a fight's centre (arbiter.py `_army`), so the
  main in contact is the role model's.
- The intent switches on its 5 s clock all the same. These spells are short: 9-15 s mean, against 27-39 s for spells
  where the main was asked.

**When asked, the first question comes at once.** Median 1.0-2.8 s after the switch, 31-36% on the switch's frame
(HOLD 75%). The commit model mostly keeps:

| First question after a switch | Its commitment (none / engage / move) | P(act), as played | P(act), commitment cleared |
|---|---|---|---|
| ATTACK (763) | 43% / 13% / 44% | 0.25 | 0.13 |
| GATHER (970) | 45% / 25% / 30% | 0.38 | 0.36 |
| DEFEND_BASE (636) | 47% / 15% / 38% | 0.10 | 0.06 |
| RETREAT (79) | 29% / 32% / 39% | 0.47 | 0.38 |

Under ATTACK with no commitment the model keeps at 0.93 (median) and acts 9% of the time. With a move commitment it
keeps at 0.62, and at 0.90 once cleared. **Clearing the old commitment makes it keep more, not less.**

**The pros' switch is an order.** The labeller reads a pros' intent from the tick's order, so at a pros' switch tick
the order comes with it:
- ATTACK: engage 92-100% of the time, whatever the commitment in force (none 3%, engage 44%, move 53%).
- GATHER: move 69-92%.
- RETREAT: move 77-92%.
- A standing pros' ATTACK or GATHER tick never has no commitment (0.0% of 20,196).

The commit model learned mostly from the standing ticks. Under ATTACK the pros' rows keep 68%, and its inputs do not
tell a fresh intent from a standing one. So at Gary's switch it answers as for a standing intent.

**The hazard reads the missing commitment.** The intent model's switch head on the pros' standing ticks:

| Pros' standing ticks | As they are | Commitment set to none | Commitment set to the other kind |
|---|---|---|---|
| ATTACK (4,000) | 0.115 | 0.454 (x3.9) | move: 0.146 (x1.3) |
| GATHER (4,000) | 0.153 | 0.593 (x3.9) | engage: 0.177 (x1.2) |
| DEFEND_BASE (4,000) | 0.070 | 0.159 (x2.3) | |

The next-intent head hardly moves: from ATTACK, GATHER 0.68-0.72.

The commitment the hazard read when it fired was rebuilt from the records: the latest sent commit order within 120 s
whose path passes within 2 cells of the main's cell, as army.py `_commitment`.

| The intent that ended | Gary: no commitment when the hazard fired | The pros: no commitment at the switch |
|---|---|---|
| ATTACK | 67% | 2% |
| GATHER | 59% | 2% |
| DEFEND_BASE | 63% | 14% |
| RETREAT | 27% | 1% |

Where the first question found the intent's own kind, spells lasted longer: ATTACK with an engage commitment 20 s
median against 15 s, GATHER with a move commitment 31 s against 18 s.

**Read.** The short holds (10-11 s against the pros' 15-20 s) come with a commitment the pros' standing intents never
lack. It is missing for two reasons: the main in contact is never asked, and a switch out of contact rarely brings an
order. From ATTACK the next intent is GATHER (the model's 0.68-0.72; 70-82% of Gary's ATTACK spells), so an ATTACK cut
short by the hazard hands its time to GATHER.
That is consistent with GATHER's excess (33-38% against 29%), but it is not measured as its cause.

**The proposal (input parity, no scripted order).**
1. **The intent's age as a commit-model input.** Ticks since the cluster's intent began: on the pros' rows as the
   labeller counts `held`, in play from the intent's `since`.
   - At a pros' switch the order follows 92-100% (ATTACK), at a standing tick 20-31%. The model can learn the
     difference only if it sees it.
   - 0 games: train/commit.py --intent with the input, checked held-out (P(act | the first tick) by intent against
     the pros'). Then re-query IN304's 13,677 saved main questions with the age from the records.
2. **The commitment in contact.** In the pros' data a fighting cluster's orders renew its commitment. In Gary the
   role model's orders in contact are not commitments, so the main's lapses to none and the hazard reads it at x3.9.
   - 0 games first: read how ingest/army_dataset.py counts the pros' orders in contact.
   - Then either count the role model's orders as the data counts them, or ask the commit model about the main in
     contact as the data has it.
- Not proposed: clearing the commitment on a switch. It lowers P(act), and the hazard reads "none" at x3.9.
- A 16-game screen only after both, judged on measures expected to move severalfold:
  - spells with no order for the main: 86% of ATTACK's;
  - no commitment when the hazard fires: 67% against the pros' 2%;
  - hold medians: 10-11 s against 15-20 s.
- The army's share at attacks (0.34 against 0.45) needs 48 games.

### Check 2: the threats nobody went to

**91 draws** of "nobody goes" against more than 20 supply (IN304a 35, IN304b 56; threat median 32, P(send) median
0.64). Each was followed in the records and on the replay's 5 s ticks. A threat "lasts" until it has been gone 20 s
(the layer's END_S). It is read from the grid's in-sight and 30 s memory channels, so up to 30 s of memory counts.

| The draws | n | A defence of it within 120 s | The threat lasted (median, p75) | Own fighters within a cell (share of its ticks) | Own supply there (median) | Losses there (mean) |
|---|---|---|---|---|---|---|
| The main within 2 cells already | 37 | | 59 s, 116 s | 92% | 17 | 15.7 |
| Main away, defended later | 18 | all | 34 s, 67 s | 76% | 4 | 22.1 |
| Main away, no defence in 120 s | 36 | none | 37 s, 70 s | 51% (none on any tick: 8) | 0 | 14.8 |

- Losses are the grid's loss weights: an SCV 2, a building 4, a fighter its supply x2.
- Over all 91, a defence of the same threat (a detachment, or the main switched to DEFEND_BASE, within 2 cells) came
  within 120 s for 37: 7 within 10 s, 13 within 30 s, 23 within 60 s, median 42 s.
  - Each of these is a redraw on a doubled threat or on Gary's losses at home growing (§10).
  - 23 draws were drawn "nobody" again within 120 s.
- Over 60 s with own fighters near on under a quarter of its ticks: 4 of 91.
  - Odyssey 4007 27:25, 80 s; Odyssey 4009 23:04, 77 s; Odyssey 4015 28:57, 63 s.
  - KnockOut 4011 7:45, 60 s, defended after 31 s.
- **Odyssey 4007's GATHER, 8:18-11:02**, was not uncontested:
  - It began with the main at the threatened cell (threat 20 at its own cell, (17,108)).
  - A 13-unit detachment held the base from 7:35 until the threat was gone at 8:56.
  - At 10:20 nobody went against 20 supply at (17,124). Five seconds later the threat was 32 and Gary's losses at home
    had grown: the redraw sent 21 units.

**Read.** Real attacks do not slip past for long.
- In 41% of the draws the main already stands at the threat.
- Where nobody goes and nobody comes within 120 s, the threat lasts about as long as elsewhere, own fighters are near
  half its ticks, and the losses there are no larger than where the main stood.
- Long uncontested threats are 4 of 91, three of them after 23:00.
- The losses redraw fires.
- Not judged here: whether the pros would have sent someone in these states. The model's P(send) was a median 0.64,
  and the 91 are its 1 - P(send) draws.

## 16. Input parity: the intent's age and the commitment in contact (2026-11-26; 0 games)

The two input-parity steps §15 proposed, approved by the user with 0 games: each step is checked offline, then the
16-game screen is written down (below), not run.

### Step 1: the intent's age as a commit-model input

**The input** (`ArmySpec.intent_age`, `gary/policy/army.py` `intent_age_inputs`): two numbers after the intent's
one-hot. The first is 1 on the intent's first tick. The second is its ticks x 5 s / 120 s, capped at 1.
- **The pros' rows:** the main cluster's age is counted as the labeller counts `held`: 0 on the tick its intent
  began. The data keeps no cluster's identity, so another cluster's age carries on from the tick before's row of the
  same intent within 2 cells (`train/tactical_intent.py` `cluster_intent_ages`).
- **In play:** the age is counted from the intent's `since` (`Tactical.intent_age_s`), as ticks of 5 s. Questions
  0-5 s after a switch are its first tick.
- **The model:** `runs/commit_intent/TvZ_T_intentage` is `TvZ_T_intent` fine-tuned 2 more epochs on the modern games
  with the age (`train/commit.py --intent --intent-age --init`; its new weights start at zero). Its control,
  `TvZ_T_intent_more`, has the same 2 epochs without the age.
- **The option:** `intentage` (with `intent`) plays it. It is not in any build.

**Held out** (47,875 ticks): order against keep AUC 0.806 (deployed), 0.817 (control), 0.845 (age). The
destination's top 5: 0.378, 0.391, 0.388.

| Held out, P(act) | Pros | Deployed | Control | Age |
|---|---|---|---|---|
| ATTACK, first tick (3,791) | 0.637 | 0.363 | 0.397 | **0.592** |
| ATTACK, standing (13,892) | 0.230 | 0.262 | 0.264 | **0.229** |
| GATHER, first tick (3,846) | 0.573 | 0.389 | 0.358 | **0.568** |
| GATHER, standing (11,309) | 0.208 | 0.300 | 0.258 | **0.224** |
| DEFEND_BASE, first tick (2,347) | 0.333 | 0.182 | 0.188 | **0.321** |
| DEFEND_BASE, standing (8,538) | 0.142 | 0.151 | 0.153 | **0.138** |
| RETREAT, first tick (639) | 0.892 | 0.667 | 0.680 | **0.827** |
| RETREAT, standing (418) | 0.289 | 0.571 | 0.587 | 0.450 |
| HOLD (both) | 0.000 | 0.010 | 0.003 | 0.002-0.003 |

**No tick-0 degeneracy.** The labeller reads a pros' intent from the tick's order, so the first tick is partly the
label's. Three checks show the model did not learn a shortcut:
- **The pros' first ticks are not all orders.** 36% of ATTACK's and 43% of GATHER's keep. Those are switches made by
  the commitment's kind, or by a threat. The model's first-tick P(act) matches the pros' share; it is not near 1.
- **The kind on the orders:** the argmax kind on the first tick's orders, ATTACK 0.45 to 0.83 and GATHER 0.52 to 0.82.
  On standing orders it fell (0.30 to 0.27, 0.37 to 0.25), and the standing P(act) went to the pros'. The age
  separates the two kinds of ticks; it does not give away the order.
- **The destination does not move with the age.** On the first tick's orders the cell is top 1 / top 5: ATTACK
  0.142 / 0.409 (control 0.142 / 0.413), GATHER 0.073 / 0.213 (0.073 / 0.219). It stays below the standing ticks
  (ATTACK 0.156 / 0.464). The age tells the model when, not where.

**IN304a+b's 13,679 saved main questions** re-queried with the age from the records (seconds since the main's
switch; every question's intent matches its record):

| Gary's questions, P(act) first tick / standing | Deployed | Control | Age |
|---|---|---|---|
| ATTACK (3,829; 752 first) | 0.243 / 0.154 | 0.282 / 0.168 | **0.480** / 0.122 |
| GATHER (6,347; 1,090) | 0.382 / 0.336 | 0.384 / 0.293 | **0.607** / 0.258 |
| DEFEND_BASE (2,227; 467) | 0.094 / 0.081 | 0.098 / 0.079 | **0.210** / 0.069 |
| RETREAT (182; 92) | 0.454 / 0.398 | 0.460 / 0.405 | **0.642** / 0.285 |

- **Per spell, as a draw** (1 - the product of keep over a spell's questions; spells never asked send none): ATTACK
  sends none in 85% (deployed), 84% (control) and 81% (age) of 2,179 spells. GATHER: 71%, 71%, 68%.
- **Why so little:** 64% of ATTACK's spells and 58% of GATHER's are never asked (§15: the main is in a fight). The age
  helps only spells where the main is asked; step 2 is about the rest.
- This is a static read: an order on the first tick changes the states after it.

**tests/test_intent_pipe.py** (one game, 7 moments; the code with the gas fix below):

| | gt1dev | gt1dev+intentage |
|---|---|---|
| Criterion 1 | 94% of 69 (pass) | 100% of 55 (pass) |
| Criterion 2 | 3 of 5 army-active moments (fail; 3 of 6 moments) | **4 of 5 (pass; 4 of 7 moments)** |
| The main after a forced ATTACK (keep / engage / move) | 8 / 4 / 0 | 6 / 7 / 0 |

Criteria 3-5 pass on both. One game: the arms diverge after the first different order, so the moments differ.

### Step 2: the commitment in contact, as the data counts it

**How the pros' data counts it** (`ingest/army_dataset.py`):
- **The orders:** every order to army units in the replay's commands counts: move, attack-move, attack or patrol,
  with at least 4 supply of fighters selected (the resim's `army` lines). Whose hand gave it is not recorded, so a
  micro order counts as much as a macro one.
- **What makes one a commitment:** an order that sends its selection 2 or more cells. Engage if its target is within
  a cell of known enemy presence, move otherwise.
- **A cluster's commitment:** the last such order within 120 s whose path, from the selection's centre to the target,
  passes within 2 cells of the cluster.
- **So a fight keeps its commitment:** the pros' orders in contact renew it whenever they move a group 2+ cells
  (chasing, pulling back), and shorter ones leave the order that brought the cluster there standing.

**In play** (`army.py`): only the commit model's sent orders are commitments (`self.commitments`). The role model's
orders, `roles` and `roles:queued`, and the intent layer's, calm's and the rules' are not, even when they send 4+
supply 2+ cells.

**Measured on IN304a+b's own replays.** `ingest/army_dataset.py` was run on Gary's games
(`data/interim/army_gary/v6`): the main's commitment at each intent switch, as play counted it (rebuilt from the
records as in §15) against as the data counts it.

| The intent that ended | Switches | No commitment, play's count | No commitment, the data's count | The pros' (§15) |
|---|---|---|---|---|
| ATTACK | 2,151 | 67% | **24%** | 2% |
| GATHER | 2,328 | 59% | **23%** | 2% |
| DEFEND_BASE | 1,576 | 63% | **21%** | 14% |
| RETREAT | 208 | 27% | **8%** | 1% |

The hazard's switches alone: ATTACK 69% to 24%, GATHER 61% to 23%.

Where play had none and the data a commitment, the order that made it (order records within 6 frames of its time):
- ATTACK's 933: the intent layer's own orders 27%, the role model's 39% (`roles:queued` 24%, `roles` 8%, both 7%),
  calm 16%, `rule:load` 13%.
- GATHER's 869: the intent layer 28%, the role model 40%, calm 15%, `rule:load` 13%.
- A load into a bunker is not one of the data's order kinds, so `rule:load` is most likely another order in the
  same frames. Read this split as approximate.

**The play-side fix (proposed, not built).** Count Gary's own army orders as the data counts them, whoever gives
them.
- **Where:** one hook where every command is sent with the selection (`gary/interface.py`, where each sent order is
  recorded). It is play's twin of the resim's `print_army_command`.
- **What it does:** for a move, attack-move, attack or patrol whose selection holds 4+ supply of fighters (2+ of
  flyers for an air cluster) and is sent 2+ cells from its centre, append (frame, from cell, to cell, engage/move,
  air) to the army's commitments. Engage when the target is within a cell of known enemy presence (the tracker's
  grid, as `engaging()`). The commit model's own orders already append theirs.
- **What it is not:** it is input parity, not a rule. No order changes; the commit model's and the intent model's
  commitment inputs are counted as their data counts them.
- **Its effect:** it changes every build whose commit or intent model reads the commitment (gt1, gz1, gp1 and the dev
  builds), so parity is recorded again, and tests/test_inputs.py should compare the commitment at commit questions.
- **Expected:** the main's "none" at the switch from 67% to about 24% (ATTACK), 59% to 23% (GATHER), per the table.
  The remaining gap to the pros' 2% is the clusters' and cells' matching (records' cells against the data's densest
  cell) and Gary's own order pattern.

### The 16-game screen (written before it runs; not launched)

**What runs:** `gt1dev+intentage` with the commitment fix (one new option, `ordercommit`; first named `incontact`, an older option's name, so it never ran) against
`gt1dev` on the same code. Both play gz1 on the 8 ladder maps, seeds 4004-4005 (16 paired games), 30 minutes,
`--gg 0`, paired by map and seed. The baseline is replayed on this code.

**What it judges, on measures expected to move severalfold** (16 games resolve those, not the score):

| Measure | Now (IN304a+b, gt1dev's arm) | The pros' | Expected | Read as moved if |
|---|---|---|---|---|
| The main has no commitment when the hazard fires (ATTACK / GATHER) | 67% / 59% | 2% / 2% | about 24% / 23% (step 2) | under 40% |
| ATTACK spells that send the main no commit order | 86% | ATTACK's first tick acts 64% | under 70% | under 75% |
| Hold medians, ATTACK / GATHER | 10-11 s | 15-20 s | 14 s or more | a third longer |
| P(act) at the first question after a switch (ATTACK) | 0.25 | 0.64 (held out) | 0.45-0.60 | over 0.40 |

**Watched, not judged at 16:**
- The paired score by supply. 16 games resolve about +-0.17 (the §9 screen's): only a loss beyond it stops the arm.
- The army's share at attacks (0.34, the pros' 0.45: needs 48 games).
- GATHER's labelled share (33-38%, the pros' 29%).
- Deaths alone.

**Next if it moves:** a 48 against the same baseline (MDE about 0.10-0.15 by supply), per AGENTS.md.

## 17. The 16-game screen (2026-11-27; IN305a against IB305a)

**The round.**
- `gt1dev+intentage+ordercommit` (IN305a) against `gt1dev` replayed on the same code (IB305a). Both play gz1 on the 8
  ladder maps, seeds 4004-4005, 30 minutes, `--gg 0`, paired by map and seed.
- The commitment option was first named `incontact`, an older option's name (the role model in contact, in gt1dev),
  and the older entry won, so the hook never ran. It was renamed `ordercommit` before this round. On a test game, its
  commitment matches the data's count on the same replay: "none" 19% and 19% at 21 intent switches, and 8% and 8% at 73
  commit questions.
- Both arms play on the local data rebuilt after the 2026-11-26 loss, with gt1 unsteered (docs/PROGRESS.md). So the
  baseline is the replayed IB305a, not §13's IN304 figures. Its numbers differ: for example, ATTACK's "none" when the
  hazard fires is 75% here against §15's 67%.
- The measures come from the records (the main's commitment the hazard read, spells, first questions), eval/alone.py,
  eval/paired.py, eval/gap_windows.py and `train/tactical_intent.py --gary`.

**The criteria, written before it ran (§16):**

| Measure | Baseline (IB305a) | ordercommit + intentage (IN305a) | Bar | Read |
|---|---|---|---|---|
| The main has no commitment when the hazard fires: ATTACK / GATHER | 75% (238 of 318) / 63% (226 of 357) | **31% (72 of 230) / 25% (66 of 261)** | under 40% | **Moved** (the step-2 estimate was 24% / 23%) |
| ATTACK spells that send the main no commit order | 88% of 376 | 76% of 281 | under 75% | **Missed, narrowly**: down 12 points |
| Hold medians: ATTACK / GATHER | 6.2 s / 5.8 s | **15.6 s / 10.7 s** | 14 s or more, or a third longer | **Moved** |
| P(act) at the first question after an ATTACK switch | 0.21 (asked in 27% of spells) | **0.45** (asked in 44%) | over 0.40 | **Moved** |

- Other kinds: DEFEND_BASE "none" 66% → 14%, first-question P(act) 0.09 → 0.22; RETREAT "none" 42% → 7%, P(act)
  0.48 → 0.78.
- Why ATTACK still sends no order in 76% of its spells: more are asked (44%, was 27%), but most still are not. As §15
  found, the main in a fight is the role model's.

**Watched, not judged at 16:**

| Measure | Baseline | Arm | Paired difference, 90% |
|---|---|---|---|
| Paired score by supply | 0.422 | 0.375 | -0.047 [-0.125, +0.031] (within the +-0.17 a 16 resolves; 96 games would resolve +-0.031) |
| The army's share at attacks (games' median / all attacks' median) | 0.285 / 0.27 | 0.359 / 0.33 | +0.012 [-0.087, +0.111] (the pros' 0.45) |
| Attacks a game | 2.7 | 4.3 | +1.6 [+0.5, +2.8] |
| Late arrivals per fighter there | 0.082 | 0.064 | -0.018 [-0.053, +0.017] |
| Deaths alone (games' mean; all deaths) | 0.257 (20%) | 0.207 (17%) | -0.049 [-0.094, -0.003] |
| Fighters alone, 5-20 min samples | 0.098 | 0.080 | -0.018 [-0.046, +0.006] |
| Ground fighters in no asked cluster | 0.129 | 0.069 | -0.059 [-0.123, -0.012] |
| Gap, all windows (lower: nearer the pros) | 0.488 | 0.446 | -0.043 [-0.098, +0.034]; 25-30 min -0.092 [-0.176, +0.022] |

- Results: the arm had 12 games go the full 30 minutes and lost 4 (T ahead 4, even 4, Z ahead 4). The baseline had
  11 at time and lost 5 (T ahead 5, even 6).
- Deaths alone are still the roles' (89% of the arm's alone deaths had the role model's order last).

**Intent shares** (the labeller over each round's replays; the pros' in §2):

| | DEFEND_BASE | ATTACK | RETREAT | GATHER | HOLD | HOLD at 20+ min |
|---|---|---|---|---|---|---|
| Pros | 25.0% | 36.6% | 3.2% | 29.0% | 6.2% | 3% |
| Baseline (IB305a) | 22.1% | 27.6% | 1.1% | 38.9% | 10.3% | 9% |
| Arm (IN305a) | 23.2% | 34.7% | 0.6% | 28.6% | 12.9% | 10% |

- GATHER's labelled share falls to the pros' (38.9% → 28.6%, the pros' 29.0%). ATTACK rises toward theirs (27.6% →
  34.7%, the pros' 36.6%). HOLD stays above (12.9%; the first five minutes are 78% HOLD).
- The layer's own time shares, from its records: ATTACK 27.8% → 34.6%, GATHER 33.7% → 28.6%.

**Coach Q4** (12 answers at 7, 11 and 15 minutes of 4 games; runs/league/IN305a/q4_review.txt, not in the repository).
- Each answer cites the intent in force, its target, the model's odds at the switch, and the commit decisions under it.
- Each commit decision now carries the commitment the hook counted. For example: "keep its current orders (84%) for
  7 units at tile (12,36), attacking for 18 s" (KnockOut 4004, 6:40). Without the hook, an order from another layer is not
  counted, and such a group reads "no orders for 120 s".
- One pattern to watch: the main kept an ATTACK-era commitment 29-36 s into a GATHER spell (keep 50-95%) before moving
  to the gather point (KnockOut 4004, 6:51-6:58).

**Read:** three of the four criteria moved severalfold, as written. The fourth missed its bar by one point, with the
cause identified (the main in a fight is not asked). The score is not measurably worse at 16. Per §16 the next step
is a 48 against the same baseline; it is not launched (it waits for approval), and nothing is folded.

## 18. The 48 (2026-11-27; IN306a against IB306a)

**Written before it ran.**
- **Arms:** `gt1dev+intentage+ordercommit` (IN306a) against `gt1dev` (IB306a), both against gz1. The 8 ladder maps,
  seeds 4006-4011 (`--first 4006`: fresh, not the screen's 4004-4005), 48 paired games each, 30 minutes, `--gg 0`,
  paired by map and seed. Code at a29feea, unchanged.
- **The paired score by supply:**
  - The MDE planned is about 0.10-0.15, a 90% interval of about +-0.07-0.12.
  - The screen's own pairing (eval/paired.py: spread 0.188, 96 games resolve +-0.031) puts 48 at about +-0.044.
  - If the interval holds 0 and the point is within 0.10, the decision is a second 48 (`--first 4012`) before any fold.
- **The army's share at attacks** (eval/alone.py): resolves about +-0.04 at 48 (the screen's baseline 0.27-0.29;
  the pros' 0.45).
- **Ground fighters in no asked cluster, and deaths alone:** about +-0.03-0.04.
- **Fidelity: do §17's gains hold on fresh seeds?**
  - The main has no commitment when the hazard fires (ATTACK / GATHER).
  - ATTACK spells that send the main no commit order.
  - Hold medians (ATTACK / GATHER).
  - ATTACK's first-question P(act).
  - Labelled intent shares, attacks a game, late arrivals, and the gap per window (eval/gap_windows.py).
  - The defence, including "nobody went" against more than 20 supply.
- **Coach Q4:** 12 answers (7, 11 and 15 minutes of 4 games), in runs/league/IN306a/q4_review.txt (not in the
  repository). Quirks to look for: load-rule overrides, and slow moves after a switch (§17).
