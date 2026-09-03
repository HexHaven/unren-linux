"""Structured error types for unren.

Re-exported at unren.core for convenience; canonical definitions live here.
See unren.core.__init__ for the module docstring duplicate guard.
"""

from __future__ import annotations


class UnrenError(Exception):
    code = "unren-error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        d: dict = {"code": self.code, "message": self.message}
        if self.details:
            d["details"] = self.details
        return d


class PathNotFoundError(UnrenError):
    code = "path-not-found"


class NotAGameDirectoryError(UnrenError):
    code = "not-a-game-directory"


class DetectionError(UnrenError):
    code = "detection-error"


class ConfigError(UnrenError):
    code = "config-error"


class UnsupportedOperationError(UnrenError):
    code = "unsupported-operation"


class RuntimeResolutionError(UnrenError):
    code = "runtime-resolution-error"


class OutputPathError(UnrenError):
    """Output/destination path is unusable (exists as wrong type, not writable, ...)."""

    code = "output-path-error"


class OverwriteProtectionError(UnrenError):
    """A mutating action refused to overwrite existing destination file(s)."""

    code = "overwrite-protection"


class MissingGameDirectoryError(UnrenError):
    """An action requires a `game/` directory to write into, but none was found."""

    code = "missing-game-directory"


class ConfirmationRequiredError(UnrenError):
    """A genuinely destructive/irreversible action was requested without explicit confirmation."""

    code = "confirmation-required"
