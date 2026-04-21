"""Shared utilities used by both pipelines.

Anything that must behave identically across pipeline A and pipeline B lives
here - preprocessing rules, unit normalization, the AGE client wrapper, and
the LightRAG bootstrap. The whole point of the POC is comparability, so
differences between the pipelines should only come from the *ingest* strategy,
never from preprocessing or storage.
"""
