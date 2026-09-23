import time
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QTextCursor, QPainter
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QTableWidgetItem, QHeaderView, QDoubleSpinBox, QSpinBox,
    QComboBox, QDialog, QFormLayout,
    QDialogButtonBox, QSplitter, QStyledItemDelegate
)
from qfluentwidgets import (
    TableWidget, PushButton, ComboBox, SubtitleLabel, CaptionLabel, setFont,
    TextEdit
)
from config_manager import AppConfig
import REG1K0100A2 as reg


# ─── 命令定义表 ───────────────────────────────────────────────
COMMANDS = [
    {'cmd': 0x01, 'type': 'R', 'desc': 'System voltage/current (float)','params': []},
    {'cmd': 0x02, 'type': 'R', 'desc': 'System module count','params': []},
    {'cmd': 0x03, 'type': 'R', 'desc': 'Module N voltage/current (float)','params': []},
    {'cmd': 0x04, 'type': 'R', 'desc': 'Module N status','params': []},
    {'cmd': 0x06, 'type': 'R', 'desc': 'Module N three-phase input voltage','params': []},
    {'cmd': 0x08, 'type': 'R', 'desc': 'System voltage/current (fixed-point)','params': []},
    {'cmd': 0x09, 'type': 'R', 'desc': 'Module N voltage/current (fixed-point)','params': []},
    {'cmd': 0x0A, 'type': 'R', 'desc': 'Module parameters (V / I / P)','params': []},
    {'cmd': 0x0B, 'type': 'R', 'desc': 'Module barcode','params': []},
    {'cmd': 0x0C, 'type': 'R', 'desc': 'External voltage / allowed current','params': []},
    {'cmd': 0x0F, 'type': 'W', 'desc': 'Comprehensive settings','params': [], 'special': 'dialog'},
    {'cmd': 0x13, 'type': 'W', 'desc': 'Walk-In enable',
     'params': [{'type': 'combo', 'options': ['Enable', 'Disable'], 'key': 'enable'}]},
    {'cmd': 0x14, 'type': 'W', 'desc': 'Green LED blink',
     'params': [{'type': 'combo', 'options': ['Blink', 'Normal'], 'key': 'blink'}]},
    {'cmd': 0x16, 'type': 'W', 'desc': 'Set group number',
     'params': [{'type': 'spin', 'min': 1, 'max': 255, 'default': 1, 'key': 'group'}]},
    {'cmd': 0x19, 'type': 'W', 'desc': 'Module sleep',
     'params': [{'type': 'combo', 'options': ['Sleep', 'Wake'], 'key': 'sleep'}]},
    {'cmd': 0x1A, 'type': 'W', 'desc': 'Power on/off',
     'params': [{'type': 'combo', 'options': ['Power on', 'Power off'], 'key': 'power'}]},
    {'cmd': 0x1B, 'type': 'W', 'desc': 'Set system output voltage / total current',
     'params': [
         {'type': 'double', 'label': 'V', 'key': 'volt', 'min': 150.0, 'max': 1000.0, 'default': 320.0},
         {'type': 'double', 'label': 'A', 'key': 'curr', 'min': 0.0,   'max': 6000.0, 'default': 10.0},
     ], 'addr_lock': 0x3F},
    {'cmd': 0x1C, 'type': 'W', 'desc': 'Set module voltage / current',
     'params': [
         {'type': 'double', 'label': 'V', 'key': 'volt', 'min': 150.0, 'max': 1000.0, 'default': 320.0},
         {'type': 'double', 'label': 'A', 'key': 'curr', 'min': 0.0,   'max': 100.0,  'default': 10.0},
     ]},
    {'cmd': 0x1F, 'type': 'W', 'desc': 'Address assignment mode',
     'params': [{'type': 'combo', 'options': ['Automatic', 'DIP switch'], 'key': 'mode'}],
     'addr_lock': 0x3F},
]

# cmd_code -> 格式化响应字符串的函数（接收 CANControllerInfo 实例）
RESPONSE_FORMATTERS = {
    0x01: lambda ci: f"{ci.SystemVolt:.2f} V  {ci.SystemCurr:.2f} A",
    0x02: lambda ci: f"Modules: {ci.ModuleCount}",
    0x03: lambda ci: f"{ci.ModuleVoltFloat:.2f} V  {ci.ModuleCurrFloat:.2f} A",
    0x04: lambda ci: f"Temp: {ci.Temperature} ℃",
    0x06: lambda ci: f"AB:{ci.AC_AB_Volt:.1f}V  BC:{ci.AC_BC_Volt:.1f}V  CA:{ci.AC_CA_Volt:.1f}V",
    0x08: lambda ci: f"{ci.SystemVolt:.2f} V  {ci.SystemCurr:.2f} A",
    0x09: lambda ci: f"{ci.DC_Output_Volt:.2f} V  {ci.DC_Output_Curr:.2f} A",
    0x0A: lambda ci: f"Max: {ci.ParamVoltMax:.0f}V / {ci.ParamCurrMax:.1f}A  Rated: {ci.ParamPower:.0f}W",
    0x0B: lambda ci: ci.Barcode if ci.Barcode else "—",
    0x0C: lambda ci: f"Ext: {ci.ExternalVolt:.1f}V  Allowed: {ci.AllowedCurr:.1f}A",
}

# 地址选项（索引 → 地址值）
_ADDR_VALUES = list(range(16)) + [0x3F]


class TypeBadgeDelegate(QStyledItemDelegate):
    """为类型列绘制圆角徽章，跟随列宽实时更新（避免 setCellWidget 延迟刷新问题）。"""

    _COLORS = {
        'READ': ('#1a3a5c', '#89dceb'),
        'SET': ('#3d1a1a', '#f38ba8'),
    }

    def paint(self, painter, option, index):
        text = index.data(Qt.DisplayRole) or ''
        bg_hex, fg_hex = self._COLORS.get(text, ('#313244', '#cdd6f4'))

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        badge = option.rect.adjusted(8, 5, -8, -5)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(bg_hex))
        painter.drawRoundedRect(badge, 4, 4)

        painter.setPen(QColor(fg_hex))
        painter.setFont(QFont('Microsoft YaHei', 9))
        painter.drawText(badge, Qt.AlignCenter, text)
        painter.restore()


class ManualWidget(QFrame):

    OBJECT_NAME = 'ManualInterface'

    def __init__(self, can_device, canController_info, config: AppConfig = None, parent=None):
        super().__init__(parent=parent)
        self.setObjectName(self.OBJECT_NAME)
        self._can_device = can_device
        self._ci = canController_info
        self._config = config or AppConfig()
        self._row_widgets = {}      # cmd_code -> {key: widget}
        self._response_labels = {}  # cmd_code -> QLabel

        self._build_ui()
        reg.g_log_callback = self._append_log

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_responses)
        self._refresh_timer.start(150)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = SubtitleLabel('Manual Control', self)
        setFont(title, 20)
        layout.addWidget(title)

        layout.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Vertical, self)
        splitter.addWidget(self._build_table())
        splitter.addWidget(self._build_log())
        splitter.setSizes([500, 120])
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, stretch=1)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget(self)
        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        h.addWidget(CaptionLabel('Target address:', bar))
        self.addrCombo = ComboBox(bar)
        for i in range(16):
            self.addrCombo.addItem(f"0x{i:02X} — Module {i}")
        self.addrCombo.addItem("0x3F — Broadcast")
        self.addrCombo.setCurrentIndex(0)
        self.addrCombo.setFixedWidth(160)
        h.addWidget(self.addrCombo)

        h.addWidget(CaptionLabel('Device:', bar))
        self.deviceCombo = ComboBox(bar)
        self.deviceCombo.addItem("0x0A — Module")
        self.deviceCombo.addItem("0x0B — Group")
        self.deviceCombo.setFixedWidth(140)
        h.addWidget(self.deviceCombo)

        h.addStretch()

        self.readAllBtn = PushButton('⬇ Read All', bar)
        self.readAllBtn.clicked.connect(self._read_all)
        h.addWidget(self.readAllBtn)

        return bar

    def _build_table(self) -> QWidget:
        self._table = TableWidget(self)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(['CMD', 'Type', 'Description', 'Parameters', 'Response', 'Action'])
        self._table.setRowCount(len(COMMANDS))
        self._table.verticalHeader().hide()
        self._table.setEditTriggers(TableWidget.NoEditTriggers)
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.setWordWrap(False)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self._table.setColumnWidth(0, 64)
        self._table.setColumnWidth(1, 64)
        self._table.setColumnWidth(3, 220)
        self._table.setColumnWidth(5, 72)
        self._table.setItemDelegateForColumn(1, TypeBadgeDelegate(self._table))

        for i, cmd_def in enumerate(COMMANDS):
            cmd_code = cmd_def['cmd']
            self._row_widgets[cmd_code] = {}

            # 列0: CMD
            item = QTableWidgetItem(f"0x{cmd_code:02X}")
            item.setFont(QFont('Consolas', 10))
            item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 0, item)

            # 列1: 类型（由 TypeBadgeDelegate 绘制，跟随列宽实时更新）
            type_item = QTableWidgetItem('READ' if cmd_def['type'] == 'R' else 'SET')
            type_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(i, 1, type_item)

            # 列2: 说明
            desc_item = QTableWidgetItem(cmd_def['desc'])
            desc_item.setFont(QFont('Microsoft YaHei', 9))
            self._table.setItem(i, 2, desc_item)

            # 列3: 参数
            param_w = self._build_param_widget(cmd_def, cmd_code)
            self._table.setCellWidget(i, 3, param_w)

            # 列4: 响应数据
            resp_lbl = QLabel('—', self._table)
            resp_lbl.setAlignment(Qt.AlignCenter)
            resp_lbl.setFont(QFont('Consolas', 9))
            self._response_labels[cmd_code] = resp_lbl
            self._table.setCellWidget(i, 4, resp_lbl)

            # 列5: 操作按钮
            btn = self._build_action_button(cmd_def)
            btn.clicked.connect(lambda checked, c=cmd_code: self._send_command(c))
            self._table.setCellWidget(i, 5, btn)

            # 广播锁定行：高亮 CMD 列文字颜色
            if cmd_def.get('addr_lock') is not None:
                it = self._table.item(i, 0)
                if it:
                    it.setForeground(QColor('#fab387'))

        return self._table

    def _build_param_widget(self, cmd_def: dict, cmd_code: int) -> QWidget:
        container = QWidget()
        h = QHBoxLayout(container)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(4)

        params = cmd_def.get('params', [])
        if not params:
            lbl = QLabel('—')
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet('color: #6c7086')
            h.addWidget(lbl)
            return container

        for p in params:
            if p['type'] == 'combo':
                w = ComboBox(container)
                for opt in p['options']:
                    w.addItem(opt)
                w.setMinimumWidth(110)
                h.addWidget(w)
                self._row_widgets[cmd_code][p['key']] = w
            elif p['type'] == 'double':
                w = QDoubleSpinBox(container)
                w.setRange(p['min'], p['max'])
                w.setValue(p['default'])
                w.setDecimals(1)
                w.setFixedWidth(72)
                h.addWidget(w)
                h.addWidget(QLabel(p['label']))
                self._row_widgets[cmd_code][p['key']] = w
            elif p['type'] == 'spin':
                w = QSpinBox(container)
                w.setRange(p['min'], p['max'])
                w.setValue(p['default'])
                w.setFixedWidth(72)
                h.addWidget(w)
                self._row_widgets[cmd_code][p['key']] = w
            else:
                raise ValueError(
                    f"_build_param_widget: unknown parameter type {p['type']!r}, cmd=0x{cmd_code:02X}")

        h.addStretch()
        return container

    def _build_action_button(self, cmd_def: dict) -> PushButton:
        if cmd_def.get('special') == 'dialog':
            btn = PushButton('Configure...')
            btn.setStyleSheet(
                'PushButton{background:#2a1f3d;color:#cba6f7;border:1px solid #453a5a;border-radius:4px}')
        elif cmd_def['type'] == 'R':
            btn = PushButton('Send')
            btn.setStyleSheet(
                'PushButton{background:#1a3a5c;color:#89b4fa;border:1px solid #2a4a7c;border-radius:4px}')
        else:
            btn = PushButton('Send')
            btn.setStyleSheet(
                'PushButton{background:#3d1a1a;color:#f38ba8;border:1px solid #5a2020;border-radius:4px}')
        btn.setFixedSize(68, 28)
        return btn

    def _build_log(self) -> QWidget:
        frame = QFrame(self)
        frame.setFrameShape(QFrame.NoFrame)
        v = QVBoxLayout(frame)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(4)

        header = QWidget(frame)
        hh = QHBoxLayout(header)
        hh.setContentsMargins(0, 0, 0, 0)
        hh.addWidget(CaptionLabel('📋 CAN Frame Log', frame))
        hh.addStretch()
        clear_btn = PushButton('Clear')
        clear_btn.setFixedWidth(64)
        clear_btn.clicked.connect(self._clear_log)
        hh.addWidget(clear_btn)
        v.addWidget(header)

        self._log_text = TextEdit(frame)
        self._log_text.setReadOnly(True)
        self._log_text.setMinimumHeight(80)
        self._log_text.setFont(QFont('Consolas', 9))
        v.addWidget(self._log_text)

        return frame

    # ─── 占位方法（Task 7 & 8 实现）─────────────────────────
    def _get_target_addr(self, cmd_code: int) -> int:
        cmd_def = next((c for c in COMMANDS if c['cmd'] == cmd_code), None)
        if cmd_def and cmd_def.get('addr_lock') is not None:
            return cmd_def['addr_lock']
        idx = self.addrCombo.currentIndex()
        return _ADDR_VALUES[idx] if idx < len(_ADDR_VALUES) else 0x00

    def _send_command(self, cmd_code: int):
        if cmd_code == 0x0F:
            self._open_0F_dialog()
            return

        dst = self._get_target_addr(cmd_code)
        w = self._row_widgets.get(cmd_code, {})

        READ_DISPATCH = {
            0x01: lambda: reg.REGx_ReadSystemVoltCurrFloat(dst),
            0x02: lambda: reg.REGx_ReadModuleCount(dst),
            0x03: lambda: reg.REGx_ReadModuleVoltCurrFloat(dst),
            0x04: lambda: reg.REGx_ReadStateRequest(dst),
            0x06: lambda: reg.REGx_ReadInputRequest(dst),
            0x08: lambda: reg.REGx_ReadSystemVoltCurrFixed(dst),
            0x09: lambda: reg.REGx_ReadOutputRequest(dst),
            0x0A: lambda: reg.REGx_ReadModuleParams(dst),
            0x0B: lambda: reg.REGx_ReadBarcode(dst),
            0x0C: lambda: reg.REGx_ReadExternalVoltCurr(dst),
        }
        if cmd_code in READ_DISPATCH:
            READ_DISPATCH[cmd_code]()
            return

        if cmd_code == 0x13:
            reg.REGx_SetWalkIn(dst, w['enable'].currentIndex() == 0)
        elif cmd_code == 0x14:
            reg.REGx_SetGreenLED(dst, w['blink'].currentIndex() == 0)
        elif cmd_code == 0x16:
            reg.REGx_SetGroupNumber(dst, w['group'].value())
        elif cmd_code == 0x19:
            reg.REGx_SetSleep(dst, w['sleep'].currentIndex() == 0)
        elif cmd_code == 0x1A:
            if w['power'].currentIndex() == 0:
                reg.REGx_Launch(dst)
            else:
                reg.REGx_CloseOutput(dst)
        elif cmd_code == 0x1B:
            reg.REGx_SetSystemOutput(dst, w['volt'].value(), w['curr'].value())
        elif cmd_code == 0x1C:
            reg.REGx_SetOutput(dst, w['volt'].value(), w['curr'].value())
        elif cmd_code == 0x1F:
            reg.REGx_SetAddressMode(dst, w['mode'].currentIndex() == 1)

    def _read_all(self):
        read_cmds = [0x01, 0x02, 0x03, 0x04, 0x06, 0x08, 0x09, 0x0A, 0x0B, 0x0C]
        for i, cmd_code in enumerate(read_cmds):
            QTimer.singleShot(i * 50, lambda c=cmd_code: self._send_command(c))

    def _refresh_responses(self):
        for cmd_code, formatter in RESPONSE_FORMATTERS.items():
            lbl = self._response_labels.get(cmd_code)
            if lbl is None:
                continue
            try:
                text = formatter(self._ci)
                lbl.setText(text)
            except Exception:
                pass  # 格式化器异常不应中断刷新循环

    def _append_log(self, direction: str, identifier: int, data: bytes, desc: str):
        id_str = (f"{identifier >> 24 & 0xFF:02X} {identifier >> 16 & 0xFF:02X} "
                  f"{identifier >> 8 & 0xFF:02X} {identifier & 0xFF:02X}")
        data_str = ' '.join(f'{b:02X}' for b in data)
        if direction == 'TX':
            color = '#89b4fa'
            arrow = '⬆ TX'
        else:
            color = '#a6e3a1'
            arrow = '⬇ RX'
        line = (f'<span style="color:{color}">{arrow}</span> '
                f'<span style="color:#585b70">{id_str}</span>&nbsp;&nbsp;'
                f'<span style="color:#cdd6f4">{data_str}</span>')
        if desc:
            line += f'&nbsp;&nbsp;<span style="color:#6c7086">{desc}</span>'
        self._log_text.append(line)
        # 限制最多 200 行，避免内存无限增长
        doc = self._log_text.document()
        if doc.blockCount() > 200:
            cursor = self._log_text.textCursor()
            cursor.movePosition(QTextCursor.Start)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
        sb = self._log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log(self):
        self._log_text.clear()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        event.accept()

    def _open_0F_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Comprehensive Settings (0x0F)')
        dlg.setMinimumWidth(360)

        form = QFormLayout(dlg)
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(12)
        form.setContentsMargins(20, 20, 20, 20)

        # 工作模式
        work_combo = ComboBox(dlg)
        for txt in ['DCDC', 'MPPT', 'Constant input voltage']:
            work_combo.addItem(txt)
        form.addRow('Work mode:', work_combo)

        # 降噪模式
        noise_combo = ComboBox(dlg)
        for txt in ['Power priority', 'Noise reduction', 'Silent']:
            noise_combo.addItem(txt)
        form.addRow('Noise mode:', noise_combo)

        # 高低压模式
        volt_combo = ComboBox(dlg)
        for txt in ['Low-voltage mode', 'High-voltage mode', 'Auto switch']:
            volt_combo.addItem(txt)
        form.addRow('Voltage mode:', volt_combo)

        # 液冷温度
        tin_spin = QSpinBox(dlg)
        tin_spin.setRange(-40, 125)
        tin_spin.setValue(25)
        form.addRow('Inlet water temp (℃):', tin_spin)

        tout_spin = QSpinBox(dlg)
        tout_spin.setRange(-40, 125)
        tout_spin.setValue(30)
        form.addRow('Outlet water temp (℃):', tout_spin)

        tamb_spin = QSpinBox(dlg)
        tamb_spin.setRange(-40, 125)
        tamb_spin.setValue(25)
        form.addRow('Ambient temp (℃):', tamb_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, dlg)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec_() != QDialog.Accepted:
            return

        dst = self._get_target_addr(0x0F)
        _VALUES = (0xA0, 0xA1, 0xA2)

        try:
            reg.REGx_SetComprehensive(dst, 0x11, 0x11, _VALUES[work_combo.currentIndex()])
            reg.REGx_SetComprehensive(dst, 0x11, 0x13, _VALUES[noise_combo.currentIndex()])
            reg.REGx_SetComprehensive(dst, 0x11, 0x14, _VALUES[volt_combo.currentIndex()])
            reg.REGx_SetLiquidCoolTemp(dst, tin_spin.value(), tout_spin.value(), tamb_spin.value())
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, 'Send failed', f'Failed to send 0x0F command: {e}')
