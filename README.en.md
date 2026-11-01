# DST Mossling Desktop Pet

A Don't Starve Together mossling (moose/goose chick) that lives in a corner of
your desktop. It reacts to taps, feeding, dragging and nearby cursors, fidgets
on its own, takes naps — and throws a whirlwind tantrum when provoked.

> This repository contains **code and build scripts only**. The animation
> frames, manifest.json and every other game-derived asset are rendered
> offline from your own installed game by `export_mossling.py` (Klei owns the
> art; it is not committed here and not distributed).

## Highlights

- Tap different body parts, double-click for dances and take-offs.
- Press `F` to feed veggies; occasionally triggers the full **whirlwind**
  combo (angry build + lightning FX + dizzy recovery).
- Scroll down three notches to freeze, drag-and-shake to knock it back,
  four quick taps for hit sparks; it re-hatches after a knockout.
- Context menu: feeding, companionship pace, auto-idle antics, window snapping,
  skin switching (normal / **Winters' Feast**), capture window for OBS.

## Build from source

Windows x64, Python 3.12+:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe export_mossling.py --game "C:\Program Files (x86)\Steam\steamapps\common\Don't Starve Together"
.\.venv\Scripts\python.exe build_release.py --skip-export
```

The release lands in `dist\MosslingDesktopPet\` (exe + `_internal` +
manifest.json + frames). To run from source instead: export once, then
`start_pet.bat`.

## License & assets

The MIT license (see [LICENSE](LICENSE)) covers the original code only.
Don't Starve Together characters, animation frames and all other game assets
belong to Klei Entertainment. Free, non-commercial fan project, unaffiliated
with and not endorsed by Klei. Runtime architecture inspired by and adapted
from [bunnyman-desktop-pet](https://github.com/hydrangeia/bunnyman-desktop-pet).
