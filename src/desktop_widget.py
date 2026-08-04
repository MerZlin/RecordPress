"""Frameless always-on-top desktop overlay with configurable layout."""

from __future__ import annotations

import ctypes

from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config_manager import ConfigManager


BORDER_WIDTH = 6   # px for resize-edge detection
ITEM_NAMES: dict[str, str] = {
    "keyboard": "键盘按键",
    "mouse":   "鼠标点击",
    "cpu":     "CPU",
    "memory":  "内存",
    "gpu":     "GPU",
    "disk":    "C盘剩余",
}

# Windows extended style constants for click-through
_GWL_EXSTYLE = -20
_WS_EX_TRANSPARENT = 0x00000020


class DesktopWidget(QWidget):
    """Frameless always-on-top overlay that shows live stats."""

    hidden_to_tray = Signal()
    shown_from_tray = Signal()

    def __init__(
        self,
        config: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config

        # drag / resize state
        self._drag_pos: QPoint | None = None
        self._resize_edge: str | None = None
        self._resize_start_geom: QRect | None = None
        self._resize_start_pos: QPoint | None = None

        # item storage
        self._item_keys = ("keyboard", "mouse", "cpu", "memory", "gpu", "disk")
        self._item_labels: dict[str, tuple[QLabel, QLabel]] = {}

        # current layout tracking
        self._current_mode: str = self._config.get("layout.mode", "default")

        self._setup_window()
        self._rebuild_layout()

    # ------------------------------------------------------------------
    # Window setup (one-time)
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setObjectName("DesktopWidget")
        self.setWindowTitle("小桌宠")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        # Restore saved geometry
        x = self._config.get("window.x")
        y = self._config.get("window.y")
        w = self._config.get("window.width", 300)
        h = self._config.get("window.height", 200)
        if x is not None and y is not None:
            self.setGeometry(x, y, w, h)
        else:
            self.resize(w, h)
        self.setMinimumSize(180, 24)

        # Apply appearance
        self._apply_appearance()

    # ------------------------------------------------------------------
    # Layout rebuild
    # ------------------------------------------------------------------

    def _rebuild_layout(self) -> None:
        """Destroy and recreate the internal widget tree for the current mode."""
        # 1. Destroy every child widget unconditionally — hide + reparent first
        for child in self.findChildren(QWidget):
            if child is not self:
                child.hide()
                child.setParent(None)
                child.deleteLater()

        # 2. Safely remove old layout: reparent to a temp widget that gets GC'd
        old = self.layout()
        if old is not None:
            QWidget().setLayout(old)

        # 3. Flush pending deletions so old widgets are gone before creating new ones
        QApplication.processEvents()

        self._item_labels.clear()
        self._separators: list[QLabel] = []
        self._current_mode = self._config.get("layout.mode", "default")

        if self._current_mode == "horizontal":
            layout = QHBoxLayout(self)
            layout.setContentsMargins(6, 6, 6, 6)
            layout.setSpacing(0)
            self._populate_horizontal(layout)
        else:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(14, 10, 14, 10)
            layout.setSpacing(2)
            self._populate_list(layout, label_gap=8)

    def _populate_list(self, layout: QVBoxLayout, label_gap: int) -> None:
        """Vertical list layout."""
        display = self._config.data.get("display", {})
        for key in self._item_keys:
            row = QWidget(self)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(label_gap)

            name_label = QLabel(ITEM_NAMES[key], row)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

            value_label = QLabel("0", row)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            value_label.setMinimumWidth(50)

            row_layout.addWidget(name_label)
            row_layout.addWidget(value_label)
            layout.addWidget(row)

            self._item_labels[key] = (name_label, value_label)
            row.setVisible(bool(display.get(key, True)))

    def _populate_horizontal(self, layout: QHBoxLayout) -> None:
        """Single-row horizontal layout with | separators, max 5 items."""
        display = self._config.data.get("display", {})
        for i, key in enumerate(self._item_keys):
            if i > 0:
                sep = QLabel("|", self)
                sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sep.setFixedWidth(10)
                layout.addWidget(sep)
                self._separators.append(sep)

            row = QWidget(self)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(2, 0, 2, 0)
            row_layout.setSpacing(2)

            name_label = QLabel(ITEM_NAMES[key], row)
            name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)

            value_label = QLabel("0", row)
            value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            row_layout.addWidget(name_label)
            row_layout.addWidget(value_label)
            layout.addWidget(row)

            self._item_labels[key] = (name_label, value_label)
            row.setVisible(bool(display.get(key, True)))

    # ------------------------------------------------------------------
    # Appearance (opacity / font colour)
    # ------------------------------------------------------------------

    def _apply_appearance(self) -> None:
        """Read opacity + font_color from config and push to widget."""
        font_color = self._config.get("appearance.font_color", "#E8E8EC")
        self.setStyleSheet(self._stylesheet(font_color))
        self.update()

    def _stylesheet(self, font_color: str) -> str:
        return f"""
            #DesktopWidget {{
                background: transparent;
                border: none;
            }}
            #DesktopWidget QLabel {{
                color: {font_color};
                background: transparent;
            }}
        """

    def _bg_opacity(self) -> float:
        """Read current opacity from config, clamped to 0.10–1.00."""
        opacity = float(self._config.get("appearance.opacity", 0.88))
        return max(0.10, min(1.0, opacity))

    def paintEvent(self, event) -> None:
        """Paint the rounded-rect background with current opacity."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        opacity = self._bg_opacity()
        bg = QColor(28, 28, 32, int(opacity * 255))
        border = QColor(80, 80, 85, int(opacity * 255))

        rect = self.rect()
        painter.setPen(QPen(border, 2))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 10, 10)

        painter.end()

    # ------------------------------------------------------------------
    # Public update slots
    # ------------------------------------------------------------------

    def update_counts(self, keyboard: int, mouse: int) -> None:
        if "keyboard" in self._item_labels:
            self._item_labels["keyboard"][1].setText(str(keyboard))
        if "mouse" in self._item_labels:
            self._item_labels["mouse"][1].setText(str(mouse))

    def update_stats(self, stats: dict[str, float]) -> None:
        for key in ("cpu", "memory", "gpu"):
            if key in self._item_labels and key in stats:
                self._item_labels[key][1].setText(f"{stats[key]:.1f}%")
        if "disk" in self._item_labels and "disk" in stats:
            self._item_labels["disk"][1].setText(f"{stats['disk']:.1f}G")

    def refresh_from_config(self) -> None:
        """Re-apply everything from config — visibility, font, layout, appearance."""
        # Detect layout change
        new_mode = self._config.get("layout.mode", "default")
        if new_mode != self._current_mode:
            self._rebuild_layout()
            self.adjustSize()

        # Visibility
        display = self._config.data.get("display", {})
        for key, (name_lbl, value_lbl) in self._item_labels.items():
            parent = name_lbl.parent()
            if parent and parent is not self:
                parent.setVisible(bool(display.get(key, True)))

        # Separator visibility (horizontal mode only)
        if self._separators:
            keys = self._item_keys
            for idx, sep in enumerate(self._separators):
                # Separator is between keys[idx] and keys[idx+1]
                left_visible = bool(display.get(keys[idx], True))
                right_visible = bool(display.get(keys[idx + 1], True))
                sep.setVisible(left_visible and right_visible)

        # Font
        family = self._config.get("font.family", "Microsoft YaHei")
        size = self._config.get("font.size", 12)
        font = QFont(family, size)
        for name_label, value_label in self._item_labels.values():
            name_label.setFont(font)
            value_label.setFont(font)

        # Appearance (opacity / color)
        self._apply_appearance()

        # Always on top (must come BEFORE lock — setWindowFlags+show resets WA on Windows)
        on_top = bool(self._config.get("general.always_on_top", True))
        self.set_always_on_top(on_top)

        # Lock window (click-through)
        locked = bool(self._config.get("general.lock_window", False))
        self.set_window_locked(locked)

    # ------------------------------------------------------------------
    # Mouse: drag to move
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._hit_edge(event.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._resize_start_geom = self.geometry()
                self._resize_start_pos = event.globalPosition().toPoint()
            else:
                self._drag_pos = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                )
                self._resize_edge = None
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._resize_edge and self._resize_start_geom and self._resize_start_pos:
            self._do_resize(event)
            return
        if self._drag_pos:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(delta - self.frameGeometry().topLeft() + self.pos())
            event.accept()
            return
        edge = self._hit_edge(event.position().toPoint())
        self._set_resize_cursor(edge)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        self._resize_edge = None
        self._resize_start_geom = None
        self._resize_start_pos = None
        self._save_geometry()
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Resize logic
    # ------------------------------------------------------------------

    def _hit_edge(self, local: QPoint) -> str | None:
        w, h = self.width(), self.height()
        left = local.x() < BORDER_WIDTH
        right = local.x() > w - BORDER_WIDTH
        top = local.y() < BORDER_WIDTH
        bottom = local.y() > h - BORDER_WIDTH
        if top and left:     return "nw"
        if top and right:    return "ne"
        if bottom and left:  return "sw"
        if bottom and right: return "se"
        if top:    return "n"
        if bottom: return "s"
        if left:   return "w"
        if right:  return "e"
        return None

    def _set_resize_cursor(self, edge: str | None) -> None:
        cursors: dict[str | None, Qt.CursorShape] = {
            "n": Qt.CursorShape.SizeVerCursor,
            "s": Qt.CursorShape.SizeVerCursor,
            "e": Qt.CursorShape.SizeHorCursor,
            "w": Qt.CursorShape.SizeHorCursor,
            "ne": Qt.CursorShape.SizeBDiagCursor,
            "sw": Qt.CursorShape.SizeBDiagCursor,
            "nw": Qt.CursorShape.SizeFDiagCursor,
            "se": Qt.CursorShape.SizeFDiagCursor,
        }
        self.setCursor(cursors.get(edge, Qt.CursorShape.ArrowCursor))  # type: ignore[arg-type]

    def _do_resize(self, event: QMouseEvent) -> None:
        assert self._resize_start_geom and self._resize_start_pos and self._resize_edge
        delta = event.globalPosition().toPoint() - self._resize_start_pos
        geom = QRect(self._resize_start_geom)
        min_w, min_h = self.minimumWidth(), self.minimumHeight()
        edge = self._resize_edge
        if "e" in edge:
            geom.setWidth(max(min_w, geom.width() + delta.x()))
        if "w" in edge:
            new_w = max(min_w, geom.width() - delta.x())
            if new_w != geom.width():
                geom.setX(geom.x() + (geom.width() - new_w))
                geom.setWidth(new_w)
        if "s" in edge:
            geom.setHeight(max(min_h, geom.height() + delta.y()))
        if "n" in edge:
            new_h = max(min_h, geom.height() - delta.y())
            if new_h != geom.height():
                geom.setY(geom.y() + (geom.height() - new_h))
                geom.setHeight(new_h)
        self.setGeometry(geom)

    # ------------------------------------------------------------------
    # Persist geometry
    # ------------------------------------------------------------------

    def _save_geometry(self) -> None:
        g = self.geometry()
        self._config.set("window.x", g.x())
        self._config.set("window.y", g.y())
        self._config.set("window.width", g.width())
        self._config.set("window.height", g.height())

    def set_window_locked(self, locked: bool) -> None:
        """When locked, mouse events pass through to whatever is behind the window.

        Uses the Windows WS_EX_TRANSPARENT extended style — Qt's
        WA_TransparentForMouseEvents only forwards events within the same
        application, so it cannot pass clicks through to other apps.
        """
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, _GWL_EXSTYLE)
        if locked:
            style |= _WS_EX_TRANSPARENT
        else:
            style &= ~_WS_EX_TRANSPARENT
        ctypes.windll.user32.SetWindowLongPtrW(hwnd, _GWL_EXSTYLE, style)

    def set_always_on_top(self, on_top: bool) -> None:
        """Toggle whether the window stays above all other windows."""
        # Only act when the flag actually needs to change — setWindowFlags
        # recreates the native window handle which resets WS_EX_TRANSPARENT.
        current = int(self.windowFlags())
        has_flag = bool(current & Qt.WindowType.WindowStaysOnTopHint)
        if has_flag == on_top:
            return
        flags = self.windowFlags()
        if on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if self.isVisible():
            self.show()

    # ------------------------------------------------------------------
    # Window positioning
    # ------------------------------------------------------------------

    def move_to_position(self, position: str) -> None:
        """Snap window to a screen-edge position on the current monitor."""
        screen = self.screen()
        geom = screen.availableGeometry()
        w, h = self.width(), self.height()

        positions = {
            "top_left":      (geom.left(),              geom.top()),
            "top_center":    (geom.center().x() - w // 2, geom.top()),
            "top_right":     (geom.right() - w,         geom.top()),
            "bottom_left":   (geom.left(),              geom.bottom() - h),
            "bottom_center": (geom.center().x() - w // 2, geom.bottom() - h),
            "bottom_right":  (geom.right() - w,         geom.bottom() - h),
        }
        x, y = positions.get(position, (geom.left(), geom.top()))
        self.move(x, y)
        self._save_geometry()

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.shown_from_tray.emit()

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
        self.hidden_to_tray.emit()
