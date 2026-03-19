# ============================================================
# Scan All GitHub Repos with Code Improvement Agent
# ============================================================
# Run: & "C:\Users\Veteran\OneDrive\03_PROJECTS\Code_Improvement_Agent\scan_all_repos.ps1"
# Reports go to: Code_Improvement_Agent\reports\
# ============================================================

$AgentDir = "C:\Users\Veteran\OneDrive\03_PROJECTS\Code_Improvement_Agent"
$ReportsDir = "$AgentDir\reports"
$TempCloneDir = "$env:TEMP\cia_repo_scans"

New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null
New-Item -ItemType Directory -Force -Path $TempCloneDir | Out-Null

Write-Host ""
Write-Host "=== Code Improvement Agent - Full Portfolio Scan ===" -ForegroundColor Cyan
Write-Host "Fetching repos from GitHub..." -ForegroundColor Gray
Write-Host ""

$repos = gh repo list --limit 100 --json name,url | ConvertFrom-Json

$skip = @("Code-Improvement-Agent")

$summary = @()

foreach ($repo in $repos) {
    $name = $repo.name

    if ($skip -contains $name) {
        Write-Host "  SKIP: $name (skipping self)" -ForegroundColor DarkGray
        continue
    }

    Write-Host "--- Scanning: $name ---" -ForegroundColor Yellow

    $clonePath = "$TempCloneDir\$name"
    $reportFile = "$ReportsDir\${name}.md"
    $jsonFile = "$ReportsDir\${name}.json"

    if (Test-Path $clonePath) {
        Write-Host "  Using cached clone" -ForegroundColor DarkGray
    } else {
        git clone --depth 1 $repo.url $clonePath 2>&1 | Out-Null
    }

    Push-Location $AgentDir
    python -m code_improvement_agent $clonePath -o $reportFile --json -q 2>&1
    Pop-Location

    if (Test-Path $jsonFile) {
        $meta = Get-Content $jsonFile | ConvertFrom-Json
        $score = $meta.scores.overall
        $tag = $meta.tag
        $rec = $meta.recommendation
        $findings = $meta.total_findings

        if ($score -ge 7.5) { $color = "Green" } elseif ($score -ge 5) { $color = "Yellow" } else { $color = "Red" }
        Write-Host "  Score: $score/10 | Tag: $tag | $rec | $findings findings" -ForegroundColor $color

        $summary += [PSCustomObject]@{
            Repo           = $name
            Score          = $score
            Tag            = $tag
            Recommendation = $rec
            Findings       = $findings
        }
    } else {
        Write-Host "  ERROR: No output generated" -ForegroundColor Red
    }

    Write-Host ""
}

Write-Host ""
Write-Host "=== PORTFOLIO SUMMARY ===" -ForegroundColor Cyan
$summary | Sort-Object Score -Descending | Format-Table -AutoSize

$csvPath = "$ReportsDir\_portfolio_summary.csv"
$summary | Sort-Object Score -Descending | Export-Csv -Path $csvPath -NoTypeInformation
Write-Host "Summary CSV: $csvPath" -ForegroundColor Gray
Write-Host "Individual reports: $ReportsDir" -ForegroundColor Gray
Write-Host ""
Write-Host "Done!" -ForegroundColor Green
