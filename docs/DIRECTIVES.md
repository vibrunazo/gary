# Phase 2's mid-game directives and the early G4 check (design, 0 games; 2026-11-28)

docs/REFOCUS.md §4.3 leaves two Phase 2 items besides the intent layer:
- the mid-game directives, `PREP_VS_MUTA` and `PREP_VS_LURKER`'s turret cut, so `gary/agent/answers.py` can retire
  and Coach Q3 is explained by the trunk;
- one early G4 test.

This file has the 0-game counts and the design for both. Nothing is built yet; each step waits for the user's call.

## 1. What answers.py still does (gt1 and gt1dev both: `answers: True`, `mutas: True`)

`noanswers` is an option, not in gt1dev. It was on only in Phase 1's rounds (`+scansample+noanswers+shadow+trunk`).

In IN307a's records (48 games, gt0.56dev's code, against gz1):

| Job | Where | What it does | IN307a (48 games) | Successor |
|---|---|---|---|---|
| Read the Zerg's plan | `observe` | mutas on a Spire or mutalisk seen; lurkers on a lurker, its egg, or a Den with Lair and no Spire | (every game) | the trunk's plan belief (`gary/policy/plan_belief.py`, cross-fitted) |
| Tech scan (STOP-GAP) | `tech_scan` | a scan of their main at 6:30 and 8:30 when nothing is read | 42 scans | `scansample` (Phase 1's build), then the learned scan model |
| The mutalisk turret ring | `next_goal`, `turret_goal` | an Engineering Bay and an Academy, then turrets in every mineral line, 2 per base, nearest the Zerg first, at a spot off the mining paths | 686 turret goals, 26 Engineering Bay and Academy goals | **`PREP_VS_MUTA`** (new, §2) |
| The mutalisk turret gate | `allows` | the model's own turrets held until every mineral line has its own | 555 turret decisions passed over | the ring as the directive's goal; no veto |
| The lurker answer | `next_goal` | Factory, Machine Shop, Siege Mode, 2 tanks, Starport, Control Tower, Science Facility, 2 vessels, Irradiate, 4 tanks | 15 goals (games read as lurkers) | `PREP_VS_LURKER` (built in Phase 1, option `trunk`; without Irradiate and the later tanks) |
| The lurker turret cut | `allows` | turrets beyond one a base refused while the plan reads lurkers | (no lurker-first game in IN307a) | **`PREP_VS_LURKER`'s turret cut** (§3) |

## 2. `PREP_VS_MUTA`: the counts

The modern pros on the ladder maps, 2,196 spire-first TvZ games, the Spire at a median 4:00. Each item is the first
of its kind ordered, timed from the Spire's order; the interval is a 90% Wilson interval. Gary is IN307a, with
answers.py on: 43 spire-first games, the Spire at 4:48.

| Item | Pros: by +150 s | Pros: by +300 s [90%] | Pros: median from the Spire | Gary: by +300 s | Gary: median |
|---|---|---|---|---|---|
| Engineering Bay | 98% | 99% [99, 99] | +32 s (40% before the Spire) | 100% | -50 s |
| Missile Turret | 94% | 97% [97, 98] | +96 s | 100% | +64 s |
| Academy | 72% | 88% [87, 89] | -16 s | 100% | -58 s |
| Comsat Station | 62% | 81% [79, 82] | +70 s | 98% | +41 s |
| Armory | 32% | 43% [42, 45] | +42 s | 40% | +39 s |
| Goliath | 10% | 13% [12, 14] | +88 s | 21% | +76 s |
| Valkyrie | 19% | 26% [24, 27] | +105 s | 14% | +260 s |
| Starport | 36% | 87% [86, 89] | +201 s | 86% | +196 s |
| Science Facility | 5% | 45% [43, 47] | +263 s | 50% | +247 s |
| Science Vessel | 3% | 16% [15, 17] | +262 s | 10% | +283 s |
| Turrets ordered by +300 s (median, quartiles) | | 8 (6-10) | | 9 (7-11) | |

By the Terran's style:
- **Style 1, standard bio** (1,442 games): Engineering Bay and Academy 100%, the turret at +94 s, 9 turrets by +300 s,
  Goliaths 0%, a Comsat at +62 s.
- **Style 2, Factory and vultures** (489 games): an Armory 95% at +24 s, Goliaths 51%, Valkyries 55%, the Academy
  late (59% by +300 s), 7 turrets.
- **Style 3, Factory and Starport** (257 games): the Starport already there (97% before the Spire), Control Tower 92% by
  +150 s, Science Vessels 32%, 6 turrets.

eval/answer_time.py against the Spire:

| | First turret | Turrets by +150 s | Turrets within 10 minutes |
|---|---|---|---|
| Pros (2,144 games) | +96 s | 6 | 10 (8-12) |
| Gary, IN307a (43 games) | +64 s | 6 | 12 (10-14) |

**Reading:**
- With answers.py on, Gary's anti-mutalisk build is already the pros' in kind and count, its turrets about 30 s
  early.
- What answers.py adds is the ring: turrets in the mineral lines, nearest the Zerg first. That is what a human's
  mutalisks punish (human game 1, docs/PROGRESS.md v0.25).
- `PREP_VS_MUTA` must keep this, not improve on it. Its gain is the trunk owning it: Q3 explained by the pros'
  frequency, and one owner of the macro (§3.3).
- **The belief** (`runs/plan_belief/TvZ_T_oof_20261124`, cross-fitted, summed over the four spire-first plans)
  separates the spire-first games well only from 6:00. AUC by minute: 0.62 at 3:00, 0.74 at 4:00, 0.83 at 5:00,
  0.95 at 6:00, 0.99 at 7:00. In modern TvZ 89% of games are spire-first, so the pros' Engineering Bay and first
  turret are mostly the base rate, ordered before the Spire is seen. The table must keep this: against a low
  belief the contrast cell is high too, and the branch is started by the base rate in the early minutes.

## 3. `PREP_VS_LURKER`'s turret cut: the counts

Turrets ordered within 10 minutes of Lurker Aspect (eval/answer_time.py), against gz1dev told the lurker style (4
games each, Phase 1's rounds):

| | Turrets within 10 min of the tech |
|---|---|
| Pros (41 modern games running 10 minutes past it) | 5 (quartiles 2-8) |
| answers.py on (SC291a4) | 5 |
| answers.py off (NA292a4) | 9 |
| The trunk's PREP_VS_LURKER, no cut (TK293a4) | 11 |

The cut matters. Without it the model builds about twice the pros' turrets against lurkers. That is gas and
minerals the lurker answer (Siege Mode, tanks, vessels) needs.

## 4. Coach Q3 now (IN307a, 12 answers: 6, 8 and 10 minutes of 4 games)

The answers name, for every macro decision in the minute, the model's odds or the rule that set it.
- Turrets: 17. Six were set by answers.py ("chosen by a fixed rule (an answer to the zerg's plan)"). Eleven were the
  model's dice at 4-42%.
- Tech buildings and research: 10. Nine were the model's dice (a Factory at 5%, a Starport at 8%, a Science Facility
  by summed odds), and one was answers.py.
- None is explained by the trunk: neither directive is in gt1dev.

Under the two directives, the ring's turrets and the anti-mutalisk and anti-lurker items would read as the trunk's
goals, with the pros' frequency, n and the belief that started them (as `PREP_VS_LURKER`'s do in Phase 1's records).

## 5. The design

One owner, one rule at a time (docs/REFOCUS.md §3.3). Race-keyed: the directive tables are keyed by (race, enemy race),
as `trunk.DIRECTIVES` is. Every matchup without a table says "not enough evidence" and plays on.

1. **`PREP_VS_MUTA`** (TvZ, the Terran):
   - **Its items:** an Engineering Bay, then the ring, one turret in each settled base's mineral line, then a second
     per line (the pros' 8 by +300 s, 6-10), nearest the Zerg first. The Academy and Comsat stay the model's: the
     pros' style 1 has them before the Spire already, and style 2 doesn't.
   - **The table:** train/pro_branch.py gains the branch. Its event: the next missing item of the chain within
     WINDOW_S (120 s). Its belief: the cross-fitted P(spire first), summed over the four spire-first plans, in the
     same BUCKETS. Its own state: the chain's progress. MINUTES as for the lurker branch, MIN_N 25, the BACKOFF,
     and the contrast at the finest low-belief cell.
   - **The looked split** needs the pros' sighting states (ingest/sighting_dataset.py). Those were lost on
     2026-11-26 with data/interim and must be rebuilt first: 0 games, an offline step over the modern TvZ
     re-simulations. The lurker branch's table was built with them, so its refresh needs them too.
   - **The ring's placement** moves out of answers.py into a shared, race-keyed helper, used by the directive's turret
     goals. It takes the race's static anti-air (a Missile Turret; later a Spore Colony and a Photon Cannon) and the
     mineral line's spot off the mining paths (turret_goal's `near`, `avoid` and `level_at`).
   - **No veto of the model's own turrets**: the ring is the directive's goal, and rules nudge, never veto.
   - **Concurrent with `PREP_VS_LURKER`** (§3.2): both can be active; the turret cut is off while `PREP_VS_MUTA` is.
2. **`PREP_VS_LURKER`'s turret cut:**
   - While `PREP_VS_LURKER` is active and `PREP_VS_MUTA` is not, the macro's turret decisions beyond the pros' 90th
     percentile of turrets are masked. That percentile is taken for the minute under a lurker-first belief, from the
     same table's pro moments, in place of answers.py's fixed one a base.
   - It is a mask of the model's choice, so it gets its full STOP-GAP entry in AGENTS.md, as the pros' caps per minute
     have, with its replacement: the model with the belief as an input.
3. **Retirement:**
   - With both directives on, answers.py's jobs are covered: its plan read by the belief, its scan by `scansample`.
     The option `noanswers` then joins gt1dev with `trunk` and `scansample`, as Phase 1's build had them.
   - answers.py's entry leaves AGENTS.md, and the module retires once gt1 follows.

**The order, one rule at a time:**
1. The sighting dataset rebuilt, and the table built (0 games).
2. `PREP_VS_MUTA` with answers.py's mutalisk jobs off, against gt1dev.
3. The turret cut.
4. `noanswers+trunk+scansample` against gt1dev, the whole replacement, before a fold.

## 6. The screens, written before they run

**`PREP_VS_MUTA`: a 16-game screen.** gt1dev+trunk with the mutalisk answers off against gt1dev, both against gz1:
- gz1 goes spire-first in about 90% of games (43 of 48 in IN307a);
- the 8 ladder maps, seeds 4004-4005, 30 minutes, `--gg 0`, paired by map and seed.

| Measure | Now (IN307a) | Pros | Bar (moved enough, or held) |
|---|---|---|---|
| The first turret from the Spire, median | +64 s | +96 s | within 30 s of the pros' |
| Turrets by +300 s, median | 9 | 8 | 6-10 |
| An Engineering Bay by +150 s | 98% | 98% | at least 90% |
| Mineral lines with a turret by +150 s, per settled base | a new measure, to add to eval/answer_time.py (a turret within 10 tiles of the line's minerals) | the same measure | not below gt1dev's |
| SCVs lost at 6-12 minutes (paired) | a new measure, from the records' deaths | | not measurably more |
| Q3: anti-mutalisk turret and item decisions explained by the trunk | 0% | | at least 80% |
| The paired score by supply | | | not measurably worse (16 games: about +-0.17) |

**The turret cut: 8 drills.** gt1dev+trunk with the cut against gt1dev+trunk without it, against gz1dev told the
lurker style (the suite's plan 4), on 4 maps × 2 seeds:
- turrets within 10 minutes of Lurker Aspect: about 5 with the cut (pros 5, quartiles 2-8), against 9-11 without;
- the lurker answer's timings from the tech (Siege Mode, the first tank, the first vessel) no later.

**The whole replacement** (`noanswers+trunk+scansample` against gt1dev): 48 paired games. The bar is the paired score
not measurably worse (about +-0.08), with each screen's fidelity measures held.

## G4. The early G4 check (spec)

- **What exists:**
  - `gary/interface.py` PROFILES holds `pro` (fitted to the pros' select-to-command time, 7 actions a second),
    `b_rank` (3.5 a second, reaction 300 ms), `b_rank_widescreen`, and `c_rank` (2.2 a second, reaction 400 ms, wider
    scatter).
  - eval/match.py's headless game reads a manifest's `hands` key, defaulting to `pro`. No option sets it yet, and
    `Match` (the tools' replays) always uses `pro`.
  - The drills grade a strict card against its milestones (eval/drills.py, the Phase 1 gate 2 tolerance).
- **Needed (one small option, later):** `hands_b` and `hands_c`, setting the manifest's `hands`.
- **The test:** the same opening card, strict (gt1dev+strict+told1, the standard bio card), against gz1dev told 1.
  Under `pro`, then under `b_rank` and `c_rank`: 4 maps × 2 seeds each, 8 games a profile (24 games), the same seeds.
- **Read:**
  - the card's milestones met (eval/drills.py, the same tolerance);
  - the supply gap per window (eval/gap_windows.py: the macro's, at 2-10 minutes);
  - the hands: actions a minute, reaction time to a unit hit (eval/reaction.py), and camera moves a minute (the pov
    logs).
- **Expected:** milestones held under `b_rank` (the macro decides what, the hands only when), a later and wider spread
  under `c_rank`, and actions a minute falling with the profile. A collapse of milestones under `b_rank` would mean
  the build depends on pro hands: G4 is then not one system with many bands.
- It is a sanity run of the profiles, not a strength test: no win rates are judged.
