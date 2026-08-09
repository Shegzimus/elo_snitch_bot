#!/usr/bin/env python
"""
Orchestrates the ELO tracking pipeline: fetch data, generate PUUIDs, check ELO, track changes.
Replaces the Airflow DAG for simpler, cron-based scheduling.

Run hourly via cron:
  0 * * * * cd /path/to/elo_snitch_bot && python -m src.python.run_pipeline

Or via systemd timer — see README for setup.
"""

import sys
import subprocess
from pathlib import Path

def run_pipeline():
    """Execute the four pipeline stages in sequence."""
    scripts = [
        "fetch_google_forms_data.py",
        "generate_puuid.py",
        "elo_check.py",
        "elo_tracker.py",
    ]

    script_dir = Path(__file__).parent

    for script in scripts:
        script_path = script_dir / script
        if not script_path.exists():
            print(f"ERROR: {script_path} not found", file=sys.stderr)
            return 1

        print(f"Running {script}...")
        result = subprocess.run([sys.executable, str(script_path)], cwd=str(script_dir))
        if result.returncode != 0:
            print(f"ERROR: {script} failed with exit code {result.returncode}", file=sys.stderr)
            return 1
        print(f"{script} completed.\n")

    return 0

if __name__ == "__main__":
    sys.exit(run_pipeline())
