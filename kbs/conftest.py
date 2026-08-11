"""The broker depends on medperf-cc, which lives in this repo.

Put on the path so the tests run from a source checkout without installing it.
Note what is deliberately absent: anything from the MedPerf client.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "..", "cc"))
sys.path.insert(0, ROOT)
