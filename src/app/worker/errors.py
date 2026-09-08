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
