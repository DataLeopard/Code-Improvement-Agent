# ============================================================
# Scan All GitHub Repos with Code Improvement Agent (SMART MODE)
# ============================================================
# Run: & "C:\Users\Veteran\OneDrive\03_PROJECTS\Code_Improvement_Agent\scan_all_repos_smart.ps1"
# Reports go to: Code_Improvement_Agent\reports_smart\
# Requires: ANTHROPIC_API_KEY set in environment
# ============================================================

$AgentDir = "C:\Users\Veteran\OneDrive\03_PROJECTS\Code_Improvement_Agent"
$ReportsDir = "$AgentDir\reports_smart"
$TempCloneDir = "$env:TEMP\cia_repo_scans"

New-Item -ItemType Directory -Force -Path $ReportsDir | Out-Null
New-Item -ItemType Directory -Force -Path $TempCloneDir | Out-Null

# Check API key
if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "ERROR: ANTHROPIC_API_KEY not set. Run:" -ForegroundColor Red
    Write-Host '  $env:ANTHROPIC_API_KEY = "sk-ant-..."' -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "=== Code Improvement Agent - Smart Portfolio Scan ===" -ForegroundColor Cyan
Write-Host "Mode: --smart --auto-fix (dry run)" -ForegroundColor Magenta
Write-Host "Fetching repos from GitHub..." -ForegroundColor Gray
Write-Host ""

$repos = gh repo list --limit 100 --json name,url | ConvertFrom-Json

$skip = @("Code-Improvement-Agent")

$summary = @()
$totalCost = 0

foreach ($repo in $repos) {
    $name = $repo.name

    if ($skip -contains $name) {
        Write-Host "  SKIP: $name (skipping self)" -ForegroundColor DarkGray
        continue
    }

    Write-Host "--- Smart Scanning: $name ---" -ForegroundColor Yellow

    $clonePath = "$TempCloneDir\$name"
    $reportFile = "$ReportsDir\${name}.md"
    $jsonFile = "$ReportsDir\${name}.json"

    if (Test-Path $clonePath) {
        Write-Host "  Using cached clone" -ForegroundColor DarkGray
    } else {
        git clone --depth 1 $repo.url $clonePath 2>&1 | Out-Null
    }

    Push-Location $AgentDir
    python -m code_improvement_agent $clonePath -o $reportFile --json --smart --auto-fix 2>&1
    Pop-Location

    if (Test-Path $jsonFile) {
        $meta = Get-Content $jsonFile | ConvertFrom-Json
        $score = $meta.scores.overall
        $tag = $meta.tag
        $rec = $meta.recommendation
        $findings = $meta.total_findings
        $mode = $meta.mode

        if ($score -ge 7.5) { $color = "Green" } elseif ($score -ge 5) { $color = "Yellow" } else { $color = "Red" }
        Write-Host "  Score: $score/10 | Tag: $tag | $rec | $findings findings | Mode: $mode" -ForegroundColor $color

        $summary += [PSCustomObject]@{
            Repo           = $name
            Score          = $score
            Tag            = $tag
            Recommendation = $rec
            Findings       = $findings
            Mode           = $mode
        }
    } else {
        Write-Host "  ERROR: No output generated" -ForegroundColor Red
    }

    Write-Host ""
}

Write-Host ""
Write-Host "=== SMART PORTFOLIO SUMMARY ===" -ForegroundColor Cyan
$summary | Sort-Object Score -Descending | Format-Table -AutoSize

$csvPath = "$ReportsDir\_portfolio_summary_smart.csv"
$summary | Sort-Object Score -Descending | Export-Csv -Path $csvPath -NoTypeInformation
Write-Host "Summary CSV: $csvPath" -ForegroundColor Gray
Write-Host "Individual reports: $ReportsDir" -ForegroundColor Gray
Write-Host ""
Write-Host "Done! Check reports for auto-fix patches." -ForegroundColor Green
