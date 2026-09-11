# HUNT-OS release installer (Windows PowerShell 5.1+ / pwsh).
#
# Single-line install (run in PowerShell, NOT cmd.exe):
#
#   irm https://github.com/zaaaxx11/Hunter/releases/latest/download/install.ps1 | iex
#
# IF 'irm' IS NOT RECOGNIZED: you are in cmd.exe, not PowerShell.
# Type powershell.exe first (prompt becomes PS C:\...>), then run the line above.
#
# Only if the line above fails with `The underlying connection was closed`
# (old PowerShell 5.1 without TLS 1.2 by default), run once first:
#   [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
# then retry the single line. The in-script TLS fix cannot help the initial fetch. Do not use `curl -fsSL ... | bash` here: in PowerShell
# `curl` is an Invoke-WebRequest alias without those flags (causes
# ParameterBindingException) and `bash` is absent; curl|bash is for POSIX
# shells/Git-Bash/WSL only. `cmd.exe` is unsupported - use PowerShell or
# Git Bash on Windows. Preflight: $PSVersionTable.PSVersion,
# `py -3 --version` (>= 3.10; the Microsoft Store stub is rejected).
# The installer deliberately has no parameters so the one-line irm|iex flow is
# the primary UX.  Release selection and the Python executable can be changed
# with HUNTOS_BASE_URL, HUNTOS_VERSION, and HUNTOS_PYTHON respectively.
#
# HUNTOS_BASE_URL is a release-download directory (the directory containing
# SHA256SUMS and the wheel).  When it is not set, the latest release is used,
# or the v< HUNTOS_VERSION > release when HUNTOS_VERSION is set.  The wheel is
# selected from SHA256SUMS by its canonical, valid wheel filename; the old
# huntos.whl alias is intentionally never used. HUNTOS_BASE_URL only redirects
# the in-script wheel/SHA256SUMS fetch after this installer is already
# running - it does not replace the initial installer download. Fully offline
# means downloading this reviewed file locally first and running it
# (.\install.ps1). Fail closed: missing/unreachable SHA256SUMS or wheel prints
# the editable-checkout fallback; a bad manifest aborts without installing.

$ErrorActionPreference = 'Stop'

$script:StageRun = $null
$script:Venv = $null
$script:CandidateVenv = $null
$script:BackupVenv = $null
$script:OldVenvMoved = $false
$script:NewVenvPromoted = $false
$script:InstallSucceeded = $false
$script:EnvironmentSnapshot = [ordered]@{}

function Write-Err([string]$Message) {
    Write-Host "install.ps1: $Message" -ForegroundColor Red
}

function Show-Fallback([string]$PyHint) {
    $repo = if ($env:HUNTOS_REPO) { $env:HUNTOS_REPO } else { 'zaaaxx11/Hunter' }
    Write-Err 'release artifacts are not downloadable (repo not public yet, or no release tagged).'
    Write-Err 'fallback - install editable from a checkout instead:'
    Write-Host "  git clone https://github.com/$repo.git hunteros"
    Write-Host '  cd hunteros'
    Write-Host "  $PyHint -m pip install --editable ./app --no-deps"
    Write-Host '  hunt --help'
}

function Enter-IsolatedEnvironment {
    # pip --isolated ignores pip configuration, while these process-local
    # values also prevent inherited Python/pip state from affecting venv setup.
    $names = @(
        'PIP_CONFIG_FILE', 'PIP_INDEX_URL', 'PIP_EXTRA_INDEX_URL',
        'PIP_TRUSTED_HOST', 'PIP_NO_INDEX', 'PIP_FIND_LINKS',
        'PYTHONPATH', 'PYTHONHOME', 'PYTHONUSERBASE', 'PYTHONNOUSERSITE',
        'PIP_DISABLE_PIP_VERSION_CHECK', 'PIP_NO_INPUT', 'PIP_ROOT_USER_ACTION',
        'VIRTUAL_ENV'
    )
    foreach ($name in $names) {
        $script:EnvironmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    [Environment]::SetEnvironmentVariable('PYTHONNOUSERSITE', '1', 'Process')
    [Environment]::SetEnvironmentVariable('PIP_DISABLE_PIP_VERSION_CHECK', '1', 'Process')
    [Environment]::SetEnvironmentVariable('PIP_NO_INPUT', '1', 'Process')
    [Environment]::SetEnvironmentVariable('PIP_NO_INDEX', '1', 'Process')
}

function Exit-IsolatedEnvironment {
    foreach ($name in $script:EnvironmentSnapshot.Keys) {
        [Environment]::SetEnvironmentVariable($name, $script:EnvironmentSnapshot[$name], 'Process')
    }
    $script:EnvironmentSnapshot.Clear()
}

function Test-Python([string]$Exe, [string[]]$PreArgs) {
    $probe = @($PreArgs + @('-c', 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'))
    try {
        & $Exe @probe 2>$null | Out-Null
    } catch {
        return $false
    }
    return ($LASTEXITCODE -eq 0)
}

function Invoke-Checked([string]$Exe, [string[]]$Arguments, [string]$FailureMessage) {
    & $Exe @Arguments *> $null
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw $FailureMessage
    }
}

function Resolve-Python {
    # HUNTOS_PYTHON is an executable or a command name.  A command-line form
    # such as `py -3.11` is accepted when the complete value is not itself a
    # command; an absolute path containing spaces remains a single executable.
    $script:PyExe = $null
    $script:PyArgs = @()
    $override = if ($env:HUNTOS_PYTHON) { $env:HUNTOS_PYTHON.Trim() } else { $null }

    if ($override) {
        $command = Get-Command $override -ErrorAction SilentlyContinue
        if ($command) {
            $script:PyExe = $override
        } else {
            $match = [regex]::Match($override, '^(?:"(?<quoted>[^"]+)"|(?<exe>\S+))(?:\s+(?<args>.*))?$')
            if (-not $match.Success) {
                throw "HUNTOS_PYTHON='$override' could not be resolved."
            }
            $script:PyExe = if ($match.Groups['quoted'].Success) { $match.Groups['quoted'].Value } else { $match.Groups['exe'].Value }
            if ($match.Groups['args'].Success -and $match.Groups['args'].Value) {
                $script:PyArgs = @($match.Groups['args'].Value -split '\s+')
            }
            if (-not (Get-Command $script:PyExe -ErrorAction SilentlyContinue)) {
                throw "HUNTOS_PYTHON='$override' could not be resolved."
            }
        }
        if (-not (Test-Python $script:PyExe $script:PyArgs)) {
            throw "HUNTOS_PYTHON='$override' is not a usable Python 3.10+ executable."
        }
        return
    }

    # The Microsoft Store `python` app-execution alias is rejected by the
    # version probe below, rather than being mistaken for a real interpreter.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (Test-Python 'py' @('-3')) {
            $script:PyExe = 'py'
            $script:PyArgs = @('-3')
        }
    }
    if (-not $script:PyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
        if (Test-Python 'python' @()) {
            $script:PyExe = 'python'
            $script:PyArgs = @()
        }
    }
    if (-not $script:PyExe) {
        throw 'no Python >= 3.10 found (the Windows Microsoft Store python stub is rejected). Install Python 3.10+ from https://www.python.org/downloads/ and re-run.'
    }
}

function Get-ReleaseBase([string]$Repo, [string]$Version) {
    if ($env:HUNTOS_BASE_URL) {
        return $env:HUNTOS_BASE_URL.TrimEnd('/')
    }
    if ($Version -and $Version -ne 'latest') {
        return "https://github.com/$Repo/releases/download/v$Version"
    }
    return "https://github.com/$Repo/releases/latest/download"
}

function Get-CanonicalWheel([string]$SumsPath, [string]$RequestedVersion) {
    $entries = @()
    foreach ($line in (Get-Content -LiteralPath $SumsPath)) {
        $match = [regex]::Match($line.Trim(), '^(?<hash>[0-9A-Fa-f]{64})\s+\*?(?<name>[^\s]+)$')
        if (-not $match.Success) {
            continue
        }
        $name = $match.Groups['name'].Value
        if ([IO.Path]::GetFileName($name) -ne $name) {
            continue
        }
        if ($name -match '^huntos-[0-9A-Za-z][0-9A-Za-z._-]*-py3-none-any\.whl$') {
            $entries += [pscustomobject]@{
                Name = $name
                Hash = $match.Groups['hash'].Value.ToLowerInvariant()
            }
        }
    }

    if ($RequestedVersion -and $RequestedVersion -ne 'latest') {
        $expectedName = "huntos-$RequestedVersion-py3-none-any.whl"
        $entries = @($entries | Where-Object { $_.Name -eq $expectedName })
    }
    if ($entries.Count -eq 0) {
        if ($RequestedVersion -and $RequestedVersion -ne 'latest') {
            throw "SHA256SUMS does not list the canonical wheel huntos-$RequestedVersion-py3-none-any.whl."
        }
        throw 'SHA256SUMS does not list a canonical huntos-<version>-py3-none-any.whl; refusing to install.'
    }
    if ($entries.Count -ne 1) {
        throw 'SHA256SUMS lists multiple canonical HUNT-OS wheels; set HUNTOS_VERSION to select one.'
    }
    if ($entries[0].Hash -notmatch '^[0-9a-f]{64}$') {
        throw "SHA256SUMS has an invalid digest for $($entries[0].Name)."
    }
    return $entries[0]
}

function Validate-PythonInstall([string]$PythonPath) {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
        throw "venv Python not found at $PythonPath"
    }
    $importArgs = @('-c', 'import huntos; raise SystemExit(0 if huntos.__version__ else 1)')
    Invoke-Checked $PythonPath $importArgs 'installed wheel failed the Python import validation.'
    Invoke-Checked $PythonPath @('-m', 'huntos', '--help') 'installed wheel failed `python -m huntos --help` validation.'
}

function Validate-Venv([string]$PythonPath) {
    Validate-PythonInstall $PythonPath
    $scriptDir = Split-Path -Parent $PythonPath
    $hunt = Join-Path $scriptDir 'hunt.exe'
    if (-not (Test-Path -LiteralPath $hunt -PathType Leaf)) {
        $hunt = Join-Path $scriptDir 'hunt'
    }
    if (-not (Test-Path -LiteralPath $hunt -PathType Leaf)) {
        throw "installed wheel did not create the hunt console script in $scriptDir"
    }
    # `python -m huntos --help` above exercises the same CLI parser; checking
    # the generated entry point here avoids shell-specific .exe wrapper quirks.
}

function Restore-Rollback {
    if ($script:InstallSucceeded) {
        return
    }
    if ($script:NewVenvPromoted -and (Test-Path -LiteralPath $script:Venv)) {
        Remove-Item -LiteralPath $script:Venv -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($script:OldVenvMoved -and (Test-Path -LiteralPath $script:BackupVenv) -and -not (Test-Path -LiteralPath $script:Venv)) {
        Move-Item -LiteralPath $script:BackupVenv -Destination $script:Venv -Force -ErrorAction SilentlyContinue
    }
}

function Cleanup {
    Restore-Rollback
    if ($script:InstallSucceeded -and $script:BackupVenv -and (Test-Path -LiteralPath $script:BackupVenv)) {
        Remove-Item -LiteralPath $script:BackupVenv -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($script:StageRun -and (Test-Path -LiteralPath $script:StageRun)) {
        Remove-Item -LiteralPath $script:StageRun -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$failure = $null
try {
    $repo = if ($env:HUNTOS_REPO) { $env:HUNTOS_REPO } else { 'zaaaxx11/Hunter' }
    $requestedVersion = if ($env:HUNTOS_VERSION) { $env:HUNTOS_VERSION.Trim() } else { $null }
    if ($requestedVersion -and $requestedVersion.StartsWith('v')) {
        $requestedVersion = $requestedVersion.Substring(1)
    }
    if ($requestedVersion -and $requestedVersion -ne 'latest' -and $requestedVersion -notmatch '^[0-9A-Za-z][0-9A-Za-z._-]*$') {
        throw "HUNTOS_VERSION='$($env:HUNTOS_VERSION)' is not a valid release version."
    }

    Enter-IsolatedEnvironment
    Resolve-Python
    $pyDisplay = $script:PyExe
    if ($script:PyArgs.Count -gt 0) {
        $pyDisplay = "$($script:PyExe) $($script:PyArgs -join ' ')"
    }

    $HuntosHome = if ($env:HUNTOS_HOME) { $env:HUNTOS_HOME } else { Join-Path $env:USERPROFILE '.HunterOS' }
    $Venv = Join-Path $HuntosHome 'venv'
    $script:Venv = $Venv
    $stagingRoot = Join-Path $huntosHome '.staging'
    New-Item -ItemType Directory -Force -Path $stagingRoot | Out-Null
    $script:StageRun = Join-Path $stagingRoot ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $script:StageRun | Out-Null
    $script:CandidateVenv = Join-Path $script:StageRun 'venv'
    $script:BackupVenv = Join-Path $script:StageRun 'previous-venv'

    $base = Get-ReleaseBase $repo $requestedVersion
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072

    Enter-IsolatedEnvironment
    $sumsPath = Join-Path $script:StageRun 'SHA256SUMS'
    try {
        Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile $sumsPath -UseBasicParsing
    } catch {
        Show-Fallback $pyDisplay
        throw 'release SHA256SUMS could not be downloaded.'
    }
    if (-not (Test-Path -LiteralPath $sumsPath -PathType Leaf)) {
        throw 'release SHA256SUMS was not downloaded; refusing to install.'
    }

    $wheel = Get-CanonicalWheel $sumsPath $requestedVersion
    $wheelPath = Join-Path $script:StageRun $wheel.Name
    try {
        Invoke-WebRequest -Uri "$base/$($wheel.Name)" -OutFile $wheelPath -UseBasicParsing
    } catch {
        Show-Fallback $pyDisplay
        throw "release wheel $($wheel.Name) could not be downloaded."
    }
    if (-not (Test-Path -LiteralPath $wheelPath -PathType Leaf)) {
        throw "release wheel $($wheel.Name) was not downloaded; refusing to install."
    }

    $actual = (Get-FileHash -LiteralPath $wheelPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $wheel.Hash) {
        Write-Err "sha256 mismatch for $($wheel.Name) - aborting (fail closed)."
        Write-Err "  expected: $($wheel.Hash)"
        Write-Err "  actual:   $actual"
        throw 'wheel checksum verification failed.'
    }
    Write-Host "install.ps1: sha256 verified ($($actual.Substring(0, 16))...)"

    # Keep the historical opt-in available, but it is never selected by
    # default.  The normal path below is transactional and owns its venv.
    if ($env:HUNTOS_USE_PIPX -eq '1') {
        if (-not (Get-Command pipx -ErrorAction SilentlyContinue)) {
            throw 'HUNTOS_USE_PIPX=1 but pipx is not available.'
        }
        Invoke-Checked 'pipx' @('install', '--force', $wheelPath) 'pipx install failed.'
        Write-Host 'install.ps1: installed with pipx (layout is managed by pipx). Run: hunt --help'
        $script:InstallSucceeded = $true
    } else {
        if (Test-Path -LiteralPath $script:Venv -PathType Leaf) {
            throw "$($script:Venv) exists as a file; refusing to replace it."
        }

        Invoke-Checked $script:PyExe ($script:PyArgs + @('-m', 'venv', $script:CandidateVenv)) 'python -m venv failed.'
        $candidatePython = Join-Path $script:CandidateVenv 'Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $candidatePython -PathType Leaf)) {
            throw "venv Python not found at $candidatePython"
        }
        $pipArgs = @('-m', 'pip', '--isolated', '--disable-pip-version-check', '--no-input', 'install', '--no-index', '--no-deps', $wheelPath)
        Invoke-Checked $candidatePython $pipArgs 'pip install of the verified wheel failed.'
        Validate-PythonInstall $candidatePython

        # Keep an existing install untouched until the staged venv is complete
        # and validated.  Both moves are on the same volume for a rollback path.
        if (Test-Path -LiteralPath $script:Venv) {
            Move-Item -LiteralPath $script:Venv -Destination $script:BackupVenv -Force
            $script:OldVenvMoved = $true
        }
        Move-Item -LiteralPath $script:CandidateVenv -Destination $script:Venv -Force
        $script:NewVenvPromoted = $true
        $finalPython = Join-Path $script:Venv 'Scripts\python.exe'
        Validate-Venv $finalPython
        $script:InstallSucceeded = $true

        Write-Host "install.ps1: installed into $script:Venv"
        Write-Host 'install.ps1: add it to PATH for this shell, then run hunt:'
        $scriptsPath = Join-Path $Venv 'Scripts'
        Write-Host ('  $env:Path = "' + $scriptsPath + ';" + $env:Path')
        Write-Host 'for a permanent PATH entry (current user), run:'
        $permanent = '$p = [Environment]::GetEnvironmentVariable("Path", "User"); if (($p -split ";") -notcontains "' + $scriptsPath + '") { [Environment]::SetEnvironmentVariable("Path", "' + $scriptsPath + ';" + $p, "User") }'
        Write-Host "  $permanent"
        Write-Host 'then: hunt --help'
    }
} catch {
    $failure = $_
} finally {
    Cleanup
    if ($script:EnvironmentSnapshot.Count -gt 0) {
        Exit-IsolatedEnvironment
    }
}

if ($failure) {
    Write-Err $failure.Exception.Message
    exit 1
}
