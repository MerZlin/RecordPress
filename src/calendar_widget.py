"""Monthly calendar grid showing daily keyboard / mouse counts from saved data."""

from __future__ import annotations

import calendar
from datetime import date

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .data_manager import DataManager


class DayBox(QFrame):
    """Single day cell in the calendar grid."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DayBox")
        self.setMinimumSize(56, 56)
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 4, 3, 4)
        layout.setSpacing(1)

        self._date_label = QLabel("", self)
        self._date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_font = QFont()
        date_font.setPointSize(11)
        date_font.setBold(True)
        self._date_label.setFont(date_font)

        self._kb_label = QLabel("", self)
        self._kb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        kb_font = QFont()
        kb_font.setPointSize(7)
        self._kb_label.setFont(kb_font)

        self._ms_label = QLabel("", self)
        self._ms_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ms_font = QFont()
        ms_font.setPointSize(7)
        self._ms_label.setFont(ms_font)

        layout.addWidget(self._date_label)
        layout.addWidget(self._kb_label)
        layout.addWidget(self._ms_label)

        self.setStyleSheet(self._style())

    def set_data(
        self,
        day: int,
        keyboard: int = 0,
        mouse: int = 0,
        *,
        is_today: bool = False,
        is_current_month: bool = True,
    ) -> None:
        self._date_label.setText(str(day))
        if is_current_month:
            self._kb_label.setText(f"K:{keyboard}")
            self._ms_label.setText(f"M:{mouse}")
        else:
            self._kb_label.setText("")
            self._ms_label.setText("")

        self.setProperty("today", is_today)
        self.setProperty("otherMonth", not is_current_month)
        # Force style re-evaluation
        self.style().unpolish(self)
        self.style().polish(self)

    @staticmethod
    def _style() -> str:
        return """
            #DayBox {
                background-color: #3A3A3E;
                border: 1px solid #505055;
                border-radius: 6px;
            }
            #DayBox[today="true"] {
                border: 2px solid #4A9EFF;
            }
            #DayBox[otherMonth="true"] {
                background-color: #2A2A2E;
            }
            #DayBox QLabel {
                color: #D0D0D4;
                background: transparent;
            }
            #DayBox[otherMonth="true"] QLabel {
                color: #606068;
            }
        """


class CalendarWidget(QWidget):
    """A monthly calendar that reads daily stats from DataManager."""

    def __init__(
        self,
        data_manager: DataManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._data = data_manager
        self._viewing: QDate = QDate.currentDate()

        self._day_boxes: list[DayBox] = []
        self._populated = False

        self._setup_ui()
        # _populate() deferred to showEvent — avoids startup lag when
        # opening the menu window for the first time.

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # --- Navigation bar ---
        nav = QHBoxLayout()
        nav.setSpacing(12)

        self._prev_btn = QPushButton("◀")
        self._prev_btn.setFixedWidth(36)
        self._prev_btn.clicked.connect(self._go_prev)
        self._prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._title_label = QLabel()
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        self._title_label.setFont(title_font)

        self._next_btn = QPushButton("▶")
        self._next_btn.setFixedWidth(36)
        self._next_btn.clicked.connect(self._go_next)
        self._next_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        nav.addWidget(self._prev_btn)
        nav.addWidget(self._title_label, 1)
        nav.addWidget(self._next_btn)
        root.addLayout(nav)

        # --- Weekday headers ---
        wd_layout = QHBoxLayout()
        wd_layout.setSpacing(3)
        wd_names = ["一", "二", "三", "四", "五", "六", "日"]
        for name in wd_names:
            lbl = QLabel(name, self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedWidth(56)
            lbl.setStyleSheet("color: #A0A0A8; font-weight: bold;")
            wd_layout.addWidget(lbl)
        root.addLayout(wd_layout)

        # --- Day grid ---
        self._grid = QGridLayout()
        self._grid.setSpacing(3)
        root.addLayout(self._grid)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        # Clear old boxes
        for box in self._day_boxes:
            box.deleteLater()
        self._day_boxes.clear()

        year = self._viewing.year()
        month = self._viewing.month()
        today = date.today()

        # Update title
        self._title_label.setText(f"{year} 年 {month} 月")

        # Load all data for this month
        month_data = self._data.load_month_range(year, month)

        # Calendar layout
        cal = calendar.Calendar(firstweekday=0)  # Monday = 0
        weeks = cal.monthdayscalendar(year, month)

        for row_idx, week in enumerate(weeks):
            for col_idx, day in enumerate(week):
                box = DayBox(self)
                if day == 0:
                    # Empty cell (padding at start/end of month)
                    box.setVisible(False)
                else:
                    iso = f"{year:04d}-{month:02d}-{day:02d}"
                    counts = month_data.get(iso, {"keyboard": 0, "mouse": 0})
                    is_today = (
                        today.year == year
                        and today.month == month
                        and today.day == day
                    )
                    box.set_data(
                        day,
                        counts.get("keyboard", 0),
                        counts.get("mouse", 0),
                        is_today=is_today,
                        is_current_month=True,
                    )
                self._grid.addWidget(box, row_idx, col_idx)
                self._day_boxes.append(box)

    # ------------------------------------------------------------------
    # Lazy init
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._populated:
            self._populated = True
            self._populate()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_prev(self) -> None:
        self._viewing = self._viewing.addMonths(-1)
        self._populate()

    def _go_next(self) -> None:
        self._viewing = self._viewing.addMonths(1)
        self._populate()
