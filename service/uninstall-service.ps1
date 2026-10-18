#Requires -Version 5.1
<#
.SYNOPSIS
    Removes the Spotify Ad Mute service and logon task. Leaves the code, logs and Spotify alone.
.EXAMPLE
    .\uninstall-service.ps1 -Nssm C:\tools\nssm.exe
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Nssm,
    [string]$ServiceName = 'SpotifyAdMute',
    [string]$TaskName = 'SpotifyAdMute-Agent',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Invoke-Step {
    param([string]$Description, [scriptblock]$Action)
    if ($DryRun) { Write-Host "[dry-run] $Description"; return }
    Write-Host $Description
    & $Action
}

if (-not $DryRun -and -not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators')) {
    throw 'Run this script from an elevated (administrator) shell.'
}

# Service first, so the guard cannot start the task again while it is being removed
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Invoke-Step "Stop and remove service '$ServiceName'" {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue   # not "nssm stop": see install-service.ps1
        & $Nssm remove $ServiceName confirm | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "nssm remove failed with exit code $LASTEXITCODE" }
    }
} else { Write-Host "Service '$ServiceName' not installed." }

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Invoke-Step "Stop and remove task '$TaskName'" {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
} else { Write-Host "Task '$TaskName' not registered." }
