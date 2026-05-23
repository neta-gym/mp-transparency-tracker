"""Base agent with shared DB access and logging."""

from __future__ import annotations

from ..storage.database import Database
from ..utils.logger import get_logger

log = get_logger(__name__)


class BaseAgent:
    """Base class for all agents. Provides DB access and shared utilities."""

    agent_name: str = "base"

    def __init__(self, db: Database) -> None:
        self.db = db
