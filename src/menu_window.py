"""Settings + Calendar tabbed window opened from tray menu."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .config_manager import ConfigManager


FONT_SIZE_PRESETS = [8, 12, 16, 20, 24]

# ---- preset-colour helpers --------------------------------------------------

COLOR_PRESETS: list[tuple[str, str]] = [
    ("白",   "#E8E8EC"),
    ("绿",   "#7EC87E"),
    ("青",   "#5EB5C8"),
    ("橙",   "#D4A85C"),
    ("玫红", "#D47EA8"),
    ("灰蓝", "#8EA8C0"),
]

LAYOUT_MODES: list[tuple[str, str]] = [
    ("default",    "默认（竖向列表）"),
    ("horizontal", "横向（单行）"),
]


def _blocked(widget, callback):
    """Call *callback(widget)* with widget signals temporarily blocked."""
    widget.blockSignals(True)
    try:
        callback(widget)
    finally:
        widget.blockSignals(False)


# =============================================================================
# SnappingSlider
# =============================================================================

class SnappingSlider(QWidget):
    """A horizontal slider that snaps to preset font-size stops."""

    value_changed = Signal(int)

    def __init__(self, current_size: int = 12, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._presets = FONT_SIZE_PRESETS

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setRange(0, len(self._presets) - 1)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(1)

        self._label = QLabel(str(current_size), self)
        self._label.setMinimumWidth(28)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._slider, 1)
        layout.addWidget(self._label)

        self.set_value(current_size, emit=False)
        self._slider.valueChanged.connect(self._on_slider_moved)

    def _on_slider_moved(self, idx: int) -> None:
        size = self._presets[idx]
        self._label.setText(str(size))
        self.value_changed.emit(size)

    def set_value(self, size: int, emit: bool = True) -> None:
        best_idx = min(
            range(len(self._presets)),
            key=lambda i: abs(self._presets[i] - size),
        )
        self._slider.blockSignals(True)
        self._slider.setValue(best_idx)
        self._slider.blockSignals(False)
        self._label.setText(str(self._presets[best_idx]))
        if emit:
            self.value_changed.emit(self._presets[best_idx])

    def current_value(self) -> int:
        return self._presets[self._slider.value()]


# =============================================================================
# SettingsTab
# =============================================================================

class SettingsTab(QWidget):
    """Display toggles + font + layout + appearance."""

    display_changed = Signal()
    font_changed = Signal(int)
    layout_changed = Signal()
    appearance_changed = Signal()
    position_requested = Signal(str)
    lock_changed = Signal()
    topmost_changed = Signal()

    def __init__(self, config: ConfigManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        # -- Display items ------------------------------------------------------
        root.addWidget(self._build_display_group())

        # -- Font ---------------------------------------------------------------
        root.addWidget(self._build_font_group())

        # -- Layout -------------------------------------------------------------
        root.addWidget(self._build_layout_group())

        # -- Appearance ---------------------------------------------------------
        root.addWidget(self._build_appearance_group())

        # -- Position -----------------------------------------------------------
        root.addWidget(self._build_position_group())

        root.addStretch()

    # ==================================================================
    # Display items
    # ==================================================================

    def _build_display_group(self) -> QGroupBox:
        grp = QGroupBox("显示项目", self)
        layout = QVBoxLayout(grp)
        layout.setSpacing(6)

        self._checks: dict[str, QCheckBox] = {}
        item_labels = {
            "keyboard": "键盘按键数",
            "mouse":   "鼠标点击数",
            "cpu":     "CPU 使用率",
            "memory":  "内存使用率",
            "gpu":     "GPU 使用率",
            "disk":    "C盘剩余空间",
        }
        for key, text in item_labels.items():
            cb = QCheckBox(text, grp)
            cb.setChecked(bool(self._config.get(f"display.{key}", True)))
            cb.toggled.connect(self._on_display_toggled)
            layout.addWidget(cb)
            self._checks[key] = cb
        return grp

    def _on_display_toggled(self) -> None:
        for key, cb in self._checks.items():
            self._config.set(f"display.{key}", cb.isChecked())
        self.display_changed.emit()

    # ==================================================================
    # Font
    # ==================================================================

    def _build_font_group(self) -> QGroupBox:
        grp = QGroupBox("字体设置", self)
        layout = QVBoxLayout(grp)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(QLabel("字号：", grp))
        current_size = int(self._config.get("font.size", 12))
        self._font_slider = SnappingSlider(current_size, grp)
        self._font_slider.value_changed.connect(self._on_font_changed)
        row.addWidget(self._font_slider, 1)
        layout.addLayout(row)
        return grp

    def _on_font_changed(self, size: int) -> None:
        self._config.set("font.size", size)
        self.font_changed.emit(size)

    # ==================================================================
    # Layout mode
    # ==================================================================

    def _build_layout_group(self) -> QGroupBox:
        grp = QGroupBox("布局设置", self)
        layout = QVBoxLayout(grp)
        layout.setSpacing(8)

        crow = QHBoxLayout()
        crow.setSpacing(8)
        crow.addWidget(QLabel("布局模式：", grp))
        self._layout_combo = QComboBox(grp)
        for value, label in LAYOUT_MODES:
            self._layout_combo.addItem(label, value)
        current_mode = self._config.get("layout.mode", "default")
        for i, (value, _) in enumerate(LAYOUT_MODES):
            if value == current_mode:
                self._layout_combo.setCurrentIndex(i)
                break
        self._layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        crow.addWidget(self._layout_combo, 1)
        layout.addLayout(crow)

        return grp

    def _on_layout_changed(self) -> None:
        mode = self._layout_combo.currentData()
        self._config.set("layout.mode", mode)
        self.layout_changed.emit()

    # ==================================================================
    # Window position
    # ==================================================================

    def _build_position_group(self) -> QGroupBox:
        grp = QGroupBox("窗口位置", self)
        vbox = QVBoxLayout(grp)
        vbox.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(6)

        buttons = [
            ("top_left",      "左上"),
            ("top_center",    "中上"),
            ("top_right",     "右上"),
            ("bottom_left",   "左下"),
            ("bottom_center", "中下"),
            ("bottom_right",  "右下"),
        ]
        for i, (key, label) in enumerate(buttons):
            btn = QPushButton(label, grp)
            btn.clicked.connect(lambda checked, k=key: self.position_requested.emit(k))
            grid.addWidget(btn, i // 3, i % 3)

        vbox.addLayout(grid)

        # Always on top checkbox
        self._topmost_cb = QCheckBox("窗口置顶", grp)
        self._topmost_cb.setChecked(
            bool(self._config.get("general.always_on_top", True))
        )
        self._topmost_cb.toggled.connect(self._on_topmost_toggled)
        vbox.addWidget(self._topmost_cb)

        # Lock window checkbox
        self._lock_cb = QCheckBox("锁定窗口", grp)
        self._lock_cb.setChecked(
            bool(self._config.get("general.lock_window", False))
        )
        self._lock_cb.toggled.connect(self._on_lock_toggled)
        vbox.addWidget(self._lock_cb)

        lock_hint = QLabel("锁定后鼠标点击将穿透窗口，不影响后方软件操作", grp)
        lock_hint.setStyleSheet("color: #888; font-size: 11px;")
        lock_hint.setWordWrap(True)
        vbox.addWidget(lock_hint)

        # Startup checkbox
        self._startup_cb = QCheckBox("开机启动", grp)
        self._startup_cb.setChecked(
            bool(self._config.get("general.start_on_boot", False))
        )
        self._startup_cb.toggled.connect(self._on_startup_toggled)
        vbox.addWidget(self._startup_cb)

        return grp

    def _on_startup_toggled(self, checked: bool) -> None:
        from .startup_manager import set_startup

        self._config.set("general.start_on_boot", checked)
        set_startup(checked)

    def _on_topmost_toggled(self, checked: bool) -> None:
        self._config.set("general.always_on_top", checked)
        self.topmost_changed.emit()

    def _on_lock_toggled(self, checked: bool) -> None:
        self._config.set("general.lock_window", checked)
        self.lock_changed.emit()

    # ==================================================================
    # Appearance (opacity + font colour)
    # ==================================================================

    def _build_appearance_group(self) -> QGroupBox:
        grp = QGroupBox("外观设置", self)
        layout = QVBoxLayout(grp)
        layout.setSpacing(8)

        # ---- opacity slider ----
        orow = QHBoxLayout()
        orow.setSpacing(10)
        orow.addWidget(QLabel("不透明度：", grp))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal, grp)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(
            int(float(self._config.get("appearance.opacity", 0.88)) * 100)
        )
        self._opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._opacity_slider.setTickInterval(10)
        self._opacity_label = QLabel(
            f"{self._opacity_slider.value()}%", grp
        )
        self._opacity_label.setMinimumWidth(36)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        orow.addWidget(self._opacity_slider, 1)
        orow.addWidget(self._opacity_label)
        layout.addLayout(orow)

        # ---- font-colour presets ----
        crow = QHBoxLayout()
        crow.setSpacing(6)
        crow.addWidget(QLabel("字体颜色：", grp))
        self._color_buttons: list[QPushButton] = []
        current_color = self._config.get("appearance.font_color", "#E8E8EC")
        for name, hex_color in COLOR_PRESETS:
            btn = QPushButton("", grp)
            btn.setFixedSize(26, 26)
            btn.setStyleSheet(
                f"background-color: {hex_color}; "
                f"border: 2px solid {'#888' if hex_color == current_color else '#444'}; "
                f"border-radius: 4px;"
            )
            btn.setToolTip(name)
            btn.clicked.connect(lambda checked, c=hex_color: self._on_preset_color(c))
            crow.addWidget(btn)
            self._color_buttons.append(btn)
        crow.addStretch()
        layout.addLayout(crow)

        # ---- custom color + reset ----
        brow = QHBoxLayout()
        brow.setSpacing(8)
        self._custom_color_btn = QPushButton("自定义颜色…", grp)
        self._custom_color_btn.clicked.connect(self._on_custom_color)
        brow.addWidget(self._custom_color_btn)

        reset_btn = QPushButton("恢复默认", grp)
        reset_btn.clicked.connect(self._on_appearance_reset)
        brow.addWidget(reset_btn)
        brow.addStretch()
        layout.addLayout(brow)

        return grp

    def _on_opacity_changed(self, value: int) -> None:
        self._opacity_label.setText(f"{value}%")
        self._config.set("appearance.opacity", value / 100.0)
        self.appearance_changed.emit()

    def _on_preset_color(self, hex_color: str) -> None:
        self._config.set("appearance.font_color", hex_color)
        self._refresh_color_buttons(hex_color)
        self.appearance_changed.emit()

    def _on_custom_color(self) -> None:
        current = self._config.get("appearance.font_color", "#E8E8EC")
        color = QColorDialog.getColor(QColor(current), self, "选择字体颜色")
        if color.isValid():
            hex_color = color.name()
            self._config.set("appearance.font_color", hex_color)
            self._refresh_color_buttons(hex_color)
            self.appearance_changed.emit()

    def _on_appearance_reset(self) -> None:
        self._config.set("appearance.opacity", 0.88)
        self._config.set("appearance.font_color", "#E8E8EC")
        _blocked(self._opacity_slider, lambda s: s.setValue(88))
        self._opacity_label.setText("88%")
        self._refresh_color_buttons("#E8E8EC")
        self.appearance_changed.emit()

    def _refresh_color_buttons(self, active: str) -> None:
        for btn, (_, hex_color) in zip(self._color_buttons, COLOR_PRESETS):
            border = "#888" if hex_color == active else "#444"
            btn.setStyleSheet(
                f"background-color: {hex_color}; "
                f"border: 2px solid {border}; "
                f"border-radius: 4px;"
            )


# =============================================================================
# MenuWindow (container)
# =============================================================================

class MenuWindow(QWidget):
    """Tabbed window: Settings tab + Calendar tab."""

    def __init__(
        self,
        config: ConfigManager,
        calendar_widget: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("小桌宠 — 设置")
        self.setMinimumSize(480, 400)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget(self)

        # Tab 0: Settings (wrapped in scroll area for constrained window height)
        self.settings_tab = SettingsTab(config)
        self.settings_tab.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.settings_tab)
        self._tabs.addTab(scroll, "设置")

        # Tab 1: Calendar
        if calendar_widget:
            self._tabs.addTab(calendar_widget, "日历")
        else:
            placeholder = QLabel("日历加载中…", self)
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._calendar_placeholder = placeholder
            self._tabs.addTab(placeholder, "日历")

        root.addWidget(self._tabs)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()
