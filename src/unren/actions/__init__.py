"""unren.actions: mutating operations (Milestone 2+).

Detection (unren.detection) is read-only; everything here may write to disk
and therefore goes through the shared backup/overwrite-protection helpers in
unren.core.backup.
"""

from __future__ import annotations
