param(
    [ValidatePattern('^[A-Za-z0-9._/-]+$')]
    [string]$Ref = "main",
    [switch]$NoUpdateShell
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$repoUrl = if ($env:AMPLIFIER_TUI_REPO_URL) {
    $env:AMPLIFIER_TUI_REPO_URL
} else {
    "https://github.com/michaeljabbour/amplifier-app-tui.git"
}
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("amplifier-tui-install-" + [guid]::NewGuid())
$sourceDir = Join-Path $temporaryRoot "source"
$constraintsFile = Join-Path $temporaryRoot "runtime-constraints.txt"

function Fail([string]$Message) {
    throw "install failed: $Message"
}

function FailValidation([string]$Message) {
    throw "install validation failed: $Message"
}

function Resolve-Uv {
    $command = Get-Command uv -CommandType Application -ErrorAction SilentlyContinue
    if ($command) { return $command.Path }
    $uvInstallDir = if ($env:UV_INSTALL_DIR) {
        $env:UV_INSTALL_DIR
    } else {
        Join-Path $env:USERPROFILE ".local\bin"
    }
    $localUv = Join-Path $uvInstallDir "uv.exe"
    if (Test-Path -LiteralPath $localUv -PathType Leaf) { return $localUv }

    Write-Host "Installing uv from Astral's official installer"
    $priorNoModifyPath = $env:UV_NO_MODIFY_PATH
    try {
        if ($NoUpdateShell) { $env:UV_NO_MODIFY_PATH = "1" }
        Invoke-RestMethod -UseBasicParsing "https://astral.sh/uv/install.ps1" | Invoke-Expression
    } finally {
        $env:UV_NO_MODIFY_PATH = $priorNoModifyPath
    }
    if (Test-Path -LiteralPath $localUv -PathType Leaf) { return $localUv }
    Fail "uv installed, but uv.exe could not be found"
}

function Resolve-Commit([string]$RequestedRef) {
    if ($RequestedRef -match '^[0-9a-fA-F]{40}$') {
        return $RequestedRef.ToLowerInvariant()
    }
    $refs = & git ls-remote --exit-code $repoUrl `
        "refs/heads/$RequestedRef" "refs/tags/$RequestedRef" "refs/tags/$RequestedRef^{}"
    if ($LASTEXITCODE -ne 0) { Fail "could not resolve '$RequestedRef' from $repoUrl" }
    $candidates = @($refs | ForEach-Object {
        $parts = $_ -split "`t", 2
        if ($parts.Count -eq 2) { [pscustomobject]@{ Sha = $parts[0]; Name = $parts[1] } }
    })
    foreach ($target in @("refs/heads/$RequestedRef", "refs/tags/$RequestedRef^{}", "refs/tags/$RequestedRef")) {
        $match = $candidates | Where-Object Name -eq $target | Select-Object -First 1
        if ($match -and $match.Sha -match '^[0-9a-fA-F]{40}$') {
            return $match.Sha.ToLowerInvariant()
        }
    }
    Fail "remote returned an invalid commit for '$RequestedRef'"
}

try {
    if ($repoUrl -notmatch '^https://') { Fail "repository URL must use https://" }
    if ($repoUrl -match '^https://[^/]*@') { Fail "repository URL must not contain credentials" }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Fail "Git for Windows is required"
    }

    $uvBin = Resolve-Uv
    $resolvedSha = Resolve-Commit $Ref
    Write-Host "Installing Amplifier TUI source commit $resolvedSha"
    New-Item -ItemType Directory -Path $temporaryRoot -Force | Out-Null
    & git init -q $sourceDir
    if ($LASTEXITCODE -ne 0) { Fail "could not prepare the source checkout" }
    & git -C $sourceDir remote add origin $repoUrl
    & git -C $sourceDir fetch --quiet --depth=1 origin $resolvedSha
    if ($LASTEXITCODE -ne 0) { Fail "could not fetch source commit $resolvedSha" }
    & git -C $sourceDir checkout --quiet --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { Fail "could not check out source commit $resolvedSha" }
    $checkedOut = (& git -C $sourceDir rev-parse HEAD).Trim().ToLowerInvariant()
    if ($checkedOut -ne $resolvedSha) { Fail "source checkout did not match $resolvedSha" }
    if (-not (Test-Path -LiteralPath (Join-Path $sourceDir "uv.lock") -PathType Leaf)) {
        Fail "source commit does not contain uv.lock"
    }

    & $uvBin export --frozen --no-dev --no-editable --no-emit-project --no-config `
        --project $sourceDir --output-file $constraintsFile | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $constraintsFile -PathType Leaf)) {
        Fail "the checked-in uv.lock could not be exported"
    }

    $packageUrl = "git+$repoUrl@$resolvedSha"
    & $uvBin tool install --reinstall --no-config --constraints $constraintsFile $packageUrl
    if ($LASTEXITCODE -ne 0) { Fail "uv could not install Amplifier TUI" }

    $toolBinOutput = @(& $uvBin tool dir --bin)
    $toolBinDir = ($toolBinOutput -join "`n").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $toolBinDir) {
        FailValidation "uv could not locate the installed tool executable directory"
    }
    $appBin = Join-Path $toolBinDir "amplifier-tui.exe"
    if (-not (Test-Path -LiteralPath $appBin -PathType Leaf)) {
        FailValidation "installation finished without amplifier-tui.exe"
    }
    $versionOutput = @(& $appBin --version)
    $version = ($versionOutput -join "`n").Trim()
    if ($LASTEXITCODE -ne 0 -or -not $version) {
        FailValidation "the installed runtime could not report its version"
    }
    & $appBin --help | Out-Null
    if ($LASTEXITCODE -ne 0) { FailValidation "the installed runtime failed its help check" }

    if (-not $NoUpdateShell -and -not (($env:PATH -split ';') -contains $toolBinDir)) {
        & $uvBin tool update-shell | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Amplifier TUI is installed and verified, but uv could not add $toolBinDir to your shell PATH. Add it manually before opening a new terminal."
        }
    }
    Write-Host "Installed and verified $appBin - $version"
} finally {
    if (Test-Path -LiteralPath $temporaryRoot) {
        Remove-Item -LiteralPath $temporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
