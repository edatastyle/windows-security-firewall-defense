"""
Centralized path management for the application.
All data files live next to the executable (or in the script directory during development).
"""
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """Return the directory containing the application executable or main script."""
    if getattr(sys, "frozen", False):
        # PyInstaller / frozen executable
        return Path(sys.executable).resolve().parent
    # Development: assume project root is two levels up from this file
    # src/core/paths.py -> project root
    return Path(__file__).resolve().parent.parent.parent


def get_data_dir() -> Path:
    """Directory for user-editable data files (allowed-apps, blocklist, logs)."""
    d = get_app_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_scripts_dir() -> Path:
    """Directory containing the original PowerShell scripts."""
    # Prefer bundled scripts next to exe, fall back to project scripts/
    candidates = [
        get_app_dir() / "scripts",
        get_app_dir().parent / "scripts",  # development layout
        Path(__file__).resolve().parent.parent.parent / "scripts",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fallback: create and return
    d = get_app_dir() / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Convenience paths
APP_DIR = get_app_dir()
DATA_DIR = get_data_dir()
SCRIPTS_DIR = get_scripts_dir()

ALLOWED_APPS_FILE = DATA_DIR / "allowed-apps.txt"
BLOCKLIST_FILE = DATA_DIR / "malicious-ips.txt"
LOG_FILE = DATA_DIR / "security-firewall.log"
STATUS_FILE = DATA_DIR / "firewall-status.txt"
PS1_SCRIPT = SCRIPTS_DIR / "Security-Firewall-Defense.ps1"
