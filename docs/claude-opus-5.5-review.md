Round two, 2026-11-23

Review of docs/REFOCUS.md (v2.0 at 80fa001) by Claude Opus 5.5, round two's scope only. I had web search and fetch;
each work says whether I opened it. I read no other review file and ran nothing of the project's: my counts come from
grep and read-only scripts over runs/league/RD285a, RP285a and HS284a's logs and records. "Read" means read in source
or those files; "inferred" means reasoned from them.

---

## The question

### Lead: is Phase 1 as written still the right first build, in the right order, at a sensible cost in games?

No, not in its written order. Phase 0 showed that the binding constraint is the information Gary gathers, not the
inference over it. The belief already beats the floor on the pros' views (PROGRESS.md:2203-2205). On Gary's own games
it is worse than the floor because Gary hardly ever looks (PROGRESS.md:2212-2216). And the one scripted look Gary has,
answers.py's tech scan, cannot fire on six of the eight ladder maps: a bug, finding 1 below. Building the trunk,
card tables, directives and templates on a belief whose inputs are empty would give G5 answers that are honest but
amount to "I didn't look", and directives that never trigger. Phase 1 should start with the information. 3.1 and
gate 1 use the word "scout", but 3.1-3.4 name no component that decides when or how Gary looks.

What I would build first, in order, with games:

| Step | What | Games |
|---|---|---|
| 0 | Offline counts (part 1 below): how and when the pros first see the Zerg's discriminating tech (Spire, Den) apart from a Lair, by means (their own scans from the replay commands, the worker, army units) and base; the same for Gary (records for Spires and Dens, the re-simulation for Lairs, finding 12); whether the belief changes the pros' next macro choice beyond what the macro model already reads (part 2) | 0 |
| 1 | Fix `tech_scan`'s main lookup (finding 1), a plain bug adopted on its check | 0 (rides on step 2's round) |
| 2 | Scouting from the pros: first the pros' timings sampled as a hazard of a first look given nothing seen yet (scans; the worker staying, the existing `watch`), judged on the fidelity measure (tech seen by 4/6/8 min against the pros' 15/60/77%) | 16 per option to screen, as a severalfold measure needs (AGENTS.md) |
| 3 | The Zerg plan suite from gz1dev told styles (`--style-b`), each game labelled as played, not a new scripted bot (finding 7); the sighting states built in full (offline); the chosen scouting option played against the suite | 48 (12 an archetype: the fewest that score the belief per plan) |
| 4 | The belief re-scored on step 3's games against the suite's own plan shares | 0 |
| 5 | A gt0.50dev baseline against gz1dev on the gate's seeds (finding 5): gate 4 needs it and the budget has none | 48 (96 if close) |
| 6 | One directive end to end: answers.py's lurker list replaced by belief, then the pros' conditional choice, then the macro. Retire that one rule on its AGENTS.md measure, the time to the answer per archetype | 48 |
| 7 | The card and strict drills (part 2's smallest card); templates on the records | 40 drills; templates 0 |
| 8 | Army: the retreat hold only, as a pipe fix on its own check; Arm 2's commit hold dropped, Arm 3 waits on a cluster key (part 3) | 16-32 |

That totals about 220-300 games against the plan's 360-550 (REFOCUS.md:308). The savings come from three places:
the 32-game soak answered from existing records (finding 6), the army screen shrunk to the one arm not already
measured, and checks on fidelity measures sized at 16 games where they move severalfold. The trunk's tables (3.2)
and the Arm A/Arm B comparison (3.3) come after step 6, once one directive has shown that a belief changes a decision
Gary carries out.

### (1) Gary sees the Zerg's tech by 6:00 in 5% of games, the pros in 60%

In short: what the pros do that Gary doesn't, as far as the source shows, is keep a worker in the Zerg's bases (the
Zerg in sight 104 s of 3:00-6:00 against Gary's 44 s) and get a look at the main before 6:00. Gary's one scripted
look is a scan that cannot fire before 6:30, nor at all on six of eight maps. What else the pros do (scans, army
pokes) is unmeasured, which is step 0.

**What Gary does today (read).**
- *The worker scout* (gary/agent/army.py:974-1051): one SCV from 0:45 at 9 SCVs. It goes to the enemy starts,
  circles the main 7 tiles out (CIRCLE, army.py:63), passes the natural, then goes home (army.py:1026-1033). In
  RD285a the last scout order logged is at a median of about 3:00 (deciles 2:10 to 4:01; my count over the 96 logs).
- *`watch` is off in gt1dev.* It is not in the option chain (manifests.py:1398-1401), and `_ARMY` holds no `watch`
  (manifests.py:36). With it, the scout tours the Zerg's main and natural until 5:00 or until it is hunted
  (STAY_UNTIL, army.py:90), then posts outside Gary's own natural (army.py:1092-1117). It was dropped in v0.19 on
  432 games (lost 30 for 25, won 127 for 133), with the reason "an SCV off minerals for minutes, for information no
  decision uses" (manifests.py:803-810). Its fidelity measure was then near the pros: Zerg in sight 103 s of 3:00-6:00
  with the tour, 44 s without, the pros 104 s (army.py:15-16, manifests.py:807).
- *`tech_scan`* (answers.py:86-99, called at macro.py:221): one scan of the Zerg's main at 6:30 if no plan is read,
  again at 8:30. Three things stop it. The plan must be unread. A completed Comsat must have 50 energy. And the main
  must be known, which the code takes from `g.army.enemy_main` or a single enemy start (answers.py:91).
  `enemy_main` is set only under `watch` (army.py:1029-1030), and `g.enemy_starts` is never narrowed after
  the scout finds the Zerg (gary/agent/gary.py:118 is its only assignment). On a map with more than one possible
  enemy start, `tech_scan` therefore never fires. RD285a's 20 scans are all on Colorless Fate (9) and Odyssey-RE (11);
  RP285a's 20 likewise (11, 9); HS284a's two likewise (read: "scans the zerg's main" in the logs). These are the two
  maps on which the Zerg sent no overlord to scout a start, so they are the two-start maps (inferred).
- *Even fixed, it cannot move the 6:00 number*: TECH_SCAN is 6:30 (answers.py:32).
- *The hunt's scans are off* in gt1dev (`unscripted` sets `hunt=False`, manifests.py:1093).

**What that does (read from the records, RD285a, Gary's "seen ... building" records).** A Zerg tech building is
first seen by 4/6/8 minutes in 0/1/15 of 96 games. 14 of those 15 are on the two scan maps. In 15 of the 16 scan
games, the first tech sighting comes within 2 s of a scan: a 6:30 scan, then a Spire at 6:31; a 6:38 scan, then a
Den at 6:39. In one of them it was the second scan, after a first at 9:13 found nothing. In the 16th (Odyssey-RE seed
4013) a Den was seen at 7:40, before the first scan at 10:23. The plan answers.py reads in RD285a is read at a
median of 7:33, by 6:00 in 1 game and by 8:00 in 51 (logs). In HS284a the "seen" lists behind most reads contain
Mutalisks (type 43) and no Spire. So Gary learns the plan when the Mutalisks arrive. HS284a's records give 0/0/1 of
16. These are lower than the document's 5% and 20% over 112 games (REFOCUS.md:327, PROGRESS.md:2212-2213), which
come from the re-simulated view (plan_belief.py:102, 137). One reason, read in source: the records log an enemy
building the first time its *tag* is in sight (gary/agent/sightings.py:179-183). A Hatchery seen at 2:00 that becomes
a Lair keeps its tag, so its Lair never gets a record. So the records miss Lairs (and Hives and Greater Spires), and
my count is in effect Spires, Dens and the like. The re-simulated count includes the Lairs. The two agree on the
point.

**Did the tech stand when Gary hadn't seen it?** Mostly yes, but only bounded. The Zerg's logs (RD285a) decide a
Spire in 89 of 96 games, by 5:00 in 62, median about 4:44: decision times, the starts unverified. Read: in the scan
games a Spire or Den already stood when the scan came (6:30-7:10). By 6:00 is step 0's count, the re-simulated
Zerg's first Lair, Spire and Den against Gary's first sighting, as `gary_game` computes (plan_belief.py:138-143).

**What to count in the pros' games first (0 games).**
1. Split the measure. `TECH_BUILDINGS` counts a Lair (plan_belief.py:61-62). A Lair does not tell spire from lurker
   (answers.py:14-15 needs a Spire, a Mutalisk, a Lurker or a Den with a Lair). The pros' 60% may be largely Lairs
   seen by a worker that stayed. Report Lair-seen and Spire-or-Den-seen separately, by 4/5/6/7/8 min.
2. By which means: (a) the pros' own scans, which are commands in the replay with a target (ingest/build_orders.py:137
   already maps `CastScannerSweep`), with their time, target base and whether a tech building was in that base;
   (b) which of the player's units first had the building in sight (worker, army type), from the replay re-played as
   `ingest/sighting_dataset.py` does; (c) the first worker scout's stay, as `watch` measured it.
3. How long the pros' scouting worker stays, and whether they scan more when nothing is seen yet. This is the
   conditional that decides between a sampled timing and a learned model.

**The candidates, compared (inferred, under AGENTS.md's rules).**

| Candidate | What it is | Under "Fidelity before wins" / "Stop-gaps" | Strength | Weakness |
|---|---|---|---|---|
| Fix `tech_scan` only | Use the scout's discovered main | A plain bug fix, adopted on its check | Free; on the two scan maps 14 of 24 games saw tech by 8:00 | 6:30 is after the pros' 6:00 reading; answers.py is itself a stop-gap due to retire |
| `watch` again | The existing option | A pro-like change judged first on its fidelity measure; its v0.19 rejection on wins, for "information no decision uses", predates the 2026-10-23 rule and its premise ends when the belief uses the information | Exists; measured near the pros on Zerg-in-sight | It leaves at 5:00 (STAY_UNTIL); with 62 of 89 Spires decided by 5:00, whether it sees one before leaving is unverified, so it may add mostly Lairs and hatch counts |
| Pros' timings sampled | A decoder that samples when the pros first scan or keep a worker in, per style and map, given nothing seen yet | Named in AGENTS.md as a fidelity change ("a decoder that samples the pros' timings"); not a stop-gap | Cheap, honest to explain, keeps Gary's looking pattern near the pros' | Unconditional beyond "seen yet"; scans a second time when a pro wouldn't |
| Trigger on unscouted | A rule: belief entropy high and main unlooked for T s, then scan | A scripted rule: tagged STOP-GAP with an entry and a measure | Targets the decision need; explains well | Changes *how* Gary looks away from the pros. The belief is trained on the pros' looking, and in the pros' data what was looked at is itself evidence (below), so the belief's inputs shift |
| Learned look model | A hazard of "the pro scans or sends a unit to the enemy's main or natural now", conditioned on time, the sighting state, the belief's entropy, Comsat energy; with its decoder | The repo's own pattern (the stim model and its rule-as-decoder, AGENTS.md "Stim is not a stop-gap") | Conditional; scans are clean labels (commands) | Unit pokes are not labelled "scout" in the data; they are the army and calm layers' moves |

My recommendation: step 0, then the bug fix, then the sampled hazard for scans and the worker's stay, judged on the
split measure. Move to the learned look model only if the sampled timings miss the pros per situation, for example
by scanning after the tech was already seen. A trigger is the last resort, and it would need its AGENTS.md entry.
The reason to prefer imitation over a value-of-information trigger is specific to this belief: in the pros' data the
act of looking carries information. Lipton, Kale and Wetzel report the same in clinical series, where which tests
were ordered predicted about as well as their results (from search summaries, not opened). A Gary that looks
differently from the pros changes p(sightings | plan), which no prior correction fixes: label-shift methods
(Saerens et al. 2002; Lipton, Wang, Smola 2018) assume p(x | y) fixed.

**Where scouting goes, and its measure.** First in Phase 1, before the trunk and before the belief is wired into
play. The measure: Lair-seen and Spire-or-Den-seen by 4/5/6/7/8 min against the pros of the same style on the
same maps; the pros' and Gary's scans per game by minute; worker-seconds in the Zerg's bases at 3-6 min against the
pros' (`watch`'s measure); and, as a cost check, workers at 8:00 against the pros'.

**Literature (searched).** I found no work that learns scouting timing from human replays. Closest:
- Hostetler, Dereszynski, Dietterich, Fern (2012), *Inferring Strategies from Limited Reconnaissance in Real-time
  Strategy Games*, UAI 2012, https://arxiv.org/abs/1210.4880 (abstract opened; PDF text not extractable). A dynamic
  Bayes net of StarCraft strategies with scouting as evidence: the precedent for the sighting states.
- Si, Pisan, Tan (2014), *A Scouting Strategy for Real-Time Strategy Games*, IE 2014,
  https://opus.lib.uts.edu.au/handle/10453/41998 (abstract opened): multi-criterion exploration for bots; no human data.
- Cho, Park, Kim, Kim (2017), *Investigation of the Effect of "Fog of War" in the Prediction of StarCraft Strategy
  Using Machine Learning*, ACM Computers in Entertainment, https://doi.org/10.1145/2735384 (search results only):
  strategy prediction with and without fog, closest to Gary's pros-versus-own-games gap.
- Lipton, Kale, Wetzel (2016), *Directly Modeling Missing Data in Sequences with RNNs*, MLHC 2016,
  https://proceedings.mlr.press/v56/Lipton16.html (search results only): missingness indicators are informative when
  data are missing not at random, the point behind the sighting states and against a non-pro look policy.
- Saerens, Latinne, Decaestecker (2002), *Adjusting the Outputs of a Classifier to New a Priori Probabilities*,
  Neural Computation 14(1), https://doi.org/10.1162/089976602753284446, and Lipton, Wang, Smola (2018), *Detecting and
  Correcting for Label Shift with Black Box Predictors*, ICML 2018, https://arxiv.org/abs/1802.03916 (both search
  results only). These correct a changed class prior when p(x | y) holds. They fit a prior shift between opponent
  populations (gz1's one plan against the pros' mix), and not the observation shift Gary's scouting causes.

### (2) What must the card and the belief add beyond style conditioning and answers.py?

**What exists covers (read).**
- *Style conditioning.* The macro model reads the told style (the tracker's `style`, macro.py:154), and `gastarget`
  ties its gas to it. eval/style_adherence.py labels a game by its nearest neighbour among the Terran tech clusters
  (from 9,221 player-games, none of them modern, style_adherence.py:2-4). The features are each key item's first time
  in the first 8 minutes, capped at 10 (WINDOW, NEVER, style_adherence.py:26, 37-39). The 97-100% therefore counts
  *which cluster of first-tech timings the opening is nearest*. It does not count:
  - how far each item is from a target (style 2's Factory at 3.0 min against the pros' 2.5, PROGRESS.md:2177-2178,
    still labels as style 2);
  - counts (Factories, the number of units), anything after 8:00, the third base;
  - whether the build responds to the Zerg;
  - every style: style 3 is 6 of 8 (PROGRESS.md:2177), so "97 to 100%" holds for styles 1 and 2.
- *answers.py* reads mutalisks or lurkers from what was ever seen (answers.py:71-84). It forces the lurker list
  (answers.py:38-40) or turrets in each mineral line (answers.py:151-182), and vetoes the model's other turrets
  (answers.py:101-111). In RD285a that was 1,199 forced goals, 3.0% of the macro's decisions, 989 of them turrets
  (PROGRESS.md:2106-2109), read at a median of 7:33 (above). It reads neither the opening, nor the hatcheries, nor
  any probability before tech is seen.
- *The macro model already reads what was seen*: each enemy type in sight now and the most of it ever seen at once
  (gary/policy/macro.py:9, 100, 299-300; looked at between queries with `seenall`, macro.py:319-322). The plan
  belief reads the same view through the belief model's features: in sight now, the most over 30 s, 90 s, 3 min and
  ever (plan_belief.py:5-10). As an input to the macro model (3.3 Arm A) the belief therefore largely overlaps what
  the model has, adding the shorter windows, the map prior and, later, the sighting states (inferred). The offline
  test below decides whether that overlap leaves anything.

**The smallest belief that adds something.** It needs two parts, kept apart.
- *For G5*: the belief and the sighting states logged to the records, consumed by nothing. Its measure is template
  2's ground-truth accuracy against the base rate (3.5 item 3), 0 extra games. This is the one use that needs no
  decision downstream.
- *For play*: the belief's real gain over answers.py is the hatcheries part (-0.083 to -0.132 Brier against the
  floor; the tech part is no better than answers.py at 6:00, PROGRESS.md:2205-2208). That gain matters only if the
  pros' Terran choices depend on it. The test is offline and costs 0 games: does adding the belief to a model of the
  pros' next macro choice improve its held-out log-likelihood beyond the macro model's own inputs? If it does not,
  the belief is for explanations only, and Arm A's belief input should be dropped.

**The smallest card that adds something.** A per-game milestone list for the told style, taken from one pro game
of that style on that map, as `tiles` already lays out a base "as a pro did" (log line "lays out its base ... as a
pro did (30 pros' games there)"). It holds the style's key items plus the third Command Center and the first
production added after 8:00. In strict mode the decoder masks one-offs that are not on the card. Its measure is the
per-milestone timing error to the card (median |dt| and the share within a tolerance, as ARCHITECTURE's 18 of 20).
The baseline costs 0 games: gt0.50dev's existing games scored against cards of their told style drawn post hoc.
What the card adds is the error reduction over style conditioning alone. A label already at 97-100% cannot show
it.

**The measure for the pair in play** is conditional adherence: Gary's key items given the Zerg's plan, against the
pros of the same style facing the same plan, on the same maps (eval/style_adherence.py split by the opponent's
label), plus the time from the Zerg's tech standing (from the re-simulation) to Gary's first answer item, per
archetype. A learner or a viewer would notice that, and neither the style label nor answers.py's count shows it.

### (3) The deficit, the unfinished leads, and the army test's arms

**Where the deficit comes from (read).** RD285a/RP285a give gt1dev won 16, lost 20, at time 60 (30 ahead), and gt1
won 60, lost 15, at time 21 (PROGRESS.md:2160-2164). The repo's own account, unchanged since 2026-11-11, is that gt1
keeps the stop-gaps that each measurably won: the bank escape -0.203, the caps -0.109, the static guard -0.062, the
SCV cap -0.047, each measured off against the then playing build, "together more than the whole gap"
(PROGRESS.md:3140-3145). gt1 also keeps the hunt that ends its games. With the hunt back in, gt1dev closed about a
fifth: +0.057 [+0.000, +0.120] on 48, decided 46% for 33% (PROGRESS.md:3130-3135). gt1dev also loses more (20
against 15), so the deficit is not only unfinished leads.

**Does Phase 1 address it? No, and it should not take it as its gate, but the document should say three things it
does not:**
1. Phase 1 is judged against gt0.50dev, not gt1 (gate 4, REFOCUS.md:344), so the deficit does not block Phase 1. It
   does block promotion, and nothing in Phases 1-2 builds a successor for the stop-gaps that make it up. The hunt's
   named replacement is "trained with a reward for ending games (self-play)" (AGENTS.md hunt entry), and RL is parked
   (decision 4). That is a consequence of decision 4 the document doesn't draw: finishing has no successor path in
   this plan. Under the promotion rule gt1dev cannot be promoted until it does, however near the pros it plays.
2. The unfinished leads are partly a property of the opponent. gz1 cannot resign, since "only the dev builds' critics
   can resign" (PROGRESS.md:2153-2154). Against gz1dev with gg on, every game of CB280a ended (PROGRESS.md:2430-2431).
   Phase 1's rounds against gz1dev with gg on will show fewer unfinished games than RD285a. That is a change of
   opponent, not of Gary, and the document should not read it as progress on finishing.
3. A directive is no finisher. The trunk's pro-frequency tables are built from pros whose opponents leave
   (PROGRESS.md:2434-2437), so the clean-up states are rare in the data, as they were for the commit model.

**Do the three arms of 3.4 repeat what was tried? Arm 2 largely does; Arm 3 partly; read in source.**
- *Arm 2 on the commit layer is already built three ways:*
  - The commit model reads its commitment and age as inputs, so its hold is already learned: COMMIT_INPUTS,
    gary/policy/army.py:82, 109-112, 149-150; fed at army.py:592.
  - A hold at the pros' reversal hazard exists as a decoder for paired arms: HAZARD and HAZARD_AGE, army.py:44-47,
    575-588.
  - `holdtarget` (army.py:657-660; manifests.py:1121-1124) gave HT120a -0.011 +- 0.087, and `unitcommits`
    (army.py:663-679; manifests.py:1125-1127) gave UC120a -0.048 +- 0.064. Neither was adopted.

  The finding behind them: on the same measure, the pros redirect 0.79 of group orders within 30 s and gt1dev 0.70.
  "holdtarget and unitcommits ... fixed a problem that wasn't there" (PROGRESS.md:1213-1219, again 2454-2456). A
  learned commit hold is therefore measured and not missing. Round one took persistence first on the commit layer
  (record 1.2, 1.7, decision 3; I backed it) while missing this measure. Decision 3's principle stands; half its Arm
  2 had already run. New in Arm 2 is the *retreat* hold in the role layer: retreats short at 0.18-0.47 for the pros'
  0.78-1.02, "lost between the order and a move seen" (TODO.md:59-65), a pipe fault judged on its own check.
- *Arm 3's targets were measured elsewhere.* Late arrivals: `gather`, 0.26 to 0.22 only, not adopted (AGENTS.md).
  Units alone: the hands split a cluster's order into about three selections, and the open fix is "a key for the
  cluster (the grouping provider)" (PROGRESS.md:2282-2289). So that refactor, which 3.4 makes conditional
  (REFOCUS.md:189), should come first, judged on one-unit orders (pros 12%) and departures alone (pros 21%).
- 3.4's open question settled: the commit model's global inputs are time, economy, supply, own and seen unit counts,
  the commitment and the other clusters (gary/policy/army.py:135-155). Research state is not among them.

### (4) Code that blocks Phase 1 and the questions miss

Findings 1, 3, 4, 5, 7 and 12 below:
- `tech_scan` is dead on six of eight maps.
- Gate 1 on Gary's own games cannot pass as written, and plan_belief.py has no calibration measure and an in-sample
  comparator.
- sightings.py's "looked" is a distance to a base's center; it cannot confirm a tech building absent and may not
  count scans.
- Gate 4 has no baseline round against gz1dev on the current code.
- The scripted Zerg suite no longer exists.
- The records miss Lairs and other morphs.

---

## Findings

**1. `tech_scan` never fires on maps with more than one enemy start (4.3 Phase 0 results; read in source and
logs).** answers.py:91 takes the Zerg's main from `g.army.enemy_main`, set only with `watch` (army.py:1029-1030),
or from a single enemy start. `g.enemy_starts` is assigned once and never narrowed (gary/agent/gary.py:118). Scans
by map, from "scans the zerg's main" in the logs:

| Round | Colorless Fate | Odyssey-RE | Other six maps |
|---|---|---|---|
| RD285a | 9 | 11 | 0 |
| RP285a | 11 | 9 | 0 |
| HS284a | 1 | 1 | 0 |

Consequences:
- Phase 0's count misreports it. PROGRESS.md:2104 says HS284a had "No tech scan ... (0 in 16 games: the plan was
  read before 6:30, or no Comsat)". The logs show two (Colorless Fate seed 4004 at 6:31; Odyssey-RE seed 4005 at
  8:12), and the cause on the other maps is the unknown main.
- answers.py's lurker answer comes late on six maps for a reason no measure of it has named.
- The same fallback orders the turret lines in answers.py:117 and 172, which is harmless.

Fix: take the main from the scout's first enemy-building sighting, or from the sighting state's `enemy_main`
(sightings.py:58-65). A plain fix (AGENTS.md), adopted on its check (scans on all maps; tech seen by 8:00).

**2. Phase 1's order puts inference before information (3.1, 4.3; inferred).** See the lead. 3.1's two-provider
bake-off (REFOCUS.md:147-150) spends effort where the gain is bounded by what is seen, and the tree already beats the
floor on the pros. Drop the Bayesian provider unless the tree fails calibration on the suite.

**3. Gate 1's second clause cannot pass as written, and the code doesn't compute it (4.3 gate 1, REFOCUS.md:338;
read in train/plan_belief.py).**
- "Holds calibration on Gary's own self-play games": with Gary not looking, the best a correct belief can do is the
  prior. With the sighting states, a model that has learned "unlooked means no evidence" should fall back to the
  floor, not beat it. Until scouting exists the clause should read "not worse than the floor". (Round one took
  "calibrate on Gary's own games" in record 1.4; the aim was right, but its use as a pass condition needs scouting.)
- The floor itself is the pros' plan mix, while gz1 and gz1dev play one plan in 85 of 112 games (PROGRESS.md:2214-
  2216). Score on the suite with its known shares.
- `score_gary` reports Brier only, with no calibration error (plan_belief.py:199-202), although the gate names
  calibration and 3.1 names ECE (REFOCUS.md:150).
- Its "Gary's games' own shares" comparator is fitted on the very games it scores (plan_belief.py:178-179,
  198-202), which flatters it.
- The label differs by source. Gary's games are labelled from true units by plans.py's rule with the first Lurker
  for Lurker Aspect (plan_belief.py:106-144); the pros' from the taxonomy's labels (plan_belief.py:205-228). Label
  a sample of pro games by `gary_game`'s rule too and report the agreement, or the comparison carries a labeller
  difference.

**4. sightings.py doesn't yet implement the contract's "confirmed absent" (3.1, 4.2; read).**
- A base counts as looked at when any of the player's units is within 8 tiles of its center (LOOK, sightings.py:18,
  52-53). Sight ranges differ by unit, and a main is wider than 8 tiles, so a Spire at the back of a main can be
  unseen at a "look". The only absence recorded is of a town hall (`hall_at_look`, sightings.py:54-55). Contract
  4.2's `confirmed_absent: dict[str, int]` "region/feature" (REFOCUS.md:242) thus exists for halls only. For tech,
  absence comes only indirectly, from "main looked at T s ago" beside the seen counts.
- Whether a Comsat scan counts as a look depends on whether the Scanner Sweep appears among the player's units in
  the observation. env/gary_env.cpp:290 iterates `st.visible_units`; I did not settle whether the sweep is among
  them. Scans are the pros' likely main means at 6-7 min (answers.py:16-17), so this must be checked (a scan in a
  scenario, then `look()`) before the dataset is built in full.
- A name clash for G5: gary/agent/sightings.py (the "seen" records the templates will cite) and
  gary/policy/sightings.py (the states). Log the states through the first, or the records keep two notions of
  "seen".
- When wired into play it is a model input, so tests/test_inputs.py must hold it (AGENTS.md).

**5. Gate 4 has no valid baseline round (4.3 gate 4, REFOCUS.md:344; rounds read, omission inferred).** The gate
pairs arms against gt0.50dev versus gz1dev. Phase 0's reference rounds are against gz1 with gg off (REFOCUS.md:326),
and HS284a predates the seed fix that changed every stream (PROGRESS.md:2233-2234). AGENTS.md requires a replayed
baseline: add a gt0.50dev-against-gz1dev round on the gate's seeds, gg on, to the budget. Its spread will replace the
gg-off 0.466, as the document already says.

**6. The log-only soak (3.3 step 2, 32 games in 4.3) is answerable from existing records (records read; sufficiency
inferred).** Each macro decision record carries its odds, its draw and the options set aside with reasons ("waits: no
larva", "can't now: the pros' cap"); the hands' holds are in the trace; `on_card`/`off_card` can be computed against
any card afterwards. Run it over RD285a's 96 games: 0 new games.

**7. The scripted four-archetype suite does not exist (4.3 "Fixed Multi-Archetype Zerg Test Suite",
REFOCUS.md:329-334; read).** The scripted Zergs (zerg_v3) left in the refactor (gary/agent/zerg_executor.py:1-2).
gz1dev told a style is the repo's own instrument (`--style-b`), though its adherence is partial: gz0.8dev played
told style 4 as itself in 75% of games, style 0 in 50%, style 1 in 38% (PROGRESS.md:1562-1563). The 62% for style 0
in REFOCUS section 1 is not there (record 1.11's unchecked row). Label each game as played, as TODO.md:35 already
says. Whether gz1dev's catalogue has a 9-pool and a 2-hatch ling pressure I did not check (`--list-styles`); if not,
those two are the only ones worth scripting. Scripted Zergs also taught the selector its cheese (REFOCUS.md:95).

**8. The agreed order before the stop is right in content, wrong in one place (TODO.md:34-36; inferred).** The
order was the sighting states, the suite, the scouting measure, scouting, the re-score. Put the scouting measure
first: it decides what the sighting states must represent (scans as looks, tile visibility versus distance, Lair
versus Spire). It costs 0 games. Add finding 1's fix beside it.

**9. Arm A's belief input largely overlaps the macro model's own seen inputs (3.3 step 4, REFOCUS.md:179;
gary/policy/macro.py:100, 299-300 read; the overlap inferred, part 2).** Arm A against Arm B compares card
conditioning with masking; run it without the belief input (or with the sighting states only) unless part 2's
offline test shows the belief adds something.

**10. The army screen's budget buys little (4.3 Parallel Track, REFOCUS.md:314; inferred).** 16 games an arm resolve
nothing on the paired score (48 resolve about 0.17, gate 4's text). Judge the retreat hold and the cluster key on
their own checks (part 3), 16 games each: 144-240 games become about 32, plus one 96 for whatever is folded in.

**11. Stale references in the section under review (read).**
- 3.4 cites TODO.md:31-32 for the retreat hold; TODO.md was rewritten, and that text is now at TODO.md:59-65.
- 2.2 and section 6 cite TODO.md:143-145 for RL parked; it is now TODO.md:178.
- Arm 1 and the parallel track's "winner vs `gt0.48dev`" (REFOCUS.md:187, 314) should be gt0.50dev, the stated
  baseline (REFOCUS.md:326, 344).
- 5.1's first row (REFOCUS.md:354) is still an open question though 2.1 item 3 resolved it.

**12. The records miss a building's morph, which G5 templates will cite (3.5, 4.2; read).** gary/agent/sightings.py
records an enemy building the first time its tag is in sight (sightings.py:179-183). A Hatchery becoming a Lair or a
Hive, or a Spire becoming a Greater Spire, keeps its tag and gets no record. Template 2 ("what did you think I was
doing, from what evidence") would then never cite "saw your Lair". Key by (tag, type), as the macro tracker does for
Gary's own buildings (gary/policy/macro.py:332-333).

**13. A round-one item worth another look: 1.6's "not take" of a deterministic opening executor (record 1.6, row 5).**
It was refused as a second executor to keep in parity. Strict drills (18 of 20) still wait on Arm A or B holding a
card under dice (REFOCUS.md:181, 339). The card error of dice-drawn macro is measurable on existing games (part 2):
measure it first. If it exceeds the drill tolerance, the scripted queue is the drill path, not a fallback.
