import time

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
    REGx_SetSleep, REGx_SetGreenLED, REGx_RegisterListener,
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

        # RX 监听：把 CAN 帧里的组聚合 / 模块 V/I 推到 chart
        REGx_RegisterListener(self._chart_listener)

        # 周期 UI 刷新
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_aggregate_view)
        self._ui_timer.start(200)

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

    def _toggle_can(self):
        if self.btn_can.isChecked():
            if self._can.open_device():
                self.btn_can.setText('关闭 CAN')
                self._set_active_state()
                self._poller = GroupPoller(
                    state=self._state,
                    schedule_fn=lambda d, cb: QTimer.singleShot(d, cb),
                    poll_interval_ms=self._cfg.poll_interval_ms,
                )
                # 立即对当前下拉选择的组发起一次发现
                self._bind_group(self.cbo_group.currentData())
            else:
                self.btn_can.setChecked(False)
        else:
            if self._poller is not None:
                self._poller.stop()
                self._poller.detach()
                self._poller = None
            self._can.close_device()
            self.btn_can.setText('打开 CAN')
            self._set_idle_state()
            self._state.modules.clear()
            self.tbl.setRowCount(0)

    def _on_group_changed(self, idx: int):
        new_group = self.cbo_group.itemData(idx)
        if new_group is None or new_group == self._state.group_id:
            return
        old_group = self._state.group_id
        old_was_on = self._state.is_on

        # 解绑旧组：停止周期，清空模块
        if self._poller is not None:
            self._poller.stop()
        self._state.modules.clear()
        self._state.voltage = 0.0
        self._state.total_current = 0.0
        self.tbl.setRowCount(0)

        if old_was_on:
            InfoBar.warning(
                title='切组提示',
                content=f'已切到组 {new_group}。旧组（组 {old_group}）将在约 10s 后因协议通讯中断保护自动关机。',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=8000,
                parent=self,
            )

        self._bind_group(new_group)

    def _bind_group(self, group_id: int):
        if self._poller is None:
            return
        def on_finish(found):
            self._refresh_aggregate_view()
            self.chart.set_module_options(found)
            if found:
                self._poller.start_cycle()

        self._poller.discover_modules(
            group_id=group_id,
            timeout_ms=self._cfg.group_discover_timeout_ms,
            on_finish=on_finish,
        )

    def _discover_now(self):
        if self._poller is None:
            return
        self._poller.stop()
        self._state.modules.clear()
        self.tbl.setRowCount(0)
        self._bind_group(self._state.group_id)

    def _on_apply_setpoint(self):
        v = self.spn_v.value()
        i = self.spn_i.value()
        REGx_GroupSetOutput(self._state.group_id, v, i)

    def _on_group_power(self, on: bool):
        action = '启动' if on else '关闭'
        m = MessageBox('确认执行', f'是否{action}组 {self._state.group_id} 的输出？', self)
        if m.exec():
            if on:
                REGx_GroupLaunch(self._state.group_id)
            else:
                REGx_GroupClose(self._state.group_id)

    def _on_sleep_toggled(self, addr: int, new_state: bool):
        REGx_SetSleep(addr, new_state)

    def _on_led_toggled(self, addr: int, new_state: bool):
        # 本地 toggle，更新到 ModuleState（协议无读回）
        m = self._state.modules.get(addr)
        if m is not None:
            m.led_blinking = new_state
        REGx_SetGreenLED(addr, new_state)

    def _refresh_aggregate_view(self):
        now = time.time()
        s = self._state
        self.lbl_v.setText(f'{s.voltage:.1f} V' if s.module_count else '— —')
        self.lbl_i.setText(f'{s.total_current:.2f} A' if s.module_count else '— —')
        self.lbl_p.setText(f'{s.total_power/1000:.2f} kW' if s.module_count else '— —')
        if s.module_count:
            temps = [m.temperature for m in s.modules.values()]
            self.lbl_n.setText(f'{s.module_count} / {max(temps)}℃')
        else:
            self.lbl_n.setText('— —')
        self.sw_state.blockSignals(True)
        self.sw_state.setChecked(s.is_on)
        self.sw_state.blockSignals(False)
        # 模块表
        self.tbl.update_modules(self._state, (
            now,
            self._cfg.module_pending_timeout_ms,
            self._cfg.module_offline_timeout_ms,
            self._cfg.module_gone_timeout_ms,
        ))
        # 移除 gone 模块
        gone = [a for a, m in s.modules.items()
                if m.lifecycle(now,
                               self._cfg.module_pending_timeout_ms,
                               self._cfg.module_offline_timeout_ms,
                               self._cfg.module_gone_timeout_ms) == 'gone']
        for a in gone:
            s.modules.pop(a, None)
        # 同步 chart dropdown
        self.chart.set_module_options(s.modules.keys())

    def closeEvent(self, event):
        from REG1K0100A2 import REGx_UnregisterListener
        REGx_UnregisterListener(self._chart_listener)
        if self._poller is not None:
            self._poller.stop()
            self._poller.detach()
        super().closeEvent(event)

    def _chart_listener(self, ev):
        # 组级 0x08 → 整组曲线
        if ev.cmdCode == 0x08 and ev.deviceCode == 0x0B and ev.srcAddr == self._state.group_id:
            d = ev.data
            v = ((d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]) / 1000.0
            i = ((d[4] << 24) | (d[5] << 16) | (d[6] << 8) | d[7]) / 1000.0
            self.chart.push_group(v, i, v * i)
        # 模块级 0x09 → 模块曲线
        elif ev.cmdCode == 0x09 and ev.deviceCode == 0x0A:
            d = ev.data
            v = ((d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]) / 1000.0
            i = ((d[4] << 24) | (d[5] << 16) | (d[6] << 8) | d[7]) / 1000.0
            self.chart.push_module(ev.srcAddr, v, i)
