#!/usr/bin/env python3
"""Quick-run script: python scripts/run.py --state delhi"""

import sys
import os

# Add src to path so tracker is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tracker.main import cli_entry

if __name__ == "__main__":
    cli_entry()
