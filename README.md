# Mobility

A portable Windows toolbox: folders of shortcuts plus a launcher app.

**Start it:** double-click `Launch Mobility.bat` (needs Python 3 with tkinter, the standard python.org install).
**Make an .exe:** double-click `build.bat` (installs PyInstaller, writes `Mobility.exe` here). Keep the exe next to the `Res`, `Custom Tools` and `Administrative Tools` folders. The exe has your icon built in.
Right-click the blue header for *Create desktop shortcut*, *Add custom tool*, *Repair folder icons* and *About*.

## Download and setup

Just download [Mobility.exe](https://github.com/icreaterandomapps/Mobility/releases/download/v1.0/Mobility.exe) and run it. No setup, No installation.

## Launcher
- ~120 tools in 7 categories: System, Administrative, Storage, Network, Power & Mobility, Repair, Utilities
- Search (Ctrl+F), Enter to run, right-click for favorites / run as admin / copy command
- Dangerous actions (network reset, reboot to UEFI) ask first
- Your own shortcuts in `Administrative Tools` and `Custom Tools` are picked up automatically and listed under *All*; *Add custom tool* (right-click the header) adds others
- Folder icons: the old `desktop.ini` files had a hard-coded path (`C:\Users\USer\Downloads\mobilty\Res\...`). The launcher re-points them to wherever the folder lives now (also from the header's right-click menu).

## Files
- `Mobility.pyw` - the GUI
- `mobility_tools.py` - tool catalog and engine
- `build.bat` - builds `Mobility.exe` with PyInstaller
- `Res/icons/` - your original .ico files (network, shell32, imageres...) kept as-is
- `Res/ui/` - small PNGs made from your Res icons, used in the launcher
- `Res/mobility.ico` - launcher / exe icon (plus your original folder icons)
- `Custom Tools/` - drop your own tools here
