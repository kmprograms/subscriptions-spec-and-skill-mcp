from pathlib import Path


class StatementNotFoundError(Exception):
    def __init__(self, path: Path) -> None:
        super().__init__(f"Statement not found: {path}")
        self.path = path
