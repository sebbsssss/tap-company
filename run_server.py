#!/usr/bin/env python3
"""
Entry point for the occupancy API server.

Usage:
  # Live CRM mode (requires CRM_API_BASE + CRM_STAFF_API_KEY env vars)
  python3 run_server.py

  # Fixture mode (for local dev / testing without CRM access)
  python3 run_server.py --fixtures tests/fixtures

  # Custom port
  python3 run_server.py --port 9090
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from occupancy.server import run
from occupancy.config import load as load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="TAP Occupancy API server")
    parser.add_argument("--port", type=int, default=None, help="HTTP port (default: OCCUPANCY_PORT env or 8080)")
    parser.add_argument("--fixtures", type=str, default=None,
                        help="Path to fixtures directory (skips live CRM fetch)")
    args = parser.parse_args()

    cfg = load_config()
    port = args.port or cfg.port
    run(port=port, fixtures_path=args.fixtures)


if __name__ == "__main__":
    main()
