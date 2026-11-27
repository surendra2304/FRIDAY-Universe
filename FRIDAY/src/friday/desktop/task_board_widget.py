"""Task board corner panel — TASK-FRD-049 (checkpoint 2).

A frameless panel rendered by ``DesktopOverlay``: title row + one row
per board item; clicking an item opens its site. Position is one of
the four screen corners, computed from the primary screen geometry at
draw time. The widget never opens a site on its own initiative — only
on a click, or when the voice tool resolves a label.
"""

from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from friday.tools.builtin.task_board import corner_position, resolve_target

import webbrowser


class TaskBoardWidget(QFrame):
    """Frameless corner panel showing the persisted task board."""

    def __init__(
        self,
        board: dict[str, Any] | None = None,
        open_item: Callable[[str, str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._open_item = open_item or self._default_open_item
        self._board: dict[str, Any] = board or {
            "position": "bottom-left", "items": [], "visible": True,
        }

        self.setStyleSheet("""
            QFrame {
                background-color: rgba(6, 12, 20, 210);
                border: 1px solid rgba(0, 210, 255, 75);
                border-radius: 12px;
            }
            QLabel {
                color: rgba(0, 230, 255, 0.95);
                font-family: 'Segoe UI';
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton {
                background: rgba(0, 210, 255, 30);
                border: 1px solid rgba(0, 210, 255, 90);
                color: #ffffff;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 10pt;
                text-align: left;
            }
            QPushButton:hover {
                background: rgba(0, 210, 255, 70);
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(4)
        self.title = QLabel("Task Board")
        self.layout.addWidget(self.title)
        self._item_buttons: list[QPushButton] = []
        self.set_board(self._board)

    @staticmethod
    def _default_open_item(label: str, site: str) -> None:
        url = resolve_target(site)
        if url is not None:
            webbrowser.open(url)

    def set_board(self, board: dict[str, Any]) -> None:
        """Replace the displayed board; hide when empty or hidden."""
        self._board = board
        for button in self._item_buttons:
            self.layout.removeWidget(button)
            button.deleteLater()
        self._item_buttons = []
        for item in board.get("items", []):
            button = QPushButton(item["label"])
            button.setToolTip(f"Open {item.get('site', item['label'])}")
            button.clicked.connect(
                lambda _checked=False, it=item: self._open_item(
                    it["label"], it.get("site", it["label"])
                )
            )
            self.layout.addWidget(button)
            self._item_buttons.append(button)
        visible = bool(board.get("visible", True)) and bool(board.get("items"))
        self.setVisible(visible)
        if visible:
            self.move_to_corner(board.get("position", "bottom-left"))

    def move_to_corner(self, corner: str) -> None:
        """Move the panel into *corner* of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        self.adjustSize()
        x, y = corner_position(
            corner, geometry.width(), geometry.height(),
            self.width(), self.height(),
        )
        self.move(geometry.x() + x, geometry.y() + y)

    def refresh(self) -> None:
        """Re-read the persisted board and redraw (overlay calls this)."""
        from friday.tools.builtin.task_board import TaskBoardStore

        self.set_board(TaskBoardStore().load())
