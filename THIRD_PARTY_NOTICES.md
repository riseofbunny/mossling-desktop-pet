# Third-party notices

## Don't Starve Together assets

The mossling character, animation frames, textures (KTEX/BILD/ANIM data) and
all other assets rendered by `export_mossling.py` are derived from Don't
Starve Together and remain the property of **Klei Entertainment**. They are
generated locally from an owned game installation, are not part of this
repository, and may not be distributed on their own. See Klei's Player
Creation Guidelines: https://support.klei.com/hc/en-us/articles/360029880791-Player-Creation-Guidelines

## bunnyman-desktop-pet

The runtime modules (`desktop_pet.py`, `action_controller.py`,
`interaction_policy.py`, `cursor_play.py`, `snap_geometry.py`,
`capture_window.py`, `launcher.py`) are adapted from
https://github.com/hydrangeia/bunnyman-desktop-pet (MIT license, © the
bunnyman-desktop-pet authors) and modified for the mossling asset set.

## Python dependencies

- PySide6 / Qt 6 — LGPLv3 (used unmodified as a runtime library)
- numpy — BSD 3-Clause
- Pillow — HPND license
- PyInstaller — GPL with bootloader exception (build-time only)

## Format references

Binary layout knowledge for ANIM/BILD/KTEX was checked against the community
tools DstAnimTool (CN-DST-DEVELOPER) and ktools (nsimplex).
