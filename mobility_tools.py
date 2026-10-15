"""Mobility - tool catalog and engine (no GUI code in here).

Everything the launcher can do lives in this file so it can be tested without
a display: the built-in catalog, scanning your own shortcuts, launching
(normal / elevated), repairing the folder icons, and making a desktop shortcut.
"""
import ctypes
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

IS_WIN = os.name == "nt"
FROZEN = getattr(sys, "frozen", False)
# next to the .exe when built with PyInstaller, otherwise next to this file
ROOT = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
BUNDLE = getattr(sys, "_MEIPASS", ROOT)  # where PyInstaller unpacks bundled assets


def asset(*parts):
    """Path of a bundled asset (Res/...), falling back to the folder next to the exe."""
    for base in (BUNDLE, ROOT):
        p = os.path.join(base, *parts)
        if os.path.exists(p):
            return p
    return os.path.join(ROOT, *parts)


GOD_GUID = "{ED7BA470-8E54-465E-825C-99712043E01C}"

SETTINGS_FILE = os.path.join(ROOT, "settings.json")
CUSTOM_FILE = os.path.join(ROOT, "custom_tools.json")
SCAN_DIRS = ("Administrative Tools", "Custom Tools")
SCAN_EXT = (".lnk", ".exe", ".bat", ".cmd", ".url", ".msc", ".cpl")

# folder -> icon (inside Res) used for the custom folder icons
FOLDER_ICONS = {
    ".": "mobility.ico",
    "Administrative Tools": "2.ico",
    "Control Device": "1.ico",
    "Custom Tools": "icons/imageres_115.ico",
    "GodMode": "god.ico",
    "Res": "fo.ico",
}


@dataclass
class Tool:
    name: str
    cat: str
    desc: str
    exe: str
    args: str = ""
    admin: bool = False       # always needs elevation
    confirm: str = ""         # non-empty -> ask this question before running
    source: str = "builtin"   # builtin | custom | folder
    aliases: tuple = field(default_factory=tuple)

    @property
    def command(self):
        return f"{self.exe} {self.args}".strip()


# --------------------------------------------------------------------------
# catalog helpers
# --------------------------------------------------------------------------
def _msc(name, cat, desc, f, admin=False, aliases=()):
    return Tool(name, cat, desc, "mmc.exe", f, admin, aliases=tuple(aliases))


def _cpl(name, cat, desc, f, aliases=()):
    return Tool(name, cat, desc, "control.exe", f, aliases=tuple(aliases))


def _uri(name, cat, desc, uri):
    return Tool(name, cat, desc, uri)


def _app(name, cat, desc, exe, args="", admin=False, aliases=(), confirm=""):
    return Tool(name, cat, desc, exe, args, admin, confirm, aliases=tuple(aliases))


def _cmd(name, cat, desc, line, admin=False, keep=True, confirm=""):
    """Run a command line in a visible cmd window (stays open with /k)."""
    return Tool(name, cat, desc, "cmd.exe",
                f'/s /{"k" if keep else "c"} "{line}"', admin, confirm)


def _ps(name, cat, desc, line, admin=False):
    return Tool(name, cat, desc, "powershell.exe",
                f'-NoExit -NoProfile -Command "{line}"', admin)


def _mobility_center_exe():
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    real = os.path.join(sysroot, "System32", "mblctr.exe")
    local = os.path.join(ROOT, "Control Device", "mblctr.exe")
    if not os.path.exists(real) and os.path.exists(local):
        return local
    return "mblctr.exe"


def builtin_tools():
    T = []
    add = T.append

    # ---- System -----------------------------------------------------------
    S = "System"
    add(_app("System Information", S, "Hardware, drivers and software summary", "msinfo32.exe",
             aliases=("System Information",)))
    add(_cpl("System Properties", S, "Computer name, performance, remote, protection", "sysdm.cpl"))
    add(_app("Environment Variables", S, "Edit user and system PATH & variables",
             "rundll32.exe", "sysdm.cpl,EditEnvironmentVariables"))
    add(_app("Task Manager", S, "Processes, performance and startup", "taskmgr.exe"))
    add(_msc("Device Manager", S, "Drivers and hardware devices", "devmgmt.msc"))
    add(_app("Registry Editor", S, "Browse and edit the registry", "regedit.exe", aliases=("Registry Editor",)))
    add(_app("System Configuration", S, "msconfig - boot options and startup services",
             "msconfig.exe", aliases=("System Configuration",)))
    add(_app("Windows Features", S, "Turn Windows features on or off", "optionalfeatures.exe"))
    add(_app("About Windows", S, "Version and build (winver)", "winver.exe"))
    add(_app("DirectX Diagnostics", S, "dxdiag - graphics, sound and input info", "dxdiag.exe"))
    add(_cpl("Programs and Features", S, "Uninstall or change desktop programs", "appwiz.cpl"))
    add(_uri("Installed Apps", S, "Settings > Apps > Installed apps", "ms-settings:appsfeatures"))
    add(_uri("Startup Apps", S, "Choose which apps start at sign-in", "ms-settings:startupapps"))
    add(_msc("Local Group Policy Editor", S, "gpedit (Pro/Enterprise editions only)", "gpedit.msc", True))
    add(_msc("Local Security Policy", S, "Password, audit and user-rights policy", "secpol.msc", True))
    add(_cpl("Date and Time", S, "Clock, time zone, internet time", "timedate.cpl"))
    add(_cpl("Region", S, "Formats, location and administrative language", "intl.cpl"))
    add(_cpl("Sound", S, "Playback, recording and sound schemes", "mmsys.cpl"))
    add(_cpl("Mouse", S, "Buttons, pointers, wheel", "main.cpl"))
    add(_cpl("User Accounts", S, "Classic user account manager", "nusrmgr.cpl"))

    # ---- Administrative -----------------------------------------------------
    A = "Administrative"
    add(_msc("Computer Management", A, "Event viewer, disks, services in one console", "compmgmt.msc",
             aliases=("Computer Management",)))
    add(_msc("Event Viewer", A, "System and application logs", "eventvwr.msc", aliases=("Event Viewer",)))
    add(_msc("Services", A, "Start, stop and configure services", "services.msc", aliases=("services",)))
    add(_msc("Task Scheduler", A, "Scheduled tasks", "taskschd.msc", aliases=("Task Scheduler",)))
    add(_msc("Performance Monitor", A, "Counters, data collector sets", "perfmon.msc",
             aliases=("Performance Monitor",)))
    add(_app("Resource Monitor", A, "Live CPU, disk, network and memory by process", "resmon.exe",
             aliases=("Resource Monitor",)))
    add(_app("Reliability Monitor", A, "Stability history and failures", "perfmon.exe", "/rel"))
    add(_msc("Local Users and Groups", A, "Manage local accounts (Pro and above)", "lusrmgr.msc", True))
    add(_msc("Shared Folders", A, "Shares, sessions and open files", "fsmgmt.msc"))
    add(_msc("Certificates", A, "Current user certificate store", "certmgr.msc"))
    add(_msc("Windows Firewall (Advanced)", A, "Inbound/outbound rules", "wf.msc",
             aliases=("Windows Defender Firewall with Advanced Security",)))
    add(_msc("Print Management", A, "Printers, drivers and servers", "printmanagement.msc",
             aliases=("Print Management",)))
    add(_app("Component Services", A, "COM+ and DCOM configuration", "dcomcnfg.exe",
             aliases=("Component Services",)))
    add(_app("ODBC Data Sources (64-bit)", A, "ODBC drivers and DSNs", "odbcad32.exe",
             aliases=("ODBC Data Sources (64-bit)",)))
    add(_app("ODBC Data Sources (32-bit)", A, "32-bit ODBC drivers and DSNs",
             r"%SystemRoot%\SysWOW64\odbcad32.exe", aliases=("ODBC Data Sources (32-bit)",)))
    add(_app("iSCSI Initiator", A, "Connect to iSCSI storage", "iscsicpl.exe", aliases=("iSCSI Initiator",)))
    add(_msc("Hyper-V Manager", A, "Virtual machines (Hyper-V enabled editions)", "virtmgmt.msc",
             aliases=("Hyper-V Manager",)))
    add(_app("Hyper-V Quick Create", A, "Create a VM from a template", "VMCreate.exe", aliases=("VMCreate",)))
    add(_msc("Disk Management", A, "Partitions, volumes and drive letters", "diskmgmt.msc",
             aliases=("Create and format hard disk partitions",)))
    add(_uri("Windows Security", A, "Defender, firewall and device security", "windowsdefender:"))

    # ---- Storage ------------------------------------------------------------
    D = "Storage"
    add(_app("Disk Cleanup", D, "Remove temporary and system files", "cleanmgr.exe", aliases=("Disk Cleanup",)))
    add(_app("Optimize Drives", D, "Defragment HDDs / TRIM SSDs", "dfrgui.exe", aliases=("dfrgui",)))
    add(_uri("Storage Sense", D, "Automatic cleanup and storage usage", "ms-settings:storagesense"))
    add(_app("Open Temp Folder", D, "Look at %TEMP% in Explorer", "explorer.exe", "%TEMP%"))
    add(_ps("Empty Recycle Bin", D, "Delete everything in the Recycle Bin for all drives",
            "Clear-RecycleBin -Force; Write-Host 'Recycle Bin emptied.'"))
    add(_cmd("Clear User Temp Files", D, "Delete files in %TEMP% (files in use are skipped)",
             r'del /q /f /s "%TEMP%\*" 2>nul & echo. & echo Done - files in use were skipped.',
             confirm="Delete the files in your TEMP folder?\n(Files in use are skipped.)"))
    add(_ps("Disk Health", D, "Physical disk health and status",
            "Get-PhysicalDisk | Select FriendlyName,MediaType,HealthStatus,OperationalStatus,@{n='SizeGB';e={[math]::Round($_.Size/1GB)}} | Format-Table -Auto"))
    add(_ps("Drive Space", D, "Free / used space per drive",
            "Get-PSDrive -PSProvider FileSystem | Select Name,@{n='UsedGB';e={[math]::Round($_.Used/1GB,1)}},@{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}} | Format-Table -Auto"))
    add(_cmd("Check Disk (read-only scan)", D, "chkdsk C: without fixing anything", "chkdsk C:", True))
    add(_app("Create Restore Point", D, "System Protection tab", "SystemPropertiesProtection.exe"))
    add(_app("Recovery Drive", D, "Build a USB recovery drive", "RecoveryDrive.exe", admin=True,
             aliases=("RecoveryDrive",)))

    # ---- Network -------------------------------------------------------------
    N = "Network"
    add(_cpl("Network Connections", N, "Adapters (ncpa.cpl)", "ncpa.cpl"))
    add(_cpl("Network and Sharing Center", N, "Classic network overview", "/name Microsoft.NetworkAndSharingCenter"))
    add(_cmd("IP Configuration", N, "ipconfig /all", "ipconfig /all"))
    add(_cmd("Flush DNS Cache", N, "ipconfig /flushdns", "ipconfig /flushdns"))
    add(_cmd("Renew IP Address", N, "Release then renew DHCP lease", "ipconfig /release & ipconfig /renew", True))
    add(_cmd("Reset Network Stack", N, "Winsock + TCP/IP reset (needs reboot)",
             "netsh winsock reset & netsh int ip reset & echo. & echo Restart Windows to finish.", True,
             confirm="Reset Winsock and TCP/IP?\nYou will need to restart Windows afterwards."))
    add(_cmd("Active Connections", N, "netstat -ano", "netstat -ano"))
    add(_cmd("Ping Test", N, "Ping 1.1.1.1 and google.com", "ping -n 4 1.1.1.1 & ping -n 4 google.com"))
    add(_cmd("Trace Route", N, "tracert to 1.1.1.1", "tracert -d 1.1.1.1"))
    add(_cmd("Public IP Address", N, "Ask ifconfig.me for your public IP", "curl -s https://ifconfig.me & echo."))
    add(_cmd("Saved Wi-Fi Networks", N, "List remembered Wi-Fi profiles", "netsh wlan show profiles"))
    add(_cmd("Wi-Fi Report", N, "Build a WLAN history report", "netsh wlan show wlanreport", True))
    add(_app("Edit Hosts File", N, "Open hosts in Notepad as administrator", "notepad.exe",
             r"%SystemRoot%\System32\drivers\etc\hosts", True))
    add(_app("Remote Desktop", N, "mstsc - connect to another PC", "mstsc.exe"))
    add(_cpl("Windows Firewall", N, "Basic firewall settings", "firewall.cpl"))
    add(_uri("Wi-Fi Settings", N, "Settings > Network > Wi-Fi", "ms-settings:network-wifi"))
    add(_uri("VPN Settings", N, "Settings > Network > VPN", "ms-settings:network-vpn"))

    # ---- Power & Mobility -------------------------------------------------------
    P = "Power & Mobility"
    add(_app("Mobility Center", P, "Brightness, volume, battery, presentation, sync",
             _mobility_center_exe()))
    add(_cpl("Power Options", P, "Power plans and lid / button actions", "powercfg.cpl"))
    add(_cmd("Battery Report", P, "Health & capacity history, opens in browser",
             r'powercfg /batteryreport /output "%USERPROFILE%\battery-report.html" & start "" "%USERPROFILE%\battery-report.html"',
             keep=False))
    add(_cmd("Energy Report", P, "60-second power efficiency diagnosis",
             r'powercfg /energy /output "%USERPROFILE%\energy-report.html" & start "" "%USERPROFILE%\energy-report.html"',
             True))
    add(_cmd("Sleep Study", P, "Modern Standby drain report",
             r'powercfg /sleepstudy /output "%USERPROFILE%\sleepstudy.html" & start "" "%USERPROFILE%\sleepstudy.html"'))
    add(_cmd("What Is Keeping My PC Awake?", P, "powercfg /requests", "powercfg /requests", True))
    add(_cmd("Available Sleep States", P, "powercfg /a", "powercfg /a"))
    add(_cmd("Power Plans", P, "List power schemes", "powercfg /list"))
    add(_uri("Battery Saver", P, "Settings > Power & battery", "ms-settings:batterysaver"))
    add(_uri("Display Settings", P, "Resolution, scaling, brightness", "ms-settings:display"))
    add(_app("Project to a Display", P, "Duplicate / extend / second screen only", "displayswitch.exe"))
    add(_app("Presentation Settings", P, "Turn off screen saver and sound for talks", "presentationsettings.exe"))
    add(_uri("Bluetooth & Devices", P, "Settings > Bluetooth", "ms-settings:bluetooth"))
    add(_uri("Airplane Mode", P, "Settings > Network > Airplane mode", "ms-settings:network-airplanemode"))
    add(_uri("Mobile Hotspot", P, "Share your connection", "ms-settings:network-mobilehotspot"))

    # ---- Repair ---------------------------------------------------------------------
    R = "Repair"
    add(_cmd("System File Checker", R, "sfc /scannow", "sfc /scannow", True))
    add(_cmd("DISM - Check Health", R, "Quick image corruption check", "DISM /Online /Cleanup-Image /CheckHealth", True))
    add(_cmd("DISM - Restore Health", R, "Repair the Windows image (slow)",
             "DISM /Online /Cleanup-Image /RestoreHealth", True))
    add(_app("Memory Diagnostics Tool", R, "Test RAM on next restart", "mdsched.exe",
             aliases=("Memory Diagnostics Tool",), admin=True))
    add(_cmd("Restart Explorer", R, "Fix a frozen taskbar or desktop",
             "taskkill /f /im explorer.exe & start explorer.exe", keep=False))
    add(_cmd("Restart Print Spooler", R, "Clear stuck print jobs' service",
             "net stop spooler & net start spooler", True))
    add(_cmd("Group Policy Update", R, "gpupdate /force", "gpupdate /force"))
    add(_cmd("Rebuild Icon Cache", R, "Refresh shell icons", "ie4uinit.exe -show", keep=False))
    add(_uri("Windows Update", R, "Check for updates", "ms-settings:windowsupdate"))
    add(_uri("Recovery Options", R, "Reset this PC, advanced startup", "ms-settings:recovery"))
    add(_cmd("Restart to Advanced Startup", R, "Reboot into the recovery menu",
             "shutdown /r /o /t 5", keep=False,
             confirm="Restart this PC into Advanced Startup in 5 seconds?\nSave your work first."))
    add(_cmd("Restart to UEFI/BIOS", R, "Reboot into firmware setup",
             "shutdown /r /fw /t 5", keep=False,
             confirm="Restart this PC into UEFI/BIOS setup in 5 seconds?\nSave your work first."))

    # ---- Utilities ----------------------------------------------------------------------
    U = "Utilities"
    add(_app("God Mode", U, "Every Control Panel setting in one list",
             "explorer.exe", f"shell:::{GOD_GUID}"))
    add(_app("Control Panel", U, "Classic Control Panel", "control.exe"))
    add(_uri("Settings", U, "Windows Settings", "ms-settings:"))
    add(_app("Command Prompt", U, "cmd", "cmd.exe"))
    add(_app("Command Prompt (Admin)", U, "Elevated cmd", "cmd.exe", admin=True))
    add(_app("PowerShell", U, "Windows PowerShell", "powershell.exe"))
    add(_app("PowerShell (Admin)", U, "Elevated PowerShell", "powershell.exe", admin=True))
    add(_app("Windows Terminal", U, "wt (Windows 10 1903+ with Store app)", "wt.exe"))
    add(_app("Calculator", U, "calc", "calc.exe"))
    add(_app("Notepad", U, "Plain text editor", "notepad.exe"))
    add(_app("Paint", U, "mspaint", "mspaint.exe"))
    add(_app("Character Map", U, "Find and copy special characters", "charmap.exe"))
    add(_app("Snipping Tool", U, "Screenshots", "snippingtool.exe"))
    add(_app("On-Screen Keyboard", U, "osk", "osk.exe"))
    add(_app("Magnifier", U, "Zoom the screen", "magnify.exe"))
    add(_app("Quick Assist", U, "Remote help session", "quickassist.exe"))
    add(_app("Startup Folder", U, "Files that launch at sign-in", "explorer.exe", "shell:startup"))
    add(_app("AppData Folder", U, "Open %APPDATA%", "explorer.exe", "%APPDATA%"))
    add(_app("This Toolbox Folder", U, "Open the Mobility folder", "explorer.exe", ROOT))
    return T


# --------------------------------------------------------------------------
# user content: scanned shortcuts + custom tools
# --------------------------------------------------------------------------
def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def scan_shortcuts(builtins, root=ROOT):
    """Pick up your own shortcuts/programs from Administrative Tools and Custom Tools.
    Anything whose name matches a built-in tool (or its alias) is skipped."""
    known = set()
    for t in builtins:
        known.add(_norm(t.name))
        known.update(_norm(a) for a in t.aliases)
    found = []
    for d in SCAN_DIRS:
        folder = os.path.join(root, d)
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder), key=str.lower):
            base, ext = os.path.splitext(fn)
            if ext.lower() not in SCAN_EXT or fn.lower() == "desktop.ini":
                continue
            if _norm(base) in known:
                continue
            found.append(Tool(base, "Your Shortcuts", f"From the '{d}' folder",
                              os.path.join(folder, fn), source="folder"))
    return found


def load_custom(path=CUSTOM_FILE):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            rows = json.load(fh)
    except (OSError, ValueError):
        return []
    out = []
    for r in rows if isinstance(rows, list) else []:
        try:
            out.append(Tool(r["name"], r.get("cat") or "Custom", r.get("desc", ""),
                            r["exe"], r.get("args", ""), bool(r.get("admin")), source="custom"))
        except (KeyError, TypeError):
            continue
    return out


def save_custom(tools, path=CUSTOM_FILE):
    rows = [dict(name=t.name, cat=t.cat, desc=t.desc, exe=t.exe, args=t.args, admin=t.admin)
            for t in tools if t.source == "custom"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)


def load_all_tools(root=ROOT):
    b = builtin_tools()
    return b + scan_shortcuts(b, root) + load_custom(os.path.join(root, "custom_tools.json"))


# --------------------------------------------------------------------------
# settings (favorites etc.)
# --------------------------------------------------------------------------
def load_settings(path=SETTINGS_FILE):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data, path=SETTINGS_FILE):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------
# launching
# --------------------------------------------------------------------------
def launch(tool, admin=False):
    """Start a tool through ShellExecute (handles .msc/.cpl/URIs/folders and UAC)."""
    exe = os.path.expandvars(tool.exe)
    args = os.path.expandvars(tool.args)
    admin = admin or tool.admin
    if not IS_WIN:
        return f"[not Windows - would run{' as admin' if admin else ''}] {exe} {args}".strip()
    fn = ctypes.windll.shell32.ShellExecuteW
    fn.restype = ctypes.c_void_p
    rc = fn(None, "runas" if admin else "open", exe, args or None, None, 1) or 0
    if rc <= 32:
        if admin and rc in (5, 1223):
            raise OSError("Administrator permission was declined.")
        raise OSError(f"Windows could not start '{tool.name}' (code {rc}). "
                      "It may not exist on this edition of Windows.")
    return f"Started {tool.name}" + (" as administrator" if admin else "")


# --------------------------------------------------------------------------
# folder icons (desktop.ini stores an absolute path, so it breaks when moved)
# --------------------------------------------------------------------------
def _read_ini(path):
    try:
        raw = open(path, "rb").read()
    except OSError:
        return ""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    return raw.decode("utf-8-sig", "replace")


def _write_ini(path, text):
    try:
        text.encode("ascii")
        data = text.encode("ascii")
    except UnicodeEncodeError:
        data = b"\xff\xfe" + text.encode("utf-16-le")
    with open(path, "wb") as fh:
        fh.write(data)


def _attrib(args):
    if IS_WIN:
        subprocess.run(["attrib"] + args, creationflags=0x08000000,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wanted_line(root, icon):
    return "IconResource=" + os.path.join(root, "Res", *icon.split("/")) + ",0"


def icons_need_repair(root=ROOT):
    for folder, icon in FOLDER_ICONS.items():
        d = root if folder == "." else os.path.join(root, folder)
        if not os.path.isdir(d):
            continue
        ini = os.path.join(d, "desktop.ini")
        want = _wanted_line(root, icon).lower()
        have = [l.strip().lower() for l in _read_ini(ini).splitlines()]
        if want not in have:
            return True
    return False


def repair_folder_icons(root=ROOT):
    """Point every folder's desktop.ini at this copy of Res\\*.ico. Returns a list of messages."""
    notes = []
    for folder, icon in FOLDER_ICONS.items():
        d = root if folder == "." else os.path.join(root, folder)
        if not os.path.isdir(d):
            continue
        ini = os.path.join(d, "desktop.ini")
        line = _wanted_line(root, icon)
        try:
            _attrib(["-s", "-h", ini])
            text = _read_ini(ini)
            if not text.strip():
                text = "[.ShellClassInfo]\r\n" + line + "\r\n"
                if folder == ".":
                    text += "InfoTip=Mobility - Windows tools launcher\r\n"
            elif re.search(r"(?im)^\s*IconResource\s*=.*$", text):
                text = re.sub(r"(?im)^\s*IconResource\s*=.*$", lambda m: line, text, count=1)
            else:
                text = re.sub(r"(?im)^\[\.ShellClassInfo\]\s*$",
                              lambda m: "[.ShellClassInfo]\r\n" + line, text, count=1)
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
            _write_ini(ini, text)
            _attrib(["+s", "+h", ini])
            _attrib(["+s", d])
            notes.append(f"{folder if folder != '.' else '(main folder)'}: ok")
        except OSError as e:
            notes.append(f"{folder}: {e}")
    if IS_WIN:
        try:  # tell Explorer to refresh icons
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
        except Exception:
            pass
    return notes


# --------------------------------------------------------------------------
# desktop shortcut + system summary
# --------------------------------------------------------------------------
def create_desktop_shortcut(root=ROOT):
    if not IS_WIN:
        raise OSError("Desktop shortcuts can only be created on Windows.")
    if FROZEN:
        exe, arg, icon = sys.executable, "", sys.executable
    else:
        exe = sys.executable
        if os.path.basename(exe).lower() == "python.exe":
            w = os.path.join(os.path.dirname(exe), "pythonw.exe")
            if os.path.exists(w):
                exe = w
        arg = '"' + os.path.join(root, "Mobility.pyw") + '"'
        icon = os.path.join(root, "Res", "mobility.ico")
    q = lambda s: s.replace("'", "''")
    ps = ("$d=[Environment]::GetFolderPath('Desktop');"
          "$p=Join-Path $d 'Mobility.lnk';"
          "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($p);"
          f"$s.TargetPath='{q(exe)}';$s.Arguments='{q(arg)}';"
          f"$s.WorkingDirectory='{q(root)}';$s.IconLocation='{q(icon)},0';"
          "$s.Description='Mobility - Windows tools launcher';$s.Save();Write-Output $p")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps], capture_output=True,
                       text=True, creationflags=0x08000000)
    if r.returncode != 0:
        raise OSError(r.stderr.strip() or "PowerShell failed")
    return r.stdout.strip()


class _PowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_uint32), ("BatteryFullLifeTime", ctypes.c_uint32)]


def system_summary():
    if not IS_WIN:
        return "Not running on Windows - tools will not launch"
    host = os.environ.get("COMPUTERNAME", "this PC")
    try:
        ver = "11" if sys.getwindowsversion().build >= 22000 else "10"
    except Exception:
        ver = ""
    bat = "no battery"
    try:
        st = _PowerStatus()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)) and st.BatteryFlag != 128:
            pct = "?" if st.BatteryLifePercent == 255 else f"{st.BatteryLifePercent}%"
            bat = f"battery {pct}" + (", plugged in" if st.ACLineStatus == 1 else "")
    except Exception:
        pass
    return f"{host}  -  Windows {ver}  -  {bat}"
