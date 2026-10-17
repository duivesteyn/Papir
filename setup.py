# Legacy shim — packaging metadata now lives in pyproject.toml ([project] name=papir-kindle).
# Kept so `pip install .` / `python setup.py` workflows keep working.
from setuptools import setup

setup()
