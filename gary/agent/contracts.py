"""The strategic trunk's typed contracts (docs/REFOCUS.md §4.2, with round two's amendments; Phase 1 step 7b).

Every race and matchup alike: a provider with nothing to go on (no model for the matchup, before its first sample, a
table cell under its support floor) answers NotEnoughEvidence, never invented odds or counts. What a decision read is
named by its records' ids (gary/decision_log.py `id` and `parent`): the belief's record, the observation's frame, the
sighting state's looks.

Round two's amendments, here: the trunk's step and the scorer take the player's own state (OwnContext: units, research,
money, map, time), as a milestone's completion, a directive's exit and the scorer's backoff need it; the belief
provider is built for a side's slot and the enemy's race and has reset() (a paired branch replays from a copy);
TacticalIntent carries the record that triggered it; the sighting state (gary/policy/sightings.py SightingState) keeps
per region its last look and cover, so a stale look is not "never checked" (SightingView is its snapshot here).

Not frozen yet (§4.2's Schema Freeze Rule): until every matchup runs through the real providers in
tests/test_matchups.py and the sighting schema covers each race's means of scouting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class NotEnoughEvidence:
    """A provider's answer when it has nothing to go on: who said it and why."""
    provider: str
    why: str
    record_id: int | None = None


@dataclass(frozen=True)
class OwnContext:
    """The player's own state at a decision: what the scorer's cells and a directive's exit read."""
    frame: int
    race: str
    enemy: str | None
    matchup: str | None
    map_name: str | None
    units: dict[str, int]                       # own type name -> count (finished or not)
    researched: frozenset[str]                  # research and upgrades ordered
    minerals: int
    gas: int
    supply_used: int
    supply_max: int


@dataclass(frozen=True)
class SightingView:
    """A snapshot of gary/policy/sightings.py SightingState: what was seen, where it was confirmed absent, what was
    never looked at, and per region its last look (frame, cover)."""
    seen: dict[int, tuple[int, int]]            # enemy type -> (most in sight at once, last frame)
    confirmed_absent: dict[int, int]            # region -> frame of its last look that found none of the plan's tech
    unscouted: frozenset[int]                   # regions never looked at
    regions: dict[int, tuple[int, float]]       # region -> (frame of its last look, its cover then)
    looked: bool                                # Gate 1's split (train/plan_belief.py is_looked)
    plan_first: int | None                      # frame the plan's tech was first seen


@dataclass(frozen=True)
class PlanBelief:
    frame: int
    plan_probs: dict[str, float]                # joint P(enemy plan | seen) over taxonomy/plans.py
    tech_probs: dict[str, float]                # its tech part, summed
    sightings: SightingView | None
    evidence: dict[str, Any]                    # what it read: the observation's frame, the sighting looks' frames
    record_id: int                              # its record (kind "plan_belief")
    model: str                                  # the pinned model's name
    expected_counts: dict[int, float] | None = None     # (§4.2's fields this provider doesn't fill)
    workers_est: float | None = None
    town_halls_est: float | None = None


@dataclass(frozen=True)
class Directive:
    id: str                                     # e.g. "PREP_VS_LURKER"
    params: dict[str, Any]
    items: tuple[tuple[str, int], ...]          # (item name, how many in all), in order
    started_frame: int
    exit_condition: str
    trigger_record_id: int                      # the strategy_state record that started it


@dataclass
class StrategyState:
    card_id: str | None                         # the recipe card's (gary/policy/card.py), or None
    opening_card: list[dict[str, Any]]          # its milestones
    adherence_mode: Literal["strict", "reactive"]
    active_directives: list[Directive] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)   # transitions, each with its record id


@dataclass(frozen=True)
class CandidateBranch:
    name: str
    params: dict[str, Any]


@dataclass(frozen=True)
class BranchScore:
    """What pros do, kept apart from how their games ended (never decided on) and from what the branch does for Gary
    (paired branches, eval/pairs.py: not yet)."""
    p: float                                    # P_pro(branch | belief, context)
    lo: float                                   # its 95% interval (Wilson, on games)
    hi: float
    n: int                                      # modern games in the cell used
    cell: str                                   # the cell used, after backoff
    level: int                                  # 0: the full cell; k: the k-th parent
    pro_won_if_taken: float | None              # secondary context, printed only
    pro_won_if_not: float | None
    base_p: float | None = None                 # the contrast cell's P_pro (the same cell, a low belief)
    base_hi: float | None = None                # its interval's top
    take: bool = False                          # the table's rule: P_pro >= threshold, its interval above the contrast's
    base_cell: str | None = None                # the contrast cell's key


@dataclass(frozen=True)
class TacticalIntent:
    id: str                                     # persistent identity across frames
    kind: str                                   # e.g. "DEFEND_HOME", "PUSH_OR_PRESSURE"
    units: tuple[int, ...]
    target: tuple[int, int] | None
    params: dict[str, Any]
    started_frame: int
    end_condition: str
    preempt_by: tuple[str, ...]
    lease_id: str
    trigger_record_id: int                      # the record that triggered it
    attention_hint: float | None = None


class PlanBeliefProvider(Protocol):
    """Built for a side's slot and the enemy's race."""
    def update(self, obs: dict, ctx: OwnContext) -> PlanBelief | NotEnoughEvidence | None: ...   # None: no new sample
    def reset(self) -> None: ...


class BranchScorerProvider(Protocol):
    # swappable: "pro_freq_table" (gary/agent/selector.py ProFrequencyScorer); later "ebm_ga2m", "interaction_tree"
    def score(self, belief: PlanBelief, strategy: StrategyState, ctx: OwnContext,
              candidates: list[CandidateBranch]) -> dict[str, BranchScore | NotEnoughEvidence]: ...


class StrategyTrunkProvider(Protocol):
    def step(self, belief: PlanBelief | NotEnoughEvidence, current: StrategyState, ctx: OwnContext,
             rng) -> tuple[StrategyState, list[dict[str, Any]]]: ...
