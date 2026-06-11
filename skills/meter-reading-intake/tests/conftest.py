"""pytest configuration for meter-reading-intake tests.

Adds the scripts directory to sys.path so imports resolve without package prefix,
matching the Docker deployment layout.
"""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
