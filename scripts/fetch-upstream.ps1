param(
    [Parameter(Mandatory=$true)][string]$Destination,
    [string]$Ref = ''
)
$ErrorActionPreference = 'Stop'
$repo = 'https://github.com/amnweb/yasb.git'
if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Force -Recurse }

Write-Host 'Discovering the upstream default branch...'
$head = & git ls-remote --symref $repo HEAD
if ($LASTEXITCODE -ne 0) { throw 'Could not query upstream HEAD' }
$headLine = $head | Where-Object { $_ -match '^ref:\s+refs/heads/([^\s]+)\s+HEAD$' } | Select-Object -First 1
if (-not $headLine) { throw "Could not detect upstream default branch: $head" }
$defaultBranch = [regex]::Match($headLine, '^ref:\s+refs/heads/([^\s]+)\s+HEAD$').Groups[1].Value
Write-Host "Upstream default branch: $defaultBranch"

# A clean clone every run: no copy of the developer's source is committed to this builder.
& git clone --no-checkout --filter=blob:none $repo $Destination
if ($LASTEXITCODE -ne 0) { throw 'git clone failed' }
& git -C $Destination fetch --tags --force origin
if ($LASTEXITCODE -ne 0) { throw 'git fetch tags failed' }

$requested = $Ref.Trim()
if ($requested -eq '') {
    $rev = "refs/remotes/origin/$defaultBranch"
} else {
    # Resolve an explicitly selected tag, branch, or full SHA; no interpolation into a shell.
    $candidates = @("refs/tags/$requested", "refs/remotes/origin/$requested", $requested)
    $rev = $null
    foreach ($candidate in $candidates) {
        $probe = & git -C $Destination rev-parse --verify --quiet "$candidate^{commit}" 2>$null
        if ($LASTEXITCODE -eq 0 -and $probe -match '^[0-9a-f]{40}$') { $rev = $candidate; break }
    }
    if (-not $rev) {
        & git -C $Destination fetch --no-tags origin $requested
        if ($LASTEXITCODE -ne 0) { throw "Unable to fetch upstream ref '$requested'" }
        $rev = 'FETCH_HEAD'
    }
}
$commit = (& git -C $Destination rev-parse --verify "$rev^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or $commit -notmatch '^[0-9a-f]{40}$') { throw 'Could not resolve upstream commit.' }
& git -C $Destination checkout --force --detach $commit
if ($LASTEXITCODE -ne 0) { throw 'Could not check out selected upstream commit.' }

foreach ($required in @('pyproject.toml', 'LICENSE', 'src/settings.py', 'src/build.py', 'src/core/utils/system.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Destination $required))) {
        throw "Upstream layout changed: missing $required"
    }
}
Write-Host "Fetched commit: $commit"
Add-Content -Path $env:GITHUB_ENV -Value "UPSTREAM_DIR=$Destination"
Add-Content -Path $env:GITHUB_ENV -Value "UPSTREAM_COMMIT=$commit"
Add-Content -Path $env:GITHUB_ENV -Value "UPSTREAM_DEFAULT_BRANCH=$defaultBranch"
Add-Content -Path $env:GITHUB_ENV -Value "UPSTREAM_REQUESTED_REF=$requested"
