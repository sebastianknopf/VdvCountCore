param (
    [Parameter(Mandatory = $true)][string]$Template,
    [Parameter(Mandatory = $true)][string]$Target
)

function Parse-EnvKeys {
    param([string[]]$lines)
    $keys = @{}
    foreach ($line in $lines) {
        if ($line -match '^\s*#') { continue }
        if ($line -match '^\s*$') { continue }
        if ($line -match '^\s*([^=]+)\s*=(.*)$') {
            $key = $matches[1].Trim()
            if (-not $keys.ContainsKey($key)) {
                $keys[$key] = $true
            }
        }
    }
    return $keys
}

# read template
$templateLines = Get-Content $Template -Encoding UTF8
$targetLines   = if (Test-Path $Target) { Get-Content $Target -Encoding UTF8 } else { @() }

# extract existing variables of template and target
$templateKeys = Parse-EnvKeys $templateLines
$targetKeys   = Parse-EnvKeys $targetLines

# build diff stack
$missingKeys = @()
$collecting = $false
$blockLines = @()

foreach ($line in $templateLines) {
    if ($line -match '^\s*([^=]+)\s*=(.*)$') {
        $key = $matches[1].Trim()
        if (-not $targetKeys.ContainsKey($key)) {
            $missingKeys += $key
            $blockLines += $line
            $collecting = $true
        } else {
            $collecting = $false
        }
    } elseif ($collecting -or ($line -match '^\s*$' -and $blockLines.Count -gt 0)) {
        # also be aware of empty lines
        $blockLines += $line
    }
}

# if variables are missing, add them to the target
if ($blockLines.Count -gt 0) {
    $timestamp = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    $appendLines = @()
    $appendLines += ""
    $appendLines += "# Automatically added on $timestamp"
    $appendLines += $blockLines

    # add final block in the end
    Add-Content -Path $Target -Value $appendLines -Encoding UTF8

    Write-Host "Added $($missingKeys.Count) missing variable(s) in '$Target'."
} else {
    Write-Host "Variables already up-to-date. No changes required."
}