"""Generic Result type used across unren for consistent success/failure reporting.

Every operation that can meaningfully fail (detection, future actions in later
milestones) should return a Result instead of raising for "expected" failure
modes. Unexpected exceptions still propagate; the CLI layer converts any
uncaught UnrenError into a failed Result at the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from unren.core.errors import UnrenError

T = TypeVar("T")


@dataclass
class Result(Generic[T]):
    ok: bool
    value: T | None = None
    error: UnrenError | None = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def success(cls, value: T, *, warnings: list[str] | None = None) -> "Result[T]":
        return cls(ok=True, value=value, error=None, warnings=warnings or [])

    @classmethod
    def failure(cls, error: UnrenError, *, warnings: list[str] | None = None) -> "Result[T]":
        return cls(ok=False, value=None, error=error, warnings=warnings or [])

    def unwrap(self) -> T:
        """Return value or raise the wrapped error."""
        if not self.ok:
            assert self.error is not None
            raise self.error
        assert self.value is not None
        return self.value

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"ok": self.ok}
        if self.warnings:
            d["warnings"] = list(self.warnings)
        if self.ok:
            d["value"] = _jsonable(self.value)
        else:
            d["error"] = self.error.to_dict() if self.error else None
        return d


def _jsonable(value: Any) -> Any:
    """Best-effort conversion of dataclasses/enums/paths into JSON-safe values."""
    import dataclasses
    import enum
    import pathlib

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, pathlib.Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)
