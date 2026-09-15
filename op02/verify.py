"""Execute tests and retain real stdout, stderr, timestamps and source hashes."""
import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from . import paths
from .io import write_json, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    timestamp = datetime.now(timezone.utc)
    output = args.output or paths.ROOT / "results/raw" / ("tests-" + timestamp.strftime("%Y%m%dT%H%M%S%f") + ".json")
    if output.exists():
        parser.error("test output already exists; preserve previous runs")
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=paths.ROOT, capture_output=True, text=True)
    record = {"timestamp": timestamp.isoformat(), "command": command, "returncode": completed.returncode,
              "seconds": time.monotonic()-started, "stdout": completed.stdout, "stderr": completed.stderr,
              "mode": "offline_tests", "api_spend_usd": 0,
              "source_sha256": {str(p.relative_to(paths.ROOT)): sha256(p)
                  for folder in ("op02", "tests") for p in sorted((paths.ROOT / folder).glob("*.py"))}}
    write_json(output, record)
    print(completed.stdout + completed.stderr, end="")
    print(f"Raw test evidence: {output}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
