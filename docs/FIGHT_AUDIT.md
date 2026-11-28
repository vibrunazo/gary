# The fight layer: an audit (2026-11-28; 0 games)

What Phase 2's intent layer could not reach is in the fight layer:
- ATTACK spells in which the main gets no commit order: 78% at gt0.56dev's §20 round (docs/TACTICAL_INTENT.md §15:
  the main in a fight is the role model's);
- deaths alone (83% under the role model's orders).

This reads both from existing games: IN307a (gt1dev+ordercommit, now gt0.56dev) and IB306a (gt1dev), 48 each,
against gz1. Their records, traces and saved role draws are joined, and 60 modern pro TvZ games are put through
eval/alone.py. No new games, no code changed.

## 1. Deaths alone

| | Gary (IN307a / IB306a) | Pros (60 modern TvZ) |
|---|---|---|
| Fighter deaths alone (eval/alone.py) | 16% / 15% | 9% |
| Fighters alone, 5-20 min samples | 0.045 / 0.044 | 0.046 |
| Ground fighters in no asked cluster | 0.078 / 0.076 | 0.068 |
| Alone deaths outnumbered (Zerg supply within 8 tiles over own) | 81% / 79% | 75% |
| The army's share at attacks (median) | 0.27 / 0.30 | 0.59 |
| Late arrivals per fighter there | 0.11 / 0.10 | 0.05 |

- Gary's fighters are not alone more often than the pros'. They die alone more often, because of what happens in the
  fight.
- In the game records, 85% of the alone deaths (IN307a) were in the role model's hands: roles 85%, the army layer 6%,
  the stim rule 4%, the intent layer 2%. 88% were outnumbered (by the records' count), against 50% of the other
  deaths.
- **The role last drawn for the unit** (its saved draws, matched to the death by time; 76% matched; the re-issue
  model's "again" and "keep" set aside):

| Last role drawn | Alone deaths (IN307a / IB306a) | Other deaths |
|---|---|---|
| fire | 40% / 41% | 51% / 53% |
| reposition | 19% / 19% | 17% / 16% |
| stand | 11% / 15% | 12% / 11% |
| pull back + retreat | **16% / 11%** | 8% / 9% |
| close in | 6% / 8% | 6% / 6% |

  A unit that dies alone was more often pulling back or retreating on its own. Among the alone deaths, eval/alone.py
  finds 34% left alone as their neighbours died.
- The last draw before a death is the re-issue model's in 62% of cases (again 35%, keep 27%): the unit kept its order.
- **Input parity of the role model can't be checked now.** tests/test_inputs.py's roles block reports "no training
  data to compare with": the response datasets were lost on 2026-11-26 and have not been rebuilt. #52 already lists
  three role inputs as known faults: extras 3-5, the unit's age, its distance to Gary's biggest bunch and that
  bunch's size. They are filled in play and 0 in the role datasets, so the model never learned them, and the
  distance to the bunch is the input a lone unit's retreat would need.

## 2. The handoff: what holds the main inside contact

The arbiter withholds every unit within 12 tiles of the fight layer's center (gary/agent/arbiter.py `_army`) whenever
the fight snapshot finds an engagement (gary/agent/fight.py `_snapshot`). The commit layer then never asks about them.

| The main's spells (IN307a) | ATTACK | GATHER | DEFEND_BASE |
|---|---|---|---|
| Spells | 943 | 974 | 666 |
| Not asked by the commit layer | 58% | 48% | 53% |
| ... with role actions during the spell | 71% | 75% | 95% |
| ... of those, skirmishes (at most 3 units an action, at most 1 death) | 24% | 29% | 11% |
| The main's units at the switch, unasked with role actions / asked | 45 / 28 | 45 / 26 | 40 / 16 |
| Role actions in those spells: fire / reposition / close in / retreat | 48 / 27 / 14 / 7% | 45 / 27 / 16 / 9% | 51 / 26 / 15 / 4% |
| Not asked, no role action (instant switches; median length) | 29% (0 s) | 25% (0 s) | 5% (5 s) |

IB306a is the same within a few points (ATTACK unasked 62%, skirmishes 24%, main 44 against 31).
- The unasked spells are the large mains' spells: 45 units, against 28 when asked. A big army is near some fight
  most of the time, so all of it within 12 tiles of the center is the role model's.
- A quarter of those fights are skirmishes: a unit or two firing, at most a death. About 10% of all ATTACK spells
  have the whole main of 45 units withheld for a skirmish.
- The role model acts per unit (median 1 unit an action). It has no say in the army's destination, so nothing joins
  the fight or leaves it as a body. That fits the army's share at attacks (0.27-0.30, the pros' 0.59) and the late
  arrivals (twice the pros').
- **The pros' side:** their army orders are commitments in contact too. §15: their switch is an order (ATTACK engage
  92-100%), and their standing ATTACK never lacks a commitment. The data the commit model learned from had its
  fights in it. Gary's play takes the commit model away exactly there. The pros' per-unit roles at their alone deaths
  need the response datasets rebuilt (above).

## 3. Options (none built; for the user's call)

1. **Input parity first (0 games).**
   - Rebuild the TvZ response datasets, with the #52 extras filled as play fills them (option dataextras, "the clean
     fix at the next imitation retrain", docs/PROGRESS.md).
   - Run tests/test_inputs.py's roles block for the role model's play-vs-data parity.
   - Retrain the role model with the extras, and compare on held-out pro units: accuracy, and the roles at the pros'
     alone deaths against Gary's table above.
   - Race-keyed: the same datasets and trainer serve every race. Cost: the response datasets' build (hours,
     overnight) and a retrain; no games.
   - Measure: the roles block passes, and held-out accuracy at least the deployed model's. A screen only after that.
2. **Withhold only the fight's members, not 12 tiles around its center** (arbiter `_army`).
   - Withhold the units `fight.members(obs)` returns: Gary's units within own_radius of the enemy fighters engaged,
     the units the role model was trained to decide for. The rest of the main stays the commit layer's.
   - The commit model learned from pros' armies with their fights in them, and with `ordercommit` its commitments are
     counted as the data's. So the decision whether the main joins a fight goes back to a learned model, not a radius.
     No new rule, race-keyed (the arbiter is shared).
   - 0 games first: re-simulate IN307a's replays with the fight snapshot, and measure how much of each unasked spell's
     main lies outside the members.
   - Pre-written measures: the share of ATTACK spells asking the main (42% now); the army's share at attacks (0.27 →
     toward 0.59; a 16-game screen resolved +0.149 in §9, and 48 resolve about +-0.04); late arrivals (0.11 → toward
     0.05); the paired score not measurably worse (48 about +-0.08).
3. **The lone retreat** (after 1; only if it remains). Alone deaths follow a retreat or pull-back about twice as often
   as other deaths.
   - With the bunch inputs learned (option 1), measure it again before anything else.
   - If it stays, give the role model's retreat a destination input (toward the main, as the pros' retreats go)
     rather than adding a rule.
   - Measure: alone deaths after a retreat or pull-back, against the pros'.

**The user's call (2026-11-28):** options 1 and 3 are parked under docs/REFOCUS.md's maintenance cap (§6 row 6). They
are real G1 micro work, but not Phase 2's deliverables, and #52 stays open. Option 2, the seam for the intent's reach,
is Phase 2's; its 0-game check is §4.

Recommended order, before that call: 1 then 2. Option 1 makes the role model's inputs right before any fight-layer change is judged.
Option 2 is the one aimed at the gap that matters most: the army's share at attacks, 0.3 against 0.59.

## 4. Option 2's 0-game check: the radius is not what withholds the main (2026-11-28)

IN307a's 48 replays were re-simulated, and each second of the main's intent spells was read (2,394 spells of a
second or more). Per second: the main cluster (army.py `_split`, as eval/alone.py `clusters`) and three rules. The
arbiter's rule now: Gary's units within 12 tiles of the fight's center. `fight.members`: the role model's snapshot,
own units within FIGHT_OWN (24 tiles) of the center, at most 64 units. "In contact": within FIGHT_NEAR (8 tiles) of an
engaged enemy fighter. A spell "would ask the main" under a rule if at some second the main has 4+ supply left after
it.

| | ATTACK | GATHER | DEFEND_BASE |
|---|---|---|---|
| Spells | 826 | 902 | 666 |
| Asked in the records | 48% | 56% | 47% |
| Would ask the main: the 12-tile radius / members / in contact | 100% / 99% / 100% | 100% / 99% / 100% | 99% / 97% / 99% |
| Unasked spells' fight seconds: the main's supply (median) | 53 | 62 | 57 |
| ... withheld by the 12-tile radius / as members / in contact (median share) | 0% / 0% / 0% | 0% / 0% / 0% | 1% / 22% / 2% |
| ... the withheld members in contact | 13% | 5% | 25% |

- **(a)** In the unasked spells' fight seconds, the main stands outside the fight, not inside its 12 tiles. By the
  median the radius withholds none of it, and the members rule would withhold more: 22% in DEFEND_BASE. The
  members are the role model's 24 tiles, wider than the arbiter's 12.
- **(b)** Under any of the three rules the main would be asked in nearly every spell, the radius included. So the
  rule is not why 52% of ATTACK spells never ask it.
- **(c)** Of the units the members rule would withhold, 5-25% are in contact: most are bystanders within 24 tiles.

**What does withhold it** (IN307a's records and traces, the ATTACK spells):

| | Asked | Unasked |
|---|---|---|
| The spell's length, median | 22.5 s | 5.5 s |
| The arbiter's turns: the role model / the army layer | 35% / 9% | **58% / 1%** |

- In `arbiter.py _army`, the fight layer goes first, and when it acts the army layer has no step that turn. The army
  side's next turn then comes after the macro's and the chores'. In a fight the role model acts almost every turn,
  with a unit or two (median one unit an action), so the army layer, and with it the main's commit question, waits.
- The question is spread over the clusters (army.py, `COMMIT_TICK // len(clusters)`). The first one comes a median
  2.3 s after the switch (p75 7.8 s). 21% of the unasked spells are shorter than that median.

**Go / no-go:**
- **No-go** for Option 2 as written. Withholding only `fight.members` would not ask the main more often, and would
  withhold more of it.
- **A different seam, for the user's call:** the army side's turn shared, not taken. When the fight layer acts, the
  army layer still asks its clusters outside the fight at its own cadence: their units are none of the fight's, and
  the hands' budget is the arbiter's either way.
  - It touches only `arbiter.py _army`, every race (the arbiter is shared). No new rule: the commit model decides as
    it does now, only on time.
  - 0 games first: count, in IN307a's traces, the army-side turns the fight layer took while a non-fight cluster
    of 4+ supply stood, and whether those turns' hands were spent (the hands' budget).
  - Pre-written for its 16-game screen: the main asked in ATTACK spells (48% now, as the pros' first tick acts at
    64%); the army's share at attacks (0.27, pros 0.59; 16 games resolve about +-0.07, 48 about +-0.04); late
    arrivals (0.11, pros 0.05); fight micro not reduced (the role model's actions a minute in fights within 10%);
    the paired score not measurably worse.
