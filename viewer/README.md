# viewer

`gary_view` plays a replay in OpenBW's game window. With a POV log it shows the game from
one player's point of view, which is how we watch Gary play: what its camera showed, where its
mouse went and where it clicked.

**Status (v1):**

- Plays any replay `gary_resim` can play, including the ones `gary_env` saves.
- `--pov <file.pov.jsonl>` follows that player's camera frame by frame and draws a cross for
  the cursor, a green ring for a left click and a red ring for a right click. The window is
  the player's screen size. There's no fog of war yet: you see everything in the camera area.
- `--record out.mp4` renders straight to a video through `ffmpeg` (must be on `PATH`), faster
  than real time. `--from`/`--to` (seconds) pick a stretch, `--speed N` makes an N× time-lapse.
- Silent: sound files aren't extracted.

The POV log comes from the human interface
([`gary/interface.py`](../gary/interface.py), `HumanInterface.save_pov`); Gary's bots write
it next to the replay when run with `--save`.

## Build

Same requirements as `env`, plus the SDL2 development package for Visual C++
(`SDL2-devel-2.32.10-VC.zip` from the [SDL releases](https://github.com/libsdl-org/SDL/releases))
unpacked into `external/sdl2`. Run `viewer\build.bat`; it produces `viewer\build\gary_view.exe`.

## Try it

```
python -m gary.bots.terran_v01 --map tests\fixtures\replays\stardata_tvz_standard_ozp3w.rep --minutes 10 --save data\interim\gary_games\gary_v01.rep
eplaysstardata_tvz_standard_ozp3w.rep --minutes 10 --save data\interim\gary_games\gary_v01.rep
viewer\build\gary_view.exe --data data\gamedata\scr --replay data\interim\gary_games\gary_v01.rep --pov data\interim\gary_games\gary_v01.pov.jsonl
viewer\build\gary_view.exe --data data\gamedata\scr --replay data\interim\gary_games\gary_v01.rep --pov data\interim\gary_games\gary_v01.pov.jsonl --record gary_v01.mp4 --to 240
```

In the window, space pauses and the slider at the bottom seeks.
