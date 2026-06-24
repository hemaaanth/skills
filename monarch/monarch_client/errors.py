"""JSON-safe errors for the Monarch Money client."""

from __future__ import annotations


class MonarchClientError(Exception):
    """Base class for expected Monarch skill errors."""

    error_type = "monarch_error"

    def to_dict(self) -> dict[str, str]:
        return {"status": "error", "type": self.error_type, "message": str(self)}


class MissingDependencyError(MonarchClientError):
    error_type = "missing_dependency"


class MissingAuthError(MonarchClientError):
    error_type = "missing_auth"


class AuthenticationRequiredError(MonarchClientError):
    error_type = "auth_failed"


class MfaRequiredError(MonarchClientError):
    error_type = "mfa_required"


class ConfirmationRequiredError(MonarchClientError):
    error_type = "confirmation_required"


class WriteNotEnabledError(MonarchClientError):
    error_type = "write_not_enabled"
