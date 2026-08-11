class CCError(Exception):
    """Base class for anything these components refuse to do."""


class AttestationError(CCError):
    """A token could not be verified, or did not say what was required."""


class ConfigurationError(CCError):
    """A cloud environment is not set up the way its owner or operator needs."""


class OperationError(CCError):
    """An operation against the cloud environment failed."""
