"""Shared validation for workspace inputs and role results."""

class DomainError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def required(value, label, maximum=5000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise DomainError(f"{label} is required and must be at most {maximum} characters.")
    return value.strip()
