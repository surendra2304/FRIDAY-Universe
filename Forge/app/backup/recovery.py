"""Backup and disaster recovery manager for Project FORGE.

FORGE persists to Oracle Autonomous Database, which owns database backups
(automatic backups, point-in-time restore, Data Guard). This module therefore
produces metadata and configuration snapshots only; it never opens a local
database file.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.memory.db import DatabaseManager, db_manager

logger = get_logger("backup.recovery")


class BackupManifest(BaseModel):
    backup_path: str
    backup_type: str = "metadata"  # metadata, config, oracle-adb-managed
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    size_bytes: int = 0


class BackupManager:
    """Create, restore and prune workspace metadata and configuration snapshots.

    Database backups are owned by Oracle Autonomous Database; FORGE only snapshots
    the metadata it actually owns.
    """

    def __init__(self, settings: Settings | None = None, db: DatabaseManager | None = None):
        self.settings = settings or get_settings()
        self.db = db or db_manager
        self.backup_dir = self.settings.data_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def backup_database(self) -> BackupManifest:
        """Report the ADB-managed backup state.

        Oracle Autonomous Database manages its own backups, so there is no local
        data file to snapshot. The call is a logged no-op.
        """
        logger.info(
            "Database backup delegated to Oracle Autonomous Database "
            "(automatic backups, point-in-time restore and Data Guard)."
        )
        return BackupManifest(backup_path="", backup_type="oracle-adb-managed", size_bytes=0)

    def backup_workspace_metadata(self, task_id: str, metadata: dict[str, Any]) -> BackupManifest:
        """Create a JSON metadata snapshot for a workspace."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        meta_dir = self.backup_dir / "workspaces"
        meta_dir.mkdir(parents=True, exist_ok=True)
        target_path = meta_dir / f"meta_{task_id}_{timestamp}.json"

        content = json.dumps(metadata, indent=2, default=str)
        target_path.write_text(content, encoding="utf-8")
        size = target_path.stat().st_size
        return BackupManifest(backup_path=str(target_path), backup_type="metadata", size_bytes=size)

    def backup_configuration(self, config_dict: dict[str, Any]) -> BackupManifest:
        """Create a configuration snapshot backup."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        cfg_dir = self.backup_dir / "config"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        target_path = cfg_dir / f"config_backup_{timestamp}.json"

        content = json.dumps(config_dict, indent=2, default=str)
        target_path.write_text(content, encoding="utf-8")
        size = target_path.stat().st_size
        return BackupManifest(backup_path=str(target_path), backup_type="config", size_bytes=size)

    def restore_database(self, backup_file: Path) -> bool:
        """Refuse local restores; ADB restores are performed by Oracle."""
        logger.warning(
            "Database restore skipped: Oracle Autonomous Database restores are "
            "performed from ADB automatic backups / point-in-time restore, not "
            "from a local file (%s).",
            backup_file,
        )
        return False

    def list_backups(self) -> list[Path]:
        """List metadata/config snapshots, newest first."""
        if not self.backup_dir.exists():
            return []
        return sorted(self.backup_dir.rglob("*.*"), reverse=True)

    def prune_old_backups(self, retention_days: int = 7) -> int:
        """Prune metadata/config snapshots older than the retention window."""
        if not self.backup_dir.exists():
            return 0

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        pruned = 0

        for path in self.backup_dir.rglob("*"):
            if not path.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
                if mtime <= cutoff:
                    path.unlink()
                    pruned += 1
                    logger.info(f"Pruned old backup: {path.name}")
            except Exception as e:
                logger.debug(f"Error pruning backup {path.name}: {e}")

        return pruned


backup_manager = BackupManager()
