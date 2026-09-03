unren.vendor — vendored third-party decompiler sources
========================================================

Per Bauplan §12 ("keine undokumentierten Vendor-Blobs") and
docs/UPSTREAM-BEHAVIOR.md §1: upstream UnRen-forall bundles `unrpyc` as an
opaque, Windows-only CAB archive embedded as base64 text inside its `.bat`
scripts. This Linux port instead vendors the *actual upstream source*,
verbatim, as plain files with a documented pin — no CAB, no undocumented
blob.

--------------------------------------------------------------------------
unrpyc_legacy/  —  CensoredUsername/unrpyc, tag v1.3.2
--------------------------------------------------------------------------
Name:    Unrpyc ("Unrpyc Legacy for Ren'Py v7 and lower", per its own
         `__title__`/comment header)
Version: v1.3.2
URL:     https://github.com/CensoredUsername/unrpyc
Commit:  tag v1.3.2 (release tarball, not `master` HEAD)
License: MIT (see unrpyc_legacy/LICENSE, copied verbatim from upstream)

Real Python 2 source (not merely "python2-flavored" — uses `print "..."`
statements, `except Exception, e:`, `xrange`, `unicode(...)`, `StringIO`
module import, etc.). Requires an actual Python 2 interpreter to run;
this port's `unren.detection.python.resolve_python2_runtime()` locates one
(system `python2`/`python2.7`, or Ren'Py's own bundled interpreter under
the game's `lib/` tree) — see that module's docstring for the documented
"Python 2 runtime may not exist on this system" risk and this adapter's
fallback behavior.

This is the exact version upstream UnRen-forall itself resolves to for its
"legacy" (Ren'Py <=7, Python-2-bundled) code path, confirmed via
`docs/UPSTREAM-BEHAVIOR.md` §1/§7.1/§7.8 (byte-identical CAB payload
decoded and cross-checked against this tag's own `__version__` string and
comment header during the Milestone 0 archaeology pass).

--------------------------------------------------------------------------
unrpyc_current/  —  CensoredUsername/unrpyc, tag v2.0.3
--------------------------------------------------------------------------
Name:    Unrpyc
Version: v2.0.3
URL:     https://github.com/CensoredUsername/unrpyc
Commit:  tag v2.0.3 (release tarball, not `master` HEAD)
License: MIT (see unrpyc_current/LICENSE, copied verbatim from upstream)

Python 3.9+ only (its own `main()` raises if run under anything older —
see `MIN_UNRPYC_CURRENT_PYTHON` in `unren.detection.python`). Confirmed by
this port's own archaeology pass (docs/UPSTREAM-BEHAVIOR.md §1, "current"
row) to be the exact version upstream UnRen-forall resolves to for its
"current" (Ren'Py >=8, Python-3-bundled) code path — contradicting the
surrounding upstream batch-file *comment*, which claims a nonexistent
"v2.0.4 Master... with Inceton" variant; the actual shipped CAB payload
decodes to plain, unmodified v2.0.3. This port pins to the verified v2.0.3
behavior, not the aspirational v2.0.4 comment.

Verified (Milestone 3 vendoring pass, real subprocess runs — see
`tests/unit/test_unrpyc_adapter.py`) to also successfully decompile real
Ren'Py 7-era ("RENPY RPC2", Python-2-bundled-era) `.rpyc` samples, emitting
only an informational compatibility warning rather than a hard failure.
`unren.actions.decompile_rpyc` relies on this as its documented fallback
path when no Python 2 runtime can be resolved for a LEGACY-generation game.

--------------------------------------------------------------------------
Verification of provenance
--------------------------------------------------------------------------
Both trees were fetched from GitHub release tarballs at the exact tags
above (not `master` HEAD) at vendoring time. `master` and `v2.0.3` were
diffed and confirmed identical for every source file that matters here
(only `.github/workflows/*.yaml` CI config and `.gitmodules` differ, which
are not vendored). Each variant's own `unrpyc.py` `__version__` string was
read directly to confirm the pin (`'v1.3.2'` / `'v2.0.3'`), not merely
inferred from the tag name.

--------------------------------------------------------------------------
What is NOT vendored
--------------------------------------------------------------------------
- `codegen.py` (legacy only, 3-clause BSD, Armin Ronacher) and
  `screendecompiler.py` (legacy only) ARE vendored — they are load-bearing
  imports of the legacy `decompiler/__init__.py`. Their licenses are
  included in `unrpyc_legacy/LICENSE` (upstream's own LICENSE file already
  documents the BSD sub-license for `codegen.py`).
- Upstream's `testcases/` directories (compiled `.rpyc` fixtures + expected
  `.rpy` output, MIT-licensed Ren'Py tutorial content) are NOT vendored
  wholesale here; a small number of individual sample files were copied
  into `tests/fixtures/rpyc_samples/` instead (see that directory's own
  LICENSE file), used only for this port's own test suite.
- `setup.py`, `README.md`, `.github/`, `un.rpyc` (a compiled copy of
  unrpyc's own CLI help screen, unused by this port) are not vendored.

--------------------------------------------------------------------------
Modifications
--------------------------------------------------------------------------
None. Both trees are unmodified copies of the tagged upstream source.
`unren.adapters.unrpyc` invokes them as unmodified subprocesses; it never
patches, monkeypatches, or edits vendored files at runtime.
