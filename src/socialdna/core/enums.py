from enum import IntEnum, StrEnum


class ClaimLevel(StrEnum):
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    ASSOCIATION = "association"
    CAUSAL_FINDING = "causal_finding"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    STALE = "stale"
    CANCELLED = "cancelled"


class AvailabilityStatus(StrEnum):
    NOT_SUPPLIED = "not_supplied"
    NOT_PERMITTED = "not_permitted"
    NOT_APPLICABLE = "not_applicable"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class ExitCode(IntEnum):
    OK = 0
    INTERNAL = 1
    INVALID_INPUT = 2
    UNAVAILABLE = 3
    PERMISSION = 4
    PARTIAL = 5
    STORAGE_CONFLICT = 6
    PROVIDER_FAILURE = 7
    STORAGE_INTEGRITY = 8
