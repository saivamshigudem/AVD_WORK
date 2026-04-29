"""One-click demo runner for the peer review agent."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    workspace = Path(__file__).parent.parent
    script = workspace / "scripts" / "run_user_story_analysis.py"
    if not script.exists():
        raise SystemExit(f"Script not found: {script}")

    print("=== Peer Review Agent Demo ===")
    print("Running automated workflow (no input required)...")

    reports_dir = workspace / "reports"
    if reports_dir.exists():
        deleted = 0
        for report in reports_dir.glob("user_story_analysis_*.md"):
            report.unlink(missing_ok=True)
            deleted += 1
        if deleted:
            print(f"Cleared {deleted} previous user story analysis report(s).")
    else:
        reports_dir.mkdir(parents=True, exist_ok=True)
        print("Created reports directory.")
    print()

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(workspace),
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    print()
    print("Demo finished. Check the latest report in the 'reports' directory.")


if __name__ == "__main__":
    main()

