"""Gary v0.1, Terran: a scripted one-barracks expand into marines, played with human hands.

Everything goes through the human interface (gary/interface.py): Gary sees with fog of war and a
reaction delay, moves the camera with location hotkeys and the minimap, selects by clicking and
drag boxes (no multi-building selection, like the real game), and spends APM.

Plan (the taxonomy's most common TvZ Terran opening, simplified):
  supply 9 depot, 11 barracks, 15 Command Center at the natural, 16 depot, 18 and 20 barracks;
  then constant SCVs (two bases), marines from every barracks, depots before supply runs out,
  and an attack-move to the enemy start with every 16 marines.
Not yet: gas, academy, medics, upgrades, scouting, defense, retreating, micro.

    python -m gary.bots.terran_v01 --map path/to/map.scx --minutes 10
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field

from gary import commands as C
from gary.env import Game, GameError
from gary.interface import PROFILES, HumanInterface, screen_of
from gary.mapinfo import Base, MapInfo

DEPOT, RAX, CC, SCV, MARINE = C.SUPPLY_DEPOT, C.BARRACKS, C.COMMAND_CENTER, C.SCV, C.MARINE
COST = {DEPOT: 100, RAX: 150, CC: 400, SCV: 50, MARINE: 50}
SIZE = {DEPOT: (3, 2), RAX: (4, 3), CC: (4, 3)}          # tiles
BUILD_ORDER = [(9, DEPOT, "main"), (11, RAX, "main"), (15, CC, "natural"),
               (16, DEPOT, "main"), (18, RAX, "main"), (20, RAX, "main")]
MAX_SCVS = 36
WAVE = 16
LOC_MAIN, LOC_NATURAL = 2, 3          # F2, F3
HK_CC = [4, 5]                        # one hotkey per Command Center (buildings can't share one)
HK_RAX = [6, 7, 8, 9]
HK_ARMY = [1, 2]
BUSY_ORDERS = {30, 31, 33}            # placing / constructing a building
IDLE = 3                              # order "PlayerGuard": standing around


@dataclass
class Task:
    kind: str                          # "build", "hotkey_building", "attack"
    unit_type: int = -1
    where: str = "main"
    stage: str = "start"
    data: dict = field(default_factory=dict)
    started: int = 0


class TerranGary:
    def __init__(self, hi: HumanInterface, mapinfo: MapInfo):
        self.hi = hi
        self.map = mapinfo
        self.slot = hi.slot
        obs = hi.observe()
        cc = next(u for u in obs["units"] if u["owner"] == self.slot and u["type"] == CC)
        self.main = mapinfo.base_near((cc["x"], cc["y"]))
        self.natural = mapinfo.natural_of(self.main)
        self.enemy_starts = mapinfo.enemy_starts(self.main) or mapinfo.starts
        self.rally = self._toward_center(self.natural.center, 6 * 32)
        self.order_step = 0
        self.task: Task | None = None
        self.hotkeyed: dict[int, int] = {}        # building tag -> hotkey
        self.rallied: set[int] = set()
        self.reserved: list[tuple[int, int, int]] = []   # (unit type, tile x, tile y) being built
        self.reserved_at: dict[tuple[int, int, int], int] = {}
        self.attacks_sent = 0
        self.army_sent: set[int] = set()
        self.setup_done = False
        self.ignore_idle_until: dict[int, int] = {}   # workers we failed to send: retry later

    # --- geometry ------------------------------------------------------------------------

    def _toward_center(self, p: tuple[int, int], d: int) -> tuple[int, int]:
        cx, cy = self.map.size[0] / 2, self.map.size[1] / 2
        n = math.dist(p, (cx, cy)) or 1
        return (round(p[0] + (cx - p[0]) * d / n), round(p[1] + (cy - p[1]) * d / n))

    def _spot(self, unit_type: int, base: Base, builder: int) -> tuple[int, int] | None:
        """A free spot near the base, on the side away from the minerals."""
        mx = sum(x for x, _ in base.minerals) / len(base.minerals)
        my = sum(y for _, y in base.minerals) / len(base.minerals)
        ax = base.center[0] + (base.center[0] - mx) * 0.9
        ay = base.center[1] + (base.center[1] - my) * 0.9
        w, h = SIZE[unit_type]
        cands = []
        for ty in range(int(ay // 32) - 16, int(ay // 32) + 16):
            for tx in range(int(ax // 32) - 16, int(ax // 32) + 16):
                cands.append((math.dist((tx * 32 + w * 16, ty * 32 + h * 16), (ax, ay)), tx, ty))
        for _, tx, ty in sorted(cands):
            if any(abs(tx - rx) < SIZE[rt][0] + 1 and abs(ty - ry) < SIZE[rt][1] + 1 for rt, rx, ry in self.reserved):
                continue
            # keep a walkable gap around buildings: the bigger footprint must fit too
            if self.hi.game.can_place(self.slot, unit_type, tx, ty, builder) and \
                    self.hi.game.can_place(self.slot, unit_type, tx - 1, ty - 1, builder) and \
                    self.hi.game.can_place(self.slot, unit_type, tx + 1, ty + 1, builder):
                return tx, ty
        return None

    # --- camera ---------------------------------------------------------------------------

    def _look_at(self, obs: dict, where: str) -> bool:
        """Make sure the base is on screen. True if it already is (no action taken)."""
        base = self.main if where == "main" else self.natural
        if screen_of(obs, *base.center):
            return True
        loc = LOC_MAIN if where == "main" else LOC_NATURAL
        if loc in self.hi.camera_locations:
            self.hi.camera_location(loc)
        else:
            self.hi.camera_minimap(*base.center)
        return False

    # --- main loop ------------------------------------------------------------------------

    def act(self) -> None:
        hi = self.hi
        if hi.pending:
            return
        obs = hi.observe()
        if not self.setup_done:
            return self._setup(obs)
        me = obs["me"]
        mine = [u for u in obs["units"] if u["owner"] == self.slot]
        done = [u for u in mine if u["completed"]]
        self._release_reservations(mine)

        if self.task:
            return self._run_task(obs, mine)

        # idle workers go back to mining (game start, after building something)
        idle = [u for u in done if u["type"] == SCV and u["order"] == IDLE and screen_of(obs, u["x"], u["y"])
                and self.ignore_idle_until.get(u["tag"], 0) <= hi.frame]
        if idle:
            self.task = Task("mine", data={"tags": [u["tag"] for u in idle]}, started=hi.frame)
            return
        # new buildings get a hotkey and a rally point
        for b in done:
            if b["type"] in (CC, RAX) and b["tag"] not in self.hotkeyed:
                self.task = Task("hotkey_building", b["type"], data={"tag": b["tag"], "x": b["x"], "y": b["y"]},
                                 started=hi.frame)
                return
        # build order, then supply
        supply = me["supply_used"]
        # minerals already promised to buildings ordered but not started yet
        budget = me["minerals"] - sum(COST[ut] for ut, *_ in self.reserved)
        due = self.order_step < len(BUILD_ORDER) and supply >= BUILD_ORDER[self.order_step][0]
        if due:
            _, ut, where = BUILD_ORDER[self.order_step]
            if budget >= COST[ut] - 30:
                self.order_step += 1
                self.task = Task("build", ut, where, started=hi.frame)
                return
        # supply coming: unfinished depots (8) and Command Centers (10) count already
        coming = sum(8 for u in mine if u["type"] == DEPOT and not u["completed"])
        coming += sum(10 for u in mine if u["type"] == CC and not u["completed"])
        coming += sum(8 for ut, *_ in self.reserved if ut == DEPOT)
        n_prod = sum(1 for u in mine if u["type"] in (CC, RAX) and u["completed"])
        if (me["supply_max"] + coming < 200 and self.order_step >= 2
                and me["supply_max"] + coming - supply <= 2 + 2 * n_prod and budget >= 100):
            self.task = Task("build", DEPOT, "main", started=hi.frame)
            return
        # floating money: more barracks (up to 8)
        n_rax = sum(1 for u in mine if u["type"] == RAX) + sum(1 for ut, *_ in self.reserved if ut == RAX)
        if self.order_step >= len(BUILD_ORDER) and budget >= 400 and n_rax < 8:
            self.task = Task("build", RAX, "main", started=hi.frame)
            return
        # attack with every full wave
        marines = [u for u in done if u["type"] == MARINE and u["tag"] not in self.army_sent]
        if len(marines) >= WAVE:
            self.task = Task("attack", started=hi.frame)
            return
        if due:
            return              # save up for the next building instead of spending on units
        self._produce(obs, done, me, budget)

    def _setup(self, obs: dict) -> None:
        """Remember the main as F2; the main CC gets its hotkey through the normal path."""
        if not self._look_at(obs, "main"):
            return
        self.hi.camera_location_set(LOC_MAIN)
        self.setup_done = True

    def _produce(self, obs: dict, done: list[dict], me: dict, budget: int) -> None:
        """Cycle building hotkeys: SCVs from Command Centers, marines from barracks."""
        scvs = sum(1 for u in obs["units"] if u["owner"] == self.slot and u["type"] == SCV)
        if me["supply_used"] >= me["supply_max"]:
            return
        # keep one unit queued in each building (a human keeps queues short to save money)
        idle = [u for u in done if u["type"] in (CC, RAX) and self.hotkeyed.get(u["tag"], -1) >= 0
                and u.get("queue", 0) == 0]
        for b in idle:
            want = SCV if b["type"] == CC else MARINE
            if want == SCV and scvs >= MAX_SCVS:
                continue
            if budget < COST[want]:
                return
            hk = self.hotkeyed[b["tag"]]
            if obs["selection"] != [b["tag"]]:
                self.hi.hotkey_recall(hk)
            else:
                self.hi.train(want)
            return

    # --- tasks --------------------------------------------------------------------------------

    def _run_task(self, obs: dict, mine: list[dict]) -> None:
        t = self.task
        if self.hi.frame - t.started > 24 * 40:     # give up on anything stuck for 40 s
            if t.kind == "hotkey_building":
                self.hotkeyed[t.data["tag"]] = -1    # live without a hotkey for this one
            self.task = None
            return
        if t.kind == "build":
            return self._task_build(obs, mine, t)
        if t.kind == "hotkey_building":
            return self._task_hotkey(obs, t)
        if t.kind == "attack":
            return self._task_attack(obs, mine, t)
        if t.kind == "mine":
            return self._task_mine(obs, mine, t)

    def _task_mine(self, obs: dict, mine: list[dict], t: Task) -> None:
        """Select idle workers (drag box around them, or a click) and right-click a mineral field."""
        hi = self.hi
        tags = set(t.data["tags"])
        workers = [u for u in mine if u["tag"] in tags and screen_of(obs, u["x"], u["y"])]
        if not workers:
            self.task = None
            return
        if t.stage == "start":
            pts = [screen_of(obs, u["x"], u["y"]) for u in workers]
            # a drag box only picks up own units: a plain click on a worker standing on a
            # mineral field can select the field instead
            hi.box(max(0, min(p[0] for p in pts) - 10), max(0, min(p[1] for p in pts) - 10),
                   min(hi.p.viewport[0] - 1, max(p[0] for p in pts) + 10),
                   min(hi.p.viewport[1] - 1, max(p[1] for p in pts) + 10))
            t.stage = "send"
            return
        # the box may have caught busy workers too (e.g. one walking off to build): never send
        # those back to mining; select an idle one with a click instead
        if not obs["selection"] or not set(obs["selection"]) <= tags:
            if t.stage == "send":
                t.stage = "click"
                hi.click(*screen_of(obs, workers[0]["x"], workers[0]["y"]))
                return
            for tag in tags:
                self.ignore_idle_until[tag] = hi.frame + 24 * 20
            self.task = None
            return
        fields = [m for b in self.map.bases for m in b.minerals if screen_of(obs, *m)]
        if fields:
            w = workers[0]
            m = min(fields, key=lambda m: math.dist(m, (w["x"], w["y"])))
            hi.right_click(*screen_of(obs, *m))
        # whether or not it worked, don't fixate on these workers: look again in 20 s
        for tag in tags:
            self.ignore_idle_until[tag] = hi.frame + 24 * 20
        self.task = None

    def _pick_worker(self, obs: dict, mine: list[dict]) -> dict | None:
        cands = [u for u in mine if u["type"] == SCV and u["completed"] and u["order"] not in BUSY_ORDERS
                 and screen_of(obs, u["x"], u["y"])]
        return min(cands, key=lambda u: math.dist((u["x"], u["y"]), self.main.center)) if cands else None

    def _task_build(self, obs: dict, mine: list[dict], t: Task) -> None:
        hi = self.hi
        if t.stage == "start":                      # get a worker from the main
            if not self._look_at(obs, "main"):
                return
            w = t.data.get("worker")
            if w and obs["selection"] == [w]:
                t.stage = "travel" if t.where == "natural" else "place"
                return
            w = self._pick_worker(obs, mine)
            if not w:
                self.task = None
                return
            t.data["worker"] = w["tag"]
            p = screen_of(obs, w["x"], w["y"])
            hi.click(*p)
            return
        if t.stage == "travel":                      # walk the worker to the natural
            hi.minimap_right_click(*self.natural.center)
            t.stage = "wait_arrival"
            return
        if t.stage == "wait_arrival":
            w = next((u for u in mine if u["tag"] == t.data["worker"]), None)
            if not w:
                self.task = None
                return
            if math.dist((w["x"], w["y"]), self.natural.center) > 6 * 32:
                return
            if not self._look_at(obs, "natural"):
                return
            if LOC_NATURAL not in hi.camera_locations:
                hi.camera_location_set(LOC_NATURAL)
                return
            t.stage = "place"
            return
        if t.stage == "place":
            budget = obs["me"]["minerals"] - sum(COST[ut] for ut, *_ in self.reserved)
            if budget < COST[t.unit_type]:
                return                                  # wait for money with the worker selected
            base = self.main if t.where == "main" else self.natural
            if "spot" not in t.data:
                if not self._look_at(obs, t.where):
                    return
                spot = base.tile if t.unit_type == CC else self._spot(t.unit_type, base, t.data["worker"])
                if not spot:
                    self.task = None
                    return
                t.data["spot"] = spot
            spot = t.data["spot"]
            w, h = SIZE[t.unit_type]
            p = screen_of(obs, spot[0] * 32 + 16, spot[1] * 32 + 16)
            if not p:                                   # the spot is off screen: look there first
                if t.data.get("looked"):
                    self.task = None
                    return
                t.data["looked"] = True
                hi.camera_minimap(spot[0] * 32 + w * 16, spot[1] * 32 + h * 16)
                return
            if hi.build(t.unit_type, *p).accepted:
                self.reserved.append((t.unit_type, *spot))
                self.reserved_at[(t.unit_type, *spot)] = hi.frame
                self.task = None

    def _task_hotkey(self, obs: dict, t: Task) -> None:
        hi = self.hi
        tag = t.data["tag"]
        where = "natural" if math.dist((t.data["x"], t.data["y"]), self.natural.center) < 10 * 32 else "main"
        if obs["selection"] == [tag]:
            if t.stage == "start":
                pool = HK_CC if t.unit_type == CC else HK_RAX
                used = set(self.hotkeyed.values())
                hk = next((k for k in pool if k not in used), None)
                if hk is None:
                    self.hotkeyed[tag] = -1
                    self.task = None
                    return
                hi.hotkey_set(hk)
                self.hotkeyed[tag] = hk
                t.stage = "rally"
                return
            if t.stage == "rally":                      # CCs rally to minerals (auto-mine), barracks forward
                if t.unit_type == CC:
                    base = self.main if where == "main" else self.natural
                    m = base.minerals[len(base.minerals) // 2]
                    p = screen_of(obs, *m)
                    if p:
                        hi.right_click(*p)
                else:
                    hi.minimap_right_click(*self.rally)
                self.task = None
                return
        if not screen_of(obs, t.data["x"], t.data["y"]):
            hi.camera_minimap(t.data["x"], t.data["y"])
            return
        hi.click(*screen_of(obs, t.data["x"], t.data["y"]))

    def _task_attack(self, obs: dict, mine: list[dict], t: Task) -> None:
        """Gather marines at the rally point with drag boxes, hotkey them, attack-move."""
        hi = self.hi
        waiting = [u for u in mine if u["type"] == MARINE and u["completed"] and u["tag"] not in self.army_sent]
        if not waiting:
            self.attacks_sent += 1
            self.task = None
            return
        # look where the waiting marines are (normally the rally point)
        cx = sorted(u["x"] for u in waiting)[len(waiting) // 2]
        cy = sorted(u["y"] for u in waiting)[len(waiting) // 2]
        if not screen_of(obs, cx, cy):
            hi.camera_minimap(cx, cy)
            return
        target = self.enemy_starts[self.attacks_sent % len(self.enemy_starts)]
        group = t.data.get("group", 0)
        if t.stage in ("start", "box"):
            here = [u for u in waiting if screen_of(obs, u["x"], u["y"])]
            if not here or group >= len(HK_ARMY) * 3:
                self.attacks_sent += 1
                self.task = None
                return
            xs = [screen_of(obs, u["x"], u["y"]) for u in here]
            x0 = max(0, min(p[0] for p in xs) - 12)
            y0 = max(0, min(p[1] for p in xs) - 12)
            x1 = min(hi.p.viewport[0] - 1, max(p[0] for p in xs) + 12)
            y1 = min(hi.p.viewport[1] - 1, max(p[1] for p in xs) + 12)
            hi.box(x0, y0, x1, y1)
            t.stage = "attack"
            return
        if t.stage == "attack":
            sent = [tag for tag in obs["selection"]]
            hi.minimap_command(C.ORDER_ATTACK_MOVE, *target)
            self.army_sent.update(sent)
            t.data["group"] = group + 1
            t.stage = "box"

    def _release_reservations(self, mine: list[dict]) -> None:
        """A reserved spot is free again once its building exists, or after 40 s if it never
        appeared (the worker was interrupted, or the spot got blocked)."""
        keep = []
        for r in self.reserved:
            ut, tx, ty = r
            cx, cy = tx * 32 + SIZE[ut][0] * 16, ty * 32 + SIZE[ut][1] * 16
            built = any(u["type"] == ut and math.dist((u["x"], u["y"]), (cx, cy)) < 48 for u in mine)
            if not built and self.hi.frame - self.reserved_at.get(r, 0) < 24 * 40:
                keep.append(r)
        self.reserved = keep


def _terran_slot(game) -> int:
    """The slot that owns a Command Center: TerranGary plays Terran. (Slot order is the engine's,
    not the order of the races list, so bind by what's actually on the map.)"""
    obs = game.observe()
    slots = {p["slot"] for p in obs["players"]}
    for u in obs["units"]:
        if u["type"] == CC and u["owner"] in slots:
            return u["owner"]
    raise SystemExit("no Terran (Command Center) player in this game")


def _report(hi: HumanInterface, game) -> None:
    obs = game.observe()
    me = next(p for p in obs["players"] if p["slot"] == hi.slot)
    count = lambda t: sum(1 for u in obs["units"] if u["owner"] == hi.slot and u["type"] == t)
    print(f"{hi.frame // 1440}:00  supply {me['supply_used']:.0f}/{me['supply_max']:.0f}  "
          f"minerals {me['minerals']}  SCVs {count(SCV)}  marines {count(MARINE)}  "
          f"CC {count(CC)}  rax {count(RAX)}  depots {count(DEPOT)}  "
          f"APM {round(hi.stats['actions'] / max(1, hi.frame / 1440))}", flush=True)


def play(map_path: str, minutes: float, seed: int | None, save: str, opponent: str = "idle") -> None:
    """Play on a headless OpenBW game (gary/env.py): fast, deterministic, saves a replay."""
    races = ["T", "Z"]
    with Game.new(map_path, races, ["Gary v0.1 (T)", "Idle (Z)"], seed=seed) as game:
        mapinfo = MapInfo.from_game(game)
        hi = HumanInterface(game, _terran_slot(game), PROFILES["b_rank"], seed=1)
        gary = TerranGary(hi, mapinfo)
        end = int(minutes * 60 * 24)
        while hi.frame < end:
            gary.act()
            hi.step(2)
            if hi.frame % (24 * 60) < 2:
                _report(hi, game)
        game.save_replay(save)
        pov = save[:-4] + ".pov.jsonl" if save.endswith(".rep") else save + ".pov.jsonl"
        hi.save_pov(pov)
        print(f"saved {save} and {pov}")


def play_live(pipe: str, minutes: float, profile: str, pov: str | None) -> None:
    """Play in a live StarCraft: Remastered client through the bridge (adapters/scr_bridge).

    Gary plays the client's local player (the bridge only accepts that slot), so it must be
    Terran. act() latency is calibrated from the adapter's reported latency_frames so the
    human interface lands actions when they really take effect. The client writes its own
    replay on match end.
    """
    from gary.scr_env import ScrGame
    game = ScrGame.connect(pipe)
    hi: HumanInterface | None = None
    try:
        # wait for a game to start and for Gary's Command Center to exist
        while True:
            st = game.status()
            slot = st.get("local_player", -1)
            if st.get("in_game") and slot >= 0:
                obs = game.observe()
                if any(u["owner"] == slot and u["type"] == CC for u in obs["units"]):
                    break
            print("waiting for a live game with Gary's Command Center (start one)...")
            game.step(24)
        st = game.status()
        mapinfo = MapInfo.from_game(game)
        hi = HumanInterface(game, slot, PROFILES[profile], seed=1)
        print(f"playing slot {slot} | act() latency calibrated to {hi.act_latency_frames} frames "
              f"(adapter reported latency_frames={st.get('latency_frames')})", flush=True)
        gary = TerranGary(hi, mapinfo)
        end = hi.frame + int(minutes * 60 * 24)
        while hi.frame < end:
            gary.act()
            hi.step(2)                       # waits for the live game to advance
            if hi.frame % (24 * 60) < 2:
                _report(hi, game)
    except GameError as e:
        print(f"game over / bridge lost: {e}")
    finally:
        if pov and hi is not None:
            try:
                hi.save_pov(pov)
                print(f"saved {pov}")
            except Exception as e:
                print(f"could not save pov: {e}")
        game.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", help="a .scm/.scx map (or a pre-1.18 replay) for headless play")
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--save", default="gary_v01.rep")
    ap.add_argument("--live", action="store_true",
                    help="play in a live SC:R client via the bridge instead of headless OpenBW")
    ap.add_argument("--pipe", default=r"\\.\pipe\gary_scr", help="bridge named pipe (with --live)")
    ap.add_argument("--profile", default="b_rank", choices=sorted(PROFILES))
    ap.add_argument("--pov", help="where to save the point-of-view log (default: alongside --save)")
    args = ap.parse_args()
    if args.live:
        play_live(args.pipe, args.minutes, args.profile,
                  args.pov or "gary_v01_live.pov.jsonl")
    else:
        if not args.map:
            ap.error("--map is required unless --live")
        play(args.map, args.minutes, args.seed, args.save)


if __name__ == "__main__":
    main()
