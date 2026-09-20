#!/usr/bin/env python3
"""Bootstrap launcher — lets the agent run from a checkout or an installed copy.

    ./run.py            → same as the 'agent' command
"""
import os
import sys

if sys.version_info < (3, 8):
    sys.stderr.write("TermuxAgent needs Python 3.8+ (you have %d.%d). "
                     "On Termux: pkg upgrade python\n" % sys.version_info[:2])
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from termuxagent.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
