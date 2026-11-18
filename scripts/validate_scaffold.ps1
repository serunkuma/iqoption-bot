<#
.SYNOPSIS
    Documentation health check for the IQ Option Bot repository.

.DESCRIPTION
    Checks status labels, footers, placeholders, index links, AGENTS.md
    sections, and scaffold-time artefacts.

    Run from the repository root after merging the docs.

.PARAMETER Staging
    Use while the docs are still inside docs-driven/. Skips scaffold-time
    checks and ignores scaffold-only files such as prompt.md, extract.md,
    MERGE_BACK.md, HOW_TO.md, and profiles/.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\validate_scaffold.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\validate_scaffold.ps1 -Staging
#>

param(
    [switch]$Staging
)

$ErrorActionPreference = "Stop"

$Root = (Get-Location).Path
$PassCount = 0
$FailCount = 0
$Failures = New-Object System.Collections.Generic.List[string]

function Write-Pass {
    param([string]$Message)
    Write-Host "[PASS] $Message" -ForegroundColor Green
    $script:PassCount++
}

function Write-Fail {
    param(
        [string]$Message,
        [string[]]$Details = @()
    )
    Write-Host "[FAIL] $Message" -ForegroundColor Red
    foreach ($line in $Details) {
        Write-Host "       $line"
    }
    $script:FailCount++
    $script:Failures.Add($Message)
}

function Get-ProjectMarkdown {
    $excludedPrefixes = @(
        "docs-driven\",
        "sources\",
        ".git\",
        ".venv\",
        "node_modules\"
    )

    if ($Staging) {
        $excludedPrefixes += @(
            "profiles\",
            "prompt.md",
            "extract.md",
            "MERGE_BACK.md",
            "HOW_TO.md"
        )
    }

    Get-ChildItem -Path $Root -Recurse -Filter "*.md" -File | Where-Object {
        $relative = $_.FullName.Substring($Root.Length).TrimStart('\')
        $skip = $false

        foreach ($prefix in $excludedPrefixes) {
            if ($relative.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $skip = $true
                break
            }
        }

        if (-not $skip -and $relative -match "(^|\\)__pycache__(\\|$)") {
            $skip = $true
        }

        -not $skip
    }
}

Write-Host "Validating documentation at: $Root"
Write-Host "----------------------------------------"

$markdown = @(Get-ProjectMarkdown)

# Check 1: Project Name placeholder
$hits = @($markdown | Select-String -Pattern "Project Name" -SimpleMatch)
if ($hits.Count -eq 0) {
    Write-Pass "No 'Project Name' placeholder left in project docs"
} else {
    Write-Fail "'Project Name' placeholder still present" @($hits | Select-Object -First 5 | ForEach-Object { "$($_.Path):$($_.LineNumber)" })
}

# Check 2: YYYY-MM-DD placeholder
$hits = @($markdown | Select-String -Pattern "YYYY-MM-DD" -SimpleMatch)
if ($hits.Count -eq 0) {
    Write-Pass "No 'YYYY-MM-DD' placeholder left"
} else {
    Write-Fail "'YYYY-MM-DD' placeholder still present" @($hits | Select-Object -First 5 | ForEach-Object { "$($_.Path):$($_.LineNumber)" })
}

# Check 3: AGENTS.md template placeholders
$agentsPath = Join-Path $Root "AGENTS.md"
if (Test-Path $agentsPath) {
    $agents = Get-Content -Path $agentsPath -Raw
    if ($agents -match "<!-- One-paragraph") {
        Write-Fail "AGENTS.md still has template HTML-comment placeholders"
    } else {
        Write-Pass "AGENTS.md has no template HTML-comment placeholders"
    }
} else {
    Write-Fail "AGENTS.md not found at project root"
}

# Check 4: Status labels in docs/{system,concepts,data,planning}
$statusDirs = @("docs\system", "docs\concepts", "docs\data", "docs\planning")
$missingStatus = @()
foreach ($dir in $statusDirs) {
    $full = Join-Path $Root $dir
    if (-not (Test-Path $full)) { continue }
    Get-ChildItem -Path $full -Filter "*.md" -File -Recurse | ForEach-Object {
        $head = Get-Content -Path $_.FullName -TotalCount 5
        if (-not ($head | Where-Object { $_ -match "^Status:" })) {
            $missingStatus += $_.FullName.Substring($Root.Length).TrimStart('\')
        }
    }
}

if ($missingStatus.Count -eq 0) {
    Write-Pass "All docs in system/concepts/data/planning have a Status label"
} else {
    Write-Fail "$($missingStatus.Count) doc(s) missing Status label" $missingStatus
}

# Check 5: Last updated footer in docs/
$docsRoot = Join-Path $Root "docs"
$missingFooter = @()
if (Test-Path $docsRoot) {
    Get-ChildItem -Path $docsRoot -Filter "*.md" -File -Recurse | ForEach-Object {
        $tail = Get-Content -Path $_.FullName -Tail 5
        if (-not ($tail | Where-Object { $_ -match "Last updated" })) {
            $missingFooter += $_.FullName.Substring($Root.Length).TrimStart('\')
        }
    }
}

if ($missingFooter.Count -eq 0) {
    Write-Pass "All docs/ files have a 'Last updated' footer"
} else {
    Write-Fail "$($missingFooter.Count) doc(s) missing 'Last updated' footer" $missingFooter
}

# Check 6: AGENTS.md Section 1 has content
if (Test-Path $agentsPath) {
    $agents = Get-Content -Path $agentsPath -Raw
    $sectionMatch = [regex]::Match($agents, "(?ms)^## 1\. What This System Does\s*(.*?)^---")
    $content = $null
    if ($sectionMatch.Success) {
        $content = $sectionMatch.Groups[1].Value -split "`r?`n" |
            Where-Object { $_.Trim() -ne "" -and -not $_.Trim().StartsWith("<!--") } |
            Select-Object -First 1
    }
    if ($content) {
        Write-Pass "AGENTS.md Section 1 has content"
    } else {
        Write-Fail "AGENTS.md Section 1 is empty" @("Add a one-paragraph description under '## 1. What This System Does'")
    }
}

# Check 7: README.md is project-specific
$readmePath = Join-Path $Root "README.md"
if (Test-Path $readmePath) {
    $readme = Get-Content -Path $readmePath -Raw
    if ($readme -match "Universal Project Kickstart") {
        Write-Fail "README.md still contains the universal scaffold template"
    } else {
        Write-Pass "README.md is project-specific"
    }
} else {
    Write-Fail "README.md not found at project root"
}

# Check 8: docs/index.md links resolve
$indexPath = Join-Path $docsRoot "index.md"
if (Test-Path $indexPath) {
    $index = Get-Content -Path $indexPath -Raw
    $links = [regex]::Matches($index, "\]\(([^)]+\.md[^)]*)\)") | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
    $broken = @()
    foreach ($link in $links) {
        if ($link -match "^(https?:|/|#)") { continue }
        $clean = $link -replace "#.*$", ""
        $target = [System.IO.Path]::GetFullPath((Join-Path $docsRoot $clean))
        if (-not (Test-Path $target)) {
            $broken += "$link"
        }
    }
    if ($broken.Count -eq 0) {
        Write-Pass "All links in docs/index.md resolve to existing files"
    } else {
        Write-Fail "$($broken.Count) broken link(s) in docs/index.md" $broken
    }
} else {
    Write-Fail "docs/index.md not found"
}

# Check 9: AGENTS.md Change Log has project-specific entries
if (Test-Path $agentsPath) {
    $agents = Get-Content -Path $agentsPath -Raw
    $changeLogMatch = [regex]::Match($agents, "(?ms)^## 9\. Change Log\s*(.*)$")
    $entries = @()
    if ($changeLogMatch.Success) {
        $entries = $changeLogMatch.Groups[1].Value -split "`r?`n" |
            Where-Object { $_ -match "^\|\s*\d{4}-\d{2}-\d{2}" -and $_ -notmatch "Initial scaffold created" }
    }
    if ($entries.Count -gt 0) {
        Write-Pass "AGENTS.md Change Log has project-specific entries"
    } else {
        Write-Fail "AGENTS.md Change Log only has the template entry" @("Add at least one real change-log entry")
    }
}

# Check 10: No unresolved TODO markers in AGENTS.md
if (Test-Path $agentsPath) {
    $hits = @(Select-String -Path $agentsPath -Pattern "> \*\*TODO:\*\*" -SimpleMatch)
    if ($hits.Count -eq 0) {
        Write-Pass "AGENTS.md has no unresolved TODOs"
    } else {
        Write-Fail "AGENTS.md has unresolved TODOs" @($hits | ForEach-Object { "$($_.LineNumber): $($_.Line.Trim())" })
    }
}

# Check 11: Scaffold-time artefacts absent
if (-not $Staging) {
    $leaks = @()
    if (Test-Path (Join-Path $Root "profiles")) { $leaks += "profiles/ directory" }
    if (Test-Path (Join-Path $Root "prompt.md")) { $leaks += "prompt.md" }
    if (Test-Path (Join-Path $Root "extract.md")) { $leaks += "extract.md" }
    if (Test-Path (Join-Path $Root "MERGE_BACK.md")) { $leaks += "MERGE_BACK.md" }
    if (Test-Path (Join-Path $Root "HOW_TO.md")) { $leaks += "HOW_TO.md" }

    if ($leaks.Count -eq 0) {
        Write-Pass "No scaffold-time artefacts present"
    } else {
        Write-Fail "$($leaks.Count) scaffold-time artefact(s) present" $leaks
    }
} else {
    Write-Host "[SKIP] Scaffold-time artefact check (staging mode)" -ForegroundColor Yellow
}

Write-Host "----------------------------------------"
$total = $PassCount + $FailCount
if ($FailCount -eq 0) {
    Write-Host "Summary: $PassCount/$total checks passed. Documentation is clean." -ForegroundColor Green
    exit 0
} else {
    Write-Host "Summary: $PassCount/$total checks passed. Fix the $FailCount failure(s) and re-run." -ForegroundColor Yellow
    exit 1
}
