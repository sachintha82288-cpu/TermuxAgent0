#!/usr/bin/env python3
"""Bootstrap launcher — lets the agent run from a checkout or an installed copy.

    ./run.py            → same as the 'agent' command
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from termuxagent.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
