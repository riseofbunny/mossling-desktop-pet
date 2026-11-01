@echo off
rem Source-run entry for the mossling desktop pet.
rem Requires Python 3.12+ with: pip install -r requirements.txt
setlocal
set HERE=%~dp0
python -X utf8 "%HERE%MosslingDesktopPet\launcher.py" %*
endlocal
