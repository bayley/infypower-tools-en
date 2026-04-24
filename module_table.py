from PyQt5.QtCore import Qt, QRect, QEvent
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QStyledItemDelegate, QStyle, QStyleOptionButton,
                              QApplication, QHeaderView, QWidget, QHBoxLayout,
                              QTableWidgetItem)
from qfluentwidgets import TableWidget, IconInfoBadge, FluentIcon as FIF


class _CheckDelegate(QStyledItemDelegate):
    """渲染 ✓ 圆形复选框，列宽变化时跟随"""

    def __init__(self, on_toggle, parent=None):
        super().__init__(parent)
        self._on_toggle = on_toggle  # callable(row, col, new_state)

    def paint(self, painter, option, index):
        checked = index.data(Qt.UserRole) is True
        opt = QStyleOptionButton()
        opt.rect = self._checkbox_rect(option.rect)
        opt.state = QStyle.State_Enabled
        opt.state |= QStyle.State_On if checked else QStyle.State_Off
        QApplication.style().drawControl(QStyle.CE_CheckBox, opt, painter)

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease:
            cur = index.data(Qt.UserRole) is True
            new = not cur
            model.setData(index, new, Qt.UserRole)
            self._on_toggle(index.row(), index.column(), new)
            return True
        return False

    @staticmethod
    def _checkbox_rect(cell_rect: QRect) -> QRect:
        size = 16
        x = cell_rect.center().x() - size // 2
        y = cell_rect.center().y() - size // 2
        return QRect(x, y, size, size)


COLS = ['地址', '电压', '电流', '温度℃', '💤', '💡']
COL_ADDR, COL_V, COL_I, COL_T, COL_SLEEP, COL_LED = range(6)


class ModuleTable(TableWidget):
    """组内模块表格。外部传入 on_sleep_toggle/on_led_toggle 回调。"""

    def __init__(self, on_sleep_toggle, on_led_toggle, parent=None):
        super().__init__(parent)
        self._on_sleep = on_sleep_toggle
        self._on_led   = on_led_toggle
        self.setColumnCount(len(COLS))
        self.setHorizontalHeaderLabels(COLS)
        self.setEditTriggers(TableWidget.NoEditTriggers)
        self.setBorderVisible(True)
        self.setBorderRadius(6)
        self.setWordWrap(False)
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(COL_SLEEP, QHeaderView.Fixed)
        self.horizontalHeader().setSectionResizeMode(COL_LED,   QHeaderView.Fixed)
        self.setColumnWidth(COL_SLEEP, 40)
        self.setColumnWidth(COL_LED, 40)

        self._sleep_delegate = _CheckDelegate(self._handle_sleep, self)
        self._led_delegate   = _CheckDelegate(self._handle_led, self)
        self.setItemDelegateForColumn(COL_SLEEP, self._sleep_delegate)
        self.setItemDelegateForColumn(COL_LED,   self._led_delegate)

    def update_modules(self, state, now_ms_thresholds: tuple):
        """state: GroupState；now_ms_thresholds: (now_time, pending_ms, offline_ms, gone_ms)"""
        now, pending_ms, offline_ms, gone_ms = now_ms_thresholds
        addrs = sorted(state.modules.keys())
        self.setRowCount(len(addrs))
        for row, addr in enumerate(addrs):
            m = state.modules[addr]
            life = m.lifecycle(now, pending_ms, offline_ms, gone_ms)
            is_offline = life in ('pending', 'offline', 'gone')

            self.setItem(row, COL_ADDR, QTableWidgetItem(f"0x{addr:02X}"))
            self.setItem(row, COL_V,    QTableWidgetItem("— —" if is_offline else f"{m.voltage:.1f} V"))
            self.setItem(row, COL_I,    QTableWidgetItem("— —" if is_offline else f"{m.current:.2f} A"))
            self.setItem(row, COL_T,    QTableWidgetItem("—"   if is_offline else f"{m.temperature}"))

            # 复选框列：用 UserRole 存状态
            sleep_item = QTableWidgetItem()
            sleep_item.setData(Qt.UserRole, m.sleeping)
            sleep_item.setFlags(Qt.ItemIsEnabled if not is_offline else Qt.NoItemFlags)
            self.setItem(row, COL_SLEEP, sleep_item)

            led_item = QTableWidgetItem()
            led_item.setData(Qt.UserRole, m.led_blinking)
            led_item.setFlags(Qt.ItemIsEnabled if not is_offline else Qt.NoItemFlags)
            self.setItem(row, COL_LED, led_item)

            # 告警标识：在地址列追加红色 IconInfoBadge（如果有告警）
            if m.alarms:
                badge = IconInfoBadge.error(FIF.INFO, parent=self)
                badge.setToolTip("\n".join(m.alarms))
                container = QWidget()
                hl = QHBoxLayout(container)
                hl.setContentsMargins(2, 2, 2, 2)
                hl.addWidget(badge)
                hl.addStretch()
                self.setCellWidget(row, COL_ADDR, container)
            else:
                self.removeCellWidget(row, COL_ADDR)

            # 行变红/半透明
            if life == 'pending':
                self._tint_row(row, QColor(140, 140, 140, 80))
            elif life in ('offline', 'gone'):
                self._tint_row(row, QColor(220, 53, 53, 50))
            else:
                self._tint_row(row, None)

    def _tint_row(self, row: int, color):
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item is None:
                continue
            if color is None:
                item.setData(Qt.BackgroundRole, None)
            else:
                item.setBackground(color)

    def _handle_sleep(self, row: int, col: int, new_state: bool):
        addr_item = self.item(row, COL_ADDR)
        if addr_item is None:
            return
        addr = int(addr_item.text(), 16)
        self._on_sleep(addr, new_state)

    def _handle_led(self, row: int, col: int, new_state: bool):
        addr_item = self.item(row, COL_ADDR)
        if addr_item is None:
            return
        addr = int(addr_item.text(), 16)
        self._on_led(addr, new_state)
