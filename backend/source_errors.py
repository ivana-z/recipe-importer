"""Safe, stable errors for user-supplied import sources."""


class SourceError(Exception):
    """An expected source failure that is safe to return to the browser."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status_code = status_code

    @property
    def detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}
