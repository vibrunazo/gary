"""The live path without a client: every race's dev build played through gary.play's play_live on a stand-in for the
bridge, a headless game that answers only the bridge's own methods (gary/scr_env.py ScrGame's protocol) as a bridge
built before the newest unit fields would. What a real client adds (its timing, its memory layout) is the bridge's
own check (adapters/scr_bridge/README.md); what this holds is Gary's side of it: the map found from what the client
shows, its terrain and hash the headless game's, a Gary of each race built and playing its opening.
Needs the game data (skips without it). About a minute.

Run: python -m pytest tests/test_live.py   (or plain: python tests/test_live.py)
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

MAP = REPO / "tests" / "fixtures" / "replays" / "stardata_tvz_standard_ozp3w.rep"
MINUTES = 4
PLAYS = {"T": "gt1dev", "Z": "gz1dev", "P": "gp1dev"}
ENEMY = {"T": "Z", "Z": "P", "P": "T"}
NEW_FIELDS = ("stim", "ammo", "ammo_max")


def loopback(game, slot: int):
    """ScrGame over a headless game: the bridge's requests answered by gary.env.Game, and nothing but them."""
    from gary.scr_env import ScrGame

    class Loopback(ScrGame):
        def _call(self, method: str, **a):
            if method == "status":
                return {"in_game": True, "local_player": slot, "latency_frames": game.command_delay - 1}
            if method == "observe":
                obs = game.observe()
                for u in obs["units"]:
                    for k in NEW_FIELDS:
                        u.pop(k, None)
                return obs
            if method == "act":
                assert a["slot"] == slot, "a live client acts as its local player only"
                return 1 if game.act(a["slot"], bytes.fromhex(a["hex"])) is not False else 0
            if method == "step":
                return game.step(a["frames"])
            if method == "unit_at":
                return game.unit_at(a["slot"], a["x"], a["y"])
            if method == "box_select":
                return game.box_select(a["slot"], a["x0"], a["y0"], a["x1"], a["y1"])
            if method == "unit_type":
                return game.unit_type_of(a["tag"])
            if method == "can_place":
                return 1 if game.can_place(a["slot"], a["unit_type"], a["tile_x"], a["tile_y"], a["builder"]) else 0
            if method == "depot_spot_ok":
                return 1 if game.depot_spot_ok(a["tile_x"], a["tile_y"]) else 0
            if method == "start_locations":
                return game.start_locations()
            raise AssertionError(f"not a bridge method: {method}")

    return Loopback(None)


def live_game(race: str) -> dict:
    """MINUTES of a race's dev build on the live path, against an idle enemy: what it saw of the map and what it made."""
    import numpy as np
    from gary.agent.manifests import build_gary
    from gary.env import LIVE_COMMAND_DELAY, Game
    from gary.mapinfo import MapInfo
    from gary.play import play_live, slot_of
    from gary.race import Race
    game = Game.new(MAP, [race, ENEMY[race]], ["Gary", "Idle"], seed=7, command_delay=LIVE_COMMAND_DELAY)
    slot = slot_of(game, race)
    live = loopback(game, slot)
    seen = {}

    def make(hi, mapinfo, r):
        g = build_gary(hi, mapinfo, PLAYS[r], verbose=False)
        seen.update(gary=g, mapinfo=mapinfo, hi=hi)
        return g
    make.races, make.race = set(PLAYS), race
    with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as said:
        truth = (MapInfo.from_game(game).hash, game.terrain(), game.unit_type_info(Race.of(race).town_hall))
        found = live.map_path
        same_terrain = all(np.array_equal(a, b) for a, b in zip(live.terrain(), truth[1]))
        same_info = live.unit_type_info(Race.of(race).town_hall) == truth[2]
        play_live("", MINUTES, "pro", str(Path(tmp) / "live.pov.jsonl"), make, game=live)
        saved = sorted(p.name for p in Path(tmp).iterdir())
    R = Race.of(race)
    mine = [u for u in game.observe()["units"] if u["owner"] == slot]
    out = {"found": found, "hash": seen["mapinfo"].hash, "true_hash": truth[0], "same_terrain": same_terrain,
           "same_info": same_info, "matchup": seen["gary"].matchup, "said": said.getvalue(), "saved": saved,
           "workers": sum(u["type"] == R.worker for u in mine),
           "buildings": sum(u["type"] in R.sizes and u["type"] not in R.town_halls for u in mine)}
    game.close()
    return out


def check(race: str) -> None:
    try:
        from gary.env import Game
        Game.new(MAP, ["T", "Z"], seed=1).close()
    except Exception as e:                      # no game data or env DLL here
        print(f"skip: {e}")
        return
    r = live_game(race)
    assert "game over / bridge lost" not in r["said"], r["said"][-400:]
    assert r["found"] is not None and Path(r["found"]).resolve() == MAP.resolve(), f"the map found: {r['found']}"
    assert r["hash"] == r["true_hash"] is not None, "the models' map isn't the headless game's"
    assert r["same_terrain"] and r["same_info"], "the map's terrain or unit data differ from the headless game's"
    assert r["matchup"] == "v".join(sorted((race, ENEMY[race]))), r["matchup"]
    assert r["workers"] >= 12 and r["buildings"] >= 1, f"by {MINUTES}:00: {r['workers']} workers, {r['buildings']} buildings"
    assert {"live.pov.jsonl", "live.records.jsonl", "live.trace.jsonl"} <= set(r["saved"]), r["saved"]


def test_live_terran():
    check("T")


def test_live_zerg():
    check("Z")


def test_live_protoss():
    check("P")


def test_ctrl_click_selects_the_type_in_view():
    """ScrGame.type_select against the headless game's, on a start's workers (fewer than 12: the same set)."""
    try:
        from gary.env import Game
        game = Game.new(MAP, ["T", "Z"], seed=7)
    except Exception as e:
        print(f"skip: {e}")
        return
    from gary.play import slot_of
    from gary.race import Race
    slot = slot_of(game, "T")
    live = loopback(game, slot)
    game.step(8)
    units = [u for u in game.observe()["units"] if u["owner"] == slot]
    scv = next(u for u in units if u["type"] == Race.of("T").worker)
    hall = next(u for u in units if u["type"] in Race.of("T").town_halls)
    view = (scv["x"] - 320, scv["y"] - 240, scv["x"] + 320, scv["y"] + 240)
    assert sorted(live.type_select(slot, scv["x"], scv["y"], view)) == sorted(game.type_select(slot, scv["x"], scv["y"], view))
    assert len(live.type_select(slot, scv["x"], scv["y"], view)) == 4
    assert live.type_select(slot, hall["x"], hall["y"], view) == game.type_select(slot, hall["x"], hall["y"], view) == []
    game.close()


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"FAIL {name}: {type(e).__name__}: {e}")
                failed += 1
    sys.exit(1 if failed else 0)
