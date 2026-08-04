"""System tray icon with context menu."""

from __future__ import annotations

from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu

from .utils import get_icon_path


class SystemTray(QSystemTrayIcon):
    """System-tray icon with right-click menu for widget control."""

    def __init__(
        self,
        desktop_widget,
        menu_window,
        on_exit_callback,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._widget = desktop_widget
        self._menu_win = menu_window
        self._on_exit = on_exit_callback
        self._widget_visible = True

        # Icon
        icon_path = get_icon_path()
        self.setIcon(QIcon(icon_path))
        self.setToolTip("小桌宠")

        # Context menu
        self._menu = QMenu()

        self._toggle_action = QAction("隐藏桌面组件")
        self._toggle_action.triggered.connect(self._on_toggle)

        self._settings_action = QAction("菜单")
        self._settings_action.triggered.connect(self._on_menu)

        self._exit_action = QAction("退出")
        self._exit_action.triggered.connect(self._on_exit)

        self._menu.addAction(self._toggle_action)
        self._menu.addSeparator()
        self._menu.addAction(self._settings_action)
        self._menu.addSeparator()
        self._menu.addAction(self._exit_action)

        self.setContextMenu(self._menu)

        # Left-click → show widget
        self.activated.connect(self._on_activated)

        # Listen for widget hide/show to keep menu text in sync
        self._widget.hidden_to_tray.connect(self._on_widget_hidden)
        self._widget.shown_from_tray.connect(self._on_widget_shown)

        self.show()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left click
            self._widget.show()
            self._widget.raise_()
            self._widget.activateWindow()
            self._widget_visible = True
            self._toggle_action.setText("隐藏桌面组件")

    def _on_toggle(self) -> None:
        if self._widget_visible:
            self._widget.hide()
            self._widget_visible = False
            self._toggle_action.setText("显示桌面组件")
        else:
            self._widget.show()
            self._widget.raise_()
            self._widget.activateWindow()
            self._widget_visible = True
            self._toggle_action.setText("隐藏桌面组件")

    def _on_widget_hidden(self) -> None:
        self._widget_visible = False
        self._toggle_action.setText("显示桌面组件")

    def _on_widget_shown(self) -> None:
        self._widget_visible = True
        self._toggle_action.setText("隐藏桌面组件")

    def _on_menu(self) -> None:
        self._menu_win.show()
        self._menu_win.raise_()
        self._menu_win.activateWindow()
