
## 8. The pivot: directives as labels for conditioned leaves. Step 1's audit (2026-11-28; 0 games)

The user's direction: the trunk emits discrete directive labels (`PREP_VS_MUTA`, `PREP_VS_LURKER`), and the learned
leaves, MacroNet and PlacementModel, take them as inputs. This replaces the trunk's shopping lists, a scripted turret
ring and a q90 mask. This audit reads what the unconditioned leaves already do, and what conditioning would need.

### 8.1 What the leaves already do with answers.py off

The rounds: G4299a (answers off, `gt1dev+scansample+noanswers+shadow+trunk`, 96 games against gz1) against RD285a
(answers on, gt1dev, 96 games against gz1), both from 2026-11-25. Also IN307a (answers on, gt0.56dev's code) and the
modern pros. gt1dev already plays the PlacementModel (option `place`).

**Against the Spire** (spire-first games; times from the Spire's order):

| | Answers off (G4299a, 72) | Answers on (RD285a, 69) | IN307a (43) | Pros (2,196) |
|---|---|---|---|---|
| An Engineering Bay by +300 s; its median time | 99%; -24 s | 100%; -34 s | 100%; -50 s | 99%; +32 s |
| A turret by +300 s; the first's median time | 97%; +75 s | 100%; +72 s | 100%; +64 s | 97%; +96 s |
| Turrets ordered by +300 s, median (quartiles) | 9 (7-13) | 9 (7-11) | 9 (7-11) | 8 (6-10) |
| Turrets within 10 min of the Spire, median | 11 | 12 | 12 | 10 |
| Settled bases with a turret by their minerals at +150 s | 82% (89 of 109) | 84% (89 of 106) | 86% (56 of 65) | 88% (422 of 479; 400 games) |
| Turrets by a mineral line (within 10 tiles of its minerals) | 51% | 62% | 58% | 44% |
| ...of those, on a workers' lane | 33% | 25% | 24% | 43% |
| By a mineral line, before / after seeing a Spire or Mutalisk | 62% / 46% | 62% / 62% | 62% / 57% | 47% / 45% (600 games, the sightings' first sight of the plan's tech) |

- **SCVs lost at 6-12 minutes** can't be read here. The records' deaths are the army's units only; it needs a replay
  pass, a new measure for the screen.
- **Reading:**
  - With answers.py off, the unconditioned MacroNet already makes the pros' anti-mutalisk build: an Engineering Bay
    before the Spire, a turret by +75 s, 9 by +300 s, 82% of the settled lines covered.
  - The PlacementModel's turrets after a Spire is seen stand by a mineral line as often as the pros' (46% against 45%).
    The pros' Terrans don't move their turrets to the lines on seeing it, unlike the Protoss's cannons (14% → 51%,
    ingest/placement_dataset.py).
  - The executor keeps the mineral-side turrets off the lanes (24-33% on one, the pros 43%). There is no tile-level
    gap.
  - answers.py's ring adds a little coverage (+2-4 points) and more turrets by the lines than the pros put there (62%
    against 44%).
- **Against lurkers** (lurker-first games running 10 minutes past Lurker Aspect; times from it):

| | Answers off + trunk (G4299a, 7) | Answers on (RD285a, 9) | Pros (126) |
|---|---|---|---|
| Turrets within 10 min of the tech, median | 7 | 6 | 5 |
| First detection | +29 s | +54 s | +34 s |
| Siege Mode / the first Siege Tank | +163 / +165 s | +148 / +153 s | +174 / +157 s |
| The first Science Vessel | +148 s | +226 s | +256 s |

  §3's told-lurker drills (4 games each) had turrets 5 with the answers, 9 without and 11 under the trunk. The lurker
  side is where the leaves differ from the pros most. It is thin in games: gz1 plays lurker-first in 7-9 of 96.

### 8.2 The data and the models, after the loss

| | On disk | Missing |
|---|---|---|
| data/interim/macro/v1 | TvZ 2,426 modern + 14,127 old; ZvZ 2,825 + 6,107; PvZ 2,660 modern | TvT, PvT, PvP, and PvZ's old games. The shared Terran model learned TvZ, PvT and TvT |
| data/interim/placement | none (lost) | every matchup's: modern games only, re-played in-process (ingest/placement_dataset.py) |
| The plan belief's out-of-fold odds (runs/plan_belief/TvZ_T_oof_20261124) | modern TvZ Terran, 2,431 games, 2:30-10:00 every 30 s | the old era. The OOF holds only modern games, though the model trained on 16,480 |
| data/interim/sightings | TvZ_T modern, 2,423 games (rebuilt) | `--era all` for an all-era OOF |
| The models | runs/macro_exp/T_all_v2all (8.2 min to train, 8.2 M samples, 6 epochs); runs/placement/TvZ_T_20261109 (4 s, 95 k samples) | |

**Directive labels, causal:**
- At each of a game's belief samples, the directive state is what the trunk would set from the cross-fitted odds (no
  fold saw the game) and the table (§7's rule), held between samples and after 10:00.
- Every macro and placement sample of a modern TvZ Terran game gets the bits at its time. Every other sample gets
  "unknown": the other matchups, the old era, and the moments before 2:30.
- In play the trunk's pinned belief model gives them. Play and data differ only by the cross-fitting, as the trunk's
  P_pro already does.

**Thin lurkers:**
- Modern lurker-first games are 137; the PREP_VS_LURKER bit would be on in a few hundred moments.
- An all-era OOF needs the sightings `--era all` (16,000 games, about 40 minutes at 6 workers, from §7's 6 minutes for
  2,400) and train/plan_belief.py's out-of-fold pass on them. It brings the old era's lurker-first games: lurker-first
  is 17.5% of all eras' TvZ Zerg plans, 3,163 games (the v2 catalogue).

**The inputs:**
- MacroNet's FeatureSpec (gary/policy/macro.py) already carries categories with an unknown slot (`styles`, `maps`,
  `matchups`). A `directives` field would take three slots per directive: off, on, unknown. The spec lists the
  directives by name, race-keyed as trunk.DIRECTIVES is; a matchup without them reads unknown.
- PlacementModel's `encode` (gary/policy/placement.py) takes the same bits on its global row.
- The FeatureSpec travels with each model, so the deployed models stay as they are.

**The wall clock (offline, 0 league games), for the Terran:**

| Step | Time |
|---|---|
| TvT's old games re-simulated (about 2,700) | about 7 min |
| TvT and PvT macro datasets (about 7,000 games) | about 16 min |
| The directive labels joined to the macro and placement samples | minutes |
| TvZ Terran placement dataset (about 2,400 modern games re-played) | about 10 min |
| T_all retrained with the directive inputs; the TvZ placement model | about 10 min; seconds |
| Optional, the all-era OOF: sightings `--era all`, then the belief's out-of-fold pass | about 40 min + its training |
| **Total** | **about 1-1.5 h, or 2-2.5 h with the all-era OOF** |

**The tools:**
- **eval/match.py `--gg`:** unaffected. Each critic (gary/policy/value.py) carries its own FeatureSpec in its
  checkpoint (train/value.py builds it from the saved spec), so a new MacroNet spec doesn't reach it unless the critics
  are retrained.
- **Coach Q3:** eval/coach.py's answer already prints each macro decision's attribution (gary/policy/attribution.py
  `explain_macro`: the odds with an input group zeroed, "what weighed most").
  - With the directive bits as their own group, read as unknown when "zeroed", Q3 gains the counterfactual: "the
    anti-mutalisk directive (without it 12%)". That is the model's odds shift, about a millisecond a decision.
  - The other half is a line joining the directive's record: the trunk's branch_select records already hold the
    belief, the cell, P_pro and n. Q3 would cite it next to the decision the bit moved.

### 8.3 Step 2, proposed

1. **The data** (0 games): rebuild TvT and PvT's macro datasets and the TvZ Terran placement dataset. Optionally run the
   all-era sightings and OOF, recommended for the lurker side. Join the causal directive bits.
2. **The leaves** (0 games): T_all and the TvZ Terran placement model, retrained with the directive inputs. The bits are
   dropped to unknown on a random 20% of the samples where they are known, so the model also learns the unknown case.
3. **The 0-game gate, written before training** (held-out modern TvZ games, the model's own held-out split):
   1. **No regression:** held-out top-1 and log loss within 0.005 of the unconditioned model's, overall and per
      matchup.
   2. **PREP_VS_MUTA flip:** on held-out spire-first states at 4:30-8:00 with fewer turrets than twice the bases, set the
      bit off → on. P(Missile Turret) rises in at least 70% of states, and the mean shift is at least half the pros' own
      difference in turret rate between the table's taking and non-taking moments.
   3. **PREP_VS_LURKER flip:** on held-out lurker-first states at 6:00-10:00, off → on.
      - P(Missile Turret) falls in at least 70% of states.
      - P(Siege Mode) + P(Siege Tank) + P(Science Facility) + P(Science Vessel) rise in at least 70%.
      - Both shifts point the pros' way.
   4. **Placement:** P(by the minerals | PREP_VS_MUTA on) - P(… | off) within +-0.05. The pros don't shift (47% / 45%).
      A spurious shift fails.
   5. **Unknown:** with the bits unknown, the held-out odds are within 0.01 of the unconditioned model's on the
      non-TvZ matchups.
4. **Then the play side:**
   - the trunk sets the bits from its belief and table (§7's rule, re-scored every sample);
   - MacroNet and PlacementModel read them;
   - answers.py's turret jobs and the lurker answer's shopping list are off.
   - Its 16-game screen is written before it runs: §6's measures, plus the lurker drills' turret count (pros 5) and
     the lurker answer's timings.
