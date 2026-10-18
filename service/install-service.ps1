#Requires -Version 5.1
<#
.SYNOPSIS
    Installs Spotify Ad Mute as an NSSM service plus a logon task. Safe to run again.

.DESCRIPTION
    Two parts (a service runs in Session 0 and cannot see the desktop):
      1. Scheduled task "SpotifyAdMute-Agent": at logon of -User it runs "spotify-ad-mute.py --service" in that
         user's interactive session (launches Spotify, keeps it maximized, mutes ads).
      2. NSSM service "SpotifyAdMute": starts with Windows and keeps that task running (agent_guard.py).
    Needs an elevated shell and a logged-on desktop session with auto-logon and no screen lock; the script warns
    when auto-logon is missing but does not configure it (it needs the account password).

.PARAMETER Nssm
    Path to nssm.exe.
.PARAMETER Python
    Path to python.exe that has the packages from requirements.txt installed (it must be readable by SYSTEM).
.PARAMETER User
    Windows account that owns the Spotify session. Default: the current user.
.PARAMETER ImagesDir
    Optional per-machine folder with volume/ and ads/ images (passed as --images).
.PARAMETER Pycaw
    on or off (passed as --pycaw). Default: leave the script's own USE_PYCAW.
.PARAMETER DryRun
    Print what would be done and change nothing.

.EXAMPLE
    .\install-service.ps1 -Nssm C:\tools\nssm.exe -Python C:\Python312\python.exe -User Mark -Pycaw off -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Nssm,
    [Parameter(Mandatory)][string]$Python,
    [string]$User = $env:USERNAME,
    [string]$ImagesDir,
    [ValidateSet('on', 'off')][string]$Pycaw,
    [string]$ServiceName = 'SpotifyAdMute',
    [string]$TaskName = 'SpotifyAdMute-Agent',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$script = Join-Path $repoRoot 'spotify-ad-mute.py'
$guard = Join-Path $PSScriptRoot 'agent_guard.py'
$logDir = Join-Path $env:ProgramData 'spotify-ad-mute'

function Invoke-Step {
    param([string]$Description, [scriptblock]$Action)
    if ($DryRun) { Write-Host "[dry-run] $Description"; return }
    Write-Host $Description
    & $Action
}

function Assert-ExitCode {
    param([string]$Action)
    if ($LASTEXITCODE -ne 0) { throw "$Action failed with exit code $LASTEXITCODE" }
}

# --- Gates ---------------------------------------------------------------
if (-not $DryRun -and -not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators')) {
    throw 'Run this script from an elevated (administrator) shell.'
}
foreach ($f in @($Nssm, $Python, $script, $guard)) {
    if (-not (Test-Path -LiteralPath $f)) { throw "Not found: $f" }
}
$profilePath = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\*' |
    Where-Object { $_.ProfileImagePath -like "*\$User" } | Select-Object -First 1).ProfileImagePath
if (-not $profilePath) { throw "No profile found for user '$User'" }

$winlogon = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
if ($winlogon.AutoAdminLogon -ne '1') {
    Write-Warning 'Auto-logon is not configured: after a reboot nothing runs until the user logs in (use Sysinternals Autologon).'
}
if ((Get-ItemProperty 'Registry::HKEY_USERS\*\Control Panel\Desktop' -ErrorAction SilentlyContinue |
        Where-Object { $_.ScreenSaveActive -eq '1' })) {
    Write-Warning 'A screen saver is active: a locked or blank screen breaks image detection.'
}

# --- 1. Logon task: the agent, in the user's interactive session ----------
$agentArgs = @("`"$script`"", '--service')
if ($Pycaw) { $agentArgs += @('--pycaw', $Pycaw) }
if ($ImagesDir) { $agentArgs += @('--images', "`"$ImagesDir`"") }
Invoke-Step "Register task '$TaskName' for $User : $Python $($agentArgs -join ' ')" {
    $action = New-ScheduledTaskAction -Execute $Python -Argument ($agentArgs -join ' ') -WorkingDirectory $repoRoot
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $User
    $principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
        -Settings $settings -Description 'Spotify Ad Mute agent (interactive session)' -Force | Out-Null
}

# --- 2. NSSM service: starts with Windows, keeps the task alive ------------
Invoke-Step "Create log folder $logDir" { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
# Get-Service, not "nssm status": under -ErrorAction Stop, Windows PowerShell 5.1 turns nssm's stderr into an exception
$exists = [bool](Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)
if ($exists) {
    Invoke-Step "Update service '$ServiceName'" {
        & $Nssm set $ServiceName Application $Python | Out-Null; Assert-ExitCode 'nssm set Application'
        & $Nssm set $ServiceName AppParameters "`"$guard`" --task $TaskName" | Out-Null; Assert-ExitCode 'nssm set AppParameters'
    }
} else {
    Invoke-Step "Install service '$ServiceName' : $Python `"$guard`" --task $TaskName" {
        & $Nssm install $ServiceName $Python "`"$guard`" --task $TaskName" | Out-Null; Assert-ExitCode 'nssm install'
    }
}
Invoke-Step "Configure service '$ServiceName' (delayed auto-start, restart on exit, logs, profile of $User)" {
    $settings = @(
        @('AppDirectory', $PSScriptRoot),
        @('DisplayName', 'Spotify Ad Mute'),
        @('Description', 'Keeps the Spotify Ad Mute agent task running'),
        @('Start', 'SERVICE_DELAYED_AUTO_START'),
        @('AppExit', 'Default', 'Restart'),
        @('AppRestartDelay', '5000'),
        @('AppStdout', (Join-Path $logDir 'service.log')),
        @('AppStderr', (Join-Path $logDir 'service.log')),
        @('AppRotateFiles', '1'),
        @('AppRotateBytes', '1000000')
    )
    foreach ($s in $settings) { & $Nssm set $ServiceName @s | Out-Null; Assert-ExitCode "nssm set $($s[0])" }
    # The service account is LocalSystem; give it the user's profile paths (lesson from ZelloWatchdog)
    & $Nssm set $ServiceName AppEnvironmentExtra "APPDATA=$profilePath\AppData\Roaming" "LOCALAPPDATA=$profilePath\AppData\Local" "USERPROFILE=$profilePath" | Out-Null
    Assert-ExitCode 'nssm set AppEnvironmentExtra'
}
Invoke-Step "Start service '$ServiceName'" {
    & $Nssm start $ServiceName | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "Service did not report a clean start (exit $LASTEXITCODE); check $logDir\service.log" }
}

Write-Host "Done. Agent log: $profilePath\AppData\Local\spotify-ad-mute\agent.log | Service log: $logDir\service.log"
