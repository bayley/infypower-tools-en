"""
实时双Y轴折线/面积组合图
  左轴：电压(V) + 电流(A)  ← 分别归一化后共享同一显示区域
  右轴：功率(W)             ← 独立刻度，面积填充
"""
from collections import deque

from PyQt5.QtCore import Qt, QRect, QRectF, QPointF
from PyQt5.QtGui import (QColor, QFont, QLinearGradient, QPainter,
                          QPainterPath, QPen, QBrush)
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSizePolicy,
                              QVBoxLayout, QWidget)
from qfluentwidgets import (CaptionLabel, CheckBox, ComboBox, FluentIcon as FIF,
                             StrongBodyLabel, ToolButton, isDarkTheme)

# ─── 配色（Catppuccin Mocha × Fluent）─────────────────────────
_VOLT_HEX = '#60a5fa'   # 蓝
_CURR_HEX = '#c084fc'   # 紫
_PWR_HEX  = '#fb923c'   # 橙


def _fmt_y(val: float, unit: str) -> str:
    """格式化 Y 轴刻度标签。"""
    if unit == 'W' and val >= 1000:
        return f'{val/1000:.0f}k'
    if val == int(val):
        return str(int(val))
    return f'{val:.1f}'


class _ChartCanvas(QWidget):
    """
    双Y轴实时绘图区：
      - 左轴：电压 / 电流（各自归一化到自身最大值，共享 0-100% 高度）
      - 右轴：功率（同样归一化，刻度独立标注）
      - 功率绘为渐变面积 + 轮廓线
      - 电压 / 电流绘为折线
    """

    _LM  = 52   # 左边距（左Y轴刻度）
    _RM  = 52   # 右边距（右Y轴刻度）
    _TM  = 28   # 上边距：容纳轴单位标注 + 顶部刻度文字，避免重叠
    _BM  = 30   # 下边距（X轴时间标注）
    _TICKS = 4  # 网格格数（5条线）

    def __init__(self, chart: 'RealtimeChart', parent=None):
        super().__init__(parent)
        self._c = chart
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ── 绘制入口 ─────────────────────────────────────────────
    def paintEvent(self, _ev):
        dark = isDarkTheme()
        bg        = QColor(22,  22,  38)  if dark else QColor(247, 247, 252)
        grid_c    = QColor(48,  48,  75)  if dark else QColor(215, 215, 230)
        axis_l_c  = QColor(148, 186, 252) if dark else QColor( 59, 130, 246)  # 左轴标 蓝
        axis_r_c  = QColor(253, 186, 116) if dark else QColor(234, 100,  10)  # 右轴标 橙
        tick_c    = QColor(110, 110, 155) if dark else QColor(140, 140, 170)  # 时间标

        W, H = self.width(), self.height()
        lm, rm, tm, bm = self._LM, self._RM, self._TM, self._BM
        pw = W - lm - rm
        ph = H - tm - bm
        px, py = lm, tm

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # ── 背景 + 圆角边框 ─────────────────────────────────
        painter.fillRect(self.rect(), bg)
        border = QColor(55, 55, 85) if dark else QColor(200, 200, 220)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(QRectF(.5, .5, W - 1, H - 1), 6, 6)

        font8 = QFont('Consolas', 8)
        painter.setFont(font8)

        c = self._c

        # ── 水平网格 + 左/右Y轴刻度 ─────────────────────────
        for i in range(self._TICKS + 1):
            frac = i / self._TICKS
            y = int(py + ph * (1.0 - frac))

            # 网格线
            painter.setPen(QPen(grid_c, 1, Qt.DashLine))
            painter.drawLine(px, y, px + pw, y)

            # 左轴标（电压）
            v_lbl = _fmt_y(c._volt_max * frac, 'V') + 'V'
            painter.setPen(axis_l_c)
            painter.drawText(0, y - 7, lm - 5, 14,
                             Qt.AlignRight | Qt.AlignVCenter, v_lbl)

            # 右轴标（功率）
            p_lbl = _fmt_y(c._pwr_max * frac, 'W') + ('W' if c._pwr_max < 1000 else '')
            painter.setPen(axis_r_c)
            painter.drawText(W - rm + 4, y - 7, rm - 4, 14,
                             Qt.AlignLeft | Qt.AlignVCenter, p_lbl)

        # ── X轴时间标注 ──────────────────────────────────────
        ws = c.WINDOW_SECONDS
        for frac, lbl in [(0.0, f'-{ws}s'), (0.5, f'-{ws//2}s'), (1.0, '0s')]:
            x = px + int(frac * pw)
            painter.setPen(tick_c)
            painter.drawText(x - 22, py + ph + 5, 44, 20,
                             Qt.AlignCenter, lbl)

        # ── 轴单位标注（位于上边距顶部，避开顶端刻度文字）────
        font9b = QFont('Microsoft YaHei', 8)
        font9b.setBold(True)
        painter.setFont(font9b)
        painter.setPen(axis_l_c)
        painter.drawText(0, 2, lm, 12, Qt.AlignCenter, 'V / A')
        painter.setPen(axis_r_c)
        painter.drawText(W - rm, 2, rm, 12, Qt.AlignCenter, 'W')
        painter.setFont(font8)

        # ── 剪裁到绘图区 ─────────────────────────────────────
        painter.setClipRect(QRect(px, py, pw, ph))

        # ── 功率：渐变面积填充 + 轮廓线 ─────────────────────
        if c._show_pwr and len(c._pwr_data) >= 2:
            pts_pwr = list(c._pwr_data)
            path_fill = QPainterPath()
            path_line = QPainterPath()
            n   = len(pts_pwr)
            cap = c._max_points
            first = True
            x0 = y_base = 0
            for j, val in enumerate(pts_pwr):
                xf = (cap - n + j) / max(cap - 1, 1)
                yf = min(val / c._pwr_max, 1.0) if c._pwr_max > 0 else 0.0
                xp = px + xf * pw
                yp = py + ph * (1.0 - yf)
                if first:
                    path_fill.moveTo(xp, py + ph)   # 起点在底部
                    path_fill.lineTo(xp, yp)
                    path_line.moveTo(xp, yp)
                    x0 = xp
                    first = False
                else:
                    path_fill.lineTo(xp, yp)
                    path_line.lineTo(xp, yp)
                x_last = xp

            path_fill.lineTo(x_last, py + ph)    # 终点回到底部
            path_fill.closeSubpath()

            # 渐变填充
            grad = QLinearGradient(QPointF(0, py), QPointF(0, py + ph))
            grad.setColorAt(0.0, QColor(251, 146, 60, 130))
            grad.setColorAt(1.0, QColor(251, 146, 60,  15))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(grad))
            painter.drawPath(path_fill)

            # 轮廓线
            painter.setPen(QPen(QColor(_PWR_HEX), 2,
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path_line)

        # ── 电压折线 ─────────────────────────────────────────
        self._draw_line(painter, c._volt_data, c._show_volt,
                        _VOLT_HEX, c._volt_max, px, py, pw, ph, c._max_points)

        # ── 电流折线 ─────────────────────────────────────────
        self._draw_line(painter, c._curr_data, c._show_curr,
                        _CURR_HEX, c._curr_max, px, py, pw, ph, c._max_points)

        # ── 暂停遮罩 ─────────────────────────────────────────
        if c._paused:
            painter.setClipping(False)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 60))
            tag_w, tag_h = 90, 26
            tag_x = W - rm - tag_w - 4
            tag_y = py + 6
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(251, 146, 60, 200))
            painter.drawRoundedRect(QRectF(tag_x, tag_y, tag_w, tag_h), 4, 4)
            font_tag = QFont('Microsoft YaHei', 9)
            font_tag.setBold(True)
            painter.setFont(font_tag)
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(int(tag_x), int(tag_y), tag_w, tag_h,
                             Qt.AlignCenter, '⏸  Paused')

        painter.end()

    # ── 辅助：绘制普通折线 ───────────────────────────────────
    @staticmethod
    def _draw_line(p: QPainter, data, visible: bool, color_hex: str,
                   y_max: float, px, py, pw, ph, cap):
        if not visible or len(data) < 2:
            return
        pts = list(data)
        n   = len(pts)
        path = QPainterPath()
        first = True
        for j, val in enumerate(pts):
            xf = (cap - n + j) / max(cap - 1, 1)
            yf = min(val / y_max, 1.0) if y_max > 0 else 0.0
            xp = px + xf * pw
            yp = py + ph * (1.0 - yf)
            if first:
                path.moveTo(xp, yp)
                first = False
            else:
                path.lineTo(xp, yp)
        p.setPen(QPen(QColor(color_hex), 2,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


class _LegendItem(QWidget):
    """彩色线段指示符 + CheckBox + 当前值。"""

    def __init__(self, label: str, axis_tag: str, color_hex: str,
                 is_area: bool = False, parent=None):
        super().__init__(parent)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)

        # 颜色指示：面积用矩形块，线条用细线
        indicator = QLabel()
        if is_area:
            indicator.setFixedSize(14, 10)
            indicator.setStyleSheet(
                f'background:{color_hex};border-radius:2px;opacity:0.8;')
        else:
            indicator.setFixedSize(18, 3)
            indicator.setStyleSheet(
                f'background:{color_hex};border-radius:1px;')

        self._cb = CheckBox(f'{label} {axis_tag}')
        self._cb.setChecked(True)

        h.addWidget(indicator)
        h.addWidget(self._cb)

    @property
    def checked(self) -> bool:
        return self._cb.isChecked()

    def set_value(self, text: str):
        base = self._cb.text().split('  ')[0]
        self._cb.setText(f'{base}  {text}')

    def connect_toggle(self, slot):
        self._cb.stateChanged.connect(slot)


class RealtimeChart(QFrame):
    """
    双Y轴实时曲线图。
      push(volt, curr, power) 追加数据；固定 WINDOW_SECONDS 时间窗口。
    """

    WINDOW_SECONDS = 60
    _PUSH_MS = 150

    def __init__(self, volt_max=1000.0, curr_max=100.0, pwr_max=30000.0,
                 parent=None):
        super().__init__(parent)
        cap = max(int(self.WINDOW_SECONDS * 1000 / self._PUSH_MS), 2)
        self._max_points = cap
        self._volt_data  = deque(maxlen=cap)
        self._curr_data  = deque(maxlen=cap)
        self._pwr_data   = deque(maxlen=cap)
        self._volt_max   = float(volt_max) if volt_max  > 0 else 1000.0
        self._curr_max   = float(curr_max) if curr_max  > 0 else 100.0
        self._pwr_max    = float(pwr_max)  if pwr_max   > 0 else 30000.0
        self._show_volt  = True
        self._show_curr  = True
        self._show_pwr   = True
        self._paused     = False
        self.setFrameShape(QFrame.NoFrame)
        self._target = 'group'   # 'group' or int (module addr)
        self._volt_max_single = float(volt_max) if volt_max > 0 else 1000.0
        self._curr_max_single = float(curr_max) if curr_max > 0 else 100.0
        self._module_count = 0   # N-dynamic, updated by set_module_options
        self._build_ui()

    # ── 公共接口 ─────────────────────────────────────────────
    def push(self, volt: float, curr: float, power: float):
        if self._paused:
            return
        self._volt_data.append(float(volt))
        self._curr_data.append(float(curr))
        self._pwr_data.append(float(power))
        self._canvas.update()
        self._volt_leg.set_value(f'{volt:.1f} V')
        self._curr_leg.set_value(f'{curr:.2f} A')
        self._pwr_leg.set_value(f'{power:.0f} W')

    def set_target(self, target):
        """target = 'group' or int (module addr)；切换时清空缓冲、解除暂停、根据模块数动态设定量程。"""
        self._target = target
        self._volt_data.clear()
        self._curr_data.clear()
        self._pwr_data.clear()
        self._paused = False
        self._pause_btn.setIcon(FIF.PAUSE)
        n = max(self._module_count, 1)
        self._volt_max = self._volt_max_single
        if target == 'group':
            # 组总电流/功率 = 单模块 × N；电压不随 N 变
            self._curr_max = self._curr_max_single * n
            self._pwr_max  = self._volt_max_single * self._curr_max_single * n
        else:
            self._curr_max = self._curr_max_single
            self._pwr_max  = self._volt_max_single * self._curr_max_single
        self._canvas.update()

    def set_module_options(self, addrs):
        """从外部更新 dropdown 选项，并同步模块数到 N-动态量程。若当前选中的模块消失则回退到整组视图（完整重置）。"""
        cur = self._target_combo.currentText()
        addrs_sorted = sorted(addrs)
        self._module_count = len(addrs_sorted)
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        self._target_combo.addItem('Whole group')
        for a in addrs_sorted:
            self._target_combo.addItem(f'Module 0x{a:02X}')
        idx = self._target_combo.findText(cur)
        if idx >= 0:
            self._target_combo.setCurrentIndex(idx)
            self._target_combo.blockSignals(False)
            # 当前选中仍存在：如果是 'group'，N 变了所以量程需要重算
            if self._target == 'group':
                self.set_target('group')
        else:
            # 原选中的模块已不在列表中 → 回退到整组 + 完整重置
            self._target_combo.setCurrentIndex(0)
            self._target_combo.blockSignals(False)
            self.set_target('group')

    def push_group(self, volt: float, curr: float, power: float):
        if self._target == 'group':
            self.push(volt, curr, power)

    def push_module(self, addr: int, volt: float, curr: float):
        if self._target == addr:
            self.push(volt, curr, volt * curr)

    def _on_target_changed(self, idx: int):
        if idx <= 0:
            self.set_target('group')
            return
        text = self._target_combo.currentText()
        # 'Module 0x05' → 5
        try:
            addr = int(text.split('0x')[1], 16)
            self.set_target(addr)
        except (IndexError, ValueError):
            self.set_target('group')

    # ── 构建 UI ──────────────────────────────────────────────
    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 8, 10, 8)
        vbox.setSpacing(6)

        # 标题行
        hdr = QHBoxLayout()
        hdr.addWidget(StrongBodyLabel('Real-time Chart'))
        hdr.addStretch()
        hdr.addWidget(CaptionLabel(f'Window {self.WINDOW_SECONDS} s'))

        self._target_combo = ComboBox()
        self._target_combo.addItem('Whole group')
        self._target_combo.setMinimumWidth(110)
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        hdr.addWidget(self._target_combo)

        self._pause_btn = ToolButton(FIF.PAUSE, self)
        self._pause_btn.setToolTip('Pause / Resume')
        self._pause_btn.setFixedSize(28, 28)
        self._pause_btn.clicked.connect(self._toggle_pause)
        hdr.addWidget(self._pause_btn)

        vbox.addLayout(hdr)

        # 图例行
        self._volt_leg = _LegendItem('Voltage', '(left)', _VOLT_HEX, is_area=False)
        self._curr_leg = _LegendItem('Current', '(left)', _CURR_HEX, is_area=False)
        self._pwr_leg  = _LegendItem('Power', '(right)', _PWR_HEX,  is_area=True)

        self._volt_leg.connect_toggle(
            lambda s: self._toggle('volt', s == Qt.Checked))
        self._curr_leg.connect_toggle(
            lambda s: self._toggle('curr', s == Qt.Checked))
        self._pwr_leg.connect_toggle(
            lambda s: self._toggle('pwr',  s == Qt.Checked))

        legend = QHBoxLayout()
        legend.setSpacing(20)
        legend.addWidget(self._volt_leg)
        legend.addWidget(self._curr_leg)
        legend.addWidget(self._pwr_leg)
        legend.addStretch()
        vbox.addLayout(legend)

        # 画布
        self._canvas = _ChartCanvas(self, self)
        vbox.addWidget(self._canvas, stretch=1)

    def _toggle(self, series: str, show: bool):
        if series == 'volt':
            self._show_volt = show
        elif series == 'curr':
            self._show_curr = show
        elif series == 'pwr':
            self._show_pwr = show
        self._canvas.update()

    def _toggle_pause(self):
        self._paused = not self._paused
        self._pause_btn.setIcon(FIF.PLAY if self._paused else FIF.PAUSE)
        self._canvas.update()  # 刷新以显示/隐藏暂停提示
