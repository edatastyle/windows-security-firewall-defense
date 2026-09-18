"""
Admin privilege checks and elevation helpers for Windows.
"""
import ctypes
import sys
import os
from pathlib import Path


def is_admin() -> bool:
    """Return True if the current process is running with administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_as_admin():
    """
    Relaunch the current script/executable with administrator privileges.
    Returns True if elevation was requested (caller should exit), False otherwise.
    """
    if is_admin():
        return False

    try:
        # Path of the current executable or script
        if getattr(sys, "frozen", False):
            # Running as PyInstaller bundle
            script = sys.executable
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        else:
            script = str(Path(sys.argv[0]).resolve())
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])

        # ShellExecuteW with "runas" verb
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", script, params, None, 1
        )
        if int(ret) <= 32:
            # Failed to elevate
            return False
        return True  # Elevation requested; original process should exit
    except Exception:
        return False


def require_admin(exit_on_fail: bool = True) -> bool:
    """
    Ensure the process is elevated. If not, attempt elevation.
    Returns True if admin, False if not (and may exit).
    """
    if is_admin():
        return True
    if run_as_admin():
        # Elevation launched; exit current process
        sys.exit(0)
    if exit_on_fail:
        # Could not elevate
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                "This application requires Administrator privileges.\n"
                "Please right-click and select 'Run as administrator'.",
                "Administrator Required",
                0x10,  # MB_ICONERROR
            )
        except Exception:
            pass
        sys.exit(1)
    return False
