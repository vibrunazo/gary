# env

`gary_env` is a headless Brood War game (on [OpenBW](https://github.com/OpenBW/openbw)) that
Python code can play through a small C API. The Python side is [`gary/env.py`](../gary/env.py).

**Status (v0):**

- Starts a game on a pre-1.18 replay's map, with that replay's players and races (its commands
  aren't played).
- Steps the game, takes each player's commands in the replay command format
  ([`gary/commands.py`](../gary/commands.py)), and returns the full game state as JSON.
- Saves the game as a replay that StarCraft (including Remastered) and `gary_resim` can play
  back. Re-simulating a saved game reproduces it exactly.
- Answers "what's under this pixel" and "what does this drag box select" the way the game
  does (v1: each sprite's clickable rectangle, draw depth, then smaller footprint), so the human
  interface can turn screen clicks into commands.

Gary never calls this directly: it goes through the human interface,
[`gary/interface.py`](../gary/interface.py) (v1): camera and screen-pixel clicks, Fitts's-law
mouse travel with scatter, 12-unit selections and hotkeys, an APM token bucket, fog of war,
hidden enemy HP unless selected, and a reaction-time delay on everything Gary sees. Profiles
(`b_rank`, `b_rank_widescreen`, `c_rank`) hold placeholder numbers until they're fitted from
replay and camera-logger data.

## Build

Same requirements as `resim` (OpenBW in `external/openbw`, Visual Studio C++ tools, extracted
game data in `data/gamedata/scr`). Run `env\build.bat`; it produces `env\build\gary_env.dll`.

## Try it

```
python -m gary.bots.hello --replay-map tests\fixtures\replays\stardata_tvz_standard_ozp3w.rep --minutes 4 --save gary_hello.rep
```

`gary.bots.hello` is Gary v0: every worker mines and the main building keeps making workers,
all through the human interface.
Copy the saved replay into your StarCraft replay folder to watch it.
