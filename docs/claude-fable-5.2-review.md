Round one, 2026-11-22

Reviewer: Claude Fable 5.2. Web search and page fetch were available in this run and were used; the table at the end
says, for each work, whether it was opened here (abstract page or full text), seen only in a search result, or
recalled. Nothing was built or run; the source was read, and one league record file was searched as text.
"Read" below means I read the cited lines in this run; "inferred" means I concluded it from them. Words quoted
from a paper are as the fetch tool returned them from the page, so check them against the paper before reuse.

## 1. Is a major refocus necessary?

**Short answer.** A change of priorities is necessary. The major architectural refocus as written (a new build line,
calm and commit retired for hand-specified squad options, a strict concept bottleneck) is not shown necessary by the
repo, and several of the measurements the plan uses to argue "major" do not say what the plan says they say
(findings 1, 2, 3, 7, 8). The two halves:

**What the current direction cannot reach, however long it runs.**
- TODO.md's "Direction" (TODO.md:7-145, read) is entirely G1 fidelity work: the judge per situation, the pipe table,
  abilities, positioning, finishing. Nothing in steps a-f or 1-7 builds G3 beyond a style id, G4 or G5. The items that
  would are in the index, unstarted: #40 opponent model (TODO.md:193), #45 the macro answering the scout
  (TODO.md:195), #12 macro with history (TODO.md:191), #26 strategy layer (TODO.md:205), #41 narrator (TODO.md:252),
  #15 profiles (TODO.md:251). More bug fixing and training does not start any of them.
- The plan's central point holds in source: an explanation can only cite what the deciding layer held. The records
  hold a style by a roll and decisions by dice (the first style record of
  `runs/league/HS284a/Attitude SE 2.1/gt1dev_seed4004.records.jsonl` is `"layer": "style", "choice": 1, "by": "roll"`;
  534 of that game's records are `"by": "dice"`; read as text). No narrator on those records can say more than
  "a die came up" for a strategic choice. Matching every marginal to the pros does not change that.
- Inside G1, three jobs have no imitation answer by the repo's own reading: finishing (the pros resign, so the data
  lacks the states: PROGRESS.md:2322-2325), answering what was scouted without the scripted answers (never measured
  off: AGENTS.md:218, TODO.md:195), and one variable shared between layers. The per-situation work is also unbounded:
  one mode in two matchups took five days and "moved no top-level measure" (TODO.md:14-16), and its table is
  abilities by matchups (TODO.md:56-61).

**What the repo does not show: that the layered imitation stack has to be replaced.**
- The week's review found most faults "in the pipe between a model's odds and what Gary carried out" (TODO.md:15-16).
  Those are hands and decoder faults below any trunk, and the plan keeps those layers (REFOCUS.md:321, 324), so they
  recur under `gt_ns` unchanged.
- Fixes in the present stack move their own measures severalfold: tanks sieged 0% to 58% (TODO.md:66-69), the commit
  layer's orders to the pros' size (PROGRESS.md:2155-2157).
- gt1dev's deficit to gt1 is accounted for in PROGRESS.md by the stop-gaps taken out and by games not ended, not by
  incoherence between models (finding 3).
- Everything in the plan that serves G3 and G5 (an opponent belief, counted tables with n and intervals, plan
  switches logged with evidence, a narrator on records, residual feature discovery, counterfactual consistency) is
  already the design: ARCHITECTURE.md:475-524 (§6.8), :756-765 (§7.5), :767-789 (§7.6), :842-876 (§8), and
  CONTROL.md:233-235 lists them as "the pieces the architecture lists" still to come. They were deferred, not ruled
  out, and they are additive to gt1dev: a belief that is logged, a richer plan input to the macro model, new record
  kinds, templates. None needs the stack inverted first.

**So.** Do the plan's Phase 1 in its log-only form now, as options on gt1dev (AGENTS.md:56: a change is an option),
and decide Phase 2 after it. What would justify "major" is a measurement the plan does not yet have: the log-only
card showing that most off-plan decisions are low-odds draws (not money, a busy building or the hands), and that a
held plan or a held commitment, tried as a decoder in 16 games, does not remove them. Neither path today measures the
exit criteria the architecture already wrote for these goals (build timings in 18 of 20 unharassed runs,
ARCHITECTURE.md:1057; blind sessions, ARCHITECTURE.md:1001-1003); adopting those is the first refocus.

## 2. Findings, most important first

### F1. The evidence for learning at the option timescale is an effect size, and its follow-up is at chance
- Document: §2.3 table (REFOCUS.md:88-89), Solution 3 provider C (REFOCUS.md:216), strengths (REFOCUS.md:226), H3's
  fallback (REFOCUS.md:453).
- Source, read: `eval/army_effect.py` no longer exists (deleted in the refactor: PROGRESS.md:668-669;
  SELF_PLAY.md:488 "since deleted"; eval/pairs.py:44). What it measured (SELF_PLAY.md:308-311; PROGRESS.md:172-175):
  the whole army forced to attack or hold with its army layer frozen for 90 s, 77 moments, the spread of the effect
  three times the chaos, "attacking better at 40%". That is a statement that the choice matters, not that anything
  learned which choice is better.
- The designed follow-up is the row above it in the same table. The commit pairs were built on exactly that lesson:
  the forced arm locked at the pros' hazard, half reversed by 35-55 s (SELF_PLAY.md:489-493, 507-514), not a "5 s
  grid draw" as REFOCUS.md:88 labels its timescale. On 1,004 pairs it is at chance (held-out 0.46), engaging "wins
  only 49%" of pairs (SELF_PLAY.md:512-514), and the critic "found no state where engaging pays that the deployed
  commit model doesn't already prefer" (CONTROL.md:293-294). The repo's own reading is about power, not
  impossibility: "Under the MDE ... nothing state-dependent is learnable yet" (PROGRESS.md:1155-1156).
- Consequence (inferred): the table's headline, "Temporally extended options have strong learnable signal", is
  contradicted by its own third row. Provider C and "Trunk training ... paired option branches" (REFOCUS.md:246) have
  no positive result at this compute, and H3's fallback ("workstation RL stays at Tier 2") assumes one.
- Suggest: give trunk learning its own hypothesis with a written minimum detectable effect and a kill line, or say
  that the V1 trunk is supervised and counted only. Correct the table's two rows.

### F2. Outcome tables against a weak opponent already taught Gary a cheese; the plan brings them back
- Document: §2.3 selector row, "Strategic-level outcome learning works cleanly" (REFOCUS.md:90); provider A "Counted
  Pro & Self-Play Tables" (REFOCUS.md:214); the Phase 2 gate against gt1 (REFOCUS.md:391).
- Source, read: the selector's table was counted from games against scripted Zergs (gary/agent/selector.py:5-9; the
  tool that made them is deleted, PROGRESS.md:668-669). It is the table that picked style 4, 1.5% of pro Terran games
  (AGENTS.md:79-84), and PROGRESS.md:3000-3001 describes gt1dev as gt1 "plus the pros' styles in place of the
  selector's cheese". REFOCUS.md:74 says the same of it two sections earlier.
- Consequence (inferred): "losses 57 to 30" is the failure the rule "fidelity before wins" exists for, not a success
  to scale. A win-rate scorer fed by self-play against gz1 will find the same exploits, at every branch.
- Suggest: make the V1 scorer the pros' choice frequencies given the belief and context, P(branch | concepts), with n.
  The plan's own sighting-to-response example is of that kind ("pros build a turret within 60 s in p% (n)",
  REFOCUS.md:379) and it explains better to a learner than a win rate. Keep win rate as a second column, printed,
  not decided on, until interventions against a non-exploitable opponent exist.

### F3. The −0.188 is attributed to an army "tug-of-war" that did not exist when it was measured
- Document: §2.2 item 3 (REFOCUS.md:76); the Phase 2 gate and H2 (REFOCUS.md:391, 452).
- Source, read: the figure is the standing of 2026-11-11 (PROGRESS.md:2976-2977). The mode model came on 2026-11-13
  (TODO.md:119-121) and the calm layer on 2026-11-19 (gary/agent/manifests.py:1383-1385), so two of the four
  systems the item names postdate it. It is the standing after a macro leak was fixed (−0.307 before), and
  PROGRESS.md's account of what is left is "the stop-gaps measured one at a time, and games the dev build leads and
  doesn't end" (PROGRESS.md:2976-2979), with the bank escape off −0.203, the caps off −0.109, the static guard off
  −0.062, the SCV cap off −0.047, "together more than the whole gap" (PROGRESS.md:2998-3000). TODO.md:43-44 already
  asks for it to be measured again.
- Consequence (inferred): the largest measured helpers are macro decoders and a finishing rule, not leaf overrides
  on leased units. `gt_ns` drops them too ("without conflicting side-overrides like `bank_escape` or `caps`",
  REFOCUS.md:241), and its gate (REFOCUS.md:391: "matches or beats" gt1, or "falls within pre-written MDE") is close
  to the promotion rule's second condition, not measurably worse (AGENTS.md:45-50). gt1dev fails that condition
  today with the same stop-gaps off, after a month of work on it; the plan gives `gt_ns` two to three weeks. The gate
  also leaves out the rule's first condition, fidelity per window, and puts "human live-game feel" in its place.
- Suggest: a table in the plan with one row per AGENTS.md stop-gap entry: its job, which `gt_ns` component owns it,
  and that entry's own measure. `CLEAR_FINISH` is the hunt renamed until something learns it (AGENTS.md:138).

### F4. The squad options are scripted rules, and their two worked examples were already tried
- Document: Solution 3 item 2 (REFOCUS.md:203-209); §6.2's three-way split (REFOCUS.md:461).
- Source, read: `REGROUP` "ends when ≥80% squad gathered or 15 s elapsed" (REFOCUS.md:208) is the `gather` stop-gap:
  75% or 20 s (AGENTS.md:163-171; gary/agent/army.py:78, 696-702). Measured over 96 paired games: won 47 for 54,
  late arrivals 0.26 to 0.22 "only", not adopted. `DISENGAGE` "holds until ≥6 tiles clear" (REFOCUS.md:208) is
  `retreatfar`, 6 tiles past the group, folded in on 2026-11-18 (gary/agent/manifests.py:1375-1376); what is left of
  it is "a retreat held for its stretch" (TODO.md:31-32), a decoder hold, which AGENTS.md:130-131 does not count as a
  stop-gap. Neither needs a trunk.
- Initiation, termination and preemption predicates written by hand are decisions scripted, which is what
  CONTROL.md:218-220 records as having failed ("Rules tuned one failure at a time traded one loss for another").
  Calling them "core architecture" in §6.2 changes the label, not the tuning loop. The architecture's intended route
  for the same vocabulary is labels and a learned head (ARCHITECTURE.md:353-362; the `intent_label` slot, :433).
- Literature: segments can be found in demonstrations without supervision (Kipf et al., CompILE, opened), and
  macro-actions were mined from expert trajectories for a two-level StarCraft II agent on one machine (Pang et al.,
  opened, abstract: 48 CPU cores and 8 GPUs, a 64x64 map, restricted units, against the built-in AI).
- Suggest: before retiring commit, label the pros' army commands with intents (a gold set of a few hundred windows,
  ARCHITECTURE.md:417-424), report agreement, and measure how well the intent is predicted from the fogged view.
  Terminations from the pros' measured hazards (SELF_PLAY.md:489-491), not thresholds. The plan lists option-label
  noise as a risk (REFOCUS.md:256); it is the first thing to measure, since everything in Tier 3 conditions on it.

### F5. The faithfulness test is near-trivial, and it does not test what the repo found broken
- Document: Solution 6 (REFOCUS.md:298), Phase 1 item 3 (REFOCUS.md:380), H1's kill line "Counterfactual consistency
  < 80%" (REFOCUS.md:451).
- Inferred: a deterministic scorer over named concepts changes its branch when a decisive concept is flipped, and a
  template can be made to cite only concepts whose flip changes the branch; ARCHITECTURE.md:876 designs exactly that
  ("counterfactual consistency by construction, not only as a metric"). It can come in under 100% only where a
  template cites a large but non-decisive contribution, so the 80% line tests the templates' wording and kills
  nothing about the architecture. The test is silent on the two places an explanation can be false: whether the
  concept was true of the game, and whether the branch changed what Gary did. The second is where the week's faults
  were (TODO.md:15-16, 20-28).
- Suggest three separate numbers: (a) each cited belief against the ground truth after the game
  (ARCHITECTURE.md:853), against the base rate; (b) flip the concept, branch both arms with eval/pairs.py, and compare
  what was built and ordered in the next minutes, not the trunk's output; (c) a reader's test: from the answer alone,
  can a person or a model predict Gary's next branch at a held-out moment better than from today's records.

### F6. The worked example contradicts itself, and the tables' cells are small
- Document: the illustration table (REFOCUS.md:51-54); provider A (REFOCUS.md:214); strengths (REFOCUS.md:181).
- Inferred from the document: row 2 explains a decision "at 3:31" with a sighting "at 4:40" (REFOCUS.md:52). Row 1
  offers "54%, n=312" against "47%, n=98" as the reason for an opening: the difference is 0.07 with a standard error
  near 0.058, so the target answer narrates noise, and of the confounded kind §6.8 warns about (ARCHITECTURE.md:513).
  The record behind row 2 cannot be checked: its file is not in the repo.
- Source, read (a local data file that git ignores, .gitignore:5; `shares` and `modern_games` of
  `data/interim/taxonomy/v2/TvZ_Z.json`, line 1): 2,683 modern TvZ games carry a Zerg plan label; one plan is 59% of
  them, the four spire-first plans 91%, the four lurker-first plans 5.6% (about 150 games), hydralisks and zergling
  pressure 0.2% each. "19k+ modern re-simulated games" (REFOCUS.md:181) is every matchup together
  (PROGRESS.md:32: 18.9k, about 3,000 a matchup).
- Consequence (inferred): a cell of (enemy plan, own style, map) holds tens of games for the commonest plan and
  single digits for a lurker opening. A belief of "76% on 3-Hatch Lurker" is a claim about a 5% class, calibrated
  mostly on old-era games (17% lurker-first over both eras, same file), with the era shift docs/DATA_ERAS.md is
  about.
- Suggest: write the n budget per table before Phase 1; report the belief per minute against the base rate and
  against a Bayesian model on scouted facts (ARCHITECTURE.md:763 asks for that baseline; Synnaeve and Bessière
  built one for Brood War build trees from replays, abstract opened); mark the example numbers as invented.

### F7. "Leaf stop-gaps killed RL" overstates the record, and the shielding paper claims convergence is kept
- Document: summary item 1 "made reinforcement learning (RL) impossible" (REFOCUS.md:14); §2.1 (REFOCUS.md:67);
  "Empirically proven in Gary to kill NN credit assignment and block RL" (REFOCUS.md:160); "empirically failed
  across 10+ runs" of simultaneous hierarchical RL (REFOCUS.md:260); "rightly stripped out leaf stop-gaps"
  (REFOCUS.md:72).
- Source, read: SELF_PLAY.md:467-493 gives the causes of the failed runs. One is the plan's (hand rules in contact
  left the roles model out of most fight commands, :479-480). The others are not: one order a half-second turn capped
  what a shifted logit could move (:476-478, the hands); a forced choice was undone by the same policy in 85-94% of
  pairs (:485-487); a single macro decision is worth sd 130 against chaos of 512 (CONTROL.md:274-283). The commit
  pairs were played by gt1dev (PROGRESS.md:1143-1144, 1149-1150), which had run without the army's and the macro's
  stop-gaps since the day before (gt0.10dev, 2026-10-23: PROGRESS.md:1073), and are at chance (F1). No run trained
  two levels at once: the
  count is five role runs, two army runs and the league loop, each one layer (SELF_PLAY.md:467-468).
- The dev builds still run the five fight rules at priority 3 (AGENTS.md:241; gary/agent/fight.py:405, 490, 548,
  605, 821; gary/agent/intents.py:27-30). `unscripted` turns off the army's and the macro's stop-gaps only
  (gary/agent/manifests.py:1087-1096), and no option in gt1dev's chain (manifests.py:1393-1396) turns `answers` off,
  so by the manifest it stays on against a Zerg (inferred; not traced through manifests.py:1772, and the one
  dev-build record file I searched has no decision recorded as made by it).
- Literature, opened (Alshiekh et al., full text): the paper names the two placements as the plan says, but its
  claim is "all learning algorithms that converge on standard MDPs can be shown to converge in the presence of a
  shield", and "The learning agent does not even need to know that it is shielded"; for the post-posed case it
  offers two ways to credit the overridden action. It does not say post-posed overrides break credit assignment.
  Gary's finding (a logit push that moves no command gives no gradient) is the repo's own and stands without it.
- Suggest: state the measured causes in §2.1, keep the pipe check as the argument, drop the claim on Alshiekh.

### F8. The calm layer does not show what §2.2 item 2 says it shows
- Document: "the `CalmNet` proof" (REFOCUS.md:75).
- Source, read: the rise the plan cites is real, resolved and the calm layer's: units alone 0.29 to 0.38 and 0.41
  per game window, 0.171 to 0.228 per fighter sample, and PROGRESS.md first read it as "it scatters them"
  (PROGRESS.md:2232-2235, 2266-2269). What the later reads change is the mechanism. It is "not where it sends units"
  but "who gets them": Gary's calm orders went to a median 2 units far from the army, the pros' to 7
  (PROGRESS.md:2237-2243); "the layer doesn't make them alone", 89% of its one-unit orders went to units alone
  already, and what it changes is where the lone units stand (PROGRESS.md:2268-2273); by last order, the
  calm layer accounts for 0.06 of lone samples beside the commit layer's 0.05 and never-ordered 0.05
  (PROGRESS.md:2099-2102); new units are alone at the rally before any calm order (PROGRESS.md:2105-2107). The first
  negative result rested on labels per unit where a pro's order is one command for about 10 units
  (PROGRESS.md:2202-2206). The fair baseline for the direction head is the bins' shares (2.729), not uniform (2.773);
  rebuilt per command it reaches 2.669 (PROGRESS.md:2217-2219).
- Consequence (inferred): the cost is real, and the evidence is that the unit of decision should be the command
  to a group, which does support group-level decisions. It is not a proof that matching marginals yields
  "Brownian motion": the direction was not what scattered the units.
- Literature, opened (Zhao et al., abstract): predicting a sequence of actions at once ("a generative model over
  action sequences") is the imitation-learning answer to compounding per-step error. The repo's analogue is a command
  with its group and its hold, and it needs no hand-written option vocabulary.

### F9. The gates: one is near-trivial, one swaps the fidelity condition for feel, three live games decide two phases
- Document: Phase 1 and 2 gates (REFOCUS.md:381, 391); §6.1 (REFOCUS.md:451-454); the timeline (REFOCUS.md:372-393).
- H1's consistency line is near-trivial (F5). H2's kill needs both "> 0.10 paired score" and "feels worse", so a
  build 0.2 behind that the author likes survives; H4's 0.12 is inside what 96 games resolve (0.06 to 0.14,
  AGENTS.md:60-62, read). The Phase 2 gate keeps the promotion rule's second condition and drops its first, the
  fidelity measures per window (AGENTS.md:45-50), for live feel (F3).
- Three live games judged by the plan's owner, unblinded, with no comparison answers, decide Phases 1 and 2. The
  architecture's human evaluation is blind sessions (ARCHITECTURE.md:1001-1003).
- Seven to eight weeks for Phases 0-3 sits beside five days for one mode in two matchups (TODO.md:14-16), inferred as
  optimistic severalfold.
- Suggest: written before each phase, as the repo does for rounds: card adherence per card with
  eval/style_adherence.py; the belief's Brier score against the base rate; the share of macro decisions made by a
  draw under 10% odds; the Q&As judged blind against answers built from today's records, by someone else.

### F10. Three papers are cited for what they do not say; "Verified References" needs a per-entry note
- Document: Solution 4 grounding (REFOCUS.md:249, 251), Solution 3 grounding (REFOCUS.md:222-223), §7 (REFOCUS.md:481).
- Levy et al., opened (abstract): the method learns the levels "in parallel", each trained "independently of the
  lower levels" as if those were already optimal. It is an argument for hindsight relabelling, not for
  "bilevel/alternating training" with frozen tiers. Freezing a tier is a defensible engineering choice; this paper is not its
  source. The same instability also applies to the plan: leaves imitated under a hand-written trunk are retrained
  each time the trunk's options change.
- Ross et al., opened (abstract only): the abstract names neither DAgger's expert queries nor a quadratic bound.
  Recalled, not opened: DAgger asks an expert to label the states the learner visits, and the quadratic bound is
  from Ross and Bagnell (2010). No pro can be queried on Gary's states, so "`DAgger`-style filtered imitation"
  (REFOCUS.md:453) is filtered self-imitation; SELF_PLAY.md:499-502 already names the fitting method
  (advantage-weighted regression anchored to the imitation policy).
- Swaminathan and Joachims, opened (abstract): the method works "through propensity scoring". Recalled: it assumes
  the logging policy's propensities are known. Replays log none; they would be estimated, in effect by the imitation
  models' own odds, and the confounders that matter here (the better player, what the pro had read) are unobserved.
  It does not "directly" address ARCHITECTURE.md:513; self-play interventions do (ARCHITECTURE.md:510).
- Nori et al., opened (abstract): InterpretML "includes the first implementation of the Explainable Boosting
  Machine". GA2M is Lou, Caruana, Gehrke and Hooker, 2013 (search result only).
- Reference 16's first author is Castellano Ontiveros (opened). Reference 22's author list is not the paper's
  (recalled: Vinyals, Babuschkin, Czarnecki, Mathieu and others; the Nature page appeared in search, not opened).

### F11. Better or cheaper routes in the literature, by goal
- **G3 by conditioning (the plan's `opening_card` is AlphaStar's z).** AlphaStar's policy "is also conditioned on a
  statistic z that summarizes a strategy sampled from human data (for example, a build order)" (the Nature page as
  quoted in a search result; ARCHITECTURE.md:82-84 records the same). The plan cites AlphaStar only as the contrast
  (REFOCUS.md:158). The route it implies is one change to the present stack: the macro model conditioned on one
  replay's card (its first N items with times, cumulative counts) in place of a style id, judged per card by
  eval/style_adherence.py, with a symbolic layer that only switches cards and logs why (ARCHITECTURE.md:372). That
  is testable in days and tells whether a "Plan-conditioned MacroNet" (REFOCUS.md:129) holds a plan at all.
- **A learned strategy switch in Brood War exists.** Gehring et al. (opened, abstract): a rule-based bot learns the
  value of switching among its fixed build orders from games against bots, with the full state as an auxiliary
  target in training; large gains over a fixed strategy. Tournament bots pick openings per opponent with UCB-1
  (CherryPi's 2017 survey, search result only). This supports a small learned scorer over a few branches at modest
  compute, from interventions, not from replay win rates; its reward was wins against bots, so F2 applies.
- **The opponent model has direct precedents the plan does not cite.** Synnaeve and Bessière (2011, opened,
  abstract): a Bayesian model that predicts a player's build tree from noisy observations, its parameters learned
  from replays; their paper on openings of the same year, from replays labelled with openings, I saw in a search
  result only. Synnaeve et al. (2018, opened, abstract): hidden and future state predicted from partial views of
  human Brood War games, raising a rule-based bot's win rate against strong bots. Tier 1 is the lowest-risk part of
  the plan; it should cite and beat these.
- **Improving on imitation offline.** Mathieu et al. (opened, abstract): on human StarCraft II data, offline
  actor-critic and MuZero variants reach a "90% win rate against previously published AlphaStar behavior cloning
  agent", at large scale; that behaviour value estimation with one step of policy improvement worked best is from
  its 2021 workshop version, seen in a search result only. That is the recipe of SELF_PLAY.md:499-502, not
  counterfactual risk minimization; the repo's one test of it found nothing to improve (CONTROL.md:293-294).
- **G4.** McIlroy-Young et al. (opened, abstract): models trained on human games reach "maximum accuracy when
  predicting decisions made by players at a specific skill level in a tuneable way", and existing engines "do not
  predict human moves well". Phase 4's "concept-noise/lapse rates" (REFOCUS.md:399) is noise on a pro model; the
  evidence is for data from the band. Whether the inventory has rated lower-band replays I did not check.
- **G5.** Schut et al. (opened, abstract): concepts taken from AlphaZero were shown to four grandmasters, who
  improved on the concept positions: the test of an explanation there is that the person plays better. Rubric item
  1 asks this (REFOCUS.md:470) and no gate measures it. Penney et al. (opened, abstract): experienced StarCraft
  players assessing an agent missed events that mattered to them and bore high costs to find information, so the
  answers should open at their moment in the POV viewer, not as text alone.

### F12. Smaller facts settled in source
- REFOCUS.md:87 has it backwards: `rl1` is the model "whose roles had no siege, unsiege or mine"; the relabelled
  imitation model that replaced it has them (gary/agent/manifests.py:997-999, 1357-1362, read).
- REFOCUS.md:336 lists `gary/policy/fight_cmd.py`, `fight.py`, `switch.py` and `plan.py` as dead. They are imported
  by code the current builds run: gary/agent/fight.py:43-45, gary/policy/calm.py:92, gary/agent/posture.py:248 and
  :402, gary/agent/arbiter.py:247, gary/agent/manifests.py:461 and :540 (read). `plan.py` is the learned posture of
  CONTROL.md step 7 (gary/policy/plan.py:1-15).
- REFOCUS.md:95, "`ingest/macro_dataset.py` imports nothing from `gary/`": true (ingest/macro_dataset.py:34-54,
  read). Eleven other files in `ingest/` import from `gary`; the four I opened take their feature code from
  `gary/policy` (ingest/calm_dataset.py:29-30 and :61-64, ingest/response_dataset.py:41, ingest/stim_dataset.py:23,
  ingest/army_dataset.py:104-117). So the duplication named is the macro's, and Phase 0's "unify" is that builder
  plus the trackers tests/test_inputs.py holds.
- REFOCUS.md:95, "46 scripts in `eval/`": 46 `.py` files counting `__init__.py` (directory listing).
- REFOCUS.md:66, the lease priorities: as stated (gary/agent/intents.py:27-30, read).
- REFOCUS.md:461, the row saying AGENTS.md treats every symbolic rule as stop-gap debt: AGENTS.md:124-131 already
  asks whether a rule "should stay a rule" and excludes hands, decoders and bug fixes. What the plan adds is its
  class (2).
- The document marks no fact as unverified (searched for the word and its variants), so there was none of that kind
  to settle; what the source could settle is in this list and in F1, F3, F7 and F8.
- REFOCUS.md:15, "no symbolic strategic or tactical trunk" in the dev builds: see F7 on `answers`; the tech-path
  floor that stops low-odds tech draws exists as a decoder for the Zerg only (gary/agent/macro.py:49-53, 429-431),
  so the Terran's "4.7% second Factory" class (REFOCUS.md:52, 74) has a race-keyed fix inside the present stack.
- REFOCUS.md:464 adds `gt_ns` as a third build line per race while §2.4 counts two lines as a cost (REFOCUS.md:95).
- REFOCUS.md:172 and Rudin's argument go past the stated goal: "Full transparency of the neural policy" is a
  non-goal, "not a white box" (ARCHITECTURE.md:64). The strict bottleneck should be argued from G5 as written
  (ARCHITECTURE.md:57), where it is needed only for decisions of record.
- REFOCUS.md:77, the checkpoint of about 25 changes and the last human game on 2026-10-19: as stated
  (PROGRESS.md:1796-1799); three watched games against the computer followed on 2026-11-12 (PROGRESS.md:1968-1971).

## 3. Works used

| Work | Authors, year | URL | In this run |
|---|---|---|---|
| Safe Reinforcement Learning via Shielding | Alshiekh, Bloem, Ehlers, Könighofer, Niekum, Topcu, 2018 | https://arxiv.org/abs/1708.08611 | Opened (abstract; full text at ar5iv) |
| Learning Multi-Level Hierarchies with Hindsight | Levy, Konidaris, Platt, Saenko, 2019 | https://arxiv.org/abs/1712.00948 | Opened (abstract) |
| A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning | Ross, Gordon, Bagnell, 2011 | https://arxiv.org/abs/1011.0686 | Opened (abstract); expert queries and the 2010 bound recalled |
| Counterfactual Risk Minimization: Learning from Logged Bandit Feedback | Swaminathan, Joachims, 2015 | https://arxiv.org/abs/1502.02362 | Opened (abstract); known propensities recalled |
| InterpretML: A Unified Framework for Machine Learning Interpretability | Nori, Jenkins, Koch, Caruana, 2019 | https://arxiv.org/abs/1909.09223 | Opened (abstract) |
| Accurate Intelligible Models with Pairwise Interactions | Lou, Caruana, Gehrke, Hooker, 2013 | https://www.microsoft.com/en-us/research/publication/accurate-intelligible-models-pairwise-interactions/ | Search result only |
| Grounding Methods for Neural-Symbolic AI | Castellano Ontiveros, Giannini, Gori, Marra, Diligenti, 2025 | https://arxiv.org/abs/2507.08216 | Opened (abstract); used for the author's name only |
| Grandmaster level in StarCraft II using multi-agent reinforcement learning | Vinyals, Babuschkin, Czarnecki, Mathieu, Dudzik, Chung, Choi, Powell, Ewalds, Georgiev and some thirty more, Silver last, 2019 | https://www.nature.com/articles/s41586-019-1724-z | Search result quoting the page; author list recalled |
| High-Level Strategy Selection under Partial Observability in StarCraft: Brood War | Gehring, Ju, Mella, Gant, Usunier, Synnaeve, 2018 | https://arxiv.org/abs/1811.08568 | Opened (abstract) |
| CherryPi, AIIDE 2017 competition survey | the bot's authors, 2017 | https://www.cs.mun.ca/~dchurchill/starcraftaicomp/2017/survey/CherryPi_Survey.txt | Search result only |
| A Bayesian Model for Plan Recognition in RTS Games applied to StarCraft | Synnaeve, Bessière, 2011 | https://arxiv.org/abs/1111.3735 | Opened (abstract) |
| A Bayesian Model for Opening Prediction in RTS Games with Application to StarCraft | Synnaeve, Bessière, 2011 | https://hal.archives-ouvertes.fr/hal-00607277 | Search result only |
| Forward Modeling for Partial Observation Strategy Games - A StarCraft Defogger | Synnaeve, Lin, Gehring, Gant, Mella, Khalidov, Carion, Usunier, 2018 | https://arxiv.org/abs/1812.00054 | Opened (abstract) |
| AlphaStar Unplugged: Large-Scale Offline Reinforcement Learning | Mathieu, Ozair, Srinivasan, Gulcehre, Zhang, Jiang, Le Paine, Powell, Żołna, Schrittwieser, Choi, Georgiev, Toyama, Huang, Ring, Babuschkin, Ewalds, Bordbar, Henderson, Gómez Colmenarejo, van den Oord, Czarnecki, de Freitas, Vinyals, 2023 | https://arxiv.org/abs/2308.03526 | Opened (abstract); the workshop version's finding from a search result |
| On Reinforcement Learning for Full-length Game of StarCraft | Pang, Liu, Meng, Zhang, Yu, Lu, 2019 | https://arxiv.org/abs/1809.09095 | Opened (abstract) |
| CompILE: Compositional Imitation Learning and Execution | Kipf, Li, Dai, Zambaldi, Sanchez-Gonzalez, Grefenstette, Kohli, Battaglia, 2019 | https://arxiv.org/abs/1812.01483 | Opened (abstract) |
| Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware | Zhao, Kumar, Levine, Finn, 2023 | https://arxiv.org/abs/2304.13705 | Opened (abstract) |
| Aligning Superhuman AI with Human Behavior: Chess as a Model System | McIlroy-Young, Sen, Kleinberg, Anderson, 2020 | https://arxiv.org/abs/2006.01855 | Opened (abstract) |
| Bridging the Human-AI Knowledge Gap: Concept Discovery and Transfer in AlphaZero | Schut, Tomasev, McGrath, Hassabis, Paquet, Kim, 2023 | https://arxiv.org/abs/2310.16410 | Opened (abstract) |
| Toward Foraging for Understanding of StarCraft Agents: An Empirical Study | Penney, Dodge, Hilderbrand, Anderson, Simpson, Burnett, 2018 | https://arxiv.org/abs/1711.08019 | Opened (abstract) |

Of the plan's "Verified References" (§7), findings lean on entries 1, 11, 15, 16, 17, 21 and 22 (rows 1, 2, 5, 7,
3, 4 and 8 above, with what was opened). Entries 2-10, 12-14 and 18-20 were not opened and no finding rests on them.
