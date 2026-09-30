$ErrorActionPreference = "Stop"
$Arguments = $args

function Resolve-Python {
    if ($env:PYTHON) {
        $configured = Get-Command $env:PYTHON -ErrorAction SilentlyContinue
        if ($configured) { return @($configured.Source) }
    }
    $python = Get-Command "python" -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($pyLauncher) { return @($pyLauncher.Source, "-3") }
    throw "Python 3 was not found."
}

$pythonParts = Resolve-Python
$python = $pythonParts[0]
$pythonPrefix = if ($pythonParts.Count -gt 1) { $pythonParts[1..($pythonParts.Count - 1)] } else { @() }
$scriptPath = Join-Path $PSScriptRoot "configure_codex.py"
& $python @pythonPrefix $scriptPath @Arguments
exit $LASTEXITCODE
