"""Domain exceptions for the sync pipeline."""


class SyncScheduleMissingError(RuntimeError):
    """Raised when a scheduled sync's parent row no longer exists.

    A schedule can be deleted while its sync tasks are still queued or
    running. Tasks catch this to drop gracefully instead of crashing on a
    foreign-key violation.
    """

    def __init__(self, sync_id: int) -> None:
        super().__init__(f"Scheduled sync {sync_id} no longer exists")
        self.sync_id = sync_id


class SyncValidationError(RuntimeError):
    """Raised for permanent validation errors that should not be retried.

    Examples: invalid source URL, malformed playlist URL, unknown target.
    These errors are not transient and will not succeed on retry.
    """


class SyncTargetConnectionError(RuntimeError):
    """Raised when the sync target is unreachable during the pre-flight check.

    Raised before the match phase so an unreachable target fails fast and is
    reported as a connection error instead of marking every track as failed.
    Retrying would only repeat the same failure, so tasks short-circuit.
    """


class SyncSourceError(RuntimeError):
    """Raised when the music source (YouTube Music, Deezer) is unavailable or
    returns invalid data during the fetch phase.

    This is typically a transient error (network, rate limit, API change) and
    may succeed on retry.
    """


class MatchError(RuntimeError):
    """Raised when track matching fails in the MatchPhase.

    Could be due to missing MusicBrainz data, matching algorithm issues, or
    source data quality. May be transient if dependent on external APIs.
    """


class FinalizeError(RuntimeError):
    """Raised when the FinalizePhase fails to write matched tracks to the target.

    Typically indicates a target API error (permissions, rate limits, server
    error). Usually transient and retryable.
    """
