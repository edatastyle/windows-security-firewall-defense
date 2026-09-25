# =======================================================
# Security-Firewall-Defense.ps1  (Improved Anti-RAT / Anti-Malware version)
# Standard Safe Mode:
# - Blocks all outbound except allowed apps (HTTP/HTTPS/SSH/FTP) or ANY for special apps
# - Preserves Windows Update (optional)
# - Auto-downloads threat lists and applies inbound blocks
# - Blocks high-risk inbound ports used by RATs / RDP / SMB / VNC etc.
# - Blocks outbound network access for common LOLBins abused by malware
# - Editable allowed-apps list, logs, restore option
# =======================================================

# NOTE: param() MUST be the very first statement in the script (comments are
# fine above it, but no executable code) or PowerShell cannot bind command-line
# switches like -Auto to it. That's why "-Auto" was being silently ignored before.
param(
    [switch]$Auto
)

# Ensure running as admin
If (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "Please run this script as Administrator." -ForegroundColor Red
    exit 1
}

Clear-Host
$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
if ([string]::IsNullOrEmpty($PSScriptRoot)) { $PSScriptRoot = (Get-Location).Path }

# Prefer a sibling "data" folder (used by the GUI application) when present;
# otherwise keep files next to the script for standalone use.
$DataDir = Join-Path (Split-Path -Parent $PSScriptRoot) "data"
if (-not (Test-Path $DataDir)) {
    $DataDir = Join-Path $PSScriptRoot "data"
}
if (-not (Test-Path $DataDir)) {
    $DataDir = $PSScriptRoot   # final fallback: same folder as script
}
if (-not (Test-Path $DataDir)) { New-Item -Path $DataDir -ItemType Directory -Force | Out-Null }

# Files
$AllowedListFile     = Join-Path $DataDir "allowed-apps.txt"
$BlockListFile       = Join-Path $DataDir "malicious-ips.txt"
$LogFile             = Join-Path $DataDir "security-firewall.log"
$FirewallStatusFile  = Join-Path $DataDir "firewall-status.txt"

# Create files if missing (default entries)
if (!(Test-Path $AllowedListFile)) {
    @(
        "Firefox|C:\Program Files\Mozilla Firefox\firefox.exe",
        "Chrome|C:\Program Files\Google\Chrome\Application\chrome.exe",
        "Edge|C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "PuTTY|C:\Program Files\PuTTY\putty.exe",
        "WinSCP|C:\Program Files (x86)\WinSCP\WinSCP.exe"
    ) | Out-File $AllowedListFile -Encoding utf8
}
if (!(Test-Path $BlockListFile)) { New-Item -Path $BlockListFile -ItemType File -Force | Out-Null }
if (!(Test-Path $LogFile)) { New-Item -Path $LogFile -ItemType File -Force | Out-Null }
if (!(Test-Path $FirewallStatusFile)) { "OFF" | Out-File $FirewallStatusFile -Encoding utf8 }

function Log {
    param([string]$Text)
    $entry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Text"
    $entry | Out-File -FilePath $LogFile -Append -Encoding utf8
}

# Helper: create allow rule safely (prevents duplicates)
function New-AllowRuleSafely {
    param(
        [string]$DisplayName,
        [string]$ProgramPath,
        [string]$Protocol = "TCP",
        [string]$RemotePort = $null,
        [string]$Profile = "Any"
    )
    if (-not (Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue)) {
        try {
            if ($Protocol -eq "Any") {
                New-NetFirewallRule -DisplayName $DisplayName -Program $ProgramPath -Direction Outbound -Action Allow -Profile $Profile -Protocol Any -ErrorAction Stop | Out-Null
            } elseif ($null -ne $RemotePort) {
                New-NetFirewallRule -DisplayName $DisplayName -Program $ProgramPath -Direction Outbound -Action Allow -Protocol $Protocol -RemotePort $RemotePort -Profile $Profile -ErrorAction Stop | Out-Null
            } else {
                New-NetFirewallRule -DisplayName $DisplayName -Program $ProgramPath -Direction Outbound -Action Allow -Profile $Profile -ErrorAction Stop | Out-Null
            }
            Log "Created allow rule: $DisplayName for $ProgramPath ($Protocol $RemotePort)"
        } catch {
            Log "Failed to create allow rule: $DisplayName - $($_.Exception.Message)"
        }
    } else {
        Log "Rule already exists: $DisplayName"
    }
}

# Helper: create block rule safely
function New-BlockRuleSafely {
    param(
        [string]$DisplayName,
        [string]$Direction = "Inbound",
        [string]$Protocol = "Any",
        [string]$LocalPort = $null,
        [string]$RemotePort = $null,
        [string]$Program = $null,
        [string]$RemoteAddress = $null,
        [string]$Profile = "Any"
    )
    if (-not (Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue)) {
        try {
            $params = @{
                DisplayName = $DisplayName
                Direction   = $Direction
                Action      = "Block"
                Profile     = $Profile
                ErrorAction = "Stop"
            }
            if ($Protocol -ne "Any") { $params.Protocol = $Protocol }
            if ($LocalPort)          { $params.LocalPort = $LocalPort }
            if ($RemotePort)         { $params.RemotePort = $RemotePort }
            if ($Program)            { $params.Program = $Program }
            if ($RemoteAddress)      { $params.RemoteAddress = $RemoteAddress }

            New-NetFirewallRule @params | Out-Null
            Log "Created block rule: $DisplayName"
        } catch {
            Log "Failed to create block rule: $DisplayName - $($_.Exception.Message)"
        }
    }
}

# High-risk ports used by RATs / RDP / SMB / VNC / remote tools
$HighRiskInboundPorts = @(
    "3389",          # RDP
    "5985","5986",   # WinRM
    "135",           # RPC
    "445",           # SMB
    "139","137","138", # NetBIOS
    "5900","5901","5902","5903", # VNC
    "5938",          # TeamViewer
    "7070","8443","8444", # AnyDesk
    "4444","5555","6666","6667","6668","6669",
    "1177","1604","1337","31337","12345","54321",
    "1234","1243","2000","2001","2140","3127","3128",
    "5000","5001","5400","5401","5402","5500",
    "6000","6660","6969","7000","7300","7597",
    "8080","8888","9999","10000"
)

# Extra ports historically associated with specific well-known RAT/backdoor families.
# Generated as BOTH inbound and outbound blocks below, since modern RATs usually
# beacon OUT to a C2 server rather than listening for inbound connections.
$KnownRATPorts = @(
    "20034","12345","12346","27374","6969","6970",
    "9871","9872","9873","9874","9875","16959",
    "2140","3150","1177","5150","8000","8001",
    "1024","1025","1026","1027","1028","1029",
    "2023","2989","3024","3129","4092","4321",
    "5321","6400","7300","7301","7306","7307","7308",
    "9989","10067","10167","11000","20000","20001",
    "23432","23456","26274","29559","31338","31339",
    "33333","34324","40412","50505","50766","53001",
    "61466","65000"
) | Sort-Object -Unique

# Attack Surface Reduction (ASR) rules — built into Microsoft Defender.
# These target the specific techniques RATs and malware droppers rely on
# (malicious scripts, macro payloads, LSASS credential theft, process injection, etc.)
$ASRRules = @{
    "56a863a9-875e-4185-98a7-b882c64b5ce5" = "Block abuse of exploited vulnerable signed drivers"
    "7674ba52-37eb-4a4f-a9a1-f0f9a1619a2c" = "Block Adobe Reader from creating child processes"
    "d4f940ab-401b-4efc-aadc-ad5f3c50688a" = "Block all Office applications from creating child processes"
    "9e6c4e1f-7d60-472f-ba1a-a39ef669e4b2" = "Block credential stealing from LSASS"
    "be9ba2d9-53ea-4cdc-84e5-9b1eeee46550" = "Block executable content from email/webmail"
    "01443614-cd74-433a-b99e-2ecdc07bfc25" = "Block executables that don't meet prevalence/age/trust criteria"
    "5beb7efe-fd9a-4556-801d-275e5ffc04cc" = "Block execution of potentially obfuscated scripts"
    "d3e037e1-3eb8-44c8-a917-57927947596d" = "Block JS/VBS from launching downloaded executable content"
    "3b576869-a4ec-4529-8536-b80a7769e899" = "Block Office apps from creating executable content"
    "75668c1f-73b5-4cf0-bb93-3ecf5cb7cc84" = "Block Office apps from injecting into other processes"
    "26190899-1602-49e8-8b27-eb1d0a1ce869" = "Block Office comm apps from creating child processes"
    "e6db77e5-3df2-4cf1-b95a-636979351e5b" = "Block persistence through WMI event subscription"
    "d1e49aac-8f56-4280-b9ba-993a6d77406c" = "Block process creations from PSExec/WMI"
    "b2b3f03d-6a65-4f7b-a9c7-1c7ef74a9ba4" = "Block untrusted/unsigned processes on removable drives"
    "92e97fa1-2edf-4476-bdd6-9dd0b4dddc7b" = "Block Win32 API calls from Office macros"
    "c1db55ab-c21a-4637-bb3f-a12568109d35" = "Use advanced ransomware protection"
}

# LOLBins that malware / RATs frequently abuse
$LOLBins = @(
    @{ Name = "powershell";   Path = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" },
    @{ Name = "powershell32"; Path = "$env:SystemRoot\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" },
    @{ Name = "cmd";          Path = "$env:SystemRoot\System32\cmd.exe" },
    @{ Name = "cmd32";        Path = "$env:SystemRoot\SysWOW64\cmd.exe" },
    @{ Name = "wscript";      Path = "$env:SystemRoot\System32\wscript.exe" },
    @{ Name = "wscript32";    Path = "$env:SystemRoot\SysWOW64\wscript.exe" },
    @{ Name = "cscript";      Path = "$env:SystemRoot\System32\cscript.exe" },
    @{ Name = "cscript32";    Path = "$env:SystemRoot\SysWOW64\cscript.exe" },
    @{ Name = "mshta";        Path = "$env:SystemRoot\System32\mshta.exe" },
    @{ Name = "mshta32";      Path = "$env:SystemRoot\SysWOW64\mshta.exe" },
    @{ Name = "certutil";     Path = "$env:SystemRoot\System32\certutil.exe" },
    @{ Name = "certutil32";   Path = "$env:SystemRoot\SysWOW64\certutil.exe" },
    @{ Name = "regsvr32";     Path = "$env:SystemRoot\System32\regsvr32.exe" },
    @{ Name = "regsvr3232";   Path = "$env:SystemRoot\SysWOW64\regsvr32.exe" },
    @{ Name = "rundll32";     Path = "$env:SystemRoot\System32\rundll32.exe" },
    @{ Name = "rundll3232";   Path = "$env:SystemRoot\SysWOW64\rundll32.exe" },
    @{ Name = "bitsadmin";    Path = "$env:SystemRoot\System32\bitsadmin.exe" },
    @{ Name = "msiexec";      Path = "$env:SystemRoot\System32\msiexec.exe" },
    @{ Name = "msiexec32";    Path = "$env:SystemRoot\SysWOW64\msiexec.exe" }
)

# -----------------------
# Firewall Reset + Lockdown
# -----------------------
function Apply-Lockdown {

    Write-Host "[*] Resetting Windows Firewall..." -ForegroundColor Cyan
    netsh advfirewall reset | Out-Null

    Write-Host "[*] Enabling firewall profiles..." -ForegroundColor Cyan
    Set-NetFirewallProfile -Profile Domain,Public,Private -Enabled True

    Write-Host "[*] Setting default Inbound = Block + Outbound = Block..." -ForegroundColor Yellow
    Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultInboundAction Block -DefaultOutboundAction Block

    # Enable logging of blocked packets
    Set-NetFirewallProfile -Profile Domain,Public,Private -LogBlocked True -LogMaxSizeKilobytes 32767 `
        -LogFileName "%SystemRoot%\System32\LogFiles\Firewall\pfirewall.log" | Out-Null

    Write-Host "[*] Creating required system rules..." -ForegroundColor Green

    # Optional Windows Update allow (uncomment if needed)
    # New-AllowRuleSafely -DisplayName "Allow-WindowsUpdate" `
    #     -ProgramPath "C:\Windows\System32\svchost.exe" `
    #     -Protocol TCP `
    #     -RemotePort "80,443"

    # Allow DNS
    if (-not (Get-NetFirewallRule -DisplayName "Allow-DNS-UDP" -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName "Allow-DNS-UDP" -Direction Outbound -Action Allow `
            -Protocol UDP -RemotePort 53 -Profile Any | Out-Null
    }
    if (-not (Get-NetFirewallRule -DisplayName "Allow-DNS-TCP" -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName "Allow-DNS-TCP" -Direction Outbound -Action Allow `
            -Protocol TCP -RemotePort 53 -Profile Any | Out-Null
    }

    $DefaultPorts = @("80","443")

    Write-Host "[*] Reading allowed-apps.txt..." -ForegroundColor Cyan

    $Lines = Get-Content $AllowedListFile | Where-Object {
        $_.Trim() -ne "" -and
        -not $_.Trim().StartsWith("#")
    }

    foreach ($Line in $Lines) {

        $Parts = $Line.Split('|')

        if ($Parts.Count -lt 2) {
            Write-Host "[WARN] Invalid entry: $Line" -ForegroundColor Yellow
            Log "Invalid entry: $Line"
            continue
        }

        $Name = $Parts[0].Trim()
        $Path = [Environment]::ExpandEnvironmentVariables($Parts[1].Trim())

        if (!(Test-Path $Path)) {
            Write-Host "[WARN] Path not found: $Path" -ForegroundColor Yellow
            Log "Path not found: $Path"
            continue
        }

        if ($Parts.Count -ge 3) {
            $Value = $Parts[2].Trim().ToUpper()

            if ($Value -eq "ANY") {
                $RuleName = "Allow-$Name-ALL"
                New-AllowRuleSafely -DisplayName $RuleName -ProgramPath $Path -Protocol Any
                Write-Host "[ALLOWED] $Name -> ALL PORTS" -ForegroundColor Green
                Log "Allowed $Name (ALL)"
                continue
            }

            $Ports = $Value.Split(",") | ForEach-Object { $_.Trim() }
        }
        else {
            $Ports = $DefaultPorts
        }

        foreach ($Port in $Ports) {
            $RuleName = "Allow-$Name-Port$Port"
            New-AllowRuleSafely -DisplayName $RuleName -ProgramPath $Path -Protocol TCP -RemotePort $Port
        }

        Write-Host "[ALLOWED] $Name -> Ports: $($Ports -join ',')" -ForegroundColor Green
        Log "Allowed $Name on ports $($Ports -join ',')"
    }

    # Block SearchHost
    $SearchHost = "C:\Windows\SystemApps\Microsoft.Windows.Search_cw5n1h2txyewy\SearchHost.exe"
    if (Test-Path $SearchHost) {
        New-BlockRuleSafely -DisplayName "Block-SearchHost" -Direction Outbound -Program $SearchHost
        Write-Host "[BLOCKED] SearchHost.exe" -ForegroundColor Red
        Log "Blocked SearchHost.exe"
    }

    # Block high-risk inbound ports
    Write-Host "[*] Blocking high-risk inbound ports used by RATs, RDP, SMB, VNC..." -ForegroundColor Yellow
    foreach ($port in $HighRiskInboundPorts) {
        New-BlockRuleSafely -DisplayName "Block-Inbound-Port$port" -Direction Inbound -Protocol TCP -LocalPort $port
        New-BlockRuleSafely -DisplayName "Block-Inbound-UDP-Port$port" -Direction Inbound -Protocol UDP -LocalPort $port
    }
    Write-Host "[OK] High-risk inbound ports blocked" -ForegroundColor Green
    Log "Blocked high-risk inbound ports"

    # Block known-RAT ports both inbound AND outbound (RATs usually beacon OUT to their C2)
    Write-Host "[*] Blocking known RAT/backdoor ports (inbound + outbound)..." -ForegroundColor Yellow
    foreach ($port in $KnownRATPorts) {
        New-BlockRuleSafely -DisplayName "Block-Inbound-RATPort$port"  -Direction Inbound  -Protocol TCP -LocalPort $port
        New-BlockRuleSafely -DisplayName "Block-Inbound-RATPortUDP$port" -Direction Inbound -Protocol UDP -LocalPort $port
        New-BlockRuleSafely -DisplayName "Block-Outbound-RATPort$port" -Direction Outbound -Protocol TCP -RemotePort $port
        New-BlockRuleSafely -DisplayName "Block-Outbound-RATPortUDP$port" -Direction Outbound -Protocol UDP -RemotePort $port
    }
    Write-Host "[OK] Known RAT/backdoor ports blocked" -ForegroundColor Green
    Log "Blocked known RAT/backdoor ports (inbound+outbound)"

    # Block outbound for LOLBins
    Write-Host "[*] Blocking outbound network access for LOLBins..." -ForegroundColor Yellow
    foreach ($bin in $LOLBins) {
        if (Test-Path $bin.Path) {
            New-BlockRuleSafely -DisplayName "Block-LOLBin-$($bin.Name)" -Direction Outbound -Program $bin.Path
            Write-Host "[BLOCKED] $($bin.Name)" -ForegroundColor Red
        }
    }
    Log "Blocked LOLBins outbound"

    Write-Host ""
    Write-Host "[OK] Firewall Lockdown Applied Successfully." -ForegroundColor Green
    Write-Host "[OK] All outbound connections are BLOCKED except allowed applications." -ForegroundColor Green
    Write-Host "[OK] High-risk inbound ports + LOLBins are blocked." -ForegroundColor Green

    Log "Applied outbound lockdown + anti-RAT hardening."
    "ON" | Out-File $FirewallStatusFile -Encoding UTF8
}

# -----------------------
# Threat Feed Update & Apply Blocks
# -----------------------
function Update-And-Apply-Blocklist {
    Write-Host "[*] Updating threat feed..." -ForegroundColor Cyan

    $feeds = @(
        "https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt",
        "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level1.netset",
        "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_level2.netset",
        "https://raw.githubusercontent.com/firehol/blocklist-ipsets/master/firehol_webclient.netset"
    )

    $collected = @()
    foreach ($u in $feeds) {
        try {
            $resp = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 20
            $lines = $resp.Content -split "`n"
            foreach ($l in $lines) {
                $trim = $l.Trim()
                if ($trim -match '^\d{1,3}(\.\d{1,3}){3}(\/\d+)?$') { $collected += $trim }
            }
            Write-Host "[OK] Loaded $u" -ForegroundColor Green
            Log "Loaded feed: $u"
        } catch {
            Write-Host "[ERR] Could not load $u" -ForegroundColor Yellow
            Log "Failed to load feed: $u"
        }
    }

    $unique = $collected | Sort-Object -Unique
    $unique | Out-File -FilePath $BlockListFile -Encoding utf8

    Write-Host "[*] Total unique block entries: $($unique.Count)" -ForegroundColor Yellow
    Log "Total unique block entries: $($unique.Count)"

    # Clean old AutoBlock rules
    Write-Host "[*] Cleaning old AutoBlock rules..." -ForegroundColor Cyan
    Get-NetFirewallRule -DisplayName "AutoBlock-*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue

    # Batch IPs
    $batchSize = 100
    $batches = [Math]::Ceiling($unique.Count / $batchSize)
    for ($i = 0; $i -lt $batches; $i++) {
        $start = $i * $batchSize
        $batch = $unique[$start..([Math]::Min($start + $batchSize - 1, $unique.Count - 1))]
        $ruleName = "AutoBlock-Batch$($i+1)"
        try {
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -RemoteAddress $batch `
                -Action Block -Profile Any -ErrorAction Stop | Out-Null
            Log "Created batch rule: $ruleName ($($batch.Count) IPs)"
        } catch {
            Log "Failed to create batch rule: $ruleName - $($_.Exception.Message)"
        }
    }

    Write-Host "[*] Applied inbound block rules in batches." -ForegroundColor Cyan
    Log "Applied inbound malicious-IP rules (batched)."
    "ON" | Out-File $FirewallStatusFile -Encoding utf8
}

# -----------------------
# Show Live Connections
# -----------------------
function Show-LiveConnections {
    Write-Host "Established TCP connections and owning process:" -ForegroundColor Cyan
    $conns = Get-NetTCPConnection | Where-Object { $_.State -eq 'Established' } | Sort-Object RemoteAddress
    $out = foreach ($c in $conns) {
        $proc = $null
        try { $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue } catch {}
        [PSCustomObject]@{
            LocalAddress  = $c.LocalAddress
            LocalPort     = $c.LocalPort
            RemoteAddress = $c.RemoteAddress
            RemotePort    = $c.RemotePort
            ProcessId     = $c.OwningProcess
            ProcessName   = if ($proc) { $proc.ProcessName } else { "-" }
        }
    }
    $out | Format-Table -AutoSize
}

# -----------------------
# Restore
# -----------------------
function Restore-Firewall {
    Write-Host "[*] Restoring default firewall state..." -ForegroundColor Cyan
    netsh advfirewall reset | Out-Null
    Log "Firewall reset to defaults by user."
    Write-Host "[*] Done." -ForegroundColor Green
    "OFF" | Out-File $FirewallStatusFile -Encoding utf8
}

# -----------------------
# Windows Defender / Anti-Malware Hardening
# -----------------------
function Apply-DefenderHardening {
    Write-Host "[*] Hardening Microsoft Defender against RATs/malware..." -ForegroundColor Cyan

    try {
        Set-MpPreference -DisableRealtimeMonitoring $false -ErrorAction Stop
        Set-MpPreference -MAPSReporting Advanced -ErrorAction Stop
        Set-MpPreference -SubmitSamplesConsent SendAllSamples -ErrorAction Stop
        Set-MpPreference -PUAProtection Enabled -ErrorAction Stop
        Set-MpPreference -DisableIOAVProtection $false -ErrorAction Stop
        Set-MpPreference -DisableScriptScanning $false -ErrorAction Stop
        Set-MpPreference -DisableBehaviorMonitoring $false -ErrorAction Stop
        Set-MpPreference -EnableNetworkProtection Enabled -ErrorAction Stop
        Write-Host "[OK] Real-time protection, cloud reporting, PUA blocking, network protection enabled." -ForegroundColor Green
        Log "Defender core protections enabled (real-time, PUA, network protection, behavior monitoring)."
    } catch {
        Write-Host "[WARN] Could not set some Defender preferences: $($_.Exception.Message)" -ForegroundColor Yellow
        Log "Defender preference error: $($_.Exception.Message)"
    }

    # Controlled Folder Access - blocks unauthorized/ransomware-style writes to protected folders
    try {
        Set-MpPreference -EnableControlledFolderAccess Enabled -ErrorAction Stop
        Write-Host "[OK] Controlled Folder Access enabled (anti-ransomware)." -ForegroundColor Green
        Log "Controlled Folder Access enabled."
    } catch {
        Write-Host "[WARN] Could not enable Controlled Folder Access: $($_.Exception.Message)" -ForegroundColor Yellow
        Log "Controlled Folder Access error: $($_.Exception.Message)"
    }

    # Attack Surface Reduction rules - set to Block (1) for each known RAT/malware technique
    Write-Host "[*] Applying Attack Surface Reduction (ASR) rules..." -ForegroundColor Yellow
    foreach ($guid in $ASRRules.Keys) {
        try {
            Add-MpPreference -AttackSurfaceReductionRules_Ids $guid -AttackSurfaceReductionRules_Actions Enabled -ErrorAction Stop
            Write-Host "[BLOCKED] $($ASRRules[$guid])" -ForegroundColor Red
            Log "ASR rule enabled: $($ASRRules[$guid]) ($guid)"
        } catch {
            Write-Host "[WARN] Could not enable ASR rule $guid : $($_.Exception.Message)" -ForegroundColor Yellow
            Log "ASR rule error: $guid - $($_.Exception.Message)"
        }
    }

    Write-Host "[OK] Defender hardening complete." -ForegroundColor Green
    Log "Defender hardening applied (ASR rules, controlled folder access, core protections)."
}

# -----------------------
# Read-only persistence scan (Run keys, scheduled tasks, services, startup folder)
# Reports only - does NOT delete anything automatically, since misidentifying
# legitimate software as malicious and auto-removing it could break your system.
# Review each entry yourself; if unfamiliar, look it up before removing it.
# -----------------------
function Scan-Persistence {
    Write-Host "[*] Scanning common persistence locations abused by RATs/malware..." -ForegroundColor Cyan
    Log "Persistence scan started."

    Write-Host "`n--- Registry Run keys (HKCU) ---" -ForegroundColor Yellow
    Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue |
        Select-Object * -ExcludeProperty PS* | Format-List

    Write-Host "--- Registry Run keys (HKLM) ---" -ForegroundColor Yellow
    Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue |
        Select-Object * -ExcludeProperty PS* | Format-List

    Write-Host "--- Startup folder items ---" -ForegroundColor Yellow
    Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup" -ErrorAction SilentlyContinue |
        Select-Object Name, FullName, LastWriteTime | Format-Table -AutoSize
    Get-ChildItem "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp" -ErrorAction SilentlyContinue |
        Select-Object Name, FullName, LastWriteTime | Format-Table -AutoSize

    Write-Host "--- Scheduled tasks (non-Microsoft) ---" -ForegroundColor Yellow
    Get-ScheduledTask -ErrorAction SilentlyContinue |
        Where-Object { $_.TaskPath -notlike "\Microsoft\*" } |
        Select-Object TaskName, TaskPath, State | Format-Table -AutoSize

    Write-Host "--- Non-Microsoft services set to auto-start ---" -ForegroundColor Yellow
    Get-CimInstance Win32_Service -ErrorAction SilentlyContinue |
        Where-Object { $_.StartMode -eq "Auto" -and $_.PathName -notmatch "Windows\\System32" } |
        Select-Object Name, DisplayName, PathName, StartMode | Format-Table -AutoSize

    Write-Host "`n[OK] Scan complete. This is informational only - nothing was changed or removed." -ForegroundColor Green
    Write-Host "[TIP] If you don't recognize an entry, look up its exact file name/path before deleting it." -ForegroundColor Cyan
    Log "Persistence scan completed (read-only)."
}

# -----------------------
# ON / OFF
# -----------------------
function Firewall-ON {
    Apply-Lockdown
    Update-And-Apply-Blocklist
    Apply-DefenderHardening
    Write-Host "[*] Firewall + Defender are now ON with anti-RAT/anti-malware hardening" -ForegroundColor Green
    Log "Firewall + Defender enabled (ON) with anti-RAT/anti-malware hardening"
}

function Firewall-OFF {
    Restore-Firewall
    Write-Host "[!] Firewall is now OFF" -ForegroundColor Yellow
    Log "Firewall disabled (OFF)"
}

function Toggle-Firewall {
    $status = "OFF"
    if (Test-Path $FirewallStatusFile) { $status = Get-Content $FirewallStatusFile }
    if ($status -eq "ON") { Firewall-OFF } else { Firewall-ON }
}

# -----------------------
# Menu
# -----------------------
if ($Auto) {
    # Silent mode - apply lockdown automatically
    Write-Host "Running in Auto mode - Applying Lockdown..." -ForegroundColor Cyan
    Apply-Lockdown
    # Optionally also update threat list (uncomment next line if you want)
    # Update-And-Apply-Blocklist
    exit
}

Write-Host ""
Write-Host "Security-Firewall-Defense utility - Anti-RAT / Anti-Malware hardened" -ForegroundColor Cyan
Write-Host "1) Apply Lockdown + Allow apps (recommended)"
Write-Host "2) Update threat feed and apply inbound blocks"
Write-Host "3) Apply everything (Lockdown + Update blocks + Defender hardening)"
Write-Host "4) Show live connections"
Write-Host "5) Restore firewall defaults"
Write-Host "6) Open allowed-apps.txt for editing"
Write-Host "7) Toggle Security-Firewall-Defense ON/OFF"
Write-Host "8) Apply Windows Defender / anti-malware hardening only"
Write-Host "9) Scan for suspicious persistence (Run keys, tasks, services) - read only"
Write-Host "0) Exit"
$sel = Read-Host "Choose an option (0-9)"

switch ($sel) {
    '1' { Apply-Lockdown }
    '2' { Update-And-Apply-Blocklist }
    '3' { Apply-Lockdown; Start-Sleep -Seconds 2; Update-And-Apply-Blocklist; Start-Sleep -Seconds 2; Apply-DefenderHardening }
    '4' { Show-LiveConnections }
    '5' { Restore-Firewall }
    '6' { Invoke-Item $AllowedListFile }
    '7' { Toggle-Firewall }
    '8' { Apply-DefenderHardening }
    '9' { Scan-Persistence }
    default { Write-Host "Exiting." }
}