from __future__ import annotations


class AppError(Exception):
    def __init__(self, message: str, *, status_code: int = 500, error_code: str = "internal_error"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class ExternalDependencyError(AppError):
    def __init__(self, message: str = "External dependency is unavailable."):
        super().__init__(message, status_code=503, error_code="external_dependency_error")


class RepositoryError(AppError):
    def __init__(self, message: str = "Repository query failed."):
        super().__init__(message, status_code=500, error_code="repository_error")
