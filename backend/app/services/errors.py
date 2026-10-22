"""Domain errors shared by the REST API and the MCP server."""


class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    code = "not_found"


class Forbidden(DomainError):
    code = "forbidden"


class InvalidInput(DomainError):
    code = "invalid_input"


class ApprovalRequired(DomainError):
    code = "approval_required"


class Conflict(DomainError):
    code = "conflict"
