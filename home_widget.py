from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QSplitter,
                              QVBoxLayout, QWidget)
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, FluentIcon as FIF,
                             IconInfoBadge, InfoBar, InfoBarPosition, InfoLevel,
                             MessageBox, PushButton, StrongBodyLabel, SwitchButton,
                             TitleLabel, ToggleButton, ToolButton, DoubleSpinBox)

from chart_widget import RealtimeChart
from group_state import GroupState
from group_poller import GroupPoller
from module_table import ModuleTable
from REG1K0100A2 import (
    REGx_GroupSetOutput, REGx_GroupLaunch, REGx_GroupClose,
    REGx_SetSleep, REGx_SetGreenLED,
)


class GroupHomeWidget(QFrame):
    def __init__(self, can_device, config, parent=None):
        super().__init__(parent)
        self.setObjectName('GroupHomeWidget')
        self._can = can_device
        self._cfg = config
        self._state = GroupState(group_id=config.default_group)
        self._poller = None  # 延迟到 CAN 打开后创建

        self._build_ui()
        self._wire_signals()
        self._set_idle_state()  # 全部 disabled

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── 顶部条 ──────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        self.btn_can = ToggleButton('打开 CAN', self)
        top.addWidget(self.btn_can)

        top.addWidget(BodyLabel('操作组：', self))
        self.cbo_group = ComboBox(self)
        for g in range(1, self._cfg.group_range_max + 1):
            self.cbo_group.addItem(f'组 {g}', userData=g)
        # 设默认组
        idx = self.cbo_group.findData(self._cfg.default_group)
        if idx >= 0:
            self.cbo_group.setCurrentIndex(idx)
        self.cbo_group.setMinimumWidth(90)
        top.addWidget(self.cbo_group)

        self.btn_refresh = ToolButton(FIF.SYNC, self)
        self.btn_refresh.setToolTip('重新发现组内模块')
        top.addWidget(self.btn_refresh)

        top.addStretch()

        top.addWidget(BodyLabel('CAN1', self))
        self.bdg_can1 = IconInfoBadge.info(FIF.WIFI, parent=self)
        top.addWidget(self.bdg_can1)
        top.addWidget(BodyLabel('CAN2', self))
        self.bdg_can2 = IconInfoBadge.info(FIF.WIFI, parent=self)
        top.addWidget(self.bdg_can2)

        root.addLayout(top)

        # ── 主区：左信息流 + 右控制栏 ──────────────────────
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)

        self._left = QWidget(self)
        left_v = QVBoxLayout(self._left)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(8)
        left_v.addWidget(self._build_aggregate_card())
        left_v.addWidget(self._build_chart(), stretch=2)
        left_v.addWidget(self._build_module_table(), stretch=3)

        self._right = self._build_control_panel()

        self.splitter.addWidget(self._left)
        self.splitter.addWidget(self._right)
        self.splitter.setSizes([700, 300])
        root.addWidget(self.splitter, stretch=1)

    def _build_aggregate_card(self):
        wrap = QWidget(self)
        g = QGridLayout(wrap)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(8)

        def metric(title):
            box = QFrame(wrap)
            box.setObjectName('AggCard')
            box.setStyleSheet('#AggCard{background:#fafbfd;border:1px solid #d6dee9;border-radius:8px;padding:8px;}')
            v = QVBoxLayout(box)
            v.setContentsMargins(10, 6, 10, 6)
            v.setSpacing(2)
            cap = CaptionLabel(title, box)
            val = StrongBodyLabel('— —', box)
            v.addWidget(cap)
            v.addWidget(val)
            return box, val

        c1, self.lbl_v   = metric('组电压')
        c2, self.lbl_i   = metric('组总电流')
        c3, self.lbl_p   = metric('组功率')
        c4, self.lbl_n   = metric('模块数 / 温度')

        g.addWidget(c1, 0, 0)
        g.addWidget(c2, 0, 1)
        g.addWidget(c3, 0, 2)
        g.addWidget(c4, 0, 3)
        return wrap

    def _build_chart(self):
        self.chart = RealtimeChart(
            volt_max=self._cfg.voltage_max,
            curr_max=self._cfg.current_max,
            pwr_max=self._cfg.voltage_max * self._cfg.current_max,
            parent=self,
        )
        return self.chart

    def _build_module_table(self):
        self.tbl = ModuleTable(
            on_sleep_toggle=self._on_sleep_toggled,
            on_led_toggle=self._on_led_toggled,
            parent=self,
        )
        return self.tbl

    def _build_control_panel(self):
        panel = QFrame(self)
        panel.setObjectName('ControlPanel')
        panel.setStyleSheet('#ControlPanel{border:1px solid #d6dee9;border-radius:8px;background:#fafbfd;}')
        v = QVBoxLayout(panel)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        v.addWidget(StrongBodyLabel('组控制', panel))
        v.addWidget(CaptionLabel('设定电压 (V)', panel))
        self.spn_v = DoubleSpinBox(panel)
        self.spn_v.setRange(self._cfg.voltage_min, self._cfg.voltage_max)
        self.spn_v.setDecimals(1)
        self.spn_v.setValue(min(320.0, self._cfg.voltage_max))
        v.addWidget(self.spn_v)

        v.addWidget(CaptionLabel('设定组总电流 (A)', panel))
        self.spn_i = DoubleSpinBox(panel)
        self.spn_i.setRange(0.0, self._cfg.current_max)
        self.spn_i.setDecimals(2)
        self.spn_i.setValue(min(10.0, self._cfg.current_max))
        v.addWidget(self.spn_i)

        self.btn_apply = PushButton('设定下发 (0x1B)', panel)
        v.addWidget(self.btn_apply)

        v.addSpacing(8)
        v.addWidget(CaptionLabel('组开关机 (0x1A)', panel))
        self.btn_open  = PushButton('启动组输出', panel)
        self.btn_close = PushButton('关闭组输出', panel)
        v.addWidget(self.btn_open)
        v.addWidget(self.btn_close)

        v.addSpacing(8)
        v.addWidget(CaptionLabel('组当前状态', panel))
        self.sw_state = SwitchButton(panel)
        self.sw_state.setOnText('已开机')
        self.sw_state.setOffText('已关机')
        self.sw_state.setEnabled(False)
        v.addWidget(self.sw_state)

        v.addStretch()
        return panel

    def _wire_signals(self):
        self.btn_can.clicked.connect(self._toggle_can)
        self.cbo_group.currentIndexChanged.connect(self._on_group_changed)
        self.btn_refresh.clicked.connect(self._discover_now)
        self.btn_apply.clicked.connect(self._on_apply_setpoint)
        self.btn_open.clicked.connect(lambda: self._on_group_power(True))
        self.btn_close.clicked.connect(lambda: self._on_group_power(False))

    def _set_idle_state(self):
        self.cbo_group.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.spn_v.setEnabled(False)
        self.spn_i.setEnabled(False)
        self.btn_apply.setEnabled(False)
        self.btn_open.setEnabled(False)
        self.btn_close.setEnabled(False)

    def _set_active_state(self):
        self.cbo_group.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self.spn_v.setEnabled(True)
        self.spn_i.setEnabled(True)
        self.btn_apply.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.btn_close.setEnabled(True)

    # ── 占位：下一任务实现 ───────────────────────────────────
    def _toggle_can(self): pass
    def _on_group_changed(self, idx: int): pass
    def _discover_now(self): pass
    def _on_apply_setpoint(self): pass
    def _on_group_power(self, on: bool): pass
    def _on_sleep_toggled(self, addr: int, new_state: bool): pass
    def _on_led_toggled(self, addr: int, new_state: bool): pass
