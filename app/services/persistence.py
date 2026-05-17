import json
from pathlib import Path

from app.domain.schemas import DataSnapshot, serialize
from app.services.reports import ReportService
from app.services.repository import InMemoryRepository, repository


class PersistenceService:
    """Exports an auditable JSON snapshot for MVP durability and handoff."""

    def __init__(self, repo: InMemoryRepository = repository, path: Path | None = None) -> None:
        self.repo = repo
        self.path = path or Path("runtime_snapshot.json")

    def snapshot(self) -> DataSnapshot:
        return ReportService(self.repo).export_snapshot()

    def save(self) -> DataSnapshot:
        snapshot = self.snapshot()
        self.path.write_text(json.dumps(serialize(snapshot), indent=2), encoding="utf-8")
        return snapshot
