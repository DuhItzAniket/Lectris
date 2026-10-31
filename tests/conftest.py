"""Test configuration shared by every test module.

Hypothesis runs a fixed set of examples by default (``derandomize``), so every run of the suite
tries the same inputs: a failure reproduces exactly, on any machine, and two runs of the same
code behave the same, which tools that compare runs rely on. To search for new failing inputs,
run with ``HYPOTHESIS_PROFILE=explore``: random examples, and more of them.
"""

import os

from hypothesis import settings

settings.register_profile("reproducible", derandomize=True)
settings.register_profile("explore", derandomize=False, max_examples=1000)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "reproducible"))
