# TODO: open work

Open work is tracked in the [GitHub issues](https://github.com/vibrunazo/gary/issues); this file is their index,
grouped by area, newest thinking first (reconciled with the code on 2026-10-25). When an item is done its issue is
closed and its line leaves this file; docs/PROGRESS.md keeps what was done and how it measured.

## Direction (2026-11-12): judged per situation, in every matchup

After the three live games (docs/PROGRESS.md): the rounds and the gap score never showed that Gary's tanks don't
siege against a Zerg, and one viewing did. The work is judged by what a pro would do in the situation Gary is in
(`eval/judge.py`), in every matchup, not by counts a game and not in one matchup first. The steps, in order (an item
gets its issue when it is started; the ones marked "to decide" are proposals, not agreed):

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
     sieged tank leaves the mode at a pro's rate (0.38% to 0.54% for 0.44%). Left, in order: (a) its tanks sieged in
     31% of their fight moments for a pro's 54%, entering at under half a pro's rate (0.8% to 1.0% for 2.2%): where the
     army leaves the tanks and its moves of a sieged line; (b) mines at half a pro's rate (3.0% to 4.6% for 6.2% to
     6.5%) and placed no better than chance (ranking 0.50 to 0.57 for 0.72): an event model on the judge's inputs,
     as the tanks got; (c) the fight gap further at 15-20 minutes (+0.063 [+0.019, +0.111]): which features, from
     eval/gap_windows.py.
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
7. **To decide.** Reinforcement learning parked until the fight layer has an output for every job and a reward
   ranks checkpoints as games do (#53). League games ended when the critic says a side would resign, so the late
   windows compare like with like and dead games cost no CPU; it needs its own check (the critics' grade as a
   paired score was not adopted, #63).

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
- [#64](https://github.com/vibrunazo/gary/issues/64) The army layer's draws use seed 0 in every game (fix with the next version
  bump of every build: every baseline replayed)
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
