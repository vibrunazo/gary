Round two, 2026-11-23

Review of `docs/REFOCUS.md` (Draft v2.0 as it stands after commit `80fa001`), sections 3.1 to 3.4, 4.2 and 4.3, by
Claude Fable 5.2. Web search and page fetch were available in this run; PDFs could not be read (no extractor), so a
paper counts as opened only where an HTML page served it (the list at the end says which). Nothing of the project's
was built or run. Marks: **(S)** read in source at the line given; **(R)** read from the rounds' records, logs or
`round.json` by a read-only tally (a macro decision's time is when the thing was decided, a proxy for when it stood);
**(I)** inferred.

## The lead: is Phase 1 as written still the right first build, in the right order, at a sensible cost in games?

The parts are right; the first build and the order are not, and about two fifths of the games should become
conditional on reads that cost no games. Phase 0 showed that the belief, the card's directives and macro Arm A all
consume what Gary sees of the Zerg, and Gary sees almost nothing between 3:00 and the mutalisks' arrival. So the first
build is "Gary looks", and the first step of that is a plain bug: the tech scan cannot fire on six of the eight ladder
maps (finding 1). The order agreed before the stop (`TODO.md:34-36`: sighting states, the Zerg suite, the scouting
measure, scouting, the belief re-scored) is nearly right; I would move the scouting measure and the fixes to the
front, because they cost nothing and they decide what a "look" must record (scans), and hold the full sighting
dataset (every modern replay re-played) until they are in.

| Step | What | Games |
|---|---|---|
| A | Plain fixes on their own checks (AGENTS.md): the scan's main known without `watch` (finding 1); Gary's games labelled by the pros' rule (finding 3); a scan counted as a look (finding 9) | 0 |
| B | Counts before any design: the pros' first sight of each tech building by type and by means; Gary's seen against standing; today's build on the card's measure (milestone error, from `RD285a`); `answers.py`'s goals against turrets built | 0 |
| C | One read of gt1dev with A against gz1dev told the suite's styles, gg on: the scouting measure after the fix, each Zerg game's plan as played (the suite's first labels), this pairing's own spread | 16 |
| D | Scouting: `watch` re-judged in gt1dev on its fidelity measure; the scan as a learned decision (part 1), each on its own measure | 16 + 16 |
| E | Guardrail for what D folds, against `RD285a`'s seeds (gz1, `--gg 0`: the baseline is already played) | 48, to 96 if close |
| F | The belief re-scored on C to E's games (no new ones), then belief and card log-only: the document's soak | 32 |
| G | `answers` off once Gary sees (AGENTS.md's pending measure: the time to the answer) | 16, to 48 |
| H | Only if B's milestone error leaves a gap: strict drills and the macro A/B, as written | 40 + 48 to 96 |
| I | The army: the retreat hold as a pipe fix on `eval/pipe_table.py` (16); Arm 3 against the control only after an offline read says what an owned intent would change (16 + 48 to 96); Arm 2 on commitments not run (part 3) | 16, then 64 to 112 |
| J | Gate 4 on the whole Phase 1 build, against `RD285a`'s seeds (finding 6) | 96 |

Unconditional (C to G, I's first 16, J): about 256 games, 336 with E's and G's extensions. Conditional: 88 to 136 for
the card, 64 to 112 for the army. The document's 264 to 408 (Phase 1 plus the army track) budgets neither gate 4's
round nor the baseline it needs (finding 6); with those it is about 360 to 600, so the totals are about the same if
everything runs. What changes is that the first 48 games buy the measurement Phase 1 is blocked on, and neither A/B
is played before a 0-game read says it can show something. The gate's "Week 4" should be keyed to these steps and
their games, not to a date. E and J trade one thing for the free baseline: against gz1 with gg off, 60 of gt1dev's
96 games are graded at time (part 3); against gz1dev with gg on they would end, at the price of a 96-game baseline.

## (1) Gary sees the Zerg's tech by 6:00 in 5% of games, the pros in 60%

**What Gary's scouting does today.**
- *The worker.* One SCV at 9 workers from 0:45 (`gary/agent/army.py:60-61, 989-996`) walks the enemy starts, nearest
  first (`:994`); at the first enemy building seen it walks six points 7 tiles around that start and the natural's
  centre (`:1002-1011`), then goes home to mine (`:1026-1033`). Nothing sends it again: the one replacement is inside
  `_watching` (`:1058-1063`). `gary/agent/answers.py:15-16` says it itself: "The Zerg's tech comes after Gary's scout
  has left (~3:00)". (S)
- *`watch`.* The scout stays, touring the Zerg's main and natural until three fighters are within 5 tiles, it is at
  60% HP, or 5:00, then holds a post outside Gary's natural, replaced once before 4:30 (`army.py:15-21, 90-99,
  1053-1117`). It is in neither gt1 nor gt1dev (`gary/agent/manifests.py:1224-1226, 1398-1401`). Its own measure
  moved: Zerg in sight at 3:00-6:00 78 s, 103 s with the tour, for Gary's 44 s and the pros' 104 s; it was dropped on
  v0.19 for losing 30 of 432 for 25, with the note "an SCV off minerals for minutes, for information no decision
  uses" (`manifests.py:803-810`). (S) That verdict predates "Fidelity before wins" and names as its reason the very
  thing Phase 1 builds.
- *`tech_scan`.* With no plan read at 6:30, and again at 8:30, at most twice, a scan of the Zerg's main
  (`answers.py:32-33, 86-99`), if the macro has no goal and no task (`gary/agent/macro.py:221`), a Comsat has 50
  energy, and the main is known: `g.army.enemy_main`, or the one enemy start (`answers.py:91`). `enemy_main` is
  assigned at one place, `army.py:1029-1030`, inside `if self.watch`; `g.enemy_starts` is set once
  (`gary/agent/gary.py:118`) and never narrowed. (S) So in every current build the scan fires only where the map
  has one enemy start. (I) In `RD285a` all 20 scans are on Colorless Fate 1.1 (9) and Odyssey-RE 2.0 (11), in 16 of
  their 24 games; none in the other 72 games, in 39 of which a Comsat was decided by 6:00. Where it fired, the read
  usually followed within one to three seconds, from the Lair and the Spire in sight. (R)
- *What that yields.* (R, `RD285a`, 96 games) The Zerg decided its Lair by 6:00 in 85 games (median 3:15) and its
  Spire by 6:00 in 76 (median 4:44). Gary's first plan read came by 6:30 in 3 games, by 8:00 in 50, a median 7:34;
  of the 87 first reads, 70 list a mutalisk, a lurker or its egg and no Spire or Den: the read came from the units
  arriving. So the 5% at 6:00 is by construction (nothing looks between about 3:00 and 6:30), and the 20% at 8:00 is
  the scan on two maps of eight. The tech was decided, and stood wherever the scan looked; Gary did not look.

**What the pros do that Gary doesn't, as far as the repo's own numbers say.** Their first SCV stays (Zerg in sight
104 s of 3:00-6:00, `army.py:15-16`), and they look at the main at 6:00-7:00 (`answers.py:16-17`). That their first
marines and medics move out and see the natural is recalled, not measured here (the Liquipedia guide I opened says to
move out "once Academy tech is out" and gives no scouting method). Don't design from either; count it.

**What to count first (no games).**
1. The pros' first sight **by type**: `TECH_BUILDINGS` (`train/plan_belief.py:61`) counts a Lair or a Hive as "tech
   seen", and a Lair does not tell a Spire from a Den. The read that drives an answer is Spire, or Den with Lair
   (`answers.py:77-80`). The 60% may be mostly Lairs seen by a staying SCV; the share for Spire-or-Den by 5, 6, 7 and
   8 minutes is the target curve.
2. **By which means**: scans a minute at 4:00-9:00 and the share of first Spire-or-Den sights within a few seconds
   of a scan order need only the command cache (`ingest/build_orders.py:137` names `CastScannerSweep`) and the macro
   set. Where the scan landed needs more: the cache keeps a position for `Build` only (`ingest/cmdcache.py:16, 63`),
   so a cache version with targeted orders' positions, or the re-play `ingest/sighting_dataset.py` already does.
   Then which of the player's units had the building in range at first sight (SCV, scan, army).
3. How long the pros' first SCV stays in the Zerg's bases, against `watch`'s 5:00 and three zerglings.
4. In Gary's games, seen **given standing**: `plan_belief.gary_game` already has the Zerg's true units per second
   (`:138-142`); print, per minute, the games where the Spire or Den stood and was not seen. The proxy above says
   about four in five at 6:00.

**The candidates, against each other and against what exists.**

| | What it is in this repo | Under AGENTS.md | For | Against |
|---|---|---|---|---|
| Exists | Worker once to ~3:00; a trigger at 6:30 on "no plan read" | `answers.py` is a listed stop-gap; its scan is not in the entry and the file has no `STOP-GAP` tag | Works where it fires | Fires on 2 maps of 8; nothing at 3:00-6:30 |
| Pros' timings sampled | The scan's time and the SCV's stay drawn from the pros' distributions | A rule with constants from data, not a decoder (no model's odds behind it): a stop-gap, tag and entry, like `rax_by` | Cheap; the marginal timing is the pros' | Blind to state: scans a main whose Spire the SCV saw; the pros' timing depends on what they know and when the Comsat finished |
| Trigger on what is unscouted | `tech_scan` generalized: main unlooked for N s, or the belief undecided, and energy to spare | A stop-gap with hand thresholds; a second scripted spender of Comsat energy beside Detect (finding 13) | The explanation is its own text ("unlooked for 200 s") | Thresholds by hand; "learn, don't script"; the literature's version is learned by RL, parked here |
| Learned model | The pros' scans as events: odds of a scan per tick and its target class (their main, natural, another base, own base, the army) from time, energy, the sighting state, tech seen, lurkers known | The stim model's standing: "its decision is the stim model's ... the rule is its decoder"; it is the replacement the Detect entry already names ("scans as a learned decision") | One model for two rules' jobs; judged on fidelity; the SCAN intent exists (`gary/agent/motor.py:737`), so the pipe check is short | Needs scan targets (count 2) and the sighting state as an input; data work, no games |

I would build the learned model for the scan, keep the fixed trigger as the tagged stop-gap with a measure until the
model holds it, bring `watch` back as an option in gt1dev judged on its own measure (a scripted rule: tag and entry;
its stay to be checked against count 3), and not build the sampler: the learned model's marginal is the sampler.
The generalized trigger adds little the fixed `tech_scan` doesn't do. From the literature: Hostetler et al. 2012 is
the Brood War precedent for inference from "evidence gained via scouting" (abstract opened; its observation model
not read);
ROA-Star (Huang et al. 2023) rewards scouting by the opponent-strategy prediction, learned by league RL (search
record only), which is not available here; its usable half is a **measure**: what each look bought, as the belief's
loss before and after it on the pros' games, per means. That ranks SCV, scan and army looks by information per cost
without a game.

**Where it goes and what shows it.** Before the belief in play, the directives and Arm A. Measure, the same function
for Gary and the pros: Spire-or-Den seen by 5, 6, 7, 8 minutes given standing; Zerg in sight at 3:00-6:00 (104 s);
scans a minute by window and their target shares; downstream, the first plan read's time and whether it came from a
building or from the units arriving (today 15 and 70 of 87). A move from 5% toward 60% is severalfold: 16 games a
step (AGENTS.md's sizing rule), wins second.

## (2) The least the card and the belief must add beyond style conditioning and `answers.py`

**What exists covers.** The macro model takes the style as a one-hot and the enemy's types in sight and most seen
(`gary/policy/macro.py:91-92, 100`), so it is already conditioned on a coarse z and on raw sightings. `answers.py`
reads spire or lurker from first sightings and forces the lurker answer and mineral-line turrets. The 97 to 100% is
`eval/style_adherence.py`'s label: a 15-nearest-neighbour vote on each key item's first time within 8:00, against
clusters labelled on old-era games (`eval/style_adherence.py:1-10, 26, 37-39, 115-123`). (S) It counts that the
first-times vector is nearer the told cluster than another. It does not count: any tolerance per milestone (style
2's Factory is at 3.0 minutes for the pros' 2.5, the Starport 4.6 for 4.1), order, counts past the first of a kind,
anything after 8:00, a particular replay's build, or any reaction to the enemy. And it is the Terran's: the document's
own G3 example ("practice vs. 2-hatch muta 20 times") steers the Zerg, whose adherence it gives as 56% (line 330).

**The smallest card that adds something.** Per style, the pros' median time of each key item on the same maps
(`style_adherence.py` already prints this row) with a tolerance from the pros' own spread, log-only. Its measure is
ARCHITECTURE's: per milestone, Gary's time less the card's, and the share of games with every milestone inside
tolerance. Run it on `RD285a` first (96 games exist, no new ones): that is "Arm 0", today's conditioning on the
card's measure, and 3.3 has no such arm. If Arm 0 is 12 of 20, Arms A and B have a target and a learner would notice
the difference; if it is 18 of 20 on the opening, the card's value is after 8:00, from a replay, or on the Zerg side,
and the 40 drills and the A/B answer a settled question. A second, cheaper consumer is the records: questions 1 and 3
can cite "next on the card: Starport at 4:10, decided 4:36, waited for gas".

**The smallest belief that adds something.** On the pros the joint's gain over the floor is the hatcheries and the
opening; the tech part equals `answers.py`'s read at 6:00 (0.073 against 0.072) and beats it at 8:00 (0.036 against
0.052) (`docs/PROGRESS.md`, the 2026-11-23 belief entry). The macro model already has the sightings. So beyond
`answers.py` the belief adds three things only: a calibrated number before anything is seen (the prior by map and
time: spire first in nine modern games of ten), absence where Gary looked (main looked at 6:32, no Spire: lurkers
likelier), and the hatcheries part as the mutalisks' arrival time. That is a tech belief over {spire, lurker, neither
yet} with the looked state, plus hatcheries; the 11-class joint is not needed for a first directive. For this job the
bake-off's other provider (3.1, the Bayesian one) has a structural advantage the trees lack: with a likelihood of the
form P(seen X by t | plan, looked), an unlooked base contributes no evidence by construction, so on Gary's unlooked
games it returns the floor exactly, where the trees were worse than the floor because "nothing seen" was evidence.
(I) It needs only the per-plan first-time distributions (`taxonomy/plans.py`'s cards) and the looks; build it before
the full sighting dataset. Also (I): truncate the pros' sightings at a random earlier time when training either
provider, so "not looked" has support at every minute.

**The measures.** For the belief: the tech part's Brier against `answers.py`'s read on Gary's own games against the
suite, split by looked and unlooked (`score_gary` computes the reads and never scores them: `plan_belief.py:136,
161-202`); and the lead time, from the belief passing one half to the first mutalisk or lurker in Gary's base: today
the read is those units in 70 of 87 games, a lead of zero or less. For macro use: AGENTS.md's own for `answers.py`,
the time to the answer with the rule off (step G); if the model answers alone once Gary sees, the belief's job is
explanation and it stays out of the macro model's inputs.

## (3) The deficit, the 30 unfinished leads, and the army test's arms

**Where the deficit is.** (R, `RD285a` and `RP285a`'s `round.json`, graded as `eval/paired.py:43`.) A lead at time
scores 0.75 for a win's 1.0, so gt1dev's 30 unfinished leads are at most 30 x 0.25 / 96 = 0.078 of the 0.219; with
gt1's own 11 leads counted as wins too, 0.05. The rest, 0.14 or more, is games gt1dev loses or trails in: gt1 won
60, gt1dev won or led in 46. The pair table says the same: of gt1's 60 wins, gt1dev won 13, led at time in 21, was
even in 7, behind in 10 and lost 9. That matches the hunt put back in the dev build closing +0.057 [+0.000, +0.120]
(`docs/PROGRESS.md:3132`). By the style gt1dev was told (no intervals, small counts): style 1, the bio gt1 plays,
-0.20 over 56 games; style 2 -0.27 over 32, with 11 lost. So it is not the pros' styles; it is what PROGRESS says, the
stop-gaps that each measurably won.

**Should Phase 1 address it?** Not as a goal, and the document should say so in two sentences it lacks. First,
nothing in Phases 1 or 2 aims at promotion's second condition, and nothing can soon: the finish has no imitation data
("Imitation alone has no answer", `docs/PROGRESS.md:2466`) and RL is parked. So gt1 stays the playing build, which
plays bio in 96 of 96 games told style 4, and every G3 and G5 result, the blind evaluation and the live games are a
dev build's by flag. Second, the unfinished leads distort only rounds with gg off; dev against dev with gg on ends by
resignation (`CB280a`: every game), so Phase 1's rounds against gz1dev are not hurt. The army test doesn't address
finishing either: its pass criteria (3.4) hold no finished-lead or decided-game measure, and it shouldn't gain one:
Arm 3's `PUSH_OR_PRESSURE` with a hand-written exit toward a won game is the hunt again, which 4.1 rightly keeps a
stop-gap.

**The three arms against what was tried.**
- *Arm 2, on `army.py`'s commitments: already run twice, and its premise measured false.* `holdtarget`
  (`manifests.py:1121-1124`; `army.py:193-197, 657-660`): -0.011 +- 0.087, the pipe unmoved. `unitcommits`
  (`manifests.py:1125-1127`; `army.py:198-202, 663-679`): -0.048 +- 0.064. On the same measure the pros redirect
  0.79 of their group orders within 30 s and gt1dev 0.70: the two options "fixed a problem that wasn't there"
  (`docs/PROGRESS.md:1213-1219`), confirmed on 2026-11-18 ("not a leak", `:2452-2456`). The arm's own citation says
  it: `docs/SELF_PLAY.md:489-493`, the pros' reversal hazard, ends "Gary's own commitments already have that shape".
  The commit model's head is keep, engage or move with the commitment's kind and age as inputs (`army.py:172-175,
  592`), a learned hold and exit already; the hazard lock exists for paired arms (`army.py:44-47, 575-590`). (S)
  Drop this half: 0 games.
- *Arm 2, on the roles' retreats: new, real, and not an arm.* Retreats seen against asked 0.22 for the pros' 0.78;
  within 2 s 37% get another retreat and 27-40% another role (`docs/PROGRESS.md:2550-2554`); "a retreat held for its
  stretch" is left unchased at `TODO.md:64-65` (3.4 cites `TODO.md:31-32`, which has since been rewritten). It is a
  pipe fault with its own measure (`eval/pipe_table.py`), so it is judged there in 16 games, as `retreatfar` was. The
  learned hold-and-exit the arm asks for is the mode model's mechanism (`train/modes.py`, `eval/mode_hazard.py`):
  retreat as a mode with the pros' exit hazard, rather than a deliberation cost tuned by hand.
- *Arm 3: relatives tried, none with ownership.* `gather` (the whole army to one point before an engage: late
  arrivals 0.26 to 0.22 for the pros' 0.06, won 47 for 54; AGENTS.md's entry); `anchor` with `home_guard` (no army
  out while fighters are at home: not adopted, home defenses -7 +- 10; `manifests.py:579-585`); the hunt (a scripted
  push that finishes). What Arm 3 adds is the lease and the identity, which `unitcommits` approximated without
  effect. Before any games, read from existing rounds what an owned intent would change: of units alone and late
  arrivals, the share caused by another cluster's order taking a committed unit. If small, Arm 3 is question 4's
  bookkeeping (an `intent_event` record over the commit decisions that exist), which costs no round.

## (4) What in the code blocks Phase 1 that these questions miss

1. The scan's main (finding 1): until fixed, no scouting measure, belief or directive can be judged on six maps.
2. No fixed Zerg plans exist to play against: the scripted Zergs "were deleted in docs/REFACTOR.md Phase 3"
   (`eval/block_branch.py:30`; every key of `MANIFESTS` is a Gary), and `eval/vs_rush.py`, AGENTS.md's measure for early pools, is not
   in `eval/`. (S) The suite is gz1dev told a style and labelled as played, at 56% adherence.
3. Gary's games and the pros' are labelled by two rules (finding 3); the suite's labels would inherit it.
4. A look is "a unit of the player's within 8 tiles of a base's centre" (`gary/policy/sightings.py:18, 52`); whether
   a scan's sweep is such a unit in `observe()` I could not settle from source, and the pros' 6:00-7:00 look is a scan
   (finding 9).
5. Comsat energy has three spenders and no owner (finding 13); a scouting scan and Detect will compete.
6. `answers` cannot be turned off in TvZ: no option does it (only `_VS_NON_ZERG`, `manifests.py:43`), so 3.3's
   one-at-a-time removal has no switch for its first rule.
7. Arm A adds inputs to the macro model: a dataset column from each pro game's own future (the card) and from a
   belief model's output, `tests/test_inputs.py` parity for both, and the critic that types gg reads the macro
   features (`tests/test_value.py`), so gate 4's "same `--gg`" may need a critic retrained per arm, or gg off. (I)
8. Gate 4 names an opponent its reference rounds did not play (finding 6).

## Findings

1. **4.3 Phase 0 Results ("20 tech scans"); 3.1. The tech scan cannot fire on maps with more than one enemy start.**
   `answers.py:91` needs `g.army.enemy_main`, assigned only under `watch` (`army.py:1029-1030`), or a single enemy
   start; `gary.py:118` never narrows the starts. (S) All 20 scans of `RD285a` are on two maps. (R) A plain bug by
   AGENTS.md (the scout found the main and the knowledge was dropped): fix on its check, no rounds, in gt1 too. The
   fix belongs in one shared place (the scout's find, or `SightingState.enemy_main`, `sightings.py:58-65`), read by
   `answers.py`, the hunt and the post. PROGRESS's audit of `HS284a` ("0 in 16 games: the plan was read before 6:30,
   or no Comsat") holds on neither count: its logs show 2 scans, both on those two maps, and the plan read before
   6:30 in 2 games of 16. (R)
2. **4.3 Phase 0 Results, last bullet. "Gary had seen the Zerg's tech by 6:00 in 5% of its games (pros 60%)" is
   true and under-read.** The count is of tech buildings including Lair and Hive (`plan_belief.py:61`), so the pros'
   60% may not be the read that matters (part 1, count 1); and the cause is not a missing skill but a schedule (the
   scan is at 6:30, `answers.py:32`) and finding 1. The block should give the 8:00 pair (20% and 77%) with the two
   causes, and say seen given standing. (S, R)
3. **3.1; 4.3 ("`gz1` plays one plan in 76% of them"). Gary's games are labelled by a different rule from the
   pros'.** `plan_belief.gary_game` takes each building's first time over the whole game (`:139-142`), where the
   catalogue's labeller stops at 9:00 (`taxonomy/label_all.py:119`, `taxonomy/discover.py:88`); it dates Lurker
   Aspect by the first Lurker (`:142`), later than the research the pros' label uses; its zerglings are units alive
   at 4:00 (`:143`) against order items by 4:00 (`taxonomy/plans.py:40-41`; whether one item is one unit not
   checked). (S) By decision times in `RD285a`, the 9:00 rule gives spire first 76, lurker first 9 and neither by
   9:00 in 11; the whole-game rule turns 7 of those 11 into spire first, and the first-Lurker dating can only move
   more that way. (R) `eval/style_adherence.py --race Z` already labels Gary-Z's games "as they label the pros'" from
   the replay's commands (`:85`): use that, for the belief's score and for the suite.
4. **3.4 Arm 2. Half of it repeats `holdtarget` and `unitcommits`, against a premise the cited lines deny; the other
   half is a pipe fix.** Part 3. The executive summary says the test avoids "assuming a large hand-authored
   squad-option rewrite upfront"; it should also avoid re-running two measured options. (S)
5. **3.4, "verify whether `commit` already receives research state". Settled: it does not.** `encode_global`
   (`gary/policy/army.py:135-150`) takes time, minerals, gas, supply, the group's and the army's supply, the enemy's
   remembered army, own and seen unit counts and the commitment; no research or upgrade. (S) So the offline check's
   second half is done, and an upgrade-timing criterion would need a new input and a retrained model, not a gate.
6. **4.3 gate 4, the rewritten margin.** The arithmetic holds: the pairs' sd is 0.466 (R, recomputed), and +-0.111,
   0.168, +-0.078, 0.118 follow from `eval/paired.py`'s 1.645 and 2.49. Three faults in what is built on it.
   (a) The rule passes what the sample cannot tell from zero, so its strictness is the sample's: at 48 games "a loss
   under the MDE with the interval holding zero" passes a true loss of 0.10 about half the time and 0.15 about a
   quarter, against a whole deficit to gt1 of 0.219; at 96, a third and under a tenth. (I, from the sd.) For the one
   guardrail on the whole Phase 1 build the 48 is too weak: say 96, and write the margin as the loss accepted (the
   0.118), not as whatever the sample detects.
   (b) The gate plays "fixed `gz1dev`" while the block above makes `RD285a` and `RP285a`, against gz1 with gg off,
   "the reference rounds": no gt0.50dev round of 48 or 96 against gz1dev exists (`HS284a`, `CB280a` are 16), and the
   Phase 1 row budgets none. Either name gz1 with `--gg 0` on seeds 4004-4015 (the baseline is played) or add 96
   games. (c) "close" is undefined. The spread against gz1dev with gg on, from three 16-game pairs on `CB280a`:
   0.37, 0.50, 0.52 (R): small samples sharing one baseline, and no sign that the margin shrinks when the pairing
   "prints its own".
7. **4.3 gate 1.** "classifies all 4 scripted Zerg archetypes above base rate by their scout timing" has no
   opponent to run on (part 4, item 2) and no definition of "their scout timing"; "holds calibration on Gary's own
   self-play games" fails today for a reason outside the belief. Rewrite as: on Gary's games against the suite,
   labelled by the pros' rule, no worse than the floor where Gary has not looked and better where it has; with a
   scouting precondition (Spire-or-Den seen by 7:00 given standing, within a stated distance of the pros').
8. **3.1, the belief's inputs (`train/plan_belief.py`, `gary/policy/belief.py:44-64`).** (a) No first-seen times,
   though the label is an order of first times; the ceiling fed the Zerg's true units is 0.421, 0.359, 0.398 at 4, 6
   and 8 minutes, worse at 8:00 than at 6:00, which a perfect scout cannot be: counts at 8:00 no longer say which
   came first or whether the third hatchery was before 5:00. `answers.py:66` already keeps first-seen frames. (b)
   The player's own supply and workers are inputs (`belief.py:46-47`): a pro's own build answers what he knows, so
   the belief can read the enemy's plan off Gary's supply, which no explanation may cite. (c) The lurker egg (97) is
   not in `ENEMY_TYPES["Z"]` (`belief.py:28-29`), though `answers.py:79` reads it. (d) On Gary's games "Gary's games'
   own shares" are fitted and scored on the same games (`plan_belief.py:178-179, 198`): 0.363 flatters them. (S; a's
   reading I)
9. **3.1 and 4.2, the sighting states (`gary/policy/sightings.py`, `ingest/sighting_dataset.py`).** (a) A look is
   unit distance to the base's centre (`:18, 52`), not sight: an SCV 8 tiles to one side has not seen a Spire at the
   far edge (the scout circles at 7 tiles for that reason, `army.py:63`), so "confirmed absent" is claimed too
   easily, and a scan is a look only if its sweep is a unit of the player's in `observe()` (not settled). Take the
   look from what was visible: the share of the base's tiles in sight since t. (b) Only town halls are recorded at a
   look (`:54`); absence of a Spire is left for the trees to compose from "looked" and "never seen". (c) The dataset
   is keyed by replay alone and finds the player by the first town hall of its race (`sighting_dataset.py:44, 86,
   91`): wrong in a mirror, against "race-keyed tables and shared providers". (d) With `--sightings`, old-era rows
   are NaN (`plan_belief.py:286-291, 301`; the dataset defaults to modern), which hands the trees the era the
   docstring says they don't get (`:10`). (e) 4.2's `SightingState` (seen, confirmed_absent, unscouted maps) and the
   committed class of the same name (per-base look times, seven features) are two shapes; settle one before the
   freeze rule means anything. (S)
10. **3.3 step 1; 4.3 ("989 mineral-line turrets"). The audit counted goals asked, not turrets.** At two a base
    (`answers.py:50`), a median 8.5 forced turret goals a game, 25 at the ninth decile and 38 at most (R) are more
    bases than Gary has: a goal not carried out is asked again after 30 s (`answers.py:35, 159-160`), and a turret
    lost is asked again. (I) Report turrets built by the rule against the pros' 6.9 by 10:00, and the share of asks
    never carried out (placement in a mineral line), a leak to fix whoever comes to own the turret.
11. **3.3 step 4. Arm A is partly what runs today.** The style one-hot and the seen counts are inputs already
    (`gary/policy/macro.py:91-92, 100`). Name today's build as Arm 0 and measure it on the card's own measure from
    existing games before building A or B (part 2). (S)
12. **4.3, the suite; section 6 row 2's consequence.** With the slice in TvZ Terran, the opponent that must hold a
    plan is the Zerg: both the four archetypes and G3's own example need a steerable Gary-Z, and line 330 gives its
    adherence as 56%. The document budgets 16 games "vs 4 scripted Zergs" that no code can play. Say that the suite
    is gz1dev told a style with each game labelled as played, that about half the games land on the told plan, and
    size the rounds for it; lurker-first, the plan the directives most need, is the rarest to obtain.
13. **3.3. One owner for Comsat energy.** `tech_scan` (`answers.py:86-99`), the hunt's scans (`army.py:73, 226`;
    off in the dev builds) and Detect (`gary/agent/fight.py` DetectRule, AGENTS.md's entry: "Comsat energy
    permitting") each spend it and none knows of the others. (S) The single-owner migration lists minerals, gas and
    the task slot; add energy, or the scouting scan starves the lurker scan.
14. **2.1 item 3, as resolved; section 6.** The resolution states the result and draws no consequence: promotion's
    second condition is not a target of any phase, the unfinished leads bound 0.078 of the 0.219, and the build
    that plays humans cannot be told a style. One line each in 2.1 and in the Phase 1 row (which build the blind
    evaluation and the live games use). (R, I)
15. **3.1, "Both must beat ... `answers.py`'s current heuristic read".** On the pros this is scored for the tech
    part; on Gary's games it is not scored at all (finding 8d's function). And only one of the two providers is
    built; the Bayesian one is the cheaper and the safer under Gary's look distribution (part 2). (S, I)
16. **3.2, the pro-frequency tables keyed on the belief.** Nothing else in 3.2 changed, but Phase 0 has a
    consequence for it: the pros' cells are those of a player who looked, so a table keyed on the belief inherits the
    look gap as the trees did (in 73 of `RD285a`'s 96 games no plan is read by 7:00, so every decision until then
    falls in the "nothing seen" cell, which for a pro means something else). Key the tables on the looked state too, or build them after scouting. (I)
17. **Round one's record.** Nothing in 1.4 to 1.6 was taken wrongly that this scope shows. Two rows deserve a note:
    1.11's third row (the 100% flip is a smoke check) is still in gate 3 as a threshold, harmless; and 1.6's refusal
    of a deterministic opening executor stands, but 3.3's strict-drill queue is that executor under another name, so
    whether it is needed should wait for Arm 0's number, not be assumed in the 40 drills.

## Literature relied on

| Work | Status in this run | Used for |
|---|---|---|
| Hostetler, Dereszynski, Dietterich, Fern (2012). *Inferring Strategies from Limited Reconnaissance in Real-time Strategy Games.* UAI 2012. https://arxiv.org/abs/1210.4880 | Abstract page opened; the PDF did not parse, so its observation model is not claimed | Brood War precedent for strategy inference when scouting is costly and partial (parts 1, 2) |
| Gehring, Ju, Mella, Gant, Usunier, Synnaeve (2018). *High-Level Strategy Selection under Partial Observability in StarCraft: Brood War.* NeurIPS 2018 workshop. https://arxiv.org/abs/1811.08568 | Opened (ar5iv HTML) | The auxiliary prediction of the hidden opponent state moved win rates within noise (0.878 to 0.879): a belief earns its place through a decision that uses it, or through explanation (part 2) |
| Huang, Wu, Yu, Fan, Fu, Fu, Yang (2023). *A Robust and Opponent-Aware League Training Method for StarCraft II* (ROA-Star). NeurIPS 2023. https://neurips.cc/virtual/2023/poster/70220 | Poster page opened (opponent modeling); the scouting reward is from the search record only, the PDF did not parse | Scouting valued by the opponent-strategy prediction; here as a measure, not a reward (part 1) |
| Justesen, Risi (2017). *Learning Macromanagement in StarCraft from Replays using Deep Learning.* CIG 2017. https://arxiv.org/abs/1707.03743 | Abstract page opened | Replay-trained macro whose abstract names no enemy sightings among its inputs: the contrast for "the macro model already reads sightings" |
| Liquipedia, *Bionic Terran vs. Zerg Guide.* https://liquipedia.net/starcraft/Bionic_Terran_vs._Zerg_Guide | Opened | Gives no scouting method or timing: the pros' means must be counted from replays |
| Cho and colleagues (2017; the search record names only the first author). *Investigation of the Effect of "Fog of War" in the Prediction of StarCraft Strategy Using Machine Learning.* Computers in Entertainment. https://doi.org/10.1145/2735384 | Search record only | Prediction trained on what was actually visible; named, not relied on |
| Weber, Mateas (2009). *A Data Mining Approach to Strategy Prediction.* CIG 2009. https://expressiveintelligence.github.io/papers/cig_2009.pdf | Search record only | The earlier, full-information baseline; named, not relied on |
| Synnaeve, Bessière (2011). *A Bayesian Model for Plan Recognition in RTS Games applied to StarCraft.* AIIDE 2011. https://arxiv.org/abs/1111.3735 | Recalled, not opened (the document's reference 3) | The Bayesian provider of 3.1's bake-off (part 2) |

I found no work that learns when and where to scout from human replays by imitation; the nearest (ROA-Star) learns it
by reinforcement. The learned scan model proposed in part 1 rests on this repo's own precedent (the stim model), not
on a paper.
