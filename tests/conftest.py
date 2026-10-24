"""
tests/conftest.py — Central pytest configuration.

Sets up sys.path for all test modules and provides shared fixtures.
"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add all agent package paths to sys.path
PATHS = [
    ROOT,  # repo root for mesh package
    ROOT + "/FRIDAY/apps/core/src",
    ROOT + "/Cortex/apps/api/src",
    ROOT + "/Inference",
    ROOT + "/Memora/apps/api",
    ROOT + "/Memora/apps",
    ROOT + "/Memora",
    ROOT + "/Forge",
    ROOT + "/VyralX",
    ROOT + "/IntelX",
    ROOT + "/Sentinel/sentinel/apps/api/src",
    ROOT + "/Sentinel",
    ROOT + "/Stratex",
    ROOT + "/Futuris",
]

for p in PATHS:
    if p not in sys.path:
        sys.path.insert(0, p)
