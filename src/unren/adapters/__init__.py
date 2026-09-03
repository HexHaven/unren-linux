"""Adapters: thin, version-pinned/vendored ports of upstream extraction tools.

Per Bauplan §12 and docs/UPSTREAM-BEHAVIOR.md §1: upstream UnRen-forall vendors
`rpatool`/`unrpyc` inline as base64-encoded Python payloads rather than depending
on published packages (neither is on PyPI). This package re-implements the same
algorithms as documented, standalone Python modules with a clear provenance
docstring per adapter, instead of an undocumented vendored blob.
"""

from __future__ import annotations
