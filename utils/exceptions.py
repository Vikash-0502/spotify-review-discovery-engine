"""Custom exceptions for the Review Discovery Engine."""


class ReviewDiscoveryError(Exception):
    """Base exception for application errors."""


class ConfigurationError(ReviewDiscoveryError):
    """Raised when required configuration is missing or invalid."""


class DatabaseError(ReviewDiscoveryError):
    """Raised when database operations fail."""
