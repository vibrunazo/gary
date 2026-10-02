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
- Not yet: fog of war and human limits. Those belong to the human interface layer
  (docs/ARCHITECTURE.md §6.3), which will sit between Gary and the game.

## Build

Same requirements as `resim` (OpenBW in `external/openbw`, Visual Studio C++ tools, extracted
game data in `data/gamedata/scr`). Run `env\build.bat`; it produces `env\build\gary_env.dll`.

## Try it

```
python -m gary.bots.hello --replay-map tests\fixtures\replays\stardata_tvz_standard_ozp3w.rep --minutes 4 --save gary_hello.rep
```

`gary.bots.hello` is Gary v0: every worker mines and the main building keeps making workers.
Copy the saved replay into your StarCraft replay folder to watch it.
