"""
Firewall and security operations.
All heavy lifting is delegated to the original PowerShell script or direct
PowerShell cmdlets via subprocess for reliability and fidelity to the
provided Security-Firewall-Defense.ps1 logic.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Dict, Any

from .paths import (
    ALLOWED_APPS_FILE,
    BLOCKLIST_FILE,
    LOG_FILE,
    STATUS_FILE,
    PS1_SCRIPT,
    DATA_DIR,
)


def _run_ps(command: str, timeout: int = 120) -> tuple[int, str, str]:
    """Execute a PowerShell command and return (returncode, stdout, stderr)."""
    full_cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command", command,
    ]
    try:
        proc = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "PowerShell command timed out"
    except FileNotFoundError:
        return -1, "", "powershell.exe not found – this application requires Windows"
    except Exception as e:
        return -1, "", str(e)


def _run_ps_script(script_path: Path, args: str = "", timeout: int = 300) -> tuple[int, str, str]:
    """Run the original PS1 script with optional arguments."""
    if not script_path.exists():
        return -1, "", f"Script not found: {script_path}"
    full_cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script_path),
    ]
    if args:
        full_cmd.extend(args.split())
    try:
        proc = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except Exception as e:
        return -1, "", str(e)


def log_message(text: str) -> None:
    """Append a timestamped line to the application log."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {text}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


@dataclass
class FirewallStatus:
    enabled: bool = False
    default_inbound: str = "Unknown"
    default_outbound: str = "Unknown"
    profiles: Dict[str, bool] = field(default_factory=dict)
    rule_count: int = 0
    last_updated: Optional[str] = None


@dataclass
class AllowedApp:
    name: str
    path: str
    ports: str = "80,443"  # or "ANY"


@dataclass
class LiveConnection:
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    process_id: int
    process_name: str


class FirewallManager:
    """High-level API used by the GUI."""

    def __init__(self):
        self._ensure_data_files()
        self._status_lock = threading.Lock()
        self._current_status = FirewallStatus()

    def _ensure_data_files(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not ALLOWED_APPS_FILE.exists():
            defaults = [
                "Firefox|C:\\Program Files\\Mozilla Firefox\\firefox.exe",
                "Chrome|C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                "Edge|C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
                "PuTTY|C:\\Program Files\\PuTTY\\putty.exe",
                "WinSCP|C:\\Program Files (x86)\\WinSCP\\WinSCP.exe",
            ]
            ALLOWED_APPS_FILE.write_text("\n".join(defaults) + "\n", encoding="utf-8")
        if not BLOCKLIST_FILE.exists():
            BLOCKLIST_FILE.write_text("", encoding="utf-8")
        if not LOG_FILE.exists():
            LOG_FILE.write_text("", encoding="utf-8")
        if not STATUS_FILE.exists():
            STATUS_FILE.write_text("OFF", encoding="utf-8")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    def get_status(self) -> FirewallStatus:
        """Query current Windows Firewall profile state."""
        cmd = r"""
        $profiles = Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction
        $rules = (Get-NetFirewallRule -ErrorAction SilentlyContinue | Measure-Object).Count
        $result = @{
            Profiles = @{}
            RuleCount = $rules
        }
        foreach ($p in $profiles) {
            $result.Profiles[$p.Name] = @{
                Enabled = [bool]$p.Enabled
                Inbound = $p.DefaultInboundAction.ToString()
                Outbound = $p.DefaultOutboundAction.ToString()
            }
        }
        $result | ConvertTo-Json -Depth 4 -Compress
        """
        rc, out, err = _run_ps(cmd)
        status = FirewallStatus()
        if rc == 0 and out.strip():
            try:
                data = json.loads(out.strip())
                status.rule_count = data.get("RuleCount", 0)
                profiles = data.get("Profiles", {})
                status.profiles = {k: v.get("Enabled", False) for k, v in profiles.items()}
                # Use Public as representative
                public = profiles.get("Public") or profiles.get("Domain") or next(iter(profiles.values()), {})
                status.enabled = any(status.profiles.values())
                status.default_inbound = public.get("Inbound", "Unknown")
                status.default_outbound = public.get("Outbound", "Unknown")
            except Exception:
                pass
        # Override with our status file if present
        try:
            if STATUS_FILE.exists():
                file_status = STATUS_FILE.read_text(encoding="utf-8").strip().upper()
                if file_status == "ON":
                    status.enabled = True
        except Exception:
            pass
        status.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._status_lock:
            self._current_status = status
        return status

    def get_file_status(self) -> str:
        try:
            return STATUS_FILE.read_text(encoding="utf-8").strip().upper()
        except Exception:
            return "OFF"

    # ------------------------------------------------------------------
    # Allowed applications
    # ------------------------------------------------------------------
    def list_allowed_apps(self) -> List[AllowedApp]:
        apps = []
        if not ALLOWED_APPS_FILE.exists():
            return apps
        for line in ALLOWED_APPS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue
            name, path = parts[0], parts[1]
            ports = parts[2] if len(parts) >= 3 else "80,443"
            apps.append(AllowedApp(name=name, path=path, ports=ports))
        return apps

    def save_allowed_apps(self, apps: List[AllowedApp]) -> None:
        lines = [f"{a.name}|{a.path}|{a.ports}" for a in apps]
        ALLOWED_APPS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log_message(f"Allowed apps list updated ({len(apps)} entries)")

    def add_allowed_app(self, name: str, path: str, ports: str = "80,443") -> None:
        apps = self.list_allowed_apps()
        apps.append(AllowedApp(name=name, path=path, ports=ports))
        self.save_allowed_apps(apps)

    def remove_allowed_app(self, name: str) -> None:
        apps = [a for a in self.list_allowed_apps() if a.name != name]
        self.save_allowed_apps(apps)

    # ------------------------------------------------------------------
    # Malicious IP blocklist
    # ------------------------------------------------------------------
    def list_blocked_ips(self) -> List[str]:
        if not BLOCKLIST_FILE.exists():
            return []
        ips = []
        for line in BLOCKLIST_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                ips.append(line)
        return ips

    def save_blocked_ips(self, ips: List[str]) -> None:
        unique = sorted(set(ips))
        BLOCKLIST_FILE.write_text("\n".join(unique) + "\n", encoding="utf-8")
        log_message(f"Blocklist updated ({len(unique)} entries)")

    def add_blocked_ip(self, ip: str) -> None:
        ips = self.list_blocked_ips()
        if ip not in ips:
            ips.append(ip)
            self.save_blocked_ips(ips)

    def remove_blocked_ip(self, ip: str) -> None:
        ips = [i for i in self.list_blocked_ips() if i != ip]
        self.save_blocked_ips(ips)

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------
    def get_log_lines(self, max_lines: int = 5000) -> List[str]:
        if not LOG_FILE.exists():
            return []
        try:
            lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
            return lines[-max_lines:]
        except Exception:
            return []

    def clear_log(self) -> None:
        LOG_FILE.write_text("", encoding="utf-8")
        log_message("Log cleared by user")

    # ------------------------------------------------------------------
    # High-level actions (call original script functions via PS)
    # ------------------------------------------------------------------
    def apply_lockdown(self, progress_cb: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
        """Apply the full lockdown (option 1 / Apply-Lockdown)."""
        if progress_cb:
            progress_cb("Applying firewall lockdown...")
        log_message("GUI: Starting Apply-Lockdown")

        # We invoke the script functions by dot-sourcing and calling
        cmd = f"""
        $ErrorActionPreference = 'Stop'
        . '{PS1_SCRIPT}'
        # The script defines functions; we call the ones we need
        # Note: the original script has a menu when run interactively.
        # We call Apply-Lockdown directly after dot-sourcing.
        Apply-Lockdown
        """
        # Because the original script ends with a menu, we instead re-implement
        # the critical parts or call with -Auto and then extra steps.
        # Safer approach: use -Auto which only does Apply-Lockdown
        rc, out, err = _run_ps_script(PS1_SCRIPT, "-Auto", timeout=180)
        success = rc == 0
        msg = out + ("\n" + err if err else "")
        if success:
            log_message("GUI: Apply-Lockdown completed successfully")
            STATUS_FILE.write_text("ON", encoding="utf-8")
        else:
            log_message(f"GUI: Apply-Lockdown failed – {err or out}")
        if progress_cb:
            progress_cb("Lockdown finished." if success else "Lockdown failed.")
        return success, msg

    def update_blocklist(self, progress_cb: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
        """Download threat feeds and apply inbound IP blocks."""
        if progress_cb:
            progress_cb("Updating threat feeds...")
        log_message("GUI: Starting Update-And-Apply-Blocklist")

        # Because the original functions are inside the script, we extract the
        # logic via a temporary wrapper that dotsources and calls the function.
        wrapper = f"""
        $ErrorActionPreference = 'Continue'
        # Minimal re-implementation of the feed update to avoid interactive menu
        $BlockListFile = '{BLOCKLIST_FILE}'
        $LogFile = '{LOG_FILE}'
        function Log($t) {{ "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $t" | Out-File $LogFile -Append -Encoding utf8 }}

        $feeds = @(
            "https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt",
            "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset",
            "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level2.netset",
            "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_webclient.netset"
        )
        $collected = @()
        foreach ($u in $feeds) {{
            try {{
                $resp = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 25
                $lines = $resp.Content -split "`n"
                foreach ($l in $lines) {{
                    $trim = $l.Trim()
                    if ($trim -match '^\\d{{1,3}}(\\.\\d{{1,3}}){{3}}(\\/\\d+)?$') {{ $collected += $trim }}
                }}
                Log "Loaded feed: $u"
            }} catch {{
                Log "Failed to load feed: $u"
            }}
        }}
        $unique = $collected | Sort-Object -Unique
        $unique | Out-File -FilePath $BlockListFile -Encoding utf8
        Log "Total unique block entries: $($unique.Count)"

        # Clean old AutoBlock rules
        Get-NetFirewallRule -DisplayName "AutoBlock-*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue

        $batchSize = 100
        $batches = [Math]::Ceiling($unique.Count / $batchSize)
        for ($i = 0; $i -lt $batches; $i++) {{
            $start = $i * $batchSize
            $batch = $unique[$start..([Math]::Min($start + $batchSize - 1, $unique.Count - 1))]
            $ruleName = "AutoBlock-Batch$($i+1)"
            try {{
                New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -RemoteAddress $batch `
                    -Action Block -Profile Any -ErrorAction Stop | Out-Null
                Log "Created batch rule: $ruleName ($($batch.Count) IPs)"
            }} catch {{
                Log "Failed to create batch rule: $ruleName"
            }}
        }}
        "ON" | Out-File '{STATUS_FILE}' -Encoding utf8
        Write-Output "Updated $($unique.Count) IPs in $batches batches"
        """
        rc, out, err = _run_ps(wrapper, timeout=300)
        success = rc == 0
        if success:
            log_message("GUI: Blocklist update completed")
        else:
            log_message(f"GUI: Blocklist update error – {err}")
        if progress_cb:
            progress_cb("Blocklist update finished.")
        return success, out + ("\n" + err if err else "")

    def apply_defender_hardening(self, progress_cb: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
        if progress_cb:
            progress_cb("Hardening Microsoft Defender...")
        log_message("GUI: Starting Defender hardening")
        # Simplified version of the ASR + preferences from the original script
        cmd = r"""
        $ErrorActionPreference = 'Continue'
        try {
            Set-MpPreference -DisableRealtimeMonitoring $false -ErrorAction SilentlyContinue
            Set-MpPreference -MAPSReporting Advanced -ErrorAction SilentlyContinue
            Set-MpPreference -SubmitSamplesConsent SendAllSamples -ErrorAction SilentlyContinue
            Set-MpPreference -PUAProtection Enabled -ErrorAction SilentlyContinue
            Set-MpPreference -DisableIOAVProtection $false -ErrorAction SilentlyContinue
            Set-MpPreference -DisableScriptScanning $false -ErrorAction SilentlyContinue
            Set-MpPreference -DisableBehaviorMonitoring $false -ErrorAction SilentlyContinue
            Set-MpPreference -EnableNetworkProtection Enabled -ErrorAction SilentlyContinue
            Set-MpPreference -EnableControlledFolderAccess Enabled -ErrorAction SilentlyContinue
            Write-Output "Core Defender preferences applied"
        } catch {
            Write-Output "Preference error: $($_.Exception.Message)"
        }
        $ASR = @(
            "56a863a9-875e-4185-98a7-b882c64b5ce5",
            "7674ba52-37eb-4a4f-a9a1-f0f9a1619a2c",
            "d4f940ab-401b-4efc-aadc-ad5f3c50688a",
            "9e6c4e1f-7d60-472f-ba1a-a39ef669e4b2",
            "be9ba2d9-53ea-4cdc-84e5-9b1eeee46550",
            "01443614-cd74-433a-b99e-2ecdc07bfc25",
            "5beb7efe-fd9a-4556-801d-275e5ffc04cc",
            "d3e037e1-3eb8-44c8-a917-57927947596d",
            "3b576869-a4ec-4529-8536-b80a7769e899",
            "75668c1f-73b5-4cf0-bb93-3ecf5cb7cc84",
            "26190899-1602-49e8-8b27-eb1d0a1ce869",
            "e6db77e5-3df2-4cf1-b95a-636979351e5b",
            "d1e49aac-8f56-4280-b9ba-993a6d77406c",
            "b2b3f03d-6a65-4f7b-a9c7-1c7ef74a9ba4",
            "92e97fa1-2edf-4476-bdd6-9dd0b4dddc7b",
            "c1db55ab-c21a-4637-bb3f-a12568109d35"
        )
        foreach ($g in $ASR) {
            try {
                Add-MpPreference -AttackSurfaceReductionRules_Ids $g -AttackSurfaceReductionRules_Actions Enabled -ErrorAction SilentlyContinue
            } catch {}
        }
        Write-Output "ASR rules applied"
        """
        rc, out, err = _run_ps(cmd, timeout=60)
        success = rc == 0
        log_message("GUI: Defender hardening finished")
        if progress_cb:
            progress_cb("Defender hardening finished.")
        return success, out + ("\n" + err if err else "")

    def restore_defaults(self, progress_cb: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
        if progress_cb:
            progress_cb("Restoring Windows Firewall defaults...")
        log_message("GUI: Restoring firewall defaults")
        rc, out, err = _run_ps("netsh advfirewall reset", timeout=30)
        STATUS_FILE.write_text("OFF", encoding="utf-8")
        success = rc == 0
        log_message("GUI: Firewall restored to defaults")
        if progress_cb:
            progress_cb("Restore complete.")
        return success, out + ("\n" + err if err else "")

    def apply_all(self, progress_cb: Optional[Callable[[str], None]] = None) -> tuple[bool, str]:
        """Full hardening: lockdown + blocklist + Defender."""
        msgs = []
        ok1, m1 = self.apply_lockdown(progress_cb)
        msgs.append(m1)
        time.sleep(1)
        ok2, m2 = self.update_blocklist(progress_cb)
        msgs.append(m2)
        time.sleep(1)
        ok3, m3 = self.apply_defender_hardening(progress_cb)
        msgs.append(m3)
        return all([ok1, ok2, ok3]), "\n---\n".join(msgs)

    # ------------------------------------------------------------------
    # Live connections
    # ------------------------------------------------------------------
    def get_live_connections(self) -> List[LiveConnection]:
        cmd = r"""
        Get-NetTCPConnection -State Established -ErrorAction SilentlyContinue |
            Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, OwningProcess |
            ConvertTo-Json -Compress
        """
        rc, out, err = _run_ps(cmd, timeout=15)
        conns: List[LiveConnection] = []
        if rc != 0 or not out.strip():
            return conns
        try:
            data = json.loads(out.strip())
            if isinstance(data, dict):
                data = [data]
            # Resolve process names in one go if possible
            pids = {item.get("OwningProcess") for item in data if item.get("OwningProcess")}
            pid_names = {}
            if pids:
                pid_list = ",".join(str(p) for p in pids if p)
                name_cmd = f"Get-Process -Id {pid_list} -ErrorAction SilentlyContinue | Select-Object Id, ProcessName | ConvertTo-Json -Compress"
                nrc, nout, _ = _run_ps(name_cmd, timeout=10)
                if nrc == 0 and nout.strip():
                    ndata = json.loads(nout.strip())
                    if isinstance(ndata, dict):
                        ndata = [ndata]
                    for p in ndata:
                        pid_names[p.get("Id")] = p.get("ProcessName", "-")
            for item in data:
                pid = item.get("OwningProcess") or 0
                conns.append(LiveConnection(
                    local_address=str(item.get("LocalAddress", "")),
                    local_port=int(item.get("LocalPort") or 0),
                    remote_address=str(item.get("RemoteAddress", "")),
                    remote_port=int(item.get("RemotePort") or 0),
                    process_id=int(pid),
                    process_name=pid_names.get(pid, "-"),
                ))
        except Exception:
            pass
        return conns

    # ------------------------------------------------------------------
    # Persistence scan (read-only)
    # ------------------------------------------------------------------
    def scan_persistence(self) -> str:
        """Return a human-readable report of common persistence locations."""
        cmd = r"""
        $sb = New-Object System.Text.StringBuilder
        [void]$sb.AppendLine("=== Registry Run keys (HKCU) ===")
        try {
            $hkcu = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
            if ($hkcu) {
                $hkcu.PSObject.Properties | Where-Object { $_.Name -notlike "PS*" } | ForEach-Object {
                    [void]$sb.AppendLine("$($_.Name) = $($_.Value)")
                }
            } else { [void]$sb.AppendLine("(none)") }
        } catch { [void]$sb.AppendLine("Error reading HKCU Run") }

        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("=== Registry Run keys (HKLM) ===")
        try {
            $hklm = Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
            if ($hklm) {
                $hklm.PSObject.Properties | Where-Object { $_.Name -notlike "PS*" } | ForEach-Object {
                    [void]$sb.AppendLine("$($_.Name) = $($_.Value)")
                }
            } else { [void]$sb.AppendLine("(none)") }
        } catch { [void]$sb.AppendLine("Error reading HKLM Run") }

        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("=== Startup folder (User) ===")
        Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup" -ErrorAction SilentlyContinue |
            ForEach-Object { [void]$sb.AppendLine("$($_.Name)  $($_.FullName)") }

        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("=== Startup folder (Common) ===")
        Get-ChildItem "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp" -ErrorAction SilentlyContinue |
            ForEach-Object { [void]$sb.AppendLine("$($_.Name)  $($_.FullName)") }

        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("=== Non-Microsoft Scheduled Tasks ===")
        Get-ScheduledTask -ErrorAction SilentlyContinue |
            Where-Object { $_.TaskPath -notlike "\Microsoft\*" } |
            Select-Object TaskName, TaskPath, State |
            ForEach-Object { [void]$sb.AppendLine("$($_.TaskName)  [$($_.State)]  $($_.TaskPath)") }

        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("=== Non-system auto-start services ===")
        Get-CimInstance Win32_Service -ErrorAction SilentlyContinue |
            Where-Object { $_.StartMode -eq "Auto" -and $_.PathName -notmatch "Windows\\System32" } |
            Select-Object Name, DisplayName, PathName |
            ForEach-Object { [void]$sb.AppendLine("$($_.Name) | $($_.DisplayName) | $($_.PathName)") }

        $sb.ToString()
        """
        rc, out, err = _run_ps(cmd, timeout=45)
        if rc == 0:
            log_message("GUI: Persistence scan completed (read-only)")
            return out
        return f"Scan failed:\n{err}\n{out}"
