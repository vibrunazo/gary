# TODO: open work

Open work is tracked in the [GitHub issues](https://github.com/vibrunazo/gary/issues); this file is their index,
grouped by area, newest thinking first (reconciled with the code on 2026-10-25). When an item is done its issue is
closed and its line leaves this file; docs/PROGRESS.md keeps what was done and how it measured.

## Direction (2026-11-23): docs/REFOCUS.md v2.1 (the user's call; round two folded 2026-11-23)

The plan in docs/REFOCUS.md: build the upper layers of docs/ARCHITECTURE.md that don't exist yet (an enemy-plan
belief, a persistent strategy card, branches chosen by the pros' conditional choice frequencies, templated
explanations from the records) inside gt1dev, on its existing seams, the TvZ Terran first; no new build line, no
delete list (a rule goes one at a time, on its AGENTS.md measure). RL stays parked.

- **Phase 0 (3-5 days): measurement and housekeeping.** Nothing in the dev build changes but the seed fix until the
  remeasure is in.
  1. #64 seeds: done (the army's and the calm layer's draws from the game's seed; every build, gt0.21, gt0.49dev).
  2. gt1dev against gt1 remeasured: done (RD285a gt0.49dev, RP285a gt0.21, 96 paired games against gz1, --gg 0, MDE
     0.11): -0.219 [-0.294, -0.141] by supply, measurably worse (2026-11-11: -0.188); nearer the pros in every window
     (all features -0.06 to -0.21, resolved) and on the build per style. Not promoted: gt1 stays the playing build.
  3. answers.py counted in a full gt1dev round: done (HS284a: 158 forced goals, 3.7% of the macro's decisions, 94
     turret vetoes, no tech scans, in 16 games).
  4. One watched live game per race: done (2026-11-23; docs/PROGRESS.md).
  5. The bridge's new fields over LAN (tools/parity.py): done, 1:1 in every field, but stim and ammo only at zero.
  6. The docs: this section, docs/PROGRESS.md's top summary (rl1), docs/ARCHITECTURE.md §6.8 (the pro-frequency
     departure): done.
  Found in Phase 0 and fixed after the remeasure (gt0.50dev): gt1dev couldn't start a game outside TvZ (option calm
  had only a TvZ model); the calm layer stands aside there now.
- **Phase 1 (in front, no time box; v2.1's order, docs/REFOCUS.md §4.3 "Phase 1 Order"):** scouting first, then the
  TvZ strategic trunk and five templated questions, with the gate written in §4.3. Code and 0-game counts cover every
  matchup (mirrors too); the game gates run in TvZ. Each step is judged on its own check before the next:
  1. Plain fixes (0 games): the scan's main known without `watch`, in one shared place (parity again: gt1 too); Gary's
     games labelled by the pros' rule; the trainer's and the dataset's faults (mirror lookup included); enemy buildings
     recorded by tag and type, so a morph is a sighting.
  2. The counts (0 games, every matchup with resim and taxonomy data): the pros' first sight of tech by type and by
     means, scans with targets, the first scout's stay; Gary's seen given standing; answers.py's goals against turrets
     built; Arm 0 (the milestone error on RD285a).
  3. The sighting states rebuilt race-agnostically to what step 2 says a look must record; a scan as a look verified in
     a scenario; tests/test_matchups.py green in all 6 matchups with the real providers (0 games).
  4. The suite's first read: gt1dev with step 1 against gz1dev told the suite's styles, gg on; the scouting measure,
     each Zerg game's plan as played (16 games).
  5. Scouting (§6 row 8): the learned scan model; `watch` again only if step 2 says so (16 games an option).
  6. The belief re-scored on steps 4-5's games; then belief and card log-only, first over RD285a's records (16-32).
  7. `answers` off once Gary sees; then the lurker answer handed to the trunk end to end (16-48).
  8. Only if Arm 0 leaves a gap: strict drills and the macro A/B (40 + 96-192).
  9. Templates, the execution join, the blind evaluation (live and held-out games).
  10. Gate 4's round on the whole Phase 1 build (96 against gz1, gg off, RD285a's seeds, margin 0.118).
  Steps 1-3 done 2026-11-23 at 0 games; steps 4 and 5 (the scan sampler, option `scansample`, a STOP-GAP in place of
  the learned scan model) and the retreat hold done 2026-11-24 at 48 games, with step 6's re-score of the belief on
  their games (docs/PROGRESS.md). Waiting for the user's approval before step 6's log-only soak and step 7.
- **The army (narrowed in round two):** no hold on the commit model's commitments (measured as not missing); the retreat
  hold (option `retreathold`) as a pipe fix: 16 games 2026-11-24, retreats made/asked 0.13 to 0.26 (the pros 0.78), as
  written, but the units no farther from the enemy 2 s later than without it (eval/retreat_gain.py); kept off, for the
  user's decision; an owned army intent only after the 0-game
  read of units taken from one cluster by another's order (§3.4), not a veto on Phase 2's top-down intents.
- **Maintenance cap:** other fidelity work only for regressions caught in watched games. Paused: (c)'s unstarted
  items (the army at home at 15-20, the PvT tanks) and units alone (below).

## The previous direction (2026-11-12): judged per situation, in every matchup (superseded 2026-11-23)

After the three live games (docs/PROGRESS.md): the rounds and the gap score never showed that Gary's tanks don't
siege against a Zerg, and one viewing did. The work is judged by what a pro would do in the situation Gary is in
(`eval/judge.py`), in every matchup, not by counts a game and not in one matchup first. The steps, in order (an item
gets its issue when it is started; the ones marked "to decide" are proposals, not agreed):

**The order from 2026-11-17 (the user's call, on a review of the week: the tank work fixed the flipping and moved
no top-level measure; most faults found were in the pipe between a model's odds and what Gary carried out, and
apply to every drawn decision; one mode in two matchups took five days):**
a. Done 2026-11-17: the siege work stopped; the mines folded into gt1dev (gt0.40dev, option `minemodel`); `rates`
   for gp1dev and gz1dev judged (RB274a, RR274a): no change in storms (the cast rule's, not a draw), Lurkers in too
   few games, so it is measured in b's table. Each further ability time-boxed to about a day.
b. One check of what a model asks against what Gary carried out, over every drawn decision, layer and race (the
   model's odds on Gary's own judged moments against the transitions it made, by fifths of the odds): the check that
   found every fault of the week, as one table. v1 done 2026-11-17 (`eval/pipe_table.py`, docs/PROGRESS.md): the
   fight and commit layers of every race from played rounds; it finds four of the five known faults. Left: one
   record per fight draw of the Terran and the Protoss (the stage each fault is at, the source of the unasked); the
   Terran's retreats (a fifth of those asked in TvZ); `rates` for gp1dev and gz1dev, proposed to fold on it.
   v2 (2026-11-17): the draws logged, the pros' held-out games as the reference. Found, ranked: retreats short in
   every side (0.18-0.47 for the pros' 0.78-1.02), lost between the order and a move seen; the Terran's PvT and TvT
   fights take the likeliest role (modedice); mines against a Protoss. The user's call: chase these or go to c.
   Done 2026-11-18: the retreats' point (option retreatfar, 6 tiles past the group: they get away, seen as retreats
   0.22-0.49 for the pros' 0.78-1.02; the rest is the turns after it), folded into gt1dev and gp1dev with `rates` into
   gp1dev and gz1dev (the user's call); a hands fix in every build (moves clicked on units). Left, not chased: a
   retreat held for its stretch, the Terran's PvT and TvT fights drawn, mines against a Protoss. Next: c.
c. The upstream decisions ahead of the remaining abilities: the army's positioning and engagements (where the army
   leaves the tanks), and finishing games (item 6 below, the commit layer). So far (2026-11-18, docs/PROGRESS.md): the
   floor off in gt1dev (gt0.44dev) and league games ended at the critic's gg (the user's calls); the standing read:
   out of contact no layer gives a standing unit a short order (eval/calm_check.py: the pros 1.59 a fighter a minute,
   Gary 0.31), and half the commit questions were about clusters smaller than its data's (fixed, gt0.45dev). The calm
   layer (the user's call): folded into gt1dev (gt0.46dev; a new fighter's first rest the pros' 8 s). Army orders now go
   to whole clusters (gt0.48dev and every build: the commit orders the pros' size, the spread nearer). Units alone
   unchanged (0.40, the pros 0.20; read in docs/PROGRESS.md, parked 2026-11-22: the calm layer's one-unit orders the
   next lever). Paused 2026-11-23 under REFOCUS's maintenance cap: home at 15-20 (the old army stays home twice the
   pros'), the PvT tanks.
d. One live game a race, watched, before more decoder work: done 2026-11-23 (Phase 0, step 4).
e. gt1dev against gt1 measured again (paired, and the fidelity measures per window: -0.188 [-0.302, -0.078] on
   2026-11-11), since promotion turns on it: done 2026-11-23 (Phase 0, step 2: -0.219 [-0.294, -0.141], nearer the pros
   in every window).
f. A 16-game round read only for a severalfold change in a rate, never for a ranking (the judge's ranking moves
   about 0.06 between rounds of one build).

The steps as first written (2026-11-12), kept for what they hold:

1. **The judge, states (v0 done 2026-11-12, docs/PROGRESS.md).** Would a pro's unit be in this mode here: the Siege
   Tank, against the pros of TvZ, PvT and TvT, on gt1dev's latest round of each (sieged 0% for a pro's 53%, 15% for
   51% and in the wrong situations, 23% for 34% and 2-6% where the pros are surest). Sharpened with the unit's recent
   past (held-out AUC 0.72-0.81; the instant alone 0.68-0.76). Still to try: the enemy's state (static defense
   finished or not, its sieged tanks), the map's lanes. Never an input that tells the unit's own mode (its type,
   order, cooldown, motion; its neighbours' modes).
2. **The judge, every race's states and the one-shot abilities (started: stim, mines, a Lurker's burrow and
   unburrow, Storm, each in every matchup with the pros' data).** Left: the states the re-simulator's observation
   doesn't report (a Lurker burrowed, a unit cloaked, a Marine in a bunker) and the inputs it lacks (energy, a
   Vulture's mines): the re-simulator's observe gains those fields, the response datasets built again with them;
   then scans, Irradiate, the merges (the re-simulator prints no units for a merge), Dark Swarm, Plague, Ensnare,
   Maelstrom, Stasis, Recall. One table of matchup by ability (a script that prints it from the kept judges).
3. **What the judge flags, the most visible first, as shared fixes.**
   - Siege, Tank Mode and mines against a Zerg: the TvZ response dataset relabelled with the mode roles as the PvT
     one was (pvtmodes, #60), the role model trained on it, the modes drawn (modedice). The judge: tanks sieged 0%
     for a pro's 57%, mines laid 0% for 3.3% (and the Vultures kept where pros don't: 48% of their situations).
     Done 2026-11-12 (gt0.36dev, option `tvzmodes` in place of rl1, the user's call): in 16 games its tanks sieged
     61.3% of their fight moments for a pro's 54.3%, mines 9.6% for 6.3% (TM256a). Its paired rounds (96 games against gz1,
     the old fights replayed): -0.029 [-0.083, +0.029], no measurable difference, so kept; over the 96 its tanks
     sieged in 58.0% of their fight moments for a pro's 54.7%. Left: its
     line flatter than the pros' (sieged a third of the time where the pros are a tenth). Written before its rounds: it is a fidelity change, judged first on the
     judge in 16 games (tanks sieged per situation from 0% toward a pro's 57%, mines from 0% toward 3.3%: severalfold,
     so 16 games show it) and the fight gap per window; then 96 paired games against gz1 with gt1dev's baseline
     replayed (gz1 is gz0.10 since the last one), where the pairing resolves about 0.08 of the paired score: kept in
     the dev build unless it loses more than that, and if it does, reviewed (the records) before it is dropped.
   - Stim against a Protoss and a Terran: never (0% for a pro's 11.8% in PvT), because the stim model's inputs were
     a table of Zerg fighters (gary/policy/stim.py KINDS; race-keyed since 2026-11-12, the PvT and TvT datasets and
     models trained): it stims there now, 1.9% of its Marine-moments for a pro's 10.5% (PT258a), in the right
     situations. The decoder drawn at the model's odds (option `stimdice`, 2026-11-12, 16 games in each): the
     rate nearer against a Zerg (9.7% for a pro's 11.3%, the interval holds zero) and the timing less sharp (the
     judge's ranking 0.70 to 0.61), hardly a change against a Protoss (2.2% for 6.0%): not adopted. Left: the stim
     model's inputs (the judge's history inputs: the enemy near 2 and 5 s ago, seconds in the fight, seconds since its
     last command), then the dice again. Against a Zerg it stims a third less than a pro would (7.8% for 11.4%), least where
     the pros stim most: its decoder's HP floor and threshold against the pros' per situation.
   - Mines against a Protoss and a Terran: half and a sixth of a pro's (1.5% for 3.0%, 0.4% for 2.3%; 4.0% for
     7.2% on PT258a), laid in the right situations: with the tanks' item above (the mines' odds were the weighted
     ones too; at the pros' rates Gary lays a fifth of a pro's).
   - gp1dev's storms, back (gp0.33dev: fightrules had dropped the cast rule since gp0.20dev; SJ254a: 4.6% of its
     Templar-moments for a pro's 7.1%, in the right situations): the rest of the gap is the cast decoder's rate, or
     the Templar it merges before they have the energy (26 a game, 8.6 Archons). The burrow and unburrow of
     Lurkers standing where the pros' don't (79% of gz1dev's Lurker situations: at home, by its buildings). To settle first: gt1dev's
     TvZ fights are the RL checkpoint rl1 on the older labels, so the relabelled model replaces it or the RL run
     starts again from it. Judged by Gary's line against the diagonal, the fight gap, and 96 paired games not worse
     (the minimum detectable effect written first).
   - gt0.37dev's 96 games against gz1 (2026-11-13, kept: paired +0.000 [-0.068, +0.068]): the flipping is gone, a
     sieged tank leaves the mode at a pro's rate (0.38% to 0.54% for 0.44%). Its tanks entered it at under half a
     pro's rate: a decoder's bug (the mode model's half-second odds over a tank's 1.2 s between turns), fixed in
     gt0.38dev: 1.88% for a pro's 2.16%, sieged 45.5% of their fight moments for 51% (16 games). Left, in order: (a)
     its tanks sieged where a pro's aren't (34% of the moments the judge gives under 20%, a pro's 3%) and leaving the
     mode more than the model asks: against a Protoss the army's moves unsieged tanks inside fight moments (staysieged
     looked 12 tiles round the tank, a fight moment holds units 24 tiles round the enemies), fixed in gt0.39dev
     (leaves 1.51% to 0.89%, sieged 30% to 39% for a pro's 52%; against a Zerg 0.61% to 0.42% for 0.44%); what is
     left against a Protoss: the model asking less there than a pro does (entries 1.67% for 2.35%), leaving more
     (its odds 0.63% for a pro's 0.45%), and the army's keys just before the fight reaches a tank (0.21%); (b) mines at half a pro's rate (3.0% to 4.6% for 6.2% to
     6.5%) and placed no better than chance (ranking 0.50 to 0.57 for 0.72): an event model on the judge's inputs,
     as the tanks got (option `minemodel`, gt0.40dev, 2026-11-17, PM273a, HM273a: the rate at the pros' in both,
     the ranking 0.55 to 0.67 against a Zerg and 0.72 to 0.67 against a Protoss; left: a pro's mine comes 0.8 s after
     a command to the Vulture, the end of a move, Gary's 6 s; a third to a half of Gary's mine commands go to Vultures
     kept in the selection, not the one decided for (booked since gt0.41dev; narrowing the order is a change to measure)); (c) done 2026-11-17: the fight gap
     further at 15-20 minutes is the army near the enemy and raids answered faster and with less HP lost than a pro's
     (gz1's raids are not a pro's)
     (eval/gap_windows.py --features; docs/PROGRESS.md), nothing to fix.
   - The tanks' siege in every Terran matchup: they flipped in and out of Siege Mode seven times as often as a
     pro's (a sieged tank leaving it in 3% of its fight half seconds, a pro's in 0.45%; eval/mode_hazard.py). Found
     2026-11-13 (docs/PROGRESS.md): the dice drew at the trainer's class-weighted odds (option `rates`: every race's
     draws at the pros' rates), the army's moves unsieged tanks in a fight (option `staysieged`), and drawn modes
     lost their turn. With both options the flipping is gone and the judge's ranking is up against a Protoss (0.62
     to 0.68), but the tanks siege too late (sieged 29% for a pro's 51% in PvT, 42% for 49% in TvZ) and mines fell
     (1.3% for 6.5%, 5.5% for 10.3%): the role model's odds of a siege are flat over the situations where the pros'
     are steep (a pro sieges in 6% of the half seconds of the likeliest fifth, Gary in 2%). Next, in order: (a) done
     2026-11-13 (option `modemodel`, gary/policy/modes.py, train/modes.py): against a Zerg the tanks siege where the
     pros do (the judge's ranking 0.62 to 0.76, the pros' 0.72), against a Protoss as before (0.68); the share still
     31% for a pro's 50% in both, because of where the army leaves the tanks (its moves end 29 sieges a game in PvT
     with no enemy near). To decide with the user: fold `rates`, `staysieged` and `modemodel` into gt1dev now (the
     flipping gone, the ranking up, the fight gap nearer in PvT, the paired score no worse on 16 games; the share of
     moments sieged lower than gt0.36dev's) or after the army's part. (a2) The army layer's moves of a sieged line,
     from the judge's moments by who last moved the tank. (a3) Mines by an event model on the judge's inputs.
     (b) The TvZ role model trained with the unattended units as keep (`train.roles --unattended-keep`, 50 minutes
     of GPU), or made needless by (a). (c) `rates` for the Protoss and the Zerg, whose every decision is drawn:
     their decisions' rates a half second against the pros', 16 games each. (d) Where Gary's Vultures are when the
     pros lay mines (the model's mine rate on Gary's Vulture-moments is a fifth of the pros' on theirs).
   - The Zerg's fight orders dropped after three failed selections (fixed in part, gz0.26dev: orders carried out
     tripled, the median 26 to 76 a game; 28 a game still drop when a lone click takes another unit that isn't a
     like one beside it: the records say what was selected instead).
   - The bridge's commands added on 2026-11-12 (siege, Tank Mode, the merges, a Scarab or Interceptor) seen sent in
     a live game once Gary sends them; a LAN game with tools/parity.py for the DLL's stim and ammo fields.
4. **The judge among the promotion rule's fidelity measures** (AGENTS.md), once it covers the three races' states
   and abilities. To decide: it changes the rule.
5. **A live game a race at every checkpoint, judged.** Replays against the computer can't be re-simulated, so the
   judge reads a live game from the bridge's snapshots (one a second: the moments built from them, to write) or
   from a LAN game's replay.
6. **The judge on the other fight decisions** (retreat, which enemy to shoot), after the abilities: whether a role
   for a group every half second can look like a pro at all, or the fight layer needs targets per unit.
7. **Reinforcement learning parked** (the user's call, 2026-11-17) until the fight layer has an output for every job,
   the decoders are checked (b above) and a reward ranks checkpoints as games do (#53). League games end when a side's critic reads it lost (decided 2026-11-18, the user's
   call: `eval.league --gg`, 10% for a minute, #62; docs/PROGRESS.md).

Carried over, not dropped: gp1dev's leads from its promotion verdict (its first fighters standing still at 0-5
minutes, the Corsair count, the army it keeps); the Terran's gas in the live game (six Barracks on two refineries,
2,110 minerals banked at 15:00); Probes lost to a raid past the pull's 8 supply.

## Learning (the self-play program, docs/SELF_PLAY.md)

- [#47](https://github.com/vibrunazo/gary/issues/47) Pipe checks: do the learned layers' decisions reach the game, and do
  their inputs in play match their training data? (placement fixed, widespot; the macro's enemy history and the
  bunkered units, seenall and armyseen; tests/test_inputs.py checks the inputs now; the decisions so far as the replays
  count them in every build, 2026-10-31; left: the fight roles' extras, #52)
- [#50](https://github.com/vibrunazo/gary/issues/50) Play and the replays count units differently: workers in gas buildings,
  turrets, the in-building queue's units, undetected cloaked units (the dataset's)
- [#28](https://github.com/vibrunazo/gary/issues/28) Commit decision: a learning signal from locked paired branches
  (the signal weak: scored by the critic too, nothing beats the deployed model's preference in 941 pairs; next, pairs
  again on gt0.14dev's fixed inputs, several dice per arm, or a decision with longer consequences)
- [#51](https://github.com/vibrunazo/gary/issues/51) Gary-Z's builds and burrows: the lurkers fixed (they never came up again);
  its builds held production (fixed, gz0.9dev); left: 99-233 burrows still refused a game, the late game of a
  losing Zerg (builds without drones)
- [#48](https://github.com/vibrunazo/gary/issues/48) The Zerg's macro model counts the units in its eggs twice; the fix
  (option eggs) lost 96 paired games: no rule leans on it; the right counts move the model off zerglings to
  Hydralisks and it slows (its counts a momentum cue): eggs with the macro trained on Gary-Z's own states next
- [#52](https://github.com/vibrunazo/gary/issues/52) The role models' inputs: Gary-Z's enemy HP fixed (gz0.5dev), the Terran's
  extras 3-5 in a rebuilt dataset and model (runs/roles/20261026-090057, not deployed: the next roles run's start)
- [#53](https://github.com/vibrunazo/gary/issues/53) No fight-scenario reward ranks the roles checkpoints as games do: a reward
  that counts what fighting costs the rest of the game, or 96 games
- [#54](https://github.com/vibrunazo/gary/issues/54) Build styles by name for each side, every game labelled (done: every
  matchup's catalogue, each race's model trained with them, the style check in every matchup, one Zerg macro model for
  every matchup in gz1dev, gz0.11dev, and gt1dev, gt0.24dev, the Protoss's in gp0.4); left: why Gary-Z's own states draw
  more lurkers and scourge from the shared model, and the citadel-first plans played as robotics (PvP 19%, PvT 50%)
- [#57](https://github.com/vibrunazo/gary/issues/57) Gary-Z banks the gas it mines (920 at 10-15 minutes, pros 499)
- [#58](https://github.com/vibrunazo/gary/issues/58) Gary-Z's builds per style: style 2 played as itself 31%, the third Hatchery
- [#59](https://github.com/vibrunazo/gary/issues/59) Fold the dev manifests' execution fixes (parkmany, gaswaits, the gas head)
  into gt1, gt1dev and gz1 (the inputs done, gt0.12 and gz0.5, 2026-11-11: what tests/test_inputs.py showed the playing
  builds lacked; left: parkmany, gaswaits and a gas head for gt1's model, and gz1's eggs, builtcount and pendown, which
  the test can't hold apart while gz1 reads the pros' history)
- [#55](https://github.com/vibrunazo/gary/issues/55) The opening economy: new workers sent at once, the first worker first,
  workers on gas the macro model's decision (gastarget, gt0.20dev: style 2's natural 3.6 minutes, pros 3.2; the Zerg's,
  gz0.7dev); left: about 100 minerals mined behind the pros by 2:00 (the split, doubled fields, idle builders; Gary-Z's
  first Overlord at 58 s, pros 53)
- [#29](https://github.com/vibrunazo/gary/issues/29) Why army dataset v5's commit models trail the deployed one in games
  (not the bunker counts: with armyseen v5 still trails, -0.039 over 96)
- [#3](https://github.com/vibrunazo/gary/issues/3) Close out won games (the hunt imitated: its labels on the deployed
  commit model next)
- [#11](https://github.com/vibrunazo/gary/issues/11) Learn from game outcomes
- [#12](https://github.com/vibrunazo/gary/issues/12) Macro model with game history (a sequence over recent events)
- [#39](https://github.com/vibrunazo/gary/issues/39) Anticipation: target inference for enemy groups
- [#40](https://github.com/vibrunazo/gary/issues/40) Opponent model: a belief over the enemy's plan
- [#42](https://github.com/vibrunazo/gary/issues/42) The army model's fight estimate from Gary's own fights
- [#45](https://github.com/vibrunazo/gary/issues/45) The macro answers what the scout sees, without the scripted answers
- [#35](https://github.com/vibrunazo/gary/issues/35) TvT Gary-T: its own fight model (done, gt0.23dev: the TvT role model),
  belief, plan and engage models
- [#34](https://github.com/vibrunazo/gary/issues/34) More modern replays

## Gameplay

- [#2](https://github.com/vibrunazo/gary/issues/2) Hold early zergling harass and all-ins (and how much to commit to defense)
- [#4](https://github.com/vibrunazo/gary/issues/4) Micro: spreading, sieging, spells as learned decisions (Psionic Storm
  learned, gp0.11dev: gary/policy/cast.py's spell table takes the others' area spells next)
- [#26](https://github.com/vibrunazo/gary/issues/26) Strategy layer: pick among proven builds and follow the timeline
  (and rebuild the selector's table from league games)
- [#37](https://github.com/vibrunazo/gary/issues/37) Human game 4's failure list
- [#43](https://github.com/vibrunazo/gary/issues/43) Scattered fighters back into the main group
- [#38](https://github.com/vibrunazo/gary/issues/38) Map mechanics on the current ladder maps: neutral units and per-map priors
- [#16](https://github.com/vibrunazo/gary/issues/16) Learn building placement and scouting from replays (a building's base
  and side learned for the Protoss, gp0.21dev; Corsairs scouting as the army's air clusters, PvZ, gp0.23dev; saving for the first
  Corsair, gp0.24dev, its Core, gp0.25dev, and its natural Nexus, gp0.26dev; buildings on one pro's tiles, every race and matchup, gp0.27dev, gt0.29dev, gz0.18dev; a Terran building's base learned in TvZ, gt0.30dev, and every Terran and Zerg matchup's, gz0.19dev; workers to a new base as it finishes, every race, gt0.31dev, gz0.20dev, gp0.28dev; the Terran's placement checked in TvT and PvT, 2026-11-11; next Gary-Z's colonies decided before its natural finishes (its first in the main 19%, the pros 1%: a late natural in Pool-first games, #58), Gary-T's first Barracks in PvT (by the natural 75%, the pros 27%: it starts late, and its base is drawn again as it builds), the first Comsat on the natural's Command Center (TvT 80%, the pros 28%), a builder walled in by the building it made (set aside now, one build lost), the other matchups' air clusters, the macro's look a moment after each decision)
- [#25](https://github.com/vibrunazo/gary/issues/25) Walls: copy the pros' walls per map and start location
- [#23](https://github.com/vibrunazo/gary/issues/23) Map analysis: split maps at their chokes
- [#36](https://github.com/vibrunazo/gary/issues/36) Protoss: the executor (refactor Phase 4) begun, `gp1` plays every matchup
  with its role model and styles, plays its styles as the pros do (PV161a, PZ161a); next the dev builds' fights in PvT and
  PvZ by their matchups' role models (gt0.21dev, gz0.10dev), every mirror by its own (gt0.23dev, gz0.11dev, gp0.2),
  the Protoss's PvT and PvZ apart (gp0.3), its dev build (gp1dev, docs/RACES.md), the Terran's queue of two (gp0.5dev),
  Reavers and Carriers armed (gp0.8dev: they never fired before), Archons merged as the pros do (gp0.9dev), the pros' key
  layout (gp0.10dev), storms (gp0.11dev), Pylons placed for room (gp0.12dev: its Gateways had no spot), refused buildings
  taken back (gp0.13dev), a decided building among its own until it starts (gp0.14dev: the second Stargate 1.5 to 1.2),
  buildings placed by the pros' table (gp0.15dev: the natural's wall, cannons at every base; Probes lost to raids 9.9 to 3.6),
  cannons by the mineral line and at every base in each game (gp0.16dev: Probes lost to raids 0.75 a game, the pros 0.9);
  idle Probes sent back at once (gp0.17dev: idle at the main 0.46 at a time to 0.22, the pros 0.13), the openings'
  buildings by the pros' shares per style and every matchup's tables (gp0.18dev), the gateway-first Gateway on time
  (gp0.19dev), Probes pulled against raids (gp0.20dev: lost to raids 3.48 a game to 2.31, the pros 0.90); left: the
  commit model's answer to raids at home, Mutalisk raids with no cannon by the Nexus (32%, the pros 6%), shuttles, cannons at newer bases, unit mix
  (cannons PvZ 24.5 at 20:00, the pros 13.8; High Templar two thirds of the pros')
- [#61](https://github.com/vibrunazo/gary/issues/61) The Terran's modes in PvT (gt0.22dev siege and lay mines): held as long as the
  pros hold them, the pros' mines outside fights, Spider Mines four minutes late
- [#62](https://github.com/vibrunazo/gary/issues/62) Type gg and leave when the critic's win odds stay under 20% (default;
  an option plays on; dev builds play to the end and record their would-gg moments); a critic per matchup and its
  calibration done (eval/critic_gg.py: won after a would-gg in 0-12% of decided games at 20%, 0-5% at 10%); left the
  pros' odds when they leave, then the rule
- Later, as supervised skills: [#21](https://github.com/vibrunazo/gary/issues/21) worker drilling,
  [#22](https://github.com/vibrunazo/gary/issues/22) bunker rush

## Evaluation and tools

- [#31](https://github.com/vibrunazo/gary/issues/31) Mirror health rounds and the Protoss macro models (rounds played, no errors;
  left: the death records' slot in mirrors; the Protoss PvT/PvZ misses are Zealot/Dragoon and reactive buildings)
- [#64](https://github.com/vibrunazo/gary/issues/64) The army layer's draws use seed 0 in every game: fixed 2026-11-23 (the army's
  and the calm layer's draws from the game's seed and the side's slot; every build bumped, gt0.21 and gt0.49dev; every
  baseline replayed from here; the issue to close)
- [#63](https://github.com/vibrunazo/gary/issues/63) Grade games at time by the critic's win odds, not the supply ratio
  (regraded, 2026-11-11, eleven past pairs with eval/paired.py: the critics' grade has the larger spread in every pair,
  a real difference 9-15% further out in its own: not adopted, printed beside supply's as a second reading; left: the
  middle's calibration on Gary's decided games, and whether the level the critics see, the Zerg ahead where supply
  says even, is right)
- [#32](https://github.com/vibrunazo/gary/issues/32) The gap score disagrees with results
- [#44](https://github.com/vibrunazo/gary/issues/44) Engine error at the map's edge
- [#15](https://github.com/vibrunazo/gary/issues/15) Fit human-interface profiles from replays
- [#41](https://github.com/vibrunazo/gary/issues/41) Explainability: a narrator over the decision records
- [#17](https://github.com/vibrunazo/gary/issues/17) Viewer: the action overlay in the interactive window
- When full-game self-play needs the speed: [#19](https://github.com/vibrunazo/gary/issues/19) vectorized env,
  [#20](https://github.com/vibrunazo/gary/issues/20) a C++ per-frame core

## The Remastered bridge

- [#24](https://github.com/vibrunazo/gary/issues/24) Adapt to the layer refactor (done without a client, 2026-11-11: the
  map's terrain, regions, unit data and hash from its file opened beside the live game, `type_select`, every race live,
  `stim`, `ammo` and `ammo_max` in the bridge's observation, tests/test_live.py; left: a LAN game of the current builds
  in a client, and `tools/parity.py` on its replay to pin the three fields' offsets)
