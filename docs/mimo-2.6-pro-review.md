Round one, 2026-11-22

# Review of docs/REFOCUS.md (RFC) — model mimo-2.6-pro

## 1. Is a major refocus necessary, or would the current direction get there?

Verdict: the current direction will get G1, G2, G4 and G6 there eventually with more bug
fixing and training — the last month of measured work says so. It will never get G3
(steerable) or G5 (explainable for learners), because nothing on it builds a plan state, a
steerable build spec, or a belief about the enemy's plan; those are missing components, not
bugs. So a refocus of the strategy-and-records side is necessary and should start now, but
the plan's four-tier re-stack, its retire-and-rebuild inventory, and its single-matchup pause
are not supported by the repo's own measurements. The minimal necessary change is the trunk
slice the plan itself describes in Solutions 1, 3 and 6 (opening card, counted response
tables, opponent belief, structured records), added to the existing layer/manifest
architecture, with the other matchups' judged work continuing.

What says the current direction is converging:

- The per-situation judge is new (2026-11-12) and in its first day it found, sized and led to
  fixes for the siege, stim, mines, burrow and storm gaps across every matchup, "every cell
  but two a measurable gap, and a regression found" (docs/PROGRESS.md:2807-2874, read in
  source). The tanks-never-sieged fault that the RFC uses as evidence against headless
  rounds was a missing label in one dataset ("the pros' sieges are its 'other', carried out
  as nothing", docs/PROGRESS.md:2808-2809), relabelled and fixed within days: tanks sieged
  61.3% of their fight moments for a pro's 54.3% (TODO.md:63-74, read in source).
- The fidelity gap moves toward the pros where measured work lands: gt1dev is nearer than
  gt1 in four of six windows (docs/PROGRESS.md:1904-1908); the bank and decision-rate gaps
  closed to the pros' level with the hands' and queue's fixes (docs/PROGRESS.md:2875-2913);
  army order sizes and the fight gap moved on one hands change (docs/PROGRESS.md:2155-2160).
- The dev builds' deficit to the playing builds, which the RFC reads as a failing paradigm
  (REFOCUS.md §2.2 item 3), is accounted for in the repo as the measured value of specific
  stop-gaps plus one unlearned job: "the bank escape off -0.203, the caps off -0.109, the
  static guard off -0.062, the SCV cap off -0.047 ... together more than the whole gap ...
  and the promotion rule as written asks its learned layers to make up for all of them at
  once" (docs/PROGRESS.md:2997-3003, read in source), and a third of the remaining deficit
  was a single execution leak (docs/PROGRESS.md:2976-2978). Games not ending is the hunt's
  unlearned job (docs/PROGRESS.md:1916-1921, 2980-2997). That is a coverage gap, not
  evidence that marginal BC plus decoders cannot reach the pros.

What says G3 and G5 will not arrive on the current direction:

- G3 today is a style integer rolled at 0:00; the milestone drift the RFC's table quotes is
  real (Factory by 8:00 59% for the pros' 88%, Starport 10% for 55%: docs/PROGRESS.md:1423;
  Zerg style 0 played as itself 50%, style 4 17%: docs/PROGRESS.md:1541-1545; all read in
  source). The roadmap items that would fix it are unscheduled and old: "Strategy layer: pick
  among proven builds and follow the timeline" (#26, TODO.md:205), "Opponent model: a belief
  over the enemy's plan" (#40, TODO.md:193), "Macro model with game history" (#12,
  TODO.md:191) (read in source).
- G5 is blocked for the same reason: decision records hold odds, draws and ablation deltas
  (verified against a real file, runs/league/AR180a/Radeon 1.2/gp1dev+archons_seed4009.records.jsonl,
  which carries `{"kind": "decision", "layer": "style", "choice": 21, "by": "roll"}` and
  macro decisions with `p`, `top`, `over`, `why`), but no plan, no belief, no alternatives'
  reasons — nothing a coach can quote. The narrator is parked (#41, TODO.md:252). More
  training of the current models cannot add those fields; the components must be built.

So: the refocus is necessary in what it adds to the trunk and the records, unnecessary in
what it tears down. The findings below follow, most important first.

## 2. Findings

### Finding 1 — Pausing every matchup but TvZ reverses the repo's own measured direction
Section: §4.3 ("Scope discipline: Pause tuning PvT, PvZ, PvP, ZvZ, and TvT edge cases") and
§6.2 row "Work every matchup at once".
Source: TODO.md:7-12 — the Direction is "judged per situation, in every matchup ... not in
one matchup first" (the user's call of 2026-11-12, read in source). Evidence the rule was
earned: the stim model's inputs were "a table of Zerg fighters (gary/policy/stim.py KINDS)",
so Gary never stimed against Protoss or Terran at all (docs/PROGRESS.md:2844-2847, read in
source); the PvT first-Barracks timing and Comsat placement faults were only visible in the
PvT/TvT placement checks (docs/PROGRESS.md:1802-1816); the Protoss lost storms entirely
from gp0.20dev to gp0.32dev and "a bug the gap score, the paired rounds and the promotion
verdict of the day before all missed" — the judge found it (docs/PROGRESS.md:2857-2863,
read in source).
The plan's counter-argument (one matchup hides bugs others expose is the reason for the
rule) is not addressed; §6.2 honestly lists the rule as reopened, but the evidence above is
one-sided against reopening it. Building the new stack's first vertical slice in TvZ is
sound; stopping the judged work elsewhere is not. Decouple the two.

### Finding 2 — "Made RL impossible" is contradicted by the one RL run that held
Section: §2.1 (leaf stop-gaps "broke credit assignment and made reinforcement learning (RL)
impossible") and Solution 1's alternative 3 ("Empirically proven in Gary to kill NN credit
assignment and block RL").
Source: docs/PROGRESS.md:35-39 — rl1, the roles RL, "the first run that held", lives in
gt1dev with the stop-gaps' regime around it; SELF_PLAY.md's own analysis says the failed
arms "were undone because they were forced against the model, not because the model has no
hysteresis" (docs/SELF_PLAY.md:486-492, read in source) and lists what made rl1 hold: pipe
check, the model owning the decision during training, a held-out checkpoint split
(docs/SELF_PLAY.md:505-520). The commit pairs' chance result (0.46 held-out, 1,004 pairs,
docs/SELF_PLAY.md:513) is attributed to a 5 s redraw drowning one decision — which the
repo already remedies with commitments locked at the pros' hazard (docs/SELF_PLAY.md:486-491),
the same insight as the plan's persistent options at army level.
The literature is used correctly: Alshiekh, M., Bloem, R., Ehlers, R., Könighofer, B.,
Niekum, S., & Topcu, U. (2018), "Safe Reinforcement Learning via Shielding", AAAI 2018,
https://arxiv.org/abs/1708.08611 (opened this run: the paper indeed splits preemptive
scoping from post-posed correction). But Gary's stop-gaps are registered debt with per-rule
replacement and measures (AGENTS.md:121-131, 241-246, read in source), and the plan's
Solution 4 third bullet ("explicit, bounded leaf-skill providers ... swapped 1-for-1") is
already repo policy stated more concretely ("Each goes when a learned layer owns its job in
play ... the pipe check", AGENTS.md:246). The refactor should adopt that wording, not claim
the credit for it.

### Finding 3 — The dev-build deficit is not evidence for the re-stack
Section: §2.2 item 3 ("Uncoordinated army tug-of-war ... gt1dev trails gt1 by -0.188
[-0.302, -0.078] in paired play") and Exec Summary ("the current development trajectory is
unlikely to reach Gary's core product goals").
Source: docs/PROGRESS.md:2976-3003 (read in source; the -0.188 figure and its decomposition
are quoted correctly, TODO.md:43 confirms the interval). But the same entry says "A third of
the deficit was this leak" (one builder hold) and the rest "is what the past rounds measured
one rule at a time" — the stop-gaps' accumulated measured value, plus leads the dev build
takes and does not end. Where the dev builds are further from the pros is "the windows where
its stop-gaps are off, and nearer where the learned layers play" (docs/PROGRESS.md:1966-1967).
The army tug-of-war numbers in the same item (retreats cancelled, unsieged tanks moved
mid-fight) are real faults, but the repo's account of their causes is specific and mostly
fixed or scheduled: mode draws lost their turn (fixed gt0.37dev-gt0.39dev,
docs/PROGRESS.md:2620-2679), retreats shortened in the hands (retreatfar, TODO.md:29-32),
the army's moves of a sieged line is a named open item (TODO.md:125-126). A trunk of squad
options would help here; the evidence does not say the current layers cannot.

### Finding 4 — The CalmNet "proof" is thinner than stated, and the cheap alternative is not evaluated
Section: §2.2 item 2 ("Marginal matching ≠ coherent behavior (the CalmNet proof)").
Source: the quoted rates are real but mixed across two rounds: 1.43 short orders/min is
CL281a with a new fighter's first rest of 11 s (docs/PROGRESS.md:2228-2230), while "8 s vs
8 s" is CL282a with 1.24/min (docs/PROGRESS.md:2262-2265) (read in source). The direction
head's log-loss 2.67 is against the shares' 2.73 and uniform's 2.77 (docs/PROGRESS.md:2218-2219) —
weak, but not "no more than the bins' shares", which was the first model (docs/PROGRESS.md:2197-2198).
And the repo's own later attribution shows the layer mostly moves units "alone already" and
that the lone units come from the commit layer's cluster orders and never-ordered new units
(docs/PROGRESS.md:2105-2170, 2270-2272). "Nearly random Brownian motion that scattered
units" (REFOCUS §2.2) overstates the causal chain the records support.
The diagnosis — stateless per-tick marginals drift and dither — is plausible and worth
taking seriously, but the plan never considers the standard cheap fix: condition the models
on their own recent history (already the repo's #12, TODO.md:191). Two works to A/B against
the StrategyState: Vinyals, O., Silver, D., et al. (2019), "Grandmaster level in StarCraft
II using multi-agent reinforcement learning", Nature, https://www.nature.com/articles/s41586-019-1724-z
(the plan's ref 22; recalling it this run — the policy conditions on the full history of
observations and actions, which is the property relied on here), and Chen, L., Lu, K.,
Rajeswaran, A., Lee, K., Grover, A., Laskin, M., Abbeel, P., Srinivas, A., & Mordatch, I.
(2021), "Decision Transformer: Reinforcement Learning via Sequence Modeling", NeurIPS 2021,
https://arxiv.org/abs/2106.01345 (opened this run: conditioning an autoregressive model on
past states and actions). If history conditioning alone closes the dithering, the factored
trunk earns its place on G3/G5 grounds only — which is still enough (Section 1).

### Finding 5 — §2.2 item 1 conflates three classes the repo deliberately separates
Section: §2.2 item 1 ("MacroNet required a cascade of exposure-bias patches (dice, mass,
expand_mass, parkmany, coming, comingbuild, savecoming, queued_builds, tech_min_p, gaswaits,
ownhist, pendown, builtcount, unitcount)").
Source: AGENTS.md:130-131 puts decoders and "fixes of plain bugs" outside the stop-gap
register (read in source); pendown/builtcount/unitcount/seenall are input-parity fixes held
by tests/test_inputs.py ("a model's input counted as its training data counts it ... adopted
on its own check", AGENTS.md:68); queued_builds/parkmany fix a hands hold that was worth a
third of the dev deficit (docs/PROGRESS.md:2875-2891, 2928-2978). SELF_PLAY.md's rule 4,
the repo's own investment memo, says Gary's strength came from "better and more recent
imitation data ... the decoder's exposure-bias fixes ... execution leaks found by the
records" (docs/SELF_PLAY.md:517-520, read in source) — the same items the RFC lists as
symptoms of a dead end. The Hydralisk Den example is quoted correctly (docs/PROGRESS.md:218-223,
read in source) and does support plan-state as a fix; the patch list around it does not all
belong in the same indictment.

### Finding 6 — Solution 2 mischaracterizes belief.py; the real gap is plan belief
Section: Solution 2 ("Instead of predicting only raw enemy army supply (gary/policy/belief.py)").
Source: gary/policy/belief.py:1-8 (read in source) — it already predicts "the enemy's
expected count of each army type, workers and town halls, and its army supply's median",
from fogged sightings. What is actually missing is any belief over the enemy's build or tech
line — correct in substance ("no opponent plan belief runs in play; TODO #40"), and the
plan's factored concept model is the right addition. Its distribution-shift warning is
settled and cheap: the error doubles on Gary's own games (11.7 vs 5.9 supply,
docs/PROGRESS.md:38, docs/SELF_PLAY.md:273, read in source), so calibrate on Gary's
self-play re-simulations too — the plan already says this; it should not sell it as fixing
a bare supply regressor.

### Finding 7 — Solution 4: option labels and DAgger's missing expert, with better-known mitigations
Section: Solution 4 ("Goal-conditioning ... requires relabeling pro replay datasets with
inferred option/phase tags (a noisy offline labeling step)") and its DAgger citation.
Source: the risk is real and the plan states it; two established mitigations are missing.
Hindsight relabeling — Andrychowicz, M., Wolski, F., Ray, A., Schneider, J., Fong, R.,
Welinder, P., McGrew, B., Tobin, J., Abbeel, P., & Zaremba, W. (2017), "Hindsight Experience
Replay", NIPS 2017, https://arxiv.org/abs/1707.01495 (opened this run for title and
abstract; author list recalled) — relabels trajectories with what they achieved, exactly the
escape from heuristic CONTAIN-vs-TIMING_PUSH inference; HAC, which the plan cites, is itself
"with hindsight" (Levy, A., Konidaris, G., Platt, R., & Saenko, K. (2019), "Learning
Multi-Level Hierarchies with Hindsight", ICLR 2019, https://arxiv.org/abs/1712.00948 —
opened this run; author list verified as the plan has it). And DAgger — Ross, S., Gordon,
G. J., & Bagnell, J. A. (2011), "A Reduction of Imitation Learning and Structured Prediction
to No-Regret Online Learning", AISTATS 2011, https://arxiv.org/abs/1011.0686 (opened this
run, including the body text: the quadratic T²ε bound and its tightness are as the plan's
§2.2 paraphrase says) — needs an expert labelling the learner's own visited states; a pro
replay cannot label Gary's off-distribution states. The plan should name the pseudo-expert:
the judge/response models it is already building (docs/PROGRESS.md:2811-2816), or the
filtered imitation its own H3 fallback names. Bounded leaf RL remains the open question the
plan labels it (Q5).

### Finding 8 — Solution 3's counted tables are the best-supported piece; one alternative and one caution
Section: Solution 3 (Provider A: counted pro/self-play tables with shrinkage, including
sighting-to-response tables).
Source: this matches the architecture's own design ("the strategy layer: branch rules, plus
learned, inspectable win-rate statistics", docs/ARCHITECTURE.md:127-132) and the existing
Beta-posterior selector precedent (docs/ARCHITECTURE.md:25, read in source), and it converts
the registered `answers.py` debt into its prescribed measure (AGENTS.md's answers entry;
#45, TODO.md:195). The caution is the plan's own Q4: pro response tables are observational
and confounded; Swaminathan, A., & Joachims, T. (2015), "Batch Learning from Logged Bandit
Feedback through Counterfactual Risk Minimization", JMLR 16 / ICML 2015 (the plan's ref 21;
recalling it this run — not re-opened) gives the remedy the plan names, but the repo's
paired-branch engine is the stronger instrument and should gate promotion of any counted
rule, as Solution 5.3's counterfactual verification proposes. One alternative structure
worth a slot beside "SquadOption" for the trunk: reward machines — Toro Icarte, R., Klassen,
T. Q., Valenzano, R., & McIlraith, S. A. (2022), "Reward Machines: Exploiting Reward
Function Structure in Reinforcement Learning", JAIR 73:173-208, https://doi.org/10.1613/jair.1.12440
(verified via search this run) — a finite-state reward structure with learned transitions;
it is the natural shape for "recipe card + reactive directives", and its decomposed
subpolicies map onto the plan's leaf skills. Not a replacement for the plan, a cheaper
vocabulary than 8-9 hand-chosen options, and it carries its own counterfactual semantics.

### Finding 9 — Solution 5 is premature; Solution 6 is right, with one limit
Section: Solutions 5 and 6.
Source: the taxonomy the discovery loop would extend is itself unreviewed ("Built (taxonomy
unreviewed)", docs/ARCHITECTURE.md:28; the P1b exit criteria still open, docs/PROGRESS.md:33
(read in source), and label_all.py is exactly what the plan says — a kNN on the first times
of key items in 8 minutes (taxonomy/label_all.py:5, 71-72, read in source)). The plan's own
§5.1 honesty table shows every cited invention paper (DreamCoder, LILO, VisualPredicator)
works at deterministic-verifier or tabletop scale; VisualPredicator's actual benchmark set
is broader than the table's row ("five simulated robotic domains" per its abstract —
Liang, Y., Kumar, N., Tang, H., Weller, A., Tenenbaum, J. B., Silver, T., Henriques, J. F.,
& Ellis, K. (2025), https://arxiv.org/abs/2410.23156, opened this run; authors verified,
"ICLR 2025 Spotlight" recalled, not confirmable from the arXiv page). Cut Phase 3 to the
H4 ceiling audit alone; residual concept invention belongs after the trunk has been
validated once.
Solution 6 (build templated Q&As and the counterfactual verifier now) is the plan's best
call and cheap: the records schema already carries what it needs (gary/decision_log.py:143,
"records/v1", read in source), and attribution.py already aims at "counterfactual
consistency by construction" (gary/policy/attribution.py:1-4). One limit the plan should
write into H1: flipping a cited fact F in the scorer's input proves the scorer is sensitive
to F, not that F was true or that the belief was right — a confidently wrong belief passes
the test. The live human gate it proposes covers this; keep it mandatory as written.

### Finding 10 — Scope of the inventory (§4.1) deletes measured-good code
Section: §4.1 (calm.py "DELETE / RETIRE (Phase 2)", army.py "REBUILD", posture/answers/selector
"RETIRE & REBUILD").
Source: the calm layer was folded into gt1dev on its own measured standing fixes (gt0.46dev,
docs/PROGRESS.md:2273-2274) and the plan's own §2.2 quotes it as a failure; the hunt and
caps are measured wins whose removal costs whole fractions of paired score
(docs/PROGRESS.md:2997-2999); the register says "a stop-gap that measurably wins keeps its
entry and its measure" (AGENTS.md:52). Deleting or rebuilding these is only safe behind the
same measurement discipline the plan otherwise endorses; §4.1 should mark them
"replace when the successor holds the rule's measure", per AGENTS.md:246, not delete on
schedule. (Read in source.)

### Finding 11 — Fact checks settled against source
Section: various.
- §2.2 item 4's "months of headless `gap_windows.py` / `pipe_table.py` rounds" — pipe_table.py
  is from 2026-11-17 (TODO.md:20-28, read in source); only gap_windows ran for months.
  Likewise "spotted immediately in three watched live games (TODO.md, 2026-11-12)": TODO.md:9-10
  says three live games were played and "one viewing did" show the siege gap (read in source).
- §2.2 item 4's "Only four human games were played in seven weeks (last recorded on
  2026-10-19)" — correct (docs/PROGRESS.md:1797-1798, read in source); the three live games
  of 2026-11-12 were against the computer, watched (docs/PROGRESS.md:1968-1971).
- §2.3's parenthetical "(manifests.py, though PROGRESS.md's top summary still lists rl1)" —
  settled: true. manifests.py:997-999 says tvzmodes replaced "the RL checkpoint rl1, whose
  roles have no siege, unsiege or mine", and gt1dev's chain carries tvzmodes after rl1
  (manifests.py:1393-1396), while docs/PROGRESS.md:25 and :39 still name rl1 (read in source).
- §2.4's "46 scripts in eval/" (46 .py files, counted), "ingest/macro_dataset.py imports
  nothing from gary/" (only the gary_resim binary path; read in source), intents priorities
  "3 vs. neural fight 2 vs. army 1" (gary/agent/intents.py:27-29, read in source), "92k
  replays" (docs/PROGRESS.md:32) — all correct.
- Solution 2's "Free, abundant ground-truth supervision from 19k+ modern re-simulated
  games" — overstates: 18.9k Remastered-era replays are indexed and TvZ, ZvZ, TvT are
  re-simulated (docs/PROGRESS.md:32, 60, read in source); the Protoss resim is partial.
- "~30 manifest flags" (Exec summary) — the OPTIONS table registers 154 entries
  (gary/agent/manifests.py:574, lambda entries counted); gt1dev's active chain is about 20.
  Directionally fair, imprecise.
- The §1 illustration's record snippets ("layer: style, choice: 3, by: roll") match the real
  schema exactly (settled on runs/league/AR180a/Radeon 1.2/gp1dev+archons_seed4009.records.jsonl:
  `{"kind": "decision", "layer": "style", "choice": 21, "by": "roll"}`). The document marks
  no fact "unverified"; the hedges above are the checkable ones I found and settled.

### Finding 12 — Section 7 "Verified References": spot checks agree with the record
Section: §7. Where a finding above leans on one, the status is given there. Additional
checks made for this review: Kautz, H. (2022), "The Third AI Summer", AI Magazine 43(1):105-125,
https://doi.org/10.1002/aaai.12036 (verified via search this run — year and venue as the plan
has them; the Engelmore lecture itself was 2020). Ontiveros, R. C., Giannini, F., Gori, M.,
Marra, G., & Diligenti, M. (2025), "Grounding Methods for Neural-Symbolic AI", IJCAI 2025,
https://arxiv.org/abs/2507.08216 (opened this run: authors, venue and pages verified; but the
paper is about the choice of grounding criterion in NeSy reasoners — backward-chaining
generalizations trading expressiveness for scalability — and the plan's "lifted /
parameterized grounding ... instantiating lazily per query" gloss is looser than the paper).
Delfosse, Q., Sztwiertnia, S., Rothermel, M., Stammer, W., & Kersting, K. (2024),
"Interpretable Concept Bottlenecks to Align Reinforcement Learning Agents" (SCoBots),
https://arxiv.org/abs/2401.05821 (opened this run: authors and content verified; "NeurIPS
2024" recalled, not confirmable from the arXiv page). Levy et al. (2019) HAC's author list —
"Levy, A., Konidaris, G., Platt, R., & Saenko, K." — verified correct against
https://arxiv.org/abs/1712.00948 (opened this run). Alshiekh et al. (2018) and Ross et al.
(2011) verified as cited (opened this run; see Finding 2 and Finding 7). No citation I
checked is wrong on authors or year.
