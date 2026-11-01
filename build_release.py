"""Assemble the portable release: export assets, run PyInstaller, verify.

Usage:
    python build_release.py --game "C:\\...\\Don't Starve Together"
    python build_release.py --skip-export   # reuse already exported assets

Output: dist/MosslingDesktopPet/ (exe + _internal + manifest.json + frames)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PET_DIR = HERE / 'MosslingDesktopPet'
DIST = HERE / 'dist'
WORK = HERE / 'build' / 'pyinstaller'

REQUIRED_ASSETS = [
    PET_DIR / 'manifest.json',
    PET_DIR / 'frames' / 'normal' / 'idle__5',
    PET_DIR / 'frames' / 'yule' / 'idle__5',
    PET_DIR / 'frames' / 'effects' / 'spin',
]


def run(cmd: list[str]) -> None:
    print('+', ' '.join(str(part) for part in cmd), flush=True)
    result = subprocess.run(cmd, cwd=HERE)
    if result.returncode != 0:
        raise SystemExit(f'command failed with exit code {result.returncode}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--game', type=Path,
                        help="Path to the local Don't Starve Together installation")
    parser.add_argument('--skip-export', action='store_true',
                        help='Skip export; reuse the already generated assets')
    args = parser.parse_args(argv)

    missing = [path for path in REQUIRED_ASSETS if not path.is_dir() and not path.is_file()]
    if args.skip_export and missing:
        raise SystemExit('--skip-export but assets are missing: '
                         + ', '.join(str(path) for path in missing))
    if not args.skip_export:
        export = [sys.executable, str(HERE / 'export_mossling.py')]
        if args.game is not None:
            export += ['--game', str(args.game)]
        run(export)

    if not args.skip_export or missing:
        missing = [path for path in REQUIRED_ASSETS if not path.is_dir() and not path.is_file()]
        if missing:
            raise SystemExit('export did not produce: '
                             + ', '.join(str(path) for path in missing))

    if DIST.exists():
        shutil.rmtree(DIST)
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(DIST),
         '--workpath', str(WORK), str(HERE / 'mossling.spec')])

    smoke = DIST / 'MosslingDesktopPet' / 'MosslingDesktopPet.exe'
    if smoke.is_file():
        report = HERE / 'smoke-report.json'
        run([str(smoke), '--smoke-test', '--test-report', str(report)])
        print(f'smoke report: {report}')
    print(f'release ready: {DIST / "MosslingDesktopPet"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
