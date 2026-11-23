# The refocus plan: record of the reviews

This file is the history of `docs/REFOCUS.md`: what each round of reviews said, what is taken, what isn't, and why.
It is not needed to carry out the document. Section numbers such as 2.2 or "Solution 3" refer to the document.

The review files in `docs/` (`<name>-review.md`) are overwritten by each round.

---

## 1. Round one (2026-11-22)

**State: taken on 2026-11-23.** Folded by the session that wrote the document (commits `387f2d9`, `67f41f9`: Draft v2.0),
not by this one; 1.9 holds the user's answers, 1.10 where each thing went, 1.11 what this session found in v2 after the fold.

Nine reviews of the document at commit `7492ff5` (Draft v1.1) are in `docs/`. Every reviewer got the same prompt:
the user's question in their words (is a major refocus necessary at all, or would the current direction get there
with more bug fixing and training; if it is, are the plan's solutions the best, and are there better ones in the
literature, searched for and not recalled), with the rule to answer that first, to cite file and line for claims
about source, and to say for each paper whether it was opened in the run.

| Review | From | Note |
|---|---|---|
| `claude-opus-5.5-review.md` | sub-agent of this session, effort high | 433 lines; web search and fetch used, each work marked opened or seen in search |
| `claude-fable-5.2-review.md` | sub-agent of this session, effort high | 332 lines; same; says quotes from papers are as its fetch tool extracted them |
| `gpt-6.2-sol-review.md` | Hermes, OpenRouter, effort medium | 92 dense lines; the review with the most file-and-line reads per finding |
| `deepseek-flash-review.md` | Hermes, OpenRouter, effort max | "opened" means an abstract or record page; one claim about source did not hold (1.6) |
| `mimo-2.6-pro-review.md` | Hermes, OpenRouter, effort xhigh | several works marked recalled, not opened |
| `gemini-4-carbon-review.md` | Hermes, Google's API, effort high | cites lines of real league records (`runs/league/HS284a`) |
| `muse-wonder-review.md` | Muse Code, effort high | most works "searched, not opened" |
| `gemini-4-hydrogen-review.md` | `agy`, effort xhigh | no shell; every paper checked from search summaries only, no full text |
| `gemini-4-neon-review.md` | `agy`, effort xhigh | no shell; every paper checked from search records only, no full text |

All nine were written this round, open with the round's name and name no other review (`round.py check`: none
flagged). One sentence of the prompt was stale: it said the document cites `match.records.jsonl`, which the commit
reviewed had already removed. Three reviews (Muse, Hydrogen, Opus) repeat that the document cites a file not in the
repo; that is the prompt's error, not the document's, and is not counted against it. Their point under it stands:
the section 1 illustration's numbers are traceable to no file (1.2).

**Status** in the tables below: **C** checked in source by this session on 2026-11-22; **R(n)** read in source by n
reviewers, not rechecked; **V** to verify, by the step or run named.

### 1.1 The user's question: is a major refocus necessary?

Asked of all nine. In a sentence: **no reviewer endorses the plan as written, all nine say steering (G3) and
explanations (G5) will not arrive from bug fixing and training alone, and all nine say what is missing is mostly
the upper layers `docs/ARCHITECTURE.md` already designs (sections 6.1, 6.8, 7.5, 7.6, 8), to be built inside the
present agent.** They differ on what to call that.

| Answer | Reviewers | Their ground |
|---|---|---|
| A structural refocus is necessary, but narrower than the plan: a return to ARCHITECTURE | Carbon, Neon, Hydrogen | No belief over the enemy's plan and no plan state in play, so G5 cannot be answered from any records; a style rolled at 0:00 cannot follow a replay; per-tick imitation without a held intent is incoherent in principle |
| Refocus the trunk (strategy, belief, records) only; not the four-tier re-stack, the delete list or the one-matchup pause | Muse, Mimo | G1 is converging slowly on its measures; G3 and G5 are missing components, not bugs |
| Change priorities and process, do not rebuild the architecture | Sol, Opus, Fable | The plan's evidence that the present stack is a dead end does not hold (1.2); the pieces it wants are additive providers |
| No to this refocus; the current direction is right for G1; a small gated addition for G3, G4, G5 | Deepseek | The direction in `TODO.md` is the judge and pipe loop, whose own finding is that faults are in the pipe, not the models |

Where the reviewers say the current direction falls short and where it does not:

| Goal | Would the current direction get there? | Raised by |
|---|---|---|
| G1, plays like a real opponent | Disputed. Converging slowly on its fidelity measures (Muse, Mimo, Deepseek, Sol); capped by per-tick imitation without a held intent (Carbon, Neon, Hydrogen). Opus and Fable: coherence is the plan's best case, and one persistent army intent is the smallest test of it | all |
| G3, steerable | No. Nothing on `TODO.md`'s Direction builds a plan state or a replay-to-plan path; issues #26, #40, #12 are unstarted | all nine |
| G4, adjustable skill | No work on it; partial, not unbuilt (profiles exist, the fit doesn't) | Sol, Neon, Hydrogen, Deepseek |
| G5, explainable | No. Records hold odds, draws and input ablations; a plan, a belief and the alternatives' reasons are not there to cite | all nine |

### 1.2 What the reviewers agree on

| Theme | Raised by |
|---|---|
| Most of Solutions 2, 3 (Provider A), 5 and 6 is ARCHITECTURE's own unbuilt design, to be built on the present agent's seams | all nine |
| No separate `gt_ns` build line: add providers and options to gt1dev | Sol, Opus, Fable, Deepseek, Muse, Mimo (Hydrogen, Carbon and Neon write of `gt_ns` without objecting to it) |
| The learning ledger (2.3) does not show that option-timescale or strategy-level learning works: the 90 s row is an effect size from a deleted script, its follow-up (locked commit pairs) is at chance, and the selector's gain was a cheese against scripted Zergs | Opus, Fable, Sol, Muse, Hydrogen, Deepseek |
| Counterfactual risk minimization cannot deconfound pro replays (no logged propensities, no overlap, unobserved confounders). Use the pros' choice frequencies as the prior; estimate outcomes only on Gary's own logged or branched games | Sol, Muse, Hydrogen, Neon, Carbon, Fable, Opus (Mimo: paired branches are the stronger instrument) |
| The shielding paper is misapplied: the leases filter units before a layer decides, and what broke RL was decisions never asked for or never carried out | Opus, Fable, Sol, Muse, Neon, Deepseek, Mimo |
| The counterfactual verifier is the wrong tool: re-query the trunk on the saved input (milliseconds, no game); a branched game answers a different question, and single-concept flips fail on overdetermined decisions | Carbon, Neon, Sol, Muse, Deepseek, Fable, Mimo, Hydrogen |
| The delete and archive lists remove live or measured-good code | all nine |
| The calm layer "proof" mixes two rounds and contradicts the repo's own diagnosis (which bunches get the orders) | Opus, Fable, Sol, Muse, Deepseek, Mimo |
| A milestone scheduler beside an unconditioned macro model recreates the two-owners conflict `answers.py` has; one owner of resources, or mask the model's one-off choices | Sol, Hydrogen, Neon, Carbon |
| Nine hand-written squad options repeat rules already measured (`gather`, `retreatfar`, `holdtarget`); the pros redirect 0.79 of group orders within 30 s. Start with persistence on the existing commitment and learn the hold | Opus, Fable, Sol, Muse, Neon, Hydrogen, Carbon |
| Local-reward leaf RL already failed to transfer to games (#53: `rl2`, `rl3`), DAgger has no expert to query, and RL is parked by the user | Opus, Fable, Sol, Hydrogen, Carbon, Deepseek, Mimo |
| Independent soft probabilities into a learned scorer are the leaky configuration; predict one joint belief over the enemy's plan (Bayesian plan recognition has Brood War precedent) | Carbon, Neon, Hydrogen, Sol, Muse, Deepseek |
| Pausing every matchup but TvZ reverses the 2026-11-12 decision and its reason | Mimo, Deepseek, Muse, Opus, Hydrogen, Neon |
| The gates are not gates: three unblinded live games, one judge, thresholds inside what 96 games resolve, no margin written first | Sol, Fable, Opus, Deepseek, Neon |
| Phase 3's discovery loop is premature; timelines are optimistic | Neon, Mimo, Sol, Muse, Hydrogen, Carbon, Fable |

### 1.3 Facts the document had wrong, or didn't know

| The document said | What was found | From | Status |
|---|---|---|---|
| 2.3: `rl1` was replaced in gt0.36dev by "a relabeled imitation model lacking siege/mines" | Reversed. `rl1` is the model whose roles had no siege, unsiege or mine; `tvzmodes` replaced it to add them (`gary/agent/manifests.py:994-999`) | Sol, Hydrogen, Neon, Carbon, Fable, Opus, Mimo | C |
| Summary, 2.1, 2.2: the dev builds "stripped out leaf stop-gaps"; nothing symbolic is left | `unscripted` clears the army's static guard, hunt and rules and the macro's caps, bank escape and supply-ahead only (`manifests.py:1093-1096`). gt1dev keeps the five fight rules at priority 3, `answers`, `rax_by`, `odds_mass` and `expand_mass` (also AGENTS.md's stop-gap entries) | Neon, Carbon, Hydrogen, Fable, Sol | C (configuration); R(2) that `answers` fires in HS284a's records |
| 2.1: stop-gaps are "post-posed overrides" that overwrite the model's action | `Leases.free()` removes units a higher-priority source holds before the lower layer decides (`gary/agent/intents.py:27-30, 48-60`). Equal priority is not exclusive: fight and roles can supersede each other | Deepseek, Muse, Sol | C |
| 4.1: `gary/policy/fight.py`, `fight_cmd.py`, `switch.py`, `plan.py` are "legacy dead/superseded" | All four are imported by code the current builds run (`gary/agent/fight.py:43-45`, `arbiter.py:247`, `posture.py:248, 402`, `manifests.py:461, 540`, `zerg_roles.py:110`) | Deepseek, Neon, Carbon, Hydrogen, Fable, Opus | C |
| 2.4, Phase 0: feature calculation is duplicated; a shared reader would end the input-parity tax | `ingest/macro_dataset.py` writes raw arrays and imports nothing from `gary`, but `train/macro.py:41` already imports `encode` from `gary.policy.macro`. The parity faults came from what live observation and the re-simulator each count (workers in refineries, units in bunkers), not from two encoders | Sol, Hydrogen, Neon, Carbon, Fable, Opus | C (imports); R(4) on the faults' cause |
| 2.2 item 2: the calm layer matched 1.43 short orders and an 8 s rest while its direction head was at 2.67, and units alone rose 0.29 to 0.41 | Two rounds mixed. CL281a: 1.43, rest 11 s, alone 0.38. CL282a: 1.24, rest 8 s, alone 0.41 (`docs/PROGRESS.md:2228-2232, 2262-2266`). The repo's reading is which bunches get the orders, not random direction | Deepseek, Mimo, Sol, Opus, Fable, Muse | C (numbers); R(3) on the reading |
| 2.2 item 3: "37-40% of retreats were cancelled by the next fight turn within 2 s" | 37% is another retreat; 27-40% is a reposition, close in or fire (`PROGRESS.md:2410`) | Sol, Hydrogen, Neon, Deepseek, Opus | C |
| Section 1, G3 "current standing": Factory by 8:00 in 59% for the pros' 88%, Starport 10% for 55% | Those are gt0.18dev's (2026-10-26). gt0.20dev: style 1 a Factory by 8:00 in 95% for the pros' 88%, style 2 a Starport 81% for 69% (`PROGRESS.md:1530`). The Zerg figures are likewise before gz0.8dev | Hydrogen, Neon, Carbon, Opus, Sol | C (Terran); R(3) (Zerg) |
| 2.3 and Solution 3: `eval/army_effect.py` shows options have "3x SNR" | The script is deleted (`docs/SELF_PLAY.md:488`). It measured how large a whole-army attack-or-hold contrast is over 77 moments, not that a model can learn which to choose | Sol, Muse, Opus, Fable, Hydrogen | C (deleted); R(3) on what it measured |
| 2.3: commit pairs are a "5 s grid draw" | The pairs ran with commitments locked for the window; held-out 0.46 on 1,004 pairs, and a constant-engage baseline matched the learned scorers | Fable, Sol, Opus | R(3) |
| 2.3: the selector cut losses 57 to 30, "strategic-level outcome learning works cleanly" | Most of the gain was holding one scripted Zerg's all-in; the table over-picked style 4, which the document itself calls cheese in 2.2 | Fable, Sol, Opus, Hydrogen | R(4) |
| 2.2 item 3: gt1dev trails gt1 by -0.188, shown as the tug-of-war's cost | Measured 2026-11-11, before the mode and calm models; `PROGRESS.md` attributes it to the stop-gaps removed (bank escape -0.203, caps -0.109, static guard -0.062, SCV cap -0.047) and to games not ended. The dev build is gt0.48dev now and the comparison is due again (`TODO.md` Direction) | Fable, Mimo, Sol, Deepseek, Hydrogen | R(5); V by the remeasure |
| 2.2 item 3: "army moves unsieged tanks mid-fight" as a current fault | Fixed in gt0.39dev | Deepseek, Neon | R(2); this session did the gt0.37 to gt0.38 work and the other session's gt0.39dev entry says so |
| 2.2 item 4: months of `pipe_table.py` rounds missed the tanks never sieging | `pipe_table.py` dates from 2026-11-17; the fault was found on 2026-11-12. Only the gap score ran for months | Deepseek, Mimo | R(2) |
| Summary: about ten independent stateless models (`CalmNet`, `CalmFarNet`, `EventModel` ...) | The calm models are the role network reused; the event model is a head in `gary/policy/modes.py`. They keep local state (trackers, commitments with age); what they lack is a shared plan | Muse, Hydrogen, Sol, Opus | R(4) |
| Solution 2: `belief.py` predicts "only raw enemy army supply" | It predicts expected counts per army type, workers and town halls and supply quantiles; what is missing is a belief over the enemy's plan | Neon, Mimo, Hydrogen, Carbon | R(4) |
| Solution 5: `label_all.py` is a frozen kNN projection | kNN for TvZ Terran only; the other catalogues use rule labellers | Sol, Neon | R(2) |
| 4.1: the selector is an "old 1.16 map-only" one to retire | It is the v0.19 counted table of ARCHITECTURE 6.8 (Beta posterior per map and option); Provider A extends it | Deepseek, Muse | R(2) |
| Solution 2: "19k+ modern re-simulated games" | 18.9k are indexed across all matchups; the local catalogue has 2,683 modern TvZ games, 91% spire-first and about 5.6% lurker-first | Fable, Mimo, Sol | R(3) |
| Section 1 illustration | A 4:40 sighting cannot explain a 3:31 Factory; "54% (n=312) against 47% (n=98)" is within noise; the record numbers are traceable to no file | Sol, Fable, Muse, Opus | C (the times are in the document's own table) |
| Section 7: every citation verified for its supported claims | Three are cited for what they do not say: Alshiekh et al. (a post-posed shield keeps learning sound), HAC (trains its levels in parallel), Swaminathan and Joachims (needs logged propensities). DAgger needs an expert that can be queried. Smaller: reference 16's lead author is Castellano Ontiveros, reference 22's author list is wrong, GA2M is Lou et al. 2013 | Opus, Fable, Sol, Neon, Carbon, Muse, Mimo | R(5); none opened by this session |

### 1.4 Recommended: take

These need no decision from the user. Each is a change to the document's text or to a step's list.

| Change | From |
|---|---|
| Correct every row of 1.3 in sections 1, 2, 4.1 and 7; mark the section 1 illustration as constructed, or cite a real game and frame | all |
| Say in the summary that the trunk is ARCHITECTURE 6.1, 6.8, 7.5, 7.6 and 8 built at last, and name what the plan adds beyond it (held army intents, the ownership rules, explanation in Phase 1) | all nine |
| Phase 0 first step: remeasure the dev build against the playing build and watch one live game a race (`TODO.md` Direction d and e), so the plan has a current baseline | Hydrogen, Sol, Fable |
| Replace win-rate tables as the trunk's scorer with the pros' choice frequency in the observable situation, with a support floor and its count printed; keep three quantities apart (what pros did, how those games ended, what a branch does for Gary). An outcome scorer may override the pros' usual answer only after paired branches on Gary's own games | Sol, Carbon, Opus, Fable, Neon, Muse, Hydrogen |
| Drop counterfactual risk minimization on pro replays; where propensities are wanted, use Gary's own records, which log `p` and `top` | Sol, Muse, Hydrogen, Neon, Carbon, Fable, Opus |
| Opponent model: one joint belief over the enemy's plan from the existing plan library (`taxonomy/plans.py`), compared against `answers.py`'s read and a time-and-map prior; extend `belief.py`; say "last seen", "confirmed absent" and "not scouted" apart; calibrate on held-out pro games and on Gary's own | Carbon, Neon, Hydrogen, Sol, Deepseek, Mimo |
| One owner of the macro's resources: either the card and the model share one scheduler, or the trunk masks the model's one-off choices (tech buildings, expansions, research) unless a directive allows them. Remove the "or" in Solution 4 | Sol, Hydrogen, Neon, Carbon |
| Split the faithfulness check into three: what happened (records with ids joining decision, grant, order and result); what would change Gary's decision (the trunk re-run on the saved input with a valid upstream change, the smallest set of concepts that flips it); what would happen in the game (forced branches with repeats, stated horizon). Drop "80% of single flips" as the kill line | Sol, Carbon, Neon, Muse, Deepseek, Fable, Mimo, Hydrogen |
| 4.1: replace DELETE, RETIRE and ARCHIVE with "replaced when the successor holds the rule's own measure" (AGENTS.md), keep and extend `selector.py`, take the four live modules off the prune list, and move `grouping.py` to refactor if squads are to own hotkeys | Muse, Mimo, Deepseek, Carbon, Fable, Opus |
| Gates: the promotion rule as written in AGENTS.md (fidelity per window, then 96 paired games with the margin written first, the same gg setting on both sides); live games are a discovery step, not acceptance; name the fixed opponent and add a small set of scripted Zerg plans so the belief's branches are actually triggered | Sol, Deepseek, Fable, Opus, Neon, Hydrogen |
| Contracts (4.2): give an option an identity (id, start, end, preemption, lease, target), give the trunk a plan state with the active card and directive, pass candidates with their parameters, and seed every new provider from the game's seed (the army's and the calm layer's seed faults, issue #64) | Deepseek, Sol, Neon |
| Add the Brood War and RTS work the plan omits as its comparison points: Synnaeve and Bessière 2011 (Bayesian plan recognition), Churchill and Buro 2011 and Justesen and Risi 2017 (build-order planning), AlphaStar's replay-statistic conditioning and AlphaStar Unplugged (offline improvement), Madumal et al. 2020 (explanations tested on StarCraft II players), Maia (skill bands) | Sol, Opus, Fable, Muse, Hydrogen, Neon, Deepseek, Carbon |
| Downgrade Kautz, Silver et al. and Ontiveros et al. from "grounding" to analogy; replace "Verified References" with a per-entry note of what was checked | Muse, Mimo, Sol, Fable, Opus |

### 1.5 Recommended: take in part

| Suggestion | From | What to take |
|---|---|---|
| Three arms in Phase 1: counted-table trunk, the macro model conditioned on the card (AlphaStar's z) with the belief as an input, strict concept scorer | Muse, Fable, Mimo, Sol, Opus | Take the first two as the Phase 1 comparison on style adherence and on the decision-level explanation check. The strict concept scorer waits: it is the Q1 ablation, run on one scorer family with and without the extra inputs |
| Action chunks, latent skills or offline hierarchical RL for the leaves (ACT, VQ-BeT, OPAL, HIQL, IQL) | Neon, Carbon, Hydrogen | Name action chunking as the candidate if a held intent plus the current role model still dithers. Not a step of this plan: each is a new training line, and RL is parked |
| An LLM prompt compiler for G3 (HIMA, TextStarCraft) | Deepseek | Name the `strategy_compile` slot and a constrained text-to-card lookup with ambiguity shown (Sol). No LLM on the decision path |
| Post-hoc concept models and guide claims to screen candidate concepts | Carbon, Deepseek, Neon | Note as the cheaper first pass if the discovery loop is ever built (decision 5) |
| An early two-profile test for G4 | Sol, Neon, Hydrogen | Add one line to Phase 2: the same card under two hand profiles, checked for order and for whether the weaker one still follows the card |
| Reward machines as the shape for card plus directives | Mimo | Mention under alternatives; not adopted without a reason to prefer it to the card |

### 1.6 Recommended: not take, and claims that did not hold

| Suggestion or claim | From | Why not, or what the source shows |
|---|---|---|
| Claim: gt1dev turns `answers` off | Deepseek (its finding 15) | `unscripted`, `noalarm` and `styleroll` do not touch it; gt1's `"answers": True` carries through (`manifests.py:261, 1093-1096, 1148, 1393`). C |
| Claim: unifying the macro feature code is "the one concrete, cheap Phase 0 fix" | Muse (18c) | The import fact is true, the remedy is not: the encoder is already shared (1.3) |
| Confounding-robust policy improvement, doubly robust estimators, POMDP off-policy evaluation on pro logs | Hydrogen, Carbon, Neon | With paired branches on Gary's own games available, the causal question has a direct instrument; these add machinery for a quantity the trunk no longer optimizes |
| Double machine learning on policy residuals for concept discovery | Hydrogen | Belongs to Phase 3, which is recommended deferred |
| A deterministic recipe-card executor for the opening, handing off to the macro model afterwards | Neon | It is a second macro executor to keep in parity; the masked model with one scheduler gets strict adherence without it. Revisit if the Phase 1 comparison shows the conditioned model cannot hold a card |
| Define `CLEAR_FINISH` as a scripted map sweep | Carbon | A new scripted rule for a job the user has kept for a learned layer (the hunt's entry in AGENTS.md); it stays a stop-gap question, not part of the trunk |

### 1.7 Disagreements a test decides

No vote settles these. Each names what to run.

| Question | Positions | Decided by |
|---|---|---|
| Is the dev build's deficit to the playing build still what the plan argues from? | The plan: -0.188, a failing paradigm. Mimo, Fable: the measured value of the stop-gaps removed | The remeasure of gt0.48dev against gt1 (96 paired games) with the fidelity measures per window |
| Does holding the army's existing commitment (a learned hold, an exit on evidence) fix cancelled retreats and lone units, or are named options needed? | Options: the plan, Hydrogen, Carbon. Persistence first: Sol, Muse, Opus, Fable, Neon | Three arms on the same seeds: current, hold only, one persistent option with ownership. Measures: retreat survival and distance, units alone, late arrivals; then 96 paired games |
| Is there learnable signal in which option to choose? | The plan: 3x SNR. Six reviewers: unmeasured | The effect of an option choice against the game's spread, measured before any option scorer is trained (the effect-size method of `docs/SELF_PLAY.md`) |
| Does the macro model conditioned on a card hold a requested build as well as a symbolic scheduler? | Scheduler: the plan, Neon. Conditioning: Fable, Muse, Mimo, Opus | Phase 1's two arms on `eval/style_adherence.py` and ARCHITECTURE's 18 of 20 unharassed runs |
| What does a strict concept bottleneck cost? | The plan's H4. Deepseek, Neon: likely more than the threshold | One scorer family with and without the extra inputs, on held-out replays, before any paired games |
| Does `answers.py` decide anything in gt1dev's games today? | On in the manifest (C). Carbon and Hydrogen cite record lines; Fable found none in one file | A count of its decisions over one league round's records |

### 1.8 Decisions for the user

Each reverses or extends something the document picked or the user decided, so none is taken here.

| # | Question | For | This session's recommendation |
|---|---|---|---|
| 1 | Does the plan stay an architectural refocus (four tiers, a new `gt_ns` build line, retire and rebuild), or become a change of priorities: the unbuilt ARCHITECTURE layers added as providers and options on gt1dev? | Priorities, no new line: Sol, Opus, Fable, Deepseek, Muse, Mimo. Structural but inside the present agent: Carbon, Neon, Hydrogen | Priorities. Six reviewers argue against a third build line and none argues for one, and the evidence that the present stack is a dead end did not survive the checks in 1.3. Rewrite the document as v2 on that footing |
| 2 | Pause the other matchups until TvZ passes Phases 1 and 2? This reverses the decision of 2026-11-12 | Against the pause: Mimo, Deepseek, Muse, Opus. For a TvZ-first build with wider tests: Hydrogen, Neon | Build the slice in TvZ Terran, keep the judged work in the other matchups going at a low rate, and do not freeze the contracts until one Zerg and one Protoss dev game have run through them |
| 3 | The tactical layer: nine named squad options with hand-written exits, or one held army intent with a learned hold first? | Small first: Sol, Muse, Opus, Fable, Neon. Options with the heatmap as target from day one: Hydrogen, Carbon | One held intent first, by the three-arm test of 1.7. `gather` and `retreatfar` were this idea scripted, and neither settled it |
| 4 | Keep the bounded leaf-RL pilot in Phase 2? RL is parked by the user's decision | Remove or make offline: Opus, Fable, Sol, Hydrogen, Carbon, Deepseek | Remove it from this plan. It conflicts with the park and repeats the local-reward runs that did not transfer (#53) |
| 5 | Keep Phase 3 (novelty detection, concept invention from residuals)? | Defer or cut to the bottleneck audit: Neon, Mimo, Sol, Muse, Carbon, Hydrogen | Defer all of it until one trunk slice has passed its gate. Keep one paragraph saying what would trigger it |
| 6 | Explanations and the belief in Phase 1, ahead of more fidelity work? This reorders `TODO.md`'s Direction | For: all nine, as the plan's best call | Yes, as a slice beside the current direction's item on positioning and finishing, not in place of it. *Revised 2026-11-23 after the author session's reply: in front, with other fidelity work capped to regressions seen in watched games, on two conditions: the Phase 1 gate and time box written first, and the army's three-arm test run alongside, not after, since its question 4 needs a held intent to cite* |


### 1.9 The user's answers

The user put the record and the reviews to the session that wrote the document (Gemini Neon, with Fable), read its
reply beside this session's, and on 2026-11-23 said: "Neon already wrote V2 with the consensus changes from both of
you." So the answers are the two sessions' consensus: decisions 1 to 5 as recommended in 1.8; decision 6 as the author
session argued and this session then accepted (Phase 1 in front, capped, with a written gate and time box, the army
test alongside). The author session also wrote the departure this session raised after the round: the trunk chooses by
the pros' choice frequency, where `docs/ARCHITECTURE.md:194` says win-rate statistics (v2 section 6, row 7).

### 1.10 Where it went in the document

Read from Draft v2.0 (412 lines) as it stands at commit `67f41f9`.

| Round item | Where in v2 |
|---|---|
| 1.3, every fact: `rl1` reversed, the live modules, the leases, the shared encoder, the calm rounds, 37% another retreat, the October style figures, `army_effect.py`, commit pairs, the selector's cheese, -0.188 as an open test, `belief.py` and `selector.py` understated, the catalogue counts, the illustration | 2.1 and 2.2 (each with its `PROGRESS.md` or source line); the illustration marked constructed under section 1; 4.1 KEEP (LIVE) for the four modules; 7 with per-entry verification notes and the author fixes |
| 1.4: the trunk as ARCHITECTURE 6.1, 6.8, 7.5, 7.6, 8 built at last, plus what the plan adds | Executive summary, section 3's diagram, section 6 |
| 1.4: the remeasure and the live games first | 4.3 Phase 0 (96 paired, three watched games, LAN parity, the `answers` count, the seed fix) |
| 1.4: pros' choice frequency with a support floor, three quantities apart, outcome overrides only from paired branches | 3.2, section 6 row 7 (`min_n` 25 after backoff, Wilson interval, win rate printed as context) |
| 1.4: no CRM on pro replays | 3.2, reference 21 |
| 1.4: one joint belief over the plan library, seen / confirmed absent / unscouted, calibrated on pros and on Gary's own games | 3.1 (two providers behind one slot, against a time-and-map prior and `answers.py`'s read) |
| 1.4: one owner of the macro's resources, the "or" removed | 3.3 (audit, log-only soak, rules off one at a time, then the two-arm comparison), section 6 row 1 |
| 1.4: the faithfulness check split in three, the 80% kill line dropped | 3.5 (execution join, 1 ms re-query for the minimal flipping set, outcome and human utility) |
| 1.4: 4.1 without DELETE, RETIRE, ARCHIVE; `selector.py` kept; `grouping.py` refactor if needed | 4.1 (KEEP, KEEP & EXTEND, RETIRE ONE AT A TIME ON MEASURE, REFACTOR IF NEEDED) and its stop-gap paragraph (`hunt4` not relabelled a trunk rule) |
| 1.4: gates as AGENTS.md's promotion rule, live games as discovery, a fixed opponent, scripted Zerg plans | 4.3 gate (four conditions), the four-archetype suite, "same `--gg` on both sides" |
| 1.4: contracts with identity, a plan state, candidates with parameters, seeding from the game's seed | 4.2 (`id`, `start`, `end`, `preempt`, `lease`, `target`; the schema freeze rule), 4.1 FIX SEEDS |
| 1.4: the Brood War and RTS literature; Kautz, Silver, Ontiveros as analogy | 5.2 and 7 (references 1 to 12; 22 marked analogy only) |
| 1.5: three arms in Phase 1, the strict scorer later | 3.3 as two arms (conditioned model, reserve and mask); the symbolic-versus-unconstrained cost as the Phase 3 trigger's offline audit (5.1) |
| 1.5: action chunking named, not a step | 3.4 last bullet, 5.2 |
| 1.5: `strategy_compile`, no LLM on the decision path | 3.2, section 3's diagram |
| 1.5: post-hoc concept screening if discovery is ever built | 5.2 future direction 2 (paired with the ceiling audit) |
| 1.5: an early two-profile G4 test | 4.3 Phase 2 row |
| 1.5: reward machines under alternatives | Not in v2 (a mention, dropped in the fold; no loss) |
| 1.6: CEM, the causal stacks, a deterministic opening executor, `CLEAR_FINISH` | 3.2 refuses CEM and `concept_mlp`; 3.3 keeps a scripted queue for strict drills only (ARCHITECTURE:456, 471); 4.1 keeps `hunt4` a stop-gap; the causal stacks absent |
| 1.7, the six tests | 5.1 as seven rows (the upgrade-timing audit added), each with its phase |
| 1.8, decisions 1 to 6 | Section 6 rows 1 to 6; row 7 the ARCHITECTURE departure |

### 1.11 Found in v2 after the fold

Read by this session on 2026-11-23; not reviewed by the round. Proposals for the author session or the next round.

| In v2 | What this session found | Status |
|---|---|---|
| 4.3 gate 4: "paired score vs fixed `gz1dev` within pre-written MDE (`+-0.08` at 48 games; if close, extend to 96 with MDE `+-0.06`)" | 48 paired games resolve about 0.15 and 96 resolve 0.06 to 0.14 by the pairing's own spread (AGENTS.md; the remeasure's written MDE is 0.11 at 96). A margin of 0.08 at 48 is inside the noise, the fault 1.2 lists against v1's gates. Write the margin from the pairing's spread when the round is proposed, not a fixed number | C |
| 4.3 Phase 0: "`gt0.48dev` vs `gt1`, matched `--gg`" | The run as proposed by the main session: gt0.49dev (gt0.48dev with the seed fix) and gt1 each against gz1 on seeds 4004-4015, `--gg 0` on both, MDE 0.11. Update the row after the run | C |
| 4.3 gate 3: the 1 ms flip "succeeds on 100% of logged branch switches" | For a deterministic trunk, reverting the triggering evidence always flips the switch (Fable's F5); as a gate it is a smoke check, not a measure. Keep it, but the gate's weight is the blind evaluation | R(1) |
| 4.3 Phase 0: "pausing unstarted `c` items like home at 15-20 and the PvT tanks" and the `TODO.md` Direction rewrite | `TODO.md` is the main coding session's; it should make that edit with the Phase 0 brief, not the author session, so the two don't edit one list | — |
| 2.1: `belief.py` "off by default in play (`PROGRESS.md:59`)" | The line says "not used in play by default". Holds | C |
| 1: Zerg style 4 to 75% and style 0 to 62% in gz0.8dev and gz0.11dev | Not rechecked by this session | R(3) |
