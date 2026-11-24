# The refocus plan: record of the reviews

This file is the history of `docs/REFOCUS.md`: what each round of reviews said, what is taken, what isn't, and why.
It is not needed to carry out the document. Section numbers such as 2.2 or "Solution 3" refer to the document.

The review files in `docs/` (`<name>-review.md`) are overwritten by each round. Round one's texts are in git at commit `e2dc090`.

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

---

## 2. Round two (2026-11-23)

**State: taken on 2026-11-23.** The user took all six recommendations of 2.8; this session folded them, with the takes and part-takes, into Draft v2.1. 2.10 says where each went.

A narrow round on the document at commit `80fa001`: Draft v2.0 with Phase 0 carried out and its results written into
4.3. Scope: sections 3.1 to 3.4, 4.2 and 4.3. The map was table 1.10 and the "Phase 0 Results" block; the evidence was
`docs/PROGRESS.md`'s four entries of 2026-11-23, the league rounds `RD285a`, `RP285a` and `HS284a`, and the code
written since round one (`train/plan_belief.py`, `gary/policy/sightings.py`, `ingest/sighting_dataset.py`). Phase 1 had
been begun and was stopped for this round. Five reviewers were asked and all five wrote, Carbon after a resumed run. Round one's review texts are in
git at `e2dc090`; the files of the reviewers not asked this round (`deepseek-flash`, `mimo-2.6-pro`, `muse-wonder`,
`gemini-4-hydrogen`) still hold round one's text.

| Review | From | Note |
|---|---|---|
| `claude-opus-5.5-review.md` | sub-agent of this session, effort high | 360 lines; its counts are read-only tallies over the three rounds' logs and records; two papers' abstracts opened, the rest from search results |
| `claude-fable-5.2-review.md` | sub-agent of this session, effort high | 341 lines; marks every claim read in source, read from the rounds, or inferred; PDFs could not be parsed: one paper opened as HTML (Gehring et al. 2018), the rest abstracts or search records |
| `gpt-6.2-sol-review.md` | Hermes, OpenRouter, effort medium ($0.93) | 77 dense lines; says it opened two papers' text (Hostetler et al. 2012, its sections 3 to 3.2; Synnaeve and Bessière 2011) |
| `gemini-4-neon-review.md` | `agy`, effort xhigh | 141 lines; no shell, papers from search summaries only. **Neon wrote v2.0 as the author session and proposed part of this round's prompt**, so its agreement with the document counts for little and its objections for more. `round.py check` flagged it for few quotes found in the document; on reading, its quoted strings are source lines and its own example sentences, not text attributed to the plan |
| `gemini-4-carbon-review.md` | Hermes, Google's API, effort high | 128 lines, written in a resumed session. The first run stopped after 48 calls and 13.2 million input tokens on the project's monthly spending cap, with nothing written and no cost reported; the user raised the cap and the session was resumed (7 calls, $2.48). Its context had been compacted once, so it wrote partly from a summary of what it read. It was judged after the other four and after this section's first draft. It says it opened every paper it cites |

All five files were written this round and open with the round's name. The question as asked is in 2.1. One decision
of the user's was added to the prompt: time is not a constraint, the games budget and the order are.

**Status** in the tables below: **C** checked in source or in the rounds' files by this session on 2026-11-23; **R(n)**
read by n reviewers, not rechecked; **V** to verify, by the step named.

### 2.1 The user's question

"Phase 0 is done; its results are in REFOCUS.md 4.3 and PROGRESS.md. Given them, is Phase 1 as written still the right
first build, in the right order, at a sensible cost in games?", with four parts: scouting, what the card and the belief
add, the deficit and the army test, and anything in the code that blocks Phase 1.

"All four" in the tables below means Opus, Fable, Sol and Neon; Carbon is named where it adds to or differs from them, and it agrees with them on the rows of 2.2 except where said.

In a sentence: **all five say Phase 1's goal stands and its order does not: Gary must see before it can believe, so
the first build is scouting, and the first step of that is a bug fix and counts that cost no games; and all five say
the army test's second arm has already been run.**

| Part | The reviewers' answer | Raised by |
|---|---|---|
| Lead: the first build | Scouting, before the belief drives anything. Sections 3.1 to 3.4 name no component that decides when Gary looks, and 4.3 budgets no games for it | all four |
| Lead: the order | Plain fixes and offline counts (0 games); scouting, screened at 16 games on its own measure; the Zerg plans to play against; the belief re-scored, then log-only; one answer of `answers.py` handed to the trunk end to end; the card and its drills only if existing games show a gap; the army's retreat hold as a pipe fix | all four, in nearly this order |
| Lead: the cost | Sol 52 to 68 short games before any strength round; Carbon 158 to 254; Neon about 182; Opus 220 to 300; Fable about 256 with 152 to 248 more conditional on 0-game reads. The document's 360 to 550 counts pairs as games and budgets no baseline for gate 4, so run as written it would cost more (2.3) | all four |
| (1) What the pros do that Gary doesn't | Unmeasured beyond two numbers the repo holds: their first SCV stays (Zerg in sight 104 s of 3:00-6:00, Gary's 44 s) and they look at the main around 6:00-7:00. Gary's worker leaves at about 3:00, its one scan is at 6:30, and on six of eight maps the scan cannot fire (2.3) | all four |
| (1) What to count first | The pros' first sight split by type (a Lair is not a Spire or a Den), by means (their scans are commands in the replay; which unit had the building in sight; how long the first SCV stays), and for Gary "seen, given that it stood" | all four |
| (1) How Gary should get it | Split, and the count decides (2.7). A learned scan model: Fable, Neon, Carbon (built on the spell-cast dataset and rule the repo already has, `ingest/cast_dataset.py`). The pros' timings sampled first, a learned model if that misses: Opus. Whichever existing means is mistimed, sampled; a learned policy later: Sol. A hand trigger only as a tagged stop-gap: all four | all four |
| (2) What the 97-100% counts | The nearest cluster of each key item's first time within 8 minutes. Not: timing error per item, counts, order, anything after 8:00, a particular replay's build, any response to the Zerg. Style 3 is 6 of 8 | all four |
| (2) The least the belief must add | The macro model already reads what was seen (in sight now, the most ever seen). The belief's gain on the pros is the hatcheries and the opening; on tech it ties `answers.py` at 6:00. So: logged for explanations in any case; for play, only where it changes a decision before a deadline. A tech belief with the looked state, plus hatcheries, is enough for a first directive | Opus, Fable, Sol; Neon keeps the joint |
| (2) The least the card must add | A milestone list (a pro game's, or the style's medians with the pros' spread as tolerance), measured as timing error per milestone. Today's build scored on that measure from `RD285a` first, at 0 games ("Arm 0"): the label cannot show what a card adds | Opus, Fable, Sol; Neon 6-10 milestones |
| (2) The measure for the pair | Gary's build given the Zerg's plan against the pros' of the same style facing that plan; and the time from the Zerg's tech standing (or from the first evidence) to Gary's answer carried out | all four |
| (3) Should Phase 1 address the unfinished leads | No, and it should not gate on them. The leads are at most 0.078 of the 0.219 (30 leads at 0.25 each over 96 games: Fable's arithmetic, checked); the rest is games gt1dev loses or trails in, which is the stop-gaps gt1 keeps | all four |
| (3) Do the arms repeat what was tried | Arm 2 on commitments: yes, twice, and its premise was measured false. Arm 2 on retreats: new, and a pipe fix to judge on `eval/pipe_table.py`, not a 96-game arm. Arm 3: relatives tried (`gather`, `anchor` with `home_guard`, `unitcommits`), none with ownership | all four |
| (4) Code that blocks Phase 1 | The scan's main; no Zerg plans to play against; the belief's labels, comparator and sightings fit; the sighting states' notion of a look; gate 4's missing baseline; rule switches the one-at-a-time removal needs (all in 2.3) | all four |

### 2.2 What the reviewers agree on

| Theme | Raised by |
|---|---|
| The tech scan cannot fire on maps with more than one enemy start: a plain bug, in gt1 too | all four |
| Count before designing: by type, by means, given standing | all four |
| Scouting before the belief in play; its measure is fidelity (16 games a step), wins second | all four |
| Arm 2 of 3.4 on commitments repeats `holdtarget` and `unitcommits`; only the retreat hold is new | all four |
| The commit model has no research or upgrade input: 3.4's open item is settled | all four |
| Gate 4 has no baseline against gz1dev (all four), and its margin lets real losses through at 48 games (Fable, Sol, Neon) | all four |
| The sighting states record nearness to a base's centre and town halls only; "confirmed absent" for tech is not there yet | all four |
| Gary's games and the pros' are labelled by two rules in the belief's trainer | all four |
| `watch` was dropped on wins "for information no decision uses", before the fidelity rule; the belief is that use | Opus, Fable. Sol: its history says it moved the plan read to 7:00 only. Neon: only if the count shows the SCV is the means |
| The scripted Zergs are gone; the suite is gz1dev told a style, each game labelled as played | Opus, Fable (Neon and Carbon would script four again: 2.6) |
| The document should say what it means that nothing in the plan aims at promotion | Opus, Fable, Neon |

### 2.3 Facts the document had wrong, or didn't know

| The document said | What was found | From | Status |
|---|---|---|---|
| 4.3: "20 tech scans" in `RD285a`, as a count of a working rule | `answers.py:91` needs `g.army.enemy_main`, assigned only under option `watch` (`army.py:1029-1030`), or a single enemy start; `gary.py:118` never narrows the starts and no manifest carries `watch`. All 20 scans are on Colorless Fate and Odyssey-RE; none in the other 72 games | all four | C |
| `PROGRESS.md:2104`: no tech scan in `HS284a`, "the plan was read before 6:30, or no Comsat" | Two scans, both on those two maps; on the others the cause is the unknown main | Opus, Fable, Sol | C |
| 4.3: Gary "had seen the Zerg's tech by 6:00 in 5% of its games (pros 60%)" | True and under-read. The count includes a Lair and a Hive (`plan_belief.py:61`), which tell no plan; the cause is a schedule (the scout home by about 3:00, the scan at 6:30, `answers.py:32`) and the bug above, not a missing skill | all four | C (the list, the schedule) |
| The same | Gary's first plan read in `RD285a` is at a median of 7:33: Gary learns the plan when the units arrive | Opus, Fable | R(2) |
| The same | The tech mostly stood: by decision times in `RD285a` the Zerg had its Lair by 6:00 in 85 of 96 games and its Spire in 76; 70 of Gary's 87 first reads list a mutalisk or lurker and no Spire or Den. (Opus, another count: a Spire decided by 5:00 in 62 of 89) | Fable | R(1) |
| 2.1, 3.3, 4.1, 6: `natural_bunker` among the rules gt1dev inherits | Off in gt1 and gt1dev (`nonatbunker`, `manifests.py:849, 1224`) | Sol, Neon | C |
| 3.4 Arm 2: a learned hold and exit on commitments, citing `SELF_PLAY.md:489-493` | Those lines end "Gary's own commitments already have that shape". On the same measure the pros redirect 0.79 of group orders within 30 s and gt1dev 0.70; `holdtarget` (-0.011 +- 0.087) and `unitcommits` (-0.048 +- 0.064) "fixed a problem that wasn't there" (`PROGRESS.md:1213-1219`). Round one took persistence first without this measure (1.2, 1.8 decision 3) | all four | C |
| 3.4: "verify whether `commit` already receives research state" | It does not (`gary/policy/army.py:135-156`): time, economy, supply, counts, the commitment, the other clusters | all four | C |
| 3.4 pass criterion "units alone" | Traced on 2026-11-22 to the calm layer's moves of lone units (56% of its orders go to one unit) and to having more small bunches, not to commitments (`PROGRESS.md:2306-2313`) | Neon; Sol and Opus nearby | C |
| 4.3: "16 vs 4 scripted Zergs" | The scripted Zergs were deleted in the refactor (`eval/block_branch.py:30`); `eval/vs_rush.py`, AGENTS.md's measure for early pools, is not in `eval/`. The catalogue has 11 Zerg styles in TvZ; a true 9-pool is not one of them | Opus, Fable | C |
| 4.3: "989 mineral-line turrets" | Goals asked, not turrets built: a goal not carried out is asked again after 30 s (`answers.py:35`). A median 8.5 asks a game, 38 at most | Fable | C (the re-ask); R(1) (the counts) |
| 4.3: "`gz1` plays one plan in 76% of them" | 85 of 112 is `RD285a` and `HS284a` together, gz1 and gz1dev. And Gary's games are labelled by another rule than the pros': first times over the whole game where the pros' labeller stops at 9:00, Lurker Aspect dated by the first Lurker, zerglings alive at 4:00 for zerglings ordered by 4:00 (`plan_belief.py:138-143`) | Sol; all four on the labels | C (the code); R(1) (by the 9:00 rule: spire first 76, lurker first 9, neither 11 of 96) |
| 4.3 gate 4, as rewritten: paired against "fixed `gz1dev`", with `RD285a`/`RP285a` as "the reference rounds" | Those rounds played gz1 with gg off. No gt0.50dev round of 48 or 96 against gz1dev exists or is budgeted; `HS284a` predates the seed fix. The arithmetic of the margin holds (sd 0.466) | all four | C |
| 4.3 gate 4: "a loss under the MDE with the interval holding zero passes", at 48 games | At 48 that passes a true loss of 0.10 about half the time; and `eval/paired.py:45, 148` prints the half width for 96 games whatever the sample | Fable (inferred from the spread), Sol, Neon | R(2); C (`paired.py`) |
| 4.3 budget: "48-96 paired" as 48 to 96 games | A paired round is two arms: Phase 0's "96 paired" was 192 games, as the block itself says. Rule removals of 3.3 and gate 4's round are not budgeted | Neon, Sol, Fable | C |
| 3.1: the belief trainer as the first piece of Phase 1 | With `--sightings` the categorical mask is sized from the model's columns and used for the ceiling's too (`plan_belief.py:301-303, 313, 323`): the fit would fail (read, not run). Old-era rows get NaN sightings, which hands the trees the era (`:286-302`; the dataset defaults to modern) | Sol, Neon, Fable | C (read) |
| The same | On Gary's games the "own shares" comparator is fitted on the games it scores (`:178-179`); no calibration error is computed though gate 1 names calibration; the player's own supply and workers are inputs (`belief.py:44-47`), so the belief can read the enemy's plan off Gary's own build; the lurker egg (97) is not among its types though `answers.py` reads it; no first-seen times, and the ceiling is worse at 8:00 (0.398) than at 6:00 (0.359) | Fable, Opus, Sol | C |
| 3.1, 4.2: the sighting states as "seen / confirmed absent / unscouted" | A look is any unit within 8 tiles of a base's centre (`sightings.py:18, 52`), not sight; only a town hall's presence is recorded at a look; 4.2's `SightingState` and the committed class of that name are two shapes; the dataset finds the player by the first town hall of its race, wrong in a mirror (`sighting_dataset.py:44`), fails outright on a mirror matchup's name (`:85`), and drops failures silently | all four; Carbon | C |
| The same | Whether a Comsat scan counts as a look (whether the sweep is one of the player's units in the observation) | Opus, Fable | V: a scan in a scenario, then `look()` |
| 3.5, 4.2: the records the templates will cite | Enemy buildings are recorded once per tag (`gary/agent/sightings.py:179-183`): a Hatchery that becomes a Lair gets no record | Opus | C |
| 3.3: `answers.py` as one rule to retire | Its read never moves from mutalisks to lurkers (`answers.py:76-80`: first sightings are kept, the Spire wins); no option turns it off in TvZ (only against non-Zerg, `manifests.py:43`); under-half's 0.5 has no switch (`macro.py:479`) | Neon, Fable; Carbon (lurkers follow in 64% of three-hatchery spire games, its count) | C |
| 3.3: one owner of the macro's resources (minerals, gas, the task slot) | `committed()` holds minerals only (`gary.py:176-188`). Comsat energy has three spenders that don't know of each other: the tech scan, the hunt's scans, the Detect rule | Neon; Fable | C |
| 4.3 gate 4: "a loss under the MDE with the interval holding zero passes" | AGENTS.md's rule is "the pairing's interval holds zero, or its loss is under the minimum detectable effect". With "and", the margin never binds: an interval that holds zero already means a loss under its half width, which is smaller | Carbon | C |
| 3.3 Arm A: the macro model conditioned on the card's remaining milestones | Trained on each pro game's own later milestones, the input leaks the next decision unless it is masked at random in training, as AlphaStar did with its z | Carbon, Fable | R(2), inferred |
| 3.3 Arm B: reserve and mask | The dice never roll a decision under 1% (`DICE_FLOOR`, `macro.py:41`), so a mask alone cannot make a directive's rare item happen: the directive must also ask for it. A new reserve on top of `committed()` would count parked builds twice | Carbon | C (the floor); R(1) |
| 3.3 Arm A: new inputs to the macro model | The gg check needs the critic's features equal to the macro's (`eval/match.py:113-117`): a changed input turns gg off for that side until its critic is retrained | Neon, Fable | C |
| 3.2: `min_n` 25 | Of the modern games, zergling pressure and hydralisks are 0.2% each (about 5 games) and the four lurker-first styles 5.6% together: under 25 once split by map or style | Neon | C (the shares); the counts inferred |
| 3.1: 2,683 modern TvZ games | The belief's report holds 2,431 modern games; `PROGRESS.md` says 3,059 | Neon | C (2,431); V: which is the count after "other" is left out |
| 3.3: the macro's dice | Seeded by the game's seed without the side's slot (`macro.py:149`), unlike the army and calm layers after #64 | Neon | C (read); V: whether a mirror's two sides get the same seed |
| 3.4, 4.3, 5.1: `gt0.48dev` as the control and baseline (lines 127, 187, 314, 339, 354); `TODO.md:31-32` and `:143-145` | gt0.50dev is the baseline; `TODO.md` was rewritten and the lines moved; 5.1's first two rows are resolved | Opus, Neon, Fable | C |

### 2.4 Recommended: take

These need no decision from the user. Each is a change to the document's text or to a step's list.

| Change | From |
|---|---|
| Phase 1's first step is plain fixes on their own checks, at 0 games: the scan's main known without `watch`, in one shared place; Gary's games labelled by the pros' rule; the trainer's faults in 2.3. Code is the coding session's; the document lists the step | all four |
| Then the counts, at 0 games, before any design: the pros' first sight by type and by means; their scans from the replay commands, with targets; how long their first SCV stays; Gary's seen given standing; `answers.py`'s goals against turrets built | all four |
| The scouting measure, the same function for Gary and the pros: Spire-or-Den seen by 5, 6, 7, 8 minutes given standing, Lair apart; Zerg in sight at 3:00-6:00; scans a minute and their targets; the first plan read's time and whether it came from a building or from the units arriving; workers at 8:00 as the cost | all four |
| The suite is gz1dev told a style with each game labelled as played by the pros' rule; rounds sized for about half landing on the told plan; lurker-first named as the rarest to obtain | Opus, Fable |
| Gate 1 rewritten: on Gary's games against the suite, not worse than the floor where Gary has not looked and better where it has, with a calibration error reported and a scouting precondition; the comparator fitted on other games | Opus, Fable, Sol |
| Gate 4: the margin written as the loss accepted, not as what the sample detects; 96 games for the one guardrail; its baseline named and budgeted (2.8, decision 4) | all four |
| The budget in physical games, a paired round as two arms, with what is reused said | Neon, Sol, Fable |
| "Arm 0": today's build scored on the card's measure from `RD285a` before Arm A or B is built; the 40 drills and the A/B only if it leaves a gap | Opus, Fable, Sol |
| The soak's first pass from existing records (odds, draws and reasons are in them); `on_card` defined on one-off milestones, as most macro decisions are continuous production | Opus; Neon |
| Arm 2's commitment half removed from 3.4, with the measure that settled it; the research-state item marked settled | all four |
| 4.2: the trunk's and the scorer's signatures take the observation or a context (own tech, time, map), a reset for paired branches, and an output for "not enough evidence"; the evidence a decision read is identified | Neon, Sol |
| 3.3: `natural_bunker` off the list; a switch for `answers` in TvZ and for under-half before the one-at-a-time removal; Comsat energy among the owned resources | Sol, Neon, Fable |
| 3.2: the pro-frequency tables keyed on the looked state too, or built after scouting; a written backoff for plans under `min_n` | Fable, Sol, Neon |
| The records key an enemy building by tag and type, so a morph is a sighting | Opus |
| Every log-only step (the belief, the card, the soak) draws from its own stream and pins its checkpoint, so a shadow call cannot move the dice of the build it runs beside | Sol |
| The sighting states: a look from what was visible, a scan counted once verified, tech absence recorded, one name with the contract, mirror-safe, no era through missing values | all four |
| The document says three things it leaves out: no phase aims at promotion's second condition; the unfinished leads against gz1 are partly gz1 not resigning; which build the live games and the blind evaluation use (2.8, decision 5) | Opus, Fable, Neon |
| Gate 4 states AGENTS.md's promotion rule as it is written: the interval holds zero, or the loss is under the margin written first | Carbon |
| The stale references of 2.3's last row; 1.11's row on the 1 ms flip acted on (a unit test, not a gate threshold) | Opus, Neon, Fable |

### 2.5 Recommended: take in part

| Suggestion | From | What to take |
|---|---|---|
| Scouting by the pros' timings sampled, before any model | Opus | The count first. If the pros' scan time hardly depends on what they have seen, the sampler is enough for a start; if it does, the learned model is the first build (2.7) |
| A sampler of the pros' timings is not a stop-gap, as AGENTS.md names "a decoder that samples the pros' timings" | Opus | Arguable, not settled here: AGENTS.md names it as a change judged on fidelity first, and separately defines a decoder as how a model's odds become a choice. Fable and Neon read a sampler with no model behind it as a stop-gap. It is the user's rule to place (2.8, decision 3) |
| A learned scan model, with the fixed scan kept as a tagged stop-gap | Fable, Neon | As the target: it is the replacement AGENTS.md's Detect entry already names, and scans are clean labels. Its inputs wait on the sighting states and on scan targets in the command cache |
| `watch` back in gt1dev, judged on its fidelity measure | Opus, Fable | Only if the count shows the pros' first SCV stays and is what sees the tech; its 5:00 limit is before most Spires stand |
| The Bayesian provider first, since an unlooked base then adds no evidence by construction | Fable, Neon | The test, not the order: on Gary's unlooked games a provider must return the floor. The trees get the sighting states and the pros' sightings cut at random earlier times first; the Bayesian one is built if they fail (2.7). Opus would drop it |
| Arm B (reserve and mask) first, Arm A skipped | Neon | Arm 0 first; the choice between A and B waits on its number |
| One answer of `answers.py` handed to the trunk end to end (the lurker list) | Opus, Sol | After AGENTS.md's own pending measure: `answers` off once Gary sees, to learn whether the model answers alone (Fable). If it does, the belief's job is explanation |
| A critic retrained for gz1 from the league's replays (0 games), so promotion rounds can run with gg on both sides | Carbon | Worth doing, and it changes what decision 4 costs: with gg on, fewer games are graded at time. It is the coding session's, and `RD285a` (gg off) would no longer be the matching baseline |
| The belief keeps non-exclusive flags for spire and lurker tech, so a switch is answered | Carbon | Yes for the directives; the joint's first-tech label stays as the taxonomy has it |
| A deterministic queue as the strict drills' path (reopening 1.6) | Opus, Sol, Fable | Not now. Arm 0's milestone error says whether dice-drawn macro can hold a card; reopen only if it cannot |

### 2.6 Recommended: not take, and claims that did not hold

| Suggestion or claim | From | Why not, or what the source shows |
|---|---|---|
| Port or build the scripted Zergs (four plans and a mutalisk-to-lurker switch) | Neon, Carbon | A second Zerg to keep in parity, and scripted Zergs taught the selector its cheese (2.2 of the document). gz1dev told a style first; script only what the catalogue cannot play, if the early-pool case is wanted |
| A trigger on what is unscouted as a one-day unblock | Neon | The bug-fixed `tech_scan` is that trigger already, at 6:30 and 8:30 |
| Drop the parallel army track whole and defer any intent work to after Phase 1 | Neon | The retreat hold is cheap and independent (16 games); the rest is 2.8's decision 2 |
| "0/16 in `HS284a`" scans | Neon, Carbon | Repeats `PROGRESS.md`'s error: two (2.3) |
| Section 1's "style 0 to 62%" is not in `PROGRESS.md` (gz0.8dev played style 0 as told in 50%) | Opus | The document's sentence covers two builds: the 75% for style 4 is gz0.8dev's (`PROGRESS.md:1563`) and the 62% for style 0 is gz0.11dev's (`PROGRESS.md:1643`, overall 56%). The document holds, and 1.11's unchecked row is checked |

### 2.7 Disagreements a test decides

No vote settles these. Each names what to run, and none needs a game unless said.

| Question | Positions | Decided by |
|---|---|---|
| Sampler or learned model for the scan | Opus: sampler first. Fable, Neon, Carbon: learned. Sol: by the count | The count: does the pros' chance of a scan at a minute depend on what they have seen and on the Comsat's age |
| Is `watch` worth bringing back | Opus, Fable: re-judge it. Sol: it moved the read to 7:00 only and cost worker time | The count: which unit first has the Spire or Den in sight in the pros' games, and how long their SCV stays |
| How much of the 5% is Gary not looking | Reviewers' proxy from decision times: about four in five at 6:00 | The re-simulated games: per minute, the tech stood and was not seen |
| Trees or a Bayesian likelihood for the belief | Fable, Neon: Bayesian is safer under Gary's looking. Opus: drop it | Both scored on Gary's games against the suite, split by looked and unlooked |
| Does the belief change a macro decision | Opus: test offline whether it improves the likelihood of the pros' next macro choice. Fable: `answers` off once Gary sees | Both; the second costs 16 to 48 games |
| Does a card add over style conditioning | All: unknown | Arm 0: milestone error on `RD285a`'s 96 games |
| Would an owned army intent change anything | Opus: the cluster key first. Fable: read it from existing rounds | Of units alone and late arrivals, the share caused by another cluster's order taking a committed unit |
| Is a scan a look in the observation | Unsettled | A scan in a scenario, then `look()` |
| Gate 4's spread against gz1dev | Three 16-game pairs give 0.37 to 0.52 (Fable) | The baseline round, if decision 4 buys it |

### 2.8 Decisions for the user

Each reverses or extends something the document picked or the user decided, so none is taken here.

| # | Question | For | This session's recommendation |
|---|---|---|---|
| 1 | Reorder Phase 1 so that scouting is its first build: fixes and counts at 0 games, scouting on its fidelity measure, the Zerg suite, then the belief, one directive, the card? | all four | Yes. It keeps round one's decision 6 (Phase 1 in front) and changes what is first in it. It also supersedes the order this session gave the user earlier on 2026-11-23, now in `TODO.md:34-36` (the sighting states, the suite, the scouting measure, scouting, the re-score): the counts and the fixes move to the front, because the counts decide what a look must record, and the full sighting dataset waits for them |
| 2 | Change round one's decision 3 (three army arms alongside Phase 1): drop Arm 2 on commitments as already run, judge the retreat hold as a pipe fix in 16 games, hold Arm 3 until a 0-game read says what an owned intent would change? | all four | Yes. It saves 100 to 200 games, and the measure that settles Arm 2 was in the repo before round one |
| 3 | Scouting under AGENTS.md: is a sampler of the pros' timings with no model behind it a stop-gap to tag, and is the learned scan model the target? | Stop-gap: Fable, Neon, Carbon. Not one: Opus | The learned scan model is the target. Meanwhile the fixed `tech_scan`, bug-fixed, stays and gets its tag and entry. A sampler is built only if the count says timing is nearly unconditional, and then it carries the tag: by AGENTS.md's wording a decoder turns a model's odds into a choice |
| 4 | Gate 4's round: against gz1 with gg off on `RD285a`'s seeds (the baseline is played: 96 new games) or against gz1dev with gg on (96 more for a baseline, games that end)? | A baseline against gz1dev: Opus, Neon, Carbon. A fresh control, opponent not named: Sol. Either: Fable | gz1 with gg off, 96 games, the margin written as the loss accepted (0.118). The games are the scarce thing, and the suite's rounds already show the build against gz1dev. A condition: `RD285a` stays the baseline only while gz1's code and dice are unchanged (AGENTS.md: a baseline is replayed when the opponent's manifest changed). A fix that moves every build's streams, such as seeding the macro's dice by slot (2.3), would cost the 96 games anyway |
| 5 | Accept, and write down, that no phase of this plan aims at promotion: gt1 stays the playing build, cannot be told a style, and the live games and blind evaluation use the dev build by flag; finishing has no successor while RL is parked? | Opus, Fable, Neon | Accept and write it. The alternatives are to change the promotion rule again or to un-park a finishing piece, and neither is this plan's job |
| 6 | Let the coding session make the plain fixes now, before the fold: the scan's main, the trainer's and the dataset's faults, the records' morphs? | follows from all four | Yes. They are bug fixes by AGENTS.md, depend on no decision above, and the scan fix is in gt1 too, so its parity hashes are recorded again |

### 2.9 The user's answers (2026-11-23)

After the four reviews and this section's first draft, the user raised the API project's spending cap and asked for
Carbon to be resumed "anyway" and its findings folded into the record. Then, on the six decisions: "Fold with your
recommendations." So each of 2.8's rows is answered as its last column reads: scouting is Phase 1's first build; the
army test is narrowed; the learned scan model is the target, the fixed scan keeps a stop-gap tag and a sampler would
carry one; gate 4 plays gz1 with gg off for 96 new games; the plan says in writing that it does not aim at promotion;
the coding session may make the plain fixes now. Before the round the user had also said that time is not a
constraint, which removed the time box.

### 2.10 Where it went in the document

Read from Draft v2.1 as folded (471 lines).

| What | Now in |
|---|---|
| Decision 1, scouting first, and the order of the steps | Executive summary item 3; 3.1's bullet "Scouting is the precondition"; 4.3 "Phase 1 Order (Round Two)", steps 1 to 10, with the scouting measure under it; section 6 row 6 |
| Decision 2, the army test narrowed | 3.4, retitled and rewritten (the commitment hold not run, the retreat hold a pipe fix, an owned intent after a 0-game read); the diagram in section 3; 4.3's army row; 5.1; section 6 row 3 |
| Decision 3, how Gary gets scouting | Section 6 row 8; 5.1's rows on the sampler and on `watch` |
| Decision 4, gate 4's round | 4.3 gate 4 (gz1, gg off, 96 games, margin 0.118, AGENTS.md's "or", when the baseline is played again); section 6 row 9 |
| Decision 5, promotion not a target | Executive summary item 5; section 6 row 10; 3.4's pass criteria (no criterion on finished leads) |
| Decision 6, the plain fixes now | 4.3 "Phase 1 Order", step 1. The code is the coding session's |
| No time box | The header's scope line; the Phase 1 row and the gate's heading in 4.3; section 6 row 6 |
| 2.3: the scan's main, the 5% reading, the scans on two maps, 989 as goals, the 76% | 3.1's first new bullet; 4.3 "Corrected in round two" under the Phase 0 results |
| 2.3: `natural_bunker` | Removed from 2.1, 3.3, 4.1 and section 6; a note in 2.1 item 2 |
| 2.3: the scripted Zergs gone; the suite | 4.3 "The Zerg Plans to Judge Against" (four catalogue styles, labelled as played); executive summary item 4; section 6 row 2 |
| 2.3 and 2.4: the sighting states, the trainer's faults, the provider test, tech that changes | 3.1's four further new bullets |
| 2.4: the tables keyed on the looked state, the backoff, combinable directives, the dice's floor | 3.2's last bullet |
| 2.4 and 2.5: Arm 0, the soak from records, `on_card`, log-only streams, the switches, Comsat energy, `answers` off first, Arm A's leak and gg, Arm B and `committed()` | 3.3 "Round-two amendments to these steps" |
| 2.4: the contracts' signatures | 4.2, the paragraph before the Schema Freeze Rule (the code block itself is unchanged until `contracts.py` exists) |
| 2.4: gate 1 rewritten; gate 2's baseline and tolerance; the 1 ms flip a unit test | 4.3 gates 1, 2 and 3 |
| 2.4: the budget in physical games | 4.3's budget note and "Phase 1 Order" |
| 2.3: research state settled; `units alone` | 3.4's last two bullets |
| 2.7, the tests | 5.1, seven new rows and two marked resolved |
| 2.3: stale references | `gt0.50dev` in the diagram, 3.4 and gate 2; `TODO.md:178` and `TODO.md:59–65` |
| 2.5: a resign critic for gz1 | 4.3 gate 4, as the case in which the baseline is played again; not a step of the plan |

Not in the document, by choice or because it is another file's:

- `docs/PROGRESS.md:2104` (no scans in `HS284a`) and the 989 turrets there, and `TODO.md:34-36`'s order, are the
  coding session's files: it should correct them with the step-1 fixes.
- 3.1's "2,683 modern TvZ games" stands beside the belief report's 2,431: not reconciled (2.3, V).
- The macro's dice seeded without the slot (2.3, V): not listed among step 1's fixes, as it would move every build's
  streams and void gate 4's played baseline.

Settled by this session while folding, each a proposal the user can change:

- The suite's four styles were picked from the catalogue: 9 (pool first, zergling pressure), 1 (two hatcheries, spire),
  0 (three hatcheries, spire), 4 (three hatcheries, lurker first), plus one game where lurkers follow mutalisks.
- Gate 1's scouting precondition is set at Spire-or-Den seen by 7:00 given standing; its distance from the pros' is
  left to be written after the counts.
- The budget's figures (about 180 to 240 unconditional games) are this session's sum of the steps, between the
  reviewers' 60 and 300.
- The document's version became v2.1.
