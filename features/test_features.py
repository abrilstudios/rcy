from pathlib import Path

from pytest_bdd import scenarios
from riemann_harness.features import select

scenarios(*select(Path(__file__).resolve().parent))
