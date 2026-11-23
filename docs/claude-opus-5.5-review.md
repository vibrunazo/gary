Round one, 2026-11-22

Review of docs/REFOCUS.md (Draft v1.1) by Claude Opus 5.5. I had web search and page fetch in this run; every
external work below says whether I opened it (abstract page or full text) or only saw it in search results. I read
no other review file. Line numbers are for the files as they are today.

## 1. Is a major refocus necessary, or would the current direction get there?

**My answer, in short: change the priorities and the process now. Do not rebuild the architecture.** The repo shows
the current direction is not aimed at three of the six goals and has no rule for when to stop. It does not show that
the agent's structure has to be rebuilt as a four-tier `gt_ns`. Most of what the plan proposes is already designed in
docs/ARCHITECTURE.md and was never built. Several of the measurements it gives as proof are misread (findings 1, 3,
8).

What makes me say the current direction will not get there by bug fixing and training alone:

- **Nothing on the current list builds G3 beyond styles, or G4, or G5.** TODO.md's Direction (lines 7-46) is items
  a-f. All of them are about G1 fidelity: per-situation judging, the pipe table, positioning, live games, the
  measure for promotion. The work that would build the missing goals sits in the issue index, unstarted: strategy
  layer with a timeline #26 (TODO.md:206), opponent plan belief #40 (:193), narrator #41 (:252), macro with game
  history #12 (:191).

  ARCHITECTURE.md's own status table marks the opponent model "no inference of the enemy's *z*" (line 30), feature
  discovery "Deferred" (line 31) and explainability "no narrator" (line 32). More fixes to the pipe will not produce
  an enemy-plan belief, a replay compiled to a plan, or a skill slider. On those three goals I agree with the plan.
- **On G1, the per-measure loop has no stopping rule and no top-level check.** The repo's own record:
  - TODO.md:14-16: "the tank work fixed the flipping and moved no top-level measure ... one mode in two matchups
    took five days".
  - PROGRESS.md:1796-1799: about 25 changes landed with none "played by a person or held against the playing
    builds".
  - TODO.md:43-44: gt1dev trails gt1 by -0.188 [-0.302, -0.078] (2026-11-11).
  - Watching three games found the never-sieging tanks that months of rounds had missed (TODO.md:9-11). The cause
    was a configuration fault (finding 10).

  This calls for a change of process, which REFOCUS §6.2's last two rows propose: live games before rounds, and gap
  measures used as anomaly detectors rather than as the work queue. It does not call for a new architecture.

What makes me say a rebuild is not shown to be necessary:

- **The incoherence the plan blames on the architecture has, in the repo, mostly been traced to the pipe and the
  hands.**
  - TODO.md:15 says it outright: "most faults found were in the pipe between a model's odds and what Gary carried
    out".
  - The CalmNet case the plan calls a "proof" was diagnosed in PROGRESS.md as being about who gets the orders, not
    where they go (finding 8).
  - Coherence is not solved, and this is the plan's best case. The hands fix that sends army orders to whole
    clusters (manifests.py:1386-1392) moved the spread and the fight gap over all windows nearer, but units alone
    stayed at 0.40 against the pros' 0.20 (PROGRESS.md:2155-2164; TODO.md:39-41). The remainder sits in the calm and
    commit layers' orders and in having more small bunches (PROGRESS.md:2165-2170). A persistent army intent is a
    reasonable answer to that (finding 5); a new trunk is not the only one.
- **The two "learning works" rows in REFOCUS's ledger do not show learning at the option or strategy timescale
  (finding 1).** Learning at that timescale failed in every attempt: loops a1 and a2, the forced engage arms e1 and
  e2, and the commit pairs. A learned scorer over symbolic facts, which is Provider A/B in miniature, gained nothing held
  out. The trunk's learned branch scorer has no positive precedent in this repo.
- **G5 as ARCHITECTURE.md states it is mostly reachable without a symbolic trunk.**
  - The plan's G5 row (REFOCUS line 37) restates the goal as "Faithfully explainable for learners ... causal trace
    answering *why*". ARCHITECTURE.md:57 asks for "a queryable trace: what it intended, what it believed, which
    alternatives it considered, and which human constraint got in the way", and line 64 rules out full transparency
    of the neural policy as a goal.
  - The records already hold the alternatives with their odds. A record from HS283a (gt1dev_seed4004.records.jsonl)
    carries `"by": "dice", "p": ..., "top": [...]` for every macro draw.
  - ARCHITECTURE.md §8 (lines 873-876) already prescribes counterfactual consistency by perturbing named input
    groups.
  - What is missing is the belief (#40) and a plan variable that persists. Both can be named inputs to the existing
    models, checked by the counterfactual §8 already specifies. "Blocked architecturally" holds only under the
    stronger G5 the plan writes for itself.

**What I would do instead:** build ARCHITECTURE.md's unbuilt parts as providers inside the current agent. That
means:
- the opponent model of §7.5, on the style labels that now exist (PROGRESS.md:1441-1447);
- *z* from a replay, §6.1, conditioning the existing macro model as AlphaStar's *z* does;
- the strategy selector of §6.8, choosing by pro frequency given the belief (finding 2);
- §8's records and counterfactual check.

Each of these is judged by the fidelity measures already in use. Two smaller changes go with them: one persistent
army intent per cluster, with learned hold hazards (finding 5), and the §6.2 process changes. These are a
change of priority within the current direction. They do not need a parallel `gt_ns` line, which would add a
seventh build line to a project whose §2.4 complaint is that six already cost too much.

## 2. Findings on the plan's solutions, most important first

### F1. The ledger's positive rows (§2.3) do not show what the plan builds on

Section: §2.3 table, rows "Whole-army coherent intent" and "Per-game strategy choice"; Solution 3 "(where SNR is 3×
higher than single ticks)". Read in source.

- `eval/army_effect.py` measured the size of a stark contrast. It did not learn anything.
  - Its contrast was the whole army attacking against holding, with the army layer frozen for 90 s
    (SELF_PLAY.md:308-317). Its own caveat: "real decisions will be smaller" (:316-317).
  - Learning at that timescale then failed:
    - loops a1 and a2 at 90 s: the final model against imitation scored -0.18 +- 0.30, "nothing"
      (SELF_PLAY.md:330-354);
    - e1 and e2's forced choices were undone in 85-94% of pairs (:485-489);
    - the commit model on 1,004 locked-arm pairs was "at chance" (CONTROL.md:284-286).
  - The script is deleted (SELF_PLAY.md:488; PROGRESS.md:669). The row's "Temporally extended options have strong
    learnable signal" should read "a whole-army choice moves outcomes more than chaos does; learning a scorer for it
    has not worked here yet".
- The selector's gain (losses 57 to 30 of 333) came from one scripted opponent and does not carry over.
  - PROGRESS.md:4078-4080: "Most of the gain is one matchup: Zerg v2's all-in on Fighting Spirit ... The table is
    fitted to this opponent pool".
  - That table is the one that picked style 4: two-Barracks gasless marines, 1.5% of pro games (manifests.py:1256-1257).
  - "Works cleanly" is the opposite of the repo's lesson.
- The repo has already tried a learned scorer over named symbolic facts, which is Provider A/B in miniature, and it
  gained nothing held out.
  - The early-defense switch was a 3-level tree over the posture's facts, trained on paired games
    (PROGRESS.md:3707-3720). It learned "always defend early" (false alarms in 285 of 287 games).
  - With the scout's facts added it gained "-0.013 a game ... within luck" (:3772-3781).
  - The plan policy over 19 named facts: an imitation copy of the posture rules (not outcome-learned) got "2 of 7
    held-out mode changes right: the rules change mode a few times a game, too few to learn their thresholds from"
    (gary/policy/plan.py:13-15, FACTS at :28-30). Mode transitions are data-starved.
  - These are the closest precedents for Solution 3's Branch Scorer, and the plan does not mention them.

Suggestion: rewrite the ledger with these rows. Make H1/H2 depend on a scorer that is not learned from outcomes
(F2).

### F2. Outcome-counted tables and bandits work against G1 and against "fidelity before wins"

Section: Solution 3 Providers A and C; §1 illustration ("pro win rate 54%, n=312"); §5.3.1. Read in source; the
literature parts are partly opened.

- **What the repo already learned.** The win-rate table, fitted to Gary's opponent pool, chose cheese (F1).
  AGENTS.md's "Fidelity before wins" exists because of the styleroll episode (AGENTS.md, the paragraph beginning
  "**Fidelity before wins.**").
  - Self-play counts are interventions only against Gary's own opponent. Gary-Z and gz1 are weak and exploitable
    (AGENTS.md: cheesy plans "are expected to win more against weak opponents like gz1 and Gary itself").
  - A table counted on Gary-vs-Gary outcomes will drift toward whatever beats Gary.
  - A table counted on pro replays is confounded, which ARCHITECTURE.md:513-517 already warns about.
- **The fix.** For a sparring partner whose goal is G1 (human-like play), the trunk's default should choose what pros
  choose: P(branch | belief, context) counted from pro replays, with shrinkage. Win-rate EV belongs to §6.8's
  `adaptive` mode only (ARCHITECTURE.md:518-524).
- **Coaching answers.** The learner-facing answer then becomes "pros facing this read go X in p% (n)". That is
  faithful and needs no causal claim. Win rates can be shown beside it, labelled as observational.
- **Literature.** Jacob et al. (2022) regularize search toward a human-imitation policy and become stronger while
  staying as human-predictive as imitation (opened, abstract). That is the workstation-scale way to add strength
  without leaving human-likeness. AlphaStar conditioned on a statistic *z* taken from human games to keep human
  strategies (DeepMind blog via search, not opened).

### F3. The diagnosis of RL failure (§2.1, §5.1) misreads Alshiekh et al. and the repo

Section: Executive Summary item 1 ("broke credit assignment and made reinforcement learning (RL) impossible"); §2.1;
Solution 1; Solution 4 Alternative 2 ("empirically failed across 10+ runs"). Read in source; the paper was opened as
full text.

- **What Alshiekh et al. actually say.** Their post-posed shielding is designed to keep learning working:
  - the executed action is updated with the environment's reward;
  - the agent's unsafe choice is updated too, with a punishment or with the reward;
  - their Section 7 argues that learners which converge on standard MDPs still converge with a shield attached
    (paraphrased from the fetched full text).

  The failure they guard against is a learner that is not told which action was executed. That is a logging
  problem, and Gary fixed it: "only executed decisions are logged" (PROGRESS.md:163-167). Since then the role runs
  have logged decisions "as carried out" (SELF_PLAY.md:355).
- **Gary's leases are closer to preemptive than post-posed.** With leases enforced, a lower-priority decision "leaves
  out the units a source of higher priority still holds" before it commands them (gary/agent/intents.py:54-60,
  priority at :27-30).
- **The repo gives other causes for the failed runs** (SELF_PLAY.md:467-499):
  - the pipe: one order a turn capped what could change;
  - forced choices undone;
  - batches too small for the minimum detectable effect (MDE);
  - a weak opponent.

  Apart from one PPO step on every layer at once in round r3 (PROGRESS.md:137-143), the runs trained one layer
  with the others frozen (PROGRESS.md:144-147). So "simultaneous end-to-end hierarchical RL across all tiers ...
  failed across 10+ runs" describes runs that were, with that one exception, not done.
- **The fight rules are still in gt1dev,** not only in the playing builds (AGENTS.md:241, "in gt1 and gt1dev"). The
  2026-11-17 order parked RL on the user's call (TODO.md:143-145), not because of the rules.
- **Solution 4's wrapped rules behave exactly like today's.** It wraps `PullRule`/`LoadRule` as option-scoped
  `bounded_rule_skill`. A PULL that preempts a RoleNet lease at an option boundary is the same as today's
  priority-3 lease with a 30 s TTL (intents.py:21). Renaming does not change credit assignment; logging the executed
  action does, and that is done.

Suggestion: drop "made RL impossible". State the real gate: SELF_PLAY.md's three prerequisites plus the user's park.

### F4. Most of Solutions 2, 3A, 5 and 6 is ARCHITECTURE.md's existing design; say so and reuse it

Section: Solutions 2, 3, 5, 6; §6.2 row "Narrator waits". Read in source.

| Plan element | Already in ARCHITECTURE.md |
|---|---|
| Counted tables with hierarchical shrinkage, belief-weighted EV and a printable trace | §6.8, lines 475-522 |
| Opponent model with ECE per minute and a symbolic Bayesian baseline | §7.5, lines 756-765 |
| ValueNet residual concept discovery with a multiple-comparison gate | §7.6, lines 767-790, almost word for word |
| Counterfactual consistency as a metric and by construction | §8, lines 873-876 |

- Calling this a "refocus" hides the useful fact that the design was right and was never built, and it invites
  rebuilding what exists.
- The plan dismisses `gary/policy/attribution.py` as out-of-distribution ablation (Solution 2, Alternative 1). §8
  (line 876) makes that same perturbation the *by-construction* faithfulness filter for the narrator. The
  objection fits correlated raw columns, not named concept inputs. Once the inputs are concepts (the belief, the
  plan), attribution.py's group-zeroing becomes the Solution 6 verifier at almost no cost.
- Two of §1's questions are already answerable and are not architectural failures: "Why didn't you stop my drop"
  (the plan says so itself) and "which alternatives lost" (the `top` lists in the records).
- The target answer "~42 drones" leans on a belief model that is off by 11.7 supply on Gary's games against 5.9 on
  pros (PROGRESS.md:38).

### F5. Solution 3's option terminations repeat stop-gaps already measured; learn them instead

Section: Solution 3 item 2, the examples "`REGROUP` ends when ≥80% squad gathered or 15 s elapsed" and "`DISENGAGE`
holds until ≥6 tiles clear". Read in source.

- **REGROUP is the `gather` option,** which was measured and not adopted. It waits for 75% of the army or 20 s. Its
  10-15 minute gap moved nearer the pros, but late arrivals only fell from 0.26 to 0.22, and it lost fewer games and
  won fewer (AGENTS.md:163-176).
- **DISENGAGE's 6 tiles are `retreatfar`'s click distance** (manifests.py:1375-1376, gt0.43dev). The hold is not
  built: "a retreat held for its stretch" is listed as left (TODO.md:31-32), and what still cuts retreats is "the
  turns after it" (PROGRESS.md:2408-2411). So the plan is right that a held disengage is missing. My point is only
  that its hold should be learned, not set by hand.
- **The repo already measured the pros' commitment hazard.** Reversal chances fall with a commitment's age, "10-16%
  per 5 s at first, 4-6% past 40 s", and Gary's commitments already have that shape (SELF_PLAY.md:489-493).
- **Hand-set thresholds would add stop-gaps that AGENTS.md would then have to track.** A persistent intent per
  cluster is worth adding, but its start, its hold and its end should be decoders fitted to the pros' hazards, as
  the mode models' are.
- **Literature for option labels and segments:**
  - Kipf et al. (2019) segment demonstrations into latent sub-tasks without labels (opened, abstract).
  - Le et al. (2018) mix imitation at one level of a hierarchy with RL at another (opened, abstract).

  Both are alternatives to the heuristic option labels the plan admits are noisy (Solution 4, "Option-label noise").

### F6. Solution 4 cites DAgger and HAC for things they do not provide; its leaf-RL pilot reopens a parked line

Section: Solution 4 Literature and Bilevel protocol; Phase 2 step 3; H3. Literature opened (abstracts).

- **DAgger needs an expert who labels the learner's own states.** Its loop builds a "dataset ... of visited states
  by πi and actions given by expert" (full text opened). Pro replays cannot be queried, so short rollouts do not make
  DAgger "tractable": there is still no one to label them. The only interactive expert is the user, which is
  §5.3.4's idea.
- **The quadratic bound is cited correctly enough.** The 2011 paper restates J(π) ≤ J(π*) + T²ε as Theorem 2.1 and
  credits it to Ross and Bagnell (2010) (full text opened). Citing the 2010 paper as well would be more exact.
- **HAC trains the levels concurrently, not in alternation.** Its abstract says the levels are learned "in parallel",
  each level trained as if the lower levels were already optimal (opened). It is evidence that concurrent training
  can be stabilised, not evidence for alternating freeze-and-train.
- **The leaf-RL pilot (Phase 2.3, H3) runs against the user's 2026-11-17 park,** "Reinforcement learning parked ...
  until the fight layer has an output for every job" (TODO.md:143-145). §6.2 should list that decision among those to
  reopen, or Phase 2 should drop the pilot.

### F7. Counterfactual risk minimization needs logged propensities: pro replays have none, Gary's records do

Section: Solution 3 (Swaminathan & Joachims "directly addressing ... confounding"); Provider C; Q4. The paper was
opened as full text; the source was read.

- **What the paper assumes.** CRM works from records (x, y, δ, p) whose propensity p was recorded by a stationary
  logging policy. The paper does not deal with unobserved confounding.
- **Pro replays have no propensities.** Using the macro model's odds as estimated propensities is possible. But the
  confounding §6.8 warns about (pros all-in "when they judge it favorable") comes from information that is not in
  the features. CRM does not remove that.
- **Gary's own games do log propensities.** gary/decision_log.py:99 and :105 write `p` and `top`. In
  runs/league/HS283a/Attitude SE 2.1/gt1dev_seed4004.records.jsonl, macro (line 5), commit (line 755) and roles (line
  1958) draws carry them. So off-policy evaluation of a scorer is feasible on Gary's league logs, where it is an
  intervention against Gary-Z, with F2's caveat. Say which data each estimator is for.

### F8. The CalmNet "proof" (§2.2.2) contradicts PROGRESS.md's own diagnosis

Section: §2.2 item 2. Read in source.

- **The numbers mix two rounds.**
  - The 1.43 short orders a minute are round CL281a's.
  - "units alone rose from 0.29 to 0.41" is CL282a's (PROGRESS.md:2228, 2266).
  - The log-loss 2.669 against uniform 2.773 is the direction head of the rebuilt model (:2218-2219). The bins'
    shares score 2.729.
- **The pros' own short-order directions are close to unpredictable from the obvious features** (cosines 0.00-0.19,
  :2198-2201). PROGRESS.md blames too little data and missing geography inputs (:2205-2210). Either way, my
  inference is that a near-uniform head here reflects what the pros' data teaches. It does not show "Brownian
  motion" caused by marginalising intent.
- **PROGRESS.md's diagnosis of the scattering:** "not where it sends units ... What differs is who gets them". Gary's
  calm orders went to a median 2 units 8.8 tiles from other fighters, the pros' to 7 units 2.2 tiles away
  (:2237-2241). The layer "doesn't make them alone" (:2268-2272).
- **The current direction acts on that diagnosis:** fuller selections and whole-cluster orders (manifests.py:1386-1392).
  Units alone did not move (PROGRESS.md:2160), so the cause is still open.

Suggestion: drop this as evidence for the sandwich. It is evidence that per-unit labels against per-command pro
orders matter (PROGRESS.md:2203-2205).

### F9. Stale or misquoted numbers in §1 and §2.2

Section: §1 G1/G3 rows; §2.2 items 1 and 3. Read in source.

- **G3 row: the Factory 59% and Starport 10% figures are gt0.18dev's** (manifests.py:1265; PROGRESS.md:1419-1423).
  At gt0.20dev (2026-10-27): style 1 had a Factory by 8:00 in 95% of games (pros 88%), style 2 a Starport in 81%
  (pros 69%) and its natural in 100% at 3.6 minutes (manifests.py:1273-1276; PROGRESS.md:1529-1531). Steering inside a
  style is much nearer the pros than G3's row says. What is missing is the replay-to-*z* compiler and the prompt.
- **"37–40% of retreats were cancelled by the next fight turn within 2 s" misquotes the source.** In the source, 37%
  is the next order being *another retreat* (its point moved), and 27-40% is a reposition, close-in or fire
  (PROGRESS.md:2410-2411).
- **G1 row: "AUC 0.99+" is the v0.29-era reading** (PROGRESS.md:108-112). Date it, or rerun eval/humanlike.py.
- **"Stateless per-tick classifiers" is too strong.** The models read history summaries as inputs:
  - the macro tracker keeps the most enemies seen and the decisions so far (gary/policy/macro.py:305-306);
  - the fight layer has `history_inputs` (gary/agent/fight.py:46);
  - the judge's models were sharpened with "the unit's recent past" (TODO.md:52-53), and the mine event model
    reads the judge's inputs (manifests.py:1333-1334).

  What they lack is a committed plan variable and sequence memory (#12). That is a narrower and cheaper target than
  a symbolic trunk.

### F10. The never-sieging tanks show the value of watching games, not of the sandwich

Section: §2.2 item 4. Read in source.

The cause was a configuration fault: the deployed TvZ checkpoint `rl1` had no siege, unsiege or mine role
(manifests.py:997-999, 1357-1359). It was fixed the same day by `tvzmodes` (manifests.py:1360-1362). This supports
§6.2's live-game rule, which I would adopt now in any case.

### F11. The §4.1 "ARCHIVE / PRUNE" list includes live modules

Section: §4.1 last row. Read in source.

- Module-level imports in live code: `gary/policy/fight.py` (`snapshot`, `FIGHT_AROUND`) in
  gary/agent/fight.py:43-44 and `fight_cmd.py` in fight.py:45. Pruning them breaks every build.
- Imports inside functions: fight.py in zerg_roles.py:110; `plan.py` in arbiter.py:247 and posture.py:402;
  `switch.py` in posture.py:248. I did not check whether an active manifest reaches these.
- `plan.py` and `switch.py` also hold the one precedent for a learned trunk over facts (F1). Archive them only after
  their results are carried into the plan's evidence.

### F12. §2.4's "single shared reader" is true for the macro path only

Section: §2.4; Phase 0 item 1; §4.1 row for `gary/policy/macro.py`. Read in source.

`ingest/macro_dataset.py` imports nothing from `gary` (lines 34-54), and `MacroTracker` rebuilds its features in play
(gary/policy/macro.py:293-300). But eleven other dataset builders do import `gary` (army, calm, cast, fight, hotkey,
placement, response, role, role_distill, stim, build_tiles). Phase 0 therefore covers the macro and critic features
only, and tests/test_inputs.py stays: a shared reader does not remove replay-versus-live differences (#50).

### F13. The kill criteria and the timeline are not falsifiable as written

Section: §6.1; §4.3. Read in source, partly inferred.

- **H2 cannot fire cleanly.**
  - Its threshold ("trails `gt1` by > 0.10 paired score") sits inside the 0.06-0.14 that 96 paired games resolve
    (AGENTS.md:60-61).
  - It joins two conditions with "AND feels worse in live games after option tuning". With 3 games and open-ended
    tuning, it will almost never fire.

  Write the MDE for each gate before the round, as AGENTS.md requires, and make each kill a single criterion.
- **H1's "user judges answers still unhelpful" over 3 games is not a measurement.** Anderson et al. (2019) found,
  with 124 participants, that only the combination of two explanation types improved mental models, and that it
  sometimes made prediction of the agent worse (seen in search results, not opened). Coaching utility needs a
  pre-registered task, such as predicting Gary's next decision before and after reading the answer, not an
  impression.
- **Phase 2's gate "closes won games cleanly without `--gg`" is ill-defined.** `--gg` makes the *losing* side resign
  (AGENTS.md:57). State it as "wins decided before 30:00 with `--gg 0`", against gt1's rate.
- **Phase 1's two weeks (an opponent model, StrategyState and the recipe card replacing `odds_mass`/`answers.py`, a
  verifier, 3 live games) is not credible against TODO.md:14-16** (one mode in two matchups took five days). I infer
  it would run several times over. Put the opponent model and the templates first: both are read-only and cannot
  change play.
- **H4's fallback ("calibrated hybrid ... continuous spatial features assist *where*") is already today's design:**
  the commit model decides, the role model places.

### F14. RTS-specific literature the plan omits

Section: §5.1 and every "Literature Grounding". The §5.1 table cites only Atari, tabletop robotics and AlphaStar.
Brood War has its own literature that bears directly on Solutions 2 and 3.

- **Synnaeve & Bessière (2011), two papers seen in search results, not opened.** The CIG paper predicts the
  opponent's opening with a Bayesian model learned from replays labelled with openings. The AIIDE paper predicts
  build trees learned from replays without supervision. Both are direct baselines for Solution 2 and for
  ARCHITECTURE.md §7.5's "symbolic Bayesian model" baseline, and are cheap to build on Gary's labels.
- **Synnaeve et al. (2018), the StarCraft defogger: recurrent encoder-decoders trained on Brood War games estimate
  hidden enemy units and feed a rule-based bot that wins more** (opened, abstract).
  It is the recurrent alternative to belief.py's per-moment regression (11.7 supply off on Gary's games, 5.9 on
  pros), and a precedent for neural perception feeding a symbolic consumer.
- **AlphaStar (Vinyals et al., 2019).** Its policy was conditioned on a latent that "encodes the distribution of
  opening moves from human games", and its imitation-learned initial policy played better than 84% of active players
  (both from DeepMind's blog, seen through search; the Nature page was not opened). ARCHITECTURE.md:83 describes *z*
  as build order plus cumulative unit counts.
  This is the cheap route to G3's "play the build from this replay": train the existing macro model with the
  replay's build-order prefix as *z* (ARCHITECTURE.md:82-85), with no recipe-card scheduler overriding the macro.
- **Mathieu et al. (2023), AlphaStar Unplugged: offline RL on human replays (offline actor-critic, MuZero) beat the
  AlphaStar behaviour-cloning agent 90% of the time** (opened, abstract). Gary's working pattern ("a large dataset,
  an offline objective, held-out validation, then games", SELF_PLAY.md:470-471) points to offline improvement from
  replays as the workstation-compatible route past imitation. That would serve Q5 better than bounded online leaf RL.
- **Sun et al. (2018), TStarBots: one agent learns by deep RL over a "flat action structure", the other uses
  "hard-coded rules over a hierarchical action structure"; both beat SC2's cheating built-in AI** (opened, abstract).
  The second is the nearest precedent for a hand-built hierarchy. It was judged on strength only, so it says nothing about human-likeness or steering.
- **For G4: McIlroy-Young et al. (2020), Maia, tunes human-move prediction to a rating band** (opened, abstract;
  separate models per band is recalled). G4 by imitation needs rated games: check whether the cwal packs carry
  ratings before Phase 4 promises "concept-noise/lapse rates" (not settled from the repo).
- **For per-tick incoherence: Zhao et al. (2023) predict action sequences ("action chunking") against compounding
  errors in imitation** (opened, abstract). A decision drawn as a short committed sequence, or with sequence memory
  (#12), is a cheaper experiment than a new trunk for the "marginal matching" complaint.

### F15. The "Verified References" (§7) claim more verification than holds

Section: §7 header "Every citation below was verified directly ... for exact authorship, venue, and supported
claims".

- **Supported claims that do not hold:** Alshiekh et al. 2018 (F3), Levy et al. 2019 (F6), Swaminathan & Joachims
  2015 (F7). Ross, Gordon & Bagnell 2011 is used for a DAgger step that has no expert to query (F6).
- **Havasi et al. 2022:** the abstract supports "insufficient concept set and inexpressive concept predictor" (opened).
  I could not confirm from the abstract that the paper "introduces Side-Channel CBMs". Check the body before naming
  the ablation provider after it.
- **Not checked in this run:** Kautz 2022, Ontiveros et al. 2025, Koh et al. 2020, Delfosse et al. 2023/2024, Marconato et al.
  2023, Nori et al. 2019, Silver et al. 2022, Liang et al. 2025, Ellis et al. 2021, Grand et al. 2024, Sutton et al.
  1999, Bacon et al. 2017. None of my findings leans on them.

### F16. Smaller points

- **§2.2 says gt1dev stacks "~30 options".** Read in source (manifests.py:1393-1396): 29 options are added on top of
  gt1's own 20 and its base v029 (:1224-1226). The point stands, larger than stated.
- **§6.2's TvZ-only scope reopens the user's 2026-11-12 decision** to judge "in every matchup, not ... in one
  matchup first" (TODO.md:10-11). It also reopens ARCHITECTURE.md §1's "every race" (line 40). If adopted, the shared
  fixes that came from other matchups should be named as what is lost, for example the stim model's race-keyed
  inputs (TODO.md:75-78). Inferred.
- **§2.2's "(last recorded on 2026-10-19)"** is right for human opponents (PROGRESS.md:269, 610); add the three live
  games against the computer on 2026-11-12 (PROGRESS.md:1968-1971).
- **Unverified marks and the §1 illustration.** A grep found no fact marked unverified in REFOCUS.md, so there is
  nothing of that kind to settle. The §1 illustration's specific odds (second Factory at 0.047 against Starport
  0.549; engage 0.32 against keep 0.42) come from match.records.jsonl, which is not in the repo. I could not trace
  them to any file. The record shape they assume does exist (`layer: style`, `by: roll` in HS283a's records).
- **Solution 2's Q1 ceiling test can run offline now** on held-out replays: style labels exist for 16,482 of 16,547
  TvZ Terran players (PROGRESS.md:1447-1449). Inferred.

## 3. External works relied on

Where a work was opened, it was the arXiv or proceedings abstract page unless noted.

| Work | Authors, year | URL | Status in this run |
|---|---|---|---|
| Safe Reinforcement Learning via Shielding | Alshiekh, Bloem, Ehlers, Könighofer, Niekum, Topcu, 2018 | https://arxiv.org/abs/1708.08611 (full text: https://ar5iv.labs.arxiv.org/html/1708.08611) | opened, full text |
| Learning Multi-Level Hierarchies with Hindsight | Levy, Konidaris, Platt, Saenko, 2019 | https://arxiv.org/abs/1712.00948 | opened |
| Batch Learning from Logged Bandit Feedback through Counterfactual Risk Minimization | Swaminathan, Joachims, 2015 | https://www.jmlr.org/papers/v16/swaminathan15a.html (full text: https://ar5iv.labs.arxiv.org/html/1502.02362) | opened, full text |
| A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning | Ross, Gordon, Bagnell, 2011 | https://arxiv.org/abs/1011.0686 (full text: https://ar5iv.labs.arxiv.org/html/1011.0686) | opened, full text |
| Efficient Reductions for Imitation Learning | Ross, Bagnell, 2010 | https://proceedings.mlr.press/v9/ross10a.html | search results only |
| Addressing Leakage in Concept Bottleneck Models | Havasi, Parbhoo, Doshi-Velez, 2022 | https://proceedings.neurips.cc/paper_files/paper/2022/hash/944ecf65a46feb578a43abfd5cddd960-Abstract-Conference.html | opened |
| A Bayesian Model for Opening Prediction in RTS Games with Application to StarCraft | Synnaeve, Bessière, 2011 | https://hal.archives-ouvertes.fr/hal-00607277 | search results only |
| A Bayesian Model for Plan Recognition in RTS Games Applied to StarCraft | Synnaeve, Bessière, 2011 | https://arxiv.org/abs/1111.3735 | search results only |
| Forward Modeling for Partial Observation Strategy Games - A StarCraft Defogger | Synnaeve, Lin, Gehring, Gant, Mella, Khalidov, Carion, Usunier, 2018 | https://arxiv.org/abs/1812.00054 | opened |
| Grandmaster level in StarCraft II using multi-agent reinforcement learning (and DeepMind's blog post) | Vinyals et al., 2019 | https://www.nature.com/articles/s41586-019-1724-z ; https://deepmind.google/discover/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/ | search results only |
| AlphaStar Unplugged: Large-Scale Offline Reinforcement Learning | Mathieu, Ozair, Srinivasan, Gulcehre, Zhang et al., 2023 | https://arxiv.org/abs/2308.03526 | opened |
| TStarBots: Defeating the Cheating Level Builtin AI in StarCraft II in the Full Game | Sun, Sun, Han, Xiong, Wang, Li, Zheng, Liu, Liu, Liu, Zhang, 2018 | https://arxiv.org/abs/1809.07193 | opened |
| Modeling Strong and Human-Like Gameplay with KL-Regularized Search | Jacob, Wu, Farina, Lerer, Hu, Bakhtin, Andreas, Brown, 2022 | https://arxiv.org/abs/2112.07544 | opened |
| Aligning Superhuman AI with Human Behavior: Chess as a Model System (Maia) | McIlroy-Young, Sen, Kleinberg, Anderson, 2020 | https://arxiv.org/abs/2006.01855 | opened (per-band models recalled) |
| Hierarchical Imitation and Reinforcement Learning | Le, Jiang, Agarwal, Dudík, Yue, Daumé III, 2018 | https://arxiv.org/abs/1803.00590 | opened |
| CompILE: Compositional Imitation Learning and Execution | Kipf, Li, Dai, Zambaldi, Sanchez-Gonzalez, Grefenstette, Kohli, Battaglia, 2019 | https://arxiv.org/abs/1812.01483 | opened |
| Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware (ACT) | Zhao, Kumar, Levine, Finn, 2023 | https://arxiv.org/abs/2304.13705 | opened |
| Explaining Reinforcement Learning to Mere Mortals: An Empirical Study | Anderson et al., 2019 | https://arxiv.org/abs/1903.09708 | search results only |