<#
.SYNOPSIS
Installs Codex Model Sync and runs the first-run Codex relay setup.

.DESCRIPTION
Use from Windows PowerShell. Python 3 is required. The script defaults to
$env:CODEX_HOME or $HOME\.codex and forwards setup options to the shared
Python implementation.

.EXAMPLE
.\install.ps1 -ProviderRegion us -Model gpt-6.1-sol
#>
[CmdletBinding()]
param(
    [string]$Catalog,
    [string]$SourceUrl,
    [string]$Group,
    [string]$Platform,
    [string]$Payload,
    [string]$Model,
    [ValidateSet("us", "jp")]
    [string]$ProviderRegion,
    [string]$ProviderUrl,
    [switch]$Reconfigure,
    [switch]$NonInteractive,
    [switch]$ApiKeyStdin,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Get-Help $PSCommandPath -Detailed
    exit 0
}

if (-not $SourceUrl) {
    $SourceUrl = if ($env:CODEX_MODEL_SOURCE_URL) { $env:CODEX_MODEL_SOURCE_URL } else { "https://xclis.ai/pricing" }
}
if (-not $Group) {
    $Group = if ($env:CODEX_MODEL_GROUP) { $env:CODEX_MODEL_GROUP } else { "GPT-稳定-STABLE" }
}
if (-not $Platform) {
    $Platform = if ($env:CODEX_MODEL_PLATFORM) { $env:CODEX_MODEL_PLATFORM } else { "openai" }
}
if ($env:CODEX_MODEL_CATALOG -and -not $Catalog) {
    $Catalog = $env:CODEX_MODEL_CATALOG
}
if ($Catalog -eq "") {
    throw "Catalog path cannot be empty."
}

function Resolve-Python {
    if ($env:PYTHON) {
        $configured = Get-Command $env:PYTHON -ErrorAction SilentlyContinue
        if ($configured) {
            return @($configured.Source)
        }
    }

    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @($pyLauncher.Source, "-3")
    }

    throw "Python 3 was not found. Install Python 3 and retry, or set PYTHON to its executable path."
}

function Copy-SkillTree {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$Target
    )

    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        if ($item.Name -in @(".git", "__pycache__") -or $item.Extension -eq ".pyc") {
            continue
        }
        $destination = Join-Path $Target $item.Name
        if ($item.PSIsContainer) {
            Copy-SkillTree -Source $item.FullName -Target $destination
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $destination -Force
        }
    }
}

$sourceDir = (Resolve-Path -LiteralPath $PSScriptRoot).Path
$codexHome = if ($env:CODEX_HOME) {
    [Environment]::ExpandEnvironmentVariables($env:CODEX_HOME)
} else {
    Join-Path $HOME ".codex"
}
$codexHome = [IO.Path]::GetFullPath($codexHome)
$targetDir = Join-Path $codexHome "skills\codex-model-sync"

if ([IO.Path]::GetFullPath($sourceDir).TrimEnd("\") -ine [IO.Path]::GetFullPath($targetDir).TrimEnd("\")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $codexHome "skills") | Out-Null
    if (Test-Path -LiteralPath $targetDir) {
        Remove-Item -LiteralPath $targetDir -Recurse -Force
    }
    Copy-SkillTree -Source $sourceDir -Target $targetDir
} else {
    Write-Host "Using existing installation at $targetDir"
}

$pythonParts = Resolve-Python
$python = $pythonParts[0]
$pythonPrefix = if ($pythonParts.Count -gt 1) { $pythonParts[1..($pythonParts.Count - 1)] } else { @() }
$setupScript = Join-Path $targetDir "scripts\setup_codex.py"
$setupArgs = @("--codex-home", $codexHome, "--source-url", $SourceUrl, "--group", $Group, "--platform", $Platform)

if ($Catalog) {
    $catalogParent = Split-Path -Parent ([IO.Path]::GetFullPath($Catalog))
    New-Item -ItemType Directory -Force -Path $catalogParent | Out-Null
    $setupArgs += @("--catalog", $Catalog)
}
if ($Payload) {
    $setupArgs += @("--payload", $Payload)
}
if ($Model) {
    $setupArgs += @("--model", $Model)
}
if ($ProviderRegion) {
    $setupArgs += @("--provider-region", $ProviderRegion)
}
if ($ProviderUrl) {
    $setupArgs += @("--provider-url", $ProviderUrl)
}
if ($Reconfigure) {
    $setupArgs += "--reconfigure"
}
if ($NonInteractive) {
    $setupArgs += "--non-interactive"
}
if ($ApiKeyStdin) {
    $setupArgs += "--api-key-stdin"
}

& $python @pythonPrefix $setupScript @setupArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Installed Codex Model Sync to $targetDir"
