"""Repo Review Launcher — scans projects, detects app types, launches and monitors them."""

import json
import os
import subprocess
import sys
import time
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Where to find projects
DEFAULT_PROJECTS_DIR = r"C:\Users\Veteran\OneDrive\03_PROJECTS"

# Known project type detectors
DETECTORS = [
    {
        "type": "nextjs",
        "detect": lambda p: (p / "next.config.ts").exists() or (p / "next.config.js").exists(),
        "install": "npm install",
        "launch": "npm run dev",
        "port_pattern": "localhost:3000",
        "needs_install": lambda p: not (p / "node_modules").exists(),
    },
    {
        "type": "vite-react",
        "detect": lambda p: (p / "vite.config.js").exists() or (p / "vite.config.ts").exists(),
        "install": "npm install",
        "launch": "npm run dev",
        "port_pattern": "localhost:5173",
        "needs_install": lambda p: not (p / "node_modules").exists(),
    },
    {
        "type": "node-monorepo",
        "detect": lambda p: (p / "package.json").exists() and (p / "apps").is_dir(),
        "install": "npm install",
        "launch": None,
        "port_pattern": None,
        "needs_install": lambda p: not (p / "node_modules").exists(),
    },
    {
        "type": "python-package",
        "detect": lambda p: (p / "pyproject.toml").exists() or (p / "setup.py").exists(),
        "install": "pip install -e .",
        "launch": None,
        "port_pattern": None,
        "needs_install": lambda p: True,
    },
    {
        "type": "streamlit",
        "detect": lambda p: any(f.name == "app.py" for f in p.iterdir() if f.is_file())
                            and "streamlit" in (p / "requirements.txt").read_text(errors="ignore")
                            if (p / "requirements.txt").exists() else False,
        "install": "pip install -r requirements.txt",
        "launch": "streamlit run app.py",
        "port_pattern": "localhost:8501",
        "needs_install": lambda p: True,
    },
    {
        "type": "fastapi",
        "detect": lambda p: _file_contains(p, "*.py", "from fastapi") or _file_contains(p, "*.py", "import fastapi"),
        "install": "pip install -r requirements.txt",
        "launch": "uvicorn main:app --reload",
        "port_pattern": "localhost:8000",
        "needs_install": lambda p: True,
    },
    {
        "type": "flask",
        "detect": lambda p: _file_contains(p, "*.py", "from flask") or _file_contains(p, "*.py", "import flask"),
        "install": "pip install -r requirements.txt",
        "launch": "python app.py",
        "port_pattern": "localhost:5000",
        "needs_install": lambda p: True,
    },
    {
        "type": "python-script",
        "detect": lambda p: any(f.suffix == ".py" for f in p.iterdir() if f.is_file()),
        "install": "pip install -r requirements.txt",
        "launch": None,  # not auto-launchable
        "port_pattern": None,
        "needs_install": lambda p: (p / "requirements.txt").exists(),
    },
    {
        "type": "docker",
        "detect": lambda p: (p / "docker-compose.yml").exists() or (p / "Dockerfile").exists(),
        "install": None,
        "launch": "docker-compose up",
        "port_pattern": None,
        "needs_install": lambda p: False,
    },
    {
        "type": "static-site",
        "detect": lambda p: (p / "index.html").exists(),
        "install": None,
        "launch": "python -m http.server 8080",
        "port_pattern": "localhost:8080",
        "needs_install": lambda p: False,
    },
    {
        "type": "powershell-scripts",
        "detect": lambda p: any(f.suffix == ".ps1" for f in p.iterdir() if f.is_file()),
        "install": None,
        "launch": None,
        "port_pattern": None,
        "needs_install": lambda p: False,
    },
]


def _file_contains(project_path: Path, glob_pattern: str, search_text: str) -> bool:
    """Check if any source file matching the glob contains the search text.

    Only searches direct children and src/ — skips reports, node_modules, etc.
    """
    skip = {"node_modules", "reports", "reports_smart", "reports_after", ".git",
            "__pycache__", ".next", "dist", "build"}
    try:
        for f in project_path.glob(glob_pattern):
            if f.is_file() and f.stat().st_size < 100_000:
                # Skip files inside excluded directories
                if any(part in skip for part in f.relative_to(project_path).parts):
                    continue
                # Skip non-source files (reports, docs, etc.)
                if f.suffix in (".md", ".txt", ".json", ".log"):
                    continue
                if search_text in f.read_text(errors="ignore"):
                    return True
    except OSError:
        pass
    return False


@dataclass
class ProjectInfo:
    name: str
    path: str
    project_type: str = "unknown"
    is_git: bool = False
    branch: str = ""
    has_uncommitted: bool = False
    last_commit_date: str = ""
    last_commit_msg: str = ""
    launch_command: str | None = None
    install_command: str | None = None
    needs_install: bool = False
    port: str | None = None
    status: str = "not_scanned"  # not_scanned, ready, launched, failed, skipped
    pid: int | None = None
    error: str = ""
    review: str = ""  # pass, fail, needs_review, archive


def scan_projects(projects_dir: str = DEFAULT_PROJECTS_DIR) -> list[ProjectInfo]:
    """Scan a directory for projects and detect their types."""
    projects = []
    root = Path(projects_dir)

    if not root.is_dir():
        logger.error(f"Projects directory not found: {projects_dir}")
        return projects

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith(".") or entry.name in ("node_modules", "__pycache__"):
            continue

        project = _analyze_project(entry)
        projects.append(project)

        # Check subdirectories (e.g., Claude_Projects/Quinoa_Application)
        if not project.is_git:
            for sub in sorted(entry.iterdir()):
                if sub.is_dir() and (sub / ".git").exists():
                    projects.append(_analyze_project(sub))

    return projects


def _analyze_project(path: Path) -> ProjectInfo:
    """Analyze a single project directory."""
    project = ProjectInfo(name=path.name, path=str(path))

    # Git info
    if (path / ".git").exists():
        project.is_git = True
        try:
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=path, capture_output=True, text=True, timeout=5
            )
            project.branch = branch.stdout.strip()

            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=path, capture_output=True, text=True, timeout=5
            )
            project.has_uncommitted = bool(status.stdout.strip())

            log = subprocess.run(
                ["git", "log", "-1", "--format=%ci|||%s"],
                cwd=path, capture_output=True, text=True, timeout=5
            )
            if log.stdout.strip():
                parts = log.stdout.strip().split("|||", 1)
                project.last_commit_date = parts[0][:10]
                project.last_commit_msg = parts[1] if len(parts) > 1 else ""
        except (subprocess.TimeoutExpired, OSError):
            pass

    # Detect project type
    for detector in DETECTORS:
        try:
            if detector["detect"](path):
                project.project_type = detector["type"]
                project.launch_command = detector["launch"]
                project.install_command = detector["install"]
                project.needs_install = detector["needs_install"](path)
                project.port = detector.get("port_pattern")
                project.status = "ready" if detector["launch"] else "not_launchable"
                break
        except (OSError, UnicodeDecodeError):
            continue

    return project


def print_dashboard(projects: list[ProjectInfo]):
    """Print a text-based dashboard of all projects."""
    print("\n" + "=" * 90)
    print("  REPO REVIEW LAUNCHER — Project Dashboard")
    print("=" * 90)

    # Header
    print(f"\n{'Name':<30} {'Type':<18} {'Git?':<6} {'Status':<12} {'Last Commit':<12} {'Port':<15}")
    print("-" * 90)

    for p in projects:
        git = "Yes" if p.is_git else "No"
        status = p.status
        port = p.port or "-"
        date = p.last_commit_date or "-"
        print(f"{p.name:<30} {p.project_type:<18} {git:<6} {status:<12} {date:<12} {port:<15}")

    print("-" * 90)

    # Summary
    total = len(projects)
    launchable = sum(1 for p in projects if p.launch_command)
    git_repos = sum(1 for p in projects if p.is_git)
    dirty = sum(1 for p in projects if p.has_uncommitted)

    print(f"\nTotal: {total} | Git repos: {git_repos} | Launchable: {launchable} | Uncommitted changes: {dirty}")
    print()


def launch_project(project: ProjectInfo, install_first: bool = False) -> ProjectInfo:
    """Launch a project in a new terminal window."""
    if not project.launch_command:
        project.status = "not_launchable"
        return project

    path = Path(project.path)

    # Install dependencies if needed
    if install_first and project.needs_install and project.install_command:
        logger.info(f"Installing deps for {project.name}: {project.install_command}")
        try:
            subprocess.run(
                project.install_command.split(),
                cwd=path, capture_output=True, text=True, timeout=120
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            project.error = f"Install failed: {e}"
            project.status = "failed"
            return project

    # Launch in a new terminal
    logger.info(f"Launching {project.name}: {project.launch_command}")
    try:
        proc = subprocess.Popen(
            ["cmd", "/c", "start", f"[{project.name}]", "cmd", "/k", project.launch_command],
            cwd=path,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
        project.pid = proc.pid
        project.status = "launched"
    except OSError as e:
        project.error = str(e)
        project.status = "failed"

    return project


def save_session(projects: list[ProjectInfo], output_path: str = "review_session.json"):
    """Save the review session to a JSON file."""
    session = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "projects": [asdict(p) for p in projects],
        "summary": {
            "total": len(projects),
            "launched": sum(1 for p in projects if p.status == "launched"),
            "failed": sum(1 for p in projects if p.status == "failed"),
            "reviewed": sum(1 for p in projects if p.review),
        }
    }
    Path(output_path).write_text(json.dumps(session, indent=2), encoding="utf-8")
    logger.info(f"Session saved to {output_path}")


def main():
    """CLI entry point for the Repo Review Launcher."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="repo-launcher",
        description="Scan, launch, and review all projects in your portfolio.",
    )
    parser.add_argument(
        "projects_dir",
        nargs="?",
        default=DEFAULT_PROJECTS_DIR,
        help=f"Projects directory to scan (default: {DEFAULT_PROJECTS_DIR})",
    )
    parser.add_argument("--scan", action="store_true", help="Scan and show dashboard only")
    parser.add_argument("--launch", action="store_true", help="Launch all launchable projects")
    parser.add_argument("--launch-name", help="Launch a specific project by name")
    parser.add_argument("--install", action="store_true", help="Install dependencies before launching")
    parser.add_argument("--recent", type=int, default=0,
                        help="Only show projects with commits in the last N days")
    parser.add_argument("--json", dest="json_out", help="Save session to JSON file")

    args = parser.parse_args()

    # Scan
    projects = scan_projects(args.projects_dir)

    # Filter by recent activity
    if args.recent > 0:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=args.recent)).strftime("%Y-%m-%d")
        projects = [p for p in projects if p.last_commit_date >= cutoff or not p.is_git]

    # Dashboard
    print_dashboard(projects)

    # Launch
    if args.launch:
        launchable = [p for p in projects if p.launch_command and p.status == "ready"]
        if not launchable:
            print("No launchable projects found.")
            return
        print(f"Launching {len(launchable)} projects...\n")
        for p in launchable:
            launch_project(p, install_first=args.install)
            time.sleep(2)  # stagger launches
        print_dashboard(projects)

    elif args.launch_name:
        match = [p for p in projects if p.name.lower() == args.launch_name.lower()]
        if not match:
            print(f"Project '{args.launch_name}' not found.")
            return
        launch_project(match[0], install_first=args.install)
        print(f"Launched {match[0].name} (PID: {match[0].pid})")

    # Save session
    if args.json_out:
        save_session(projects, args.json_out)


if __name__ == "__main__":
    main()
