"""
Core module for Project FORGE.
"""

from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging
from app.core.workspace import WorkspaceManager, WorkspacePaths, workspace_manager

__all__ = [
    "Settings",
    "WorkspaceManager",
    "WorkspacePaths",
    "get_logger",
    "get_settings",
    "setup_logging",
    "workspace_manager",
]
