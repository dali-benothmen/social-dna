from socialdna.core.enums import ExitCode


class SocialDNAError(Exception):
    """An actionable error that is safe to expose through the CLI."""

    code = "internal_error"
    exit_code = ExitCode.INTERNAL

    def __init__(self, message: str, *, next_action: str | None = None) -> None:
        super().__init__(message)
        self.next_action = next_action


class ConfigurationError(SocialDNAError):
    code = "invalid_configuration"
    exit_code = ExitCode.INVALID_INPUT


class StorageConflict(SocialDNAError):
    code = "storage_conflict"
    exit_code = ExitCode.STORAGE_CONFLICT


class StorageIntegrityError(SocialDNAError):
    code = "storage_integrity"
    exit_code = ExitCode.STORAGE_INTEGRITY


class StoragePermissionError(SocialDNAError):
    code = "storage_permission"
    exit_code = ExitCode.PERMISSION


class DependencyUnavailable(SocialDNAError):
    code = "dependency_unavailable"
    exit_code = ExitCode.UNAVAILABLE
