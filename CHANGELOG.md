# Code Improvement Agent — Change Log

## [2026-03-19 00:47] Test Generator + Self-Improvement

**Task:** Build --gen-tests, run self-improvement loop
**Files created:** test_generator.py, tests/ (18 test files)
**Files modified:** agent.py, __main__.py, base.py, ast_analyzer.py, functionality.py, llm.py
**Summary:** Added --gen-tests flag that auto-generates pytest tests via Claude API. Refactored long functions (run_analysis, main) into helpers. Made BaseAnalyzer an ABC. Generated 174 passing tests for agent's own code.
**Commits:** 797f429, 7c0b64a
**Rollback:** `git revert 797f429 7c0b64a`

## [2026-03-19 00:15] Config System + AST Analyzer + Trend Tracking

**Task:** Add 3 major features to the agent
**Files created:** config.py, analyzers/ast_analyzer.py, trends.py
**Files modified:** All 6 analyzers, scoring.py, agent.py, __main__.py
**Summary:** YAML config replaces all hardcoded thresholds. AST-based Python analysis (5 checks). Score trend tracking with regression detection.
**Commit:** 12d0ad0
**Rollback:** `git revert 12d0ad0`

## [2026-03-18 23:07] Smart Mode + Deep Review Fix

**Task:** Fix deep review truncation, add batch scanner
**Files created:** scan_all_repos_smart.ps1
**Files modified:** smart_analyzer.py
**Summary:** Increased per-file context from 2K to 6K chars. Added "do not report truncated" instruction. Created PowerShell batch scanner for all repos.
**Commit:** 9b4ab60
**Rollback:** `git revert 9b4ab60`

## [2026-03-18 21:26] Level 2: Claude API Integration

**Task:** Add smart analysis, auto-fix, and portfolio scanning
**Files created:** llm.py, smart_analyzer.py, auto_fix.py, scan_all_repos.ps1
**Summary:** --smart validates findings via Claude (50% false positive reduction). --auto-fix generates code patches. --cost estimates API usage.
**Commit:** 564c2eb
**Rollback:** `git revert 564c2eb`

## [2026-03-18 20:00] Initial Release v1.0.0

**Task:** Build the Code Improvement Agent from scratch
**Files created:** Entire package (14 files)
**Summary:** 6 static analyzers, scoring system, tagging, recommendations, markdown reports.
**Commit:** dae0946
