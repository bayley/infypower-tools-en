# 主页面组级控制改造 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把主页面从"硬编码控制模块 0x00"改造为"组级控制台 + 可切换的活跃组"，引入组级心跳轮询、模块发现/离线判定、模块表带 💤/💡 操作、实时曲线 target 切换、组开关机/V·I 设定。

**Architecture:** 新增 `group_state.py`（数据模型）、`group_poller.py`（链式调度）、`home_widget.py`（新主页 widget），重构 `REG1K0100A2.py`（`device_code` 参数化 + RX 监听器分发）和 `chart_widget.py`（RX 驱动 + target 切换）。旧的 `CANControllerInfo` 路径**完整保留**给 `manual_widget.py`，新路径并行可关。

**Tech Stack:** PyQt5, qfluentwidgets, dataclasses, pytest, ctypes (HDL_CAN)

**Spec:** `docs/superpowers/specs/2026-04-24-group-level-main-page-design.md`

---

## File Structure

| 文件 | 类型 | 责任 |
|---|---|---|
| `config_manager.py` | 修改 | `AppConfig` 加 7 个新字段，`ConfigManager.load` 用 `data.get` fallback |
| `group_state.py` | 新建 | `ModuleState` + `GroupState` 数据类 + lifecycle/alarms 派生 |
| `group_poller.py` | 新建 | `GroupPoller` 链式调度 + 模块发现 + 离线状态机 |
| `REG1K0100A2.py` | 修改 | 所有发送函数加 `device_code=SINGLE` 参数；新增 5 个组级 helper；`REGx_CAN_ReceviceCallback` 重构为 `RxEvent` + 监听器分发；旧 `REGx_Poll` 改名 `REGx_PollLegacy` |
| `chart_widget.py` | 修改 | 加 `set_target` / `push_group` / `push_module`；加 target dropdown；图例区可选模块；保留暂停 |
| `home_widget.py` | 新建 | 新主页 widget（`GroupHomeWidget`），构建 §3 所示布局，组合 `GroupPoller` + `GroupState` + chart + 控制面板 |
| `main.py` | 修改 | `Window` 用 `GroupHomeWidget` 替换旧 `MainWindow`；旧 `MainWindow` 类删除 |
| `tests/test_config_manager.py` | 修改 | 扩展 fallback 行为测试 |
| `tests/test_group_state.py` | 新建 | `ModuleState.lifecycle` / `alarms` / `GroupState.is_on/total_power` |
| `tests/test_reg1k_group_helpers.py` | 新建 | mock CAN 设备，断言组级命令 Identifier 编码 |
| `tests/test_group_poller.py` | 新建 | mock CAN 设备 + 注入响应序列，验证调度与生命周期 |

`FluentQtTest.py` 和 `FluentQtTest.ui` 改造后不再被使用，但**本计划不删除**（避免破坏 manual_widget 间接依赖且节省风险）。后续可单独清理。

---

## Conventions

- 提交信息按现有约定：`feat:` / `refactor:` / `test:` / `fix:` 前缀
- 中文文案保持简洁，与现有 UI 风格一致
- 测试统一用 `pytest`，文件首行 `sys.path.insert(0, ...)` 与 `tests/test_config_manager.py` 一致
- 不写 docstring/注释除非有非显然的 WHY；方法名足够自描述
- 工作目录 `C:\Users\liuyu\Desktop\WorkPlace\INFY_POWER`，所有 `pytest` 命令在此目录运行
- 当前分支 `feat/group-control-main`

---

## Task 1: 扩展 AppConfig 加入 7 个新字段

**Files:**
- Modify: `config_manager.py`
- Test: `tests/test_config_manager.py`

- [ ] **Step 1: 写失败测试 — 默认值**

在 `tests/test_config_manager.py` 末尾追加：

```python
def test_load_returns_new_default_fields(tmp_path):
    from config_manager import ConfigManager
    cfg_path = tmp_path / "config.json"
    mgr = ConfigManager(config_path=str(cfg_path))
    result = mgr.load()

    assert result.default_group == 1
    assert result.group_range_max == 15
    assert result.module_pending_timeout_ms == 3000
    assert result.module_offline_timeout_ms == 10000
    assert result.module_gone_timeout_ms == 30000
    assert result.poll_interval_ms == 100
    assert result.group_discover_timeout_ms == 600


def test_load_falls_back_when_old_config_missing_new_fields(tmp_path):
    import json
    from config_manager import ConfigManager
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "device_name": "old",
        "voltage_max": 800.0,
        "voltage_min": 100.0,
        "current_max": 50.0,
        "current_min": 0.0,
    }), encoding='utf-8')
    mgr = ConfigManager(config_path=str(cfg_path))
    result = mgr.load()

    assert result.device_name == "old"
    assert result.default_group == 1
    assert result.poll_interval_ms == 100
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_config_manager.py -v
```
Expected: 2 个 new test FAIL (AttributeError: 'AppConfig' object has no attribute 'default_group')

- [ ] **Step 3: 修改 `AppConfig` + `ConfigManager.load`**

`config_manager.py` 完整内容替换：

```python
import json
import os
from dataclasses import dataclass, asdict


@dataclass
class AppConfig:
    device_name: str = "REG1K0100A2 充电模块"
    voltage_max: float = 1000.0
    voltage_min: float = 150.0
    current_max: float = 100.0
    current_min: float = 0.0
    default_group: int = 1
    group_range_max: int = 15
    module_pending_timeout_ms: int = 3000
    module_offline_timeout_ms: int = 10000
    module_gone_timeout_ms: int = 30000
    poll_interval_ms: int = 100
    group_discover_timeout_ms: int = 600


class ConfigManager:
    def __init__(self, config_path: str = "config.json"):
        self._path = config_path

    def load(self) -> AppConfig:
        if not os.path.exists(self._path):
            default = AppConfig()
            try:
                with open(self._path, 'w', encoding='utf-8') as f:
                    json.dump(asdict(default), f, ensure_ascii=False, indent=2)
            except OSError:
                pass
            return default
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            d = AppConfig()
            return AppConfig(
                device_name=data.get("device_name", d.device_name),
                voltage_max=float(data.get("voltage_max", d.voltage_max)),
                voltage_min=float(data.get("voltage_min", d.voltage_min)),
                current_max=float(data.get("current_max", d.current_max)),
                current_min=float(data.get("current_min", d.current_min)),
                default_group=int(data.get("default_group", d.default_group)),
                group_range_max=int(data.get("group_range_max", d.group_range_max)),
                module_pending_timeout_ms=int(data.get("module_pending_timeout_ms", d.module_pending_timeout_ms)),
                module_offline_timeout_ms=int(data.get("module_offline_timeout_ms", d.module_offline_timeout_ms)),
                module_gone_timeout_ms=int(data.get("module_gone_timeout_ms", d.module_gone_timeout_ms)),
                poll_interval_ms=int(data.get("poll_interval_ms", d.poll_interval_ms)),
                group_discover_timeout_ms=int(data.get("group_discover_timeout_ms", d.group_discover_timeout_ms)),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return AppConfig()
```

- [ ] **Step 4: 运行确认所有 5 个测试通过**

```bash
pytest tests/test_config_manager.py -v
```
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add config_manager.py tests/test_config_manager.py
git commit -m "feat(config): 新增 default_group/超时阈值/轮询周期 字段，向后兼容旧 config.json"
```

---

## Task 2: 新建 ModuleState 数据类与 lifecycle 状态机

**Files:**
- Create: `group_state.py`
- Create: `tests/test_group_state.py`

- [ ] **Step 1: 写失败测试 — ModuleState lifecycle**

新建 `tests/test_group_state.py`：

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_module_lifecycle_online_when_recently_seen():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=100.5, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'online'


def test_module_lifecycle_pending_after_pending_threshold():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=104.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'pending'


def test_module_lifecycle_offline_after_offline_threshold():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=115.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'offline'


def test_module_lifecycle_gone_after_gone_threshold():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, last_seen=100.0)
    assert m.lifecycle(now=140.0, pending_ms=3000, offline_ms=10000, gone_ms=30000) == 'gone'
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_group_state.py -v
```
Expected: ModuleNotFoundError: No module named 'group_state'

- [ ] **Step 3: 新建 `group_state.py` 实现 ModuleState 基础**

```python
from dataclasses import dataclass, field


@dataclass
class ModuleState:
    addr: int
    voltage: float = 0.0
    current: float = 0.0
    temperature: int = 0
    status0: int = 0
    status1: int = 0
    status2: int = 0
    status3: int = 0
    group_id_reported: int = 0
    led_blinking: bool = False
    last_seen: float = 0.0

    def lifecycle(self, now: float, pending_ms: int,
                  offline_ms: int, gone_ms: int) -> str:
        elapsed_ms = (now - self.last_seen) * 1000.0
        if elapsed_ms < pending_ms:
            return 'online'
        if elapsed_ms < offline_ms:
            return 'pending'
        if elapsed_ms < gone_ms:
            return 'offline'
        return 'gone'

    @property
    def sleeping(self) -> bool:
        return bool(self.status0 & (1 << 4))
```

- [ ] **Step 4: 运行确认 4 个测试通过**

```bash
pytest tests/test_group_state.py -v
```
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add group_state.py tests/test_group_state.py
git commit -m "feat(group_state): 新建 ModuleState 数据类与 4 态 lifecycle"
```

---

## Task 3: ModuleState.alarms 解码状态表 0~3

**Files:**
- Modify: `group_state.py`
- Modify: `tests/test_group_state.py`

参考协议 §2.4 状态表（spec 文末已列出）：
- status0 bit3=输入或母线异常, bit4=模块休眠, bit5=模块放电异常, bit6=风道不畅, bit7=通讯中断告警
- status1 bit1=模块故障告警, bit2=模块保护告警, bit3=风扇故障告警, bit4=过温告警, bit5=输出过压告警, bit6=Walk-In 使能, bit7=模块通信中断告警
- status2 bit1=模块ID重复, bit2=模块严重不均流, bit3=三相输入缺相告警, bit4=三相输入不平衡告警, bit5=输入欠压告警, bit6=输入过压告警, bit7=PFC 关机
- status3 高低压模式标识，不视为告警，不在 alarms 列表中

> 注意：协议状态表 0 bit2 是"模块内部通信故障"，bit1 没有定义；为简化只解码协议明确写出含义的位。`sleeping` 是状态而非告警，不进 alarms 列表。

- [ ] **Step 1: 写失败测试 — alarms 解码**

在 `tests/test_group_state.py` 末尾追加：

```python
def test_module_alarms_empty_when_no_bits_set():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status0=0, status1=0, status2=0, status3=0)
    assert m.alarms == []


def test_module_alarms_decodes_status0_bits():
    from group_state import ModuleState
    m = ModuleState(addr=0x00,
                    status0=(1 << 7) | (1 << 6) | (1 << 5) | (1 << 3))
    s = m.alarms
    assert "通讯中断告警" in s
    assert "风道不畅" in s
    assert "模块放电异常" in s
    assert "输入或母线异常" in s


def test_module_alarms_skips_sleeping_bit():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status0=(1 << 4))
    assert m.alarms == []
    assert m.sleeping is True


def test_module_alarms_decodes_status1_bits():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status1=(1 << 4) | (1 << 1))
    assert "过温告警" in m.alarms
    assert "模块故障告警" in m.alarms


def test_module_alarms_decodes_status2_bits():
    from group_state import ModuleState
    m = ModuleState(addr=0x00, status2=(1 << 7) | (1 << 6))
    assert "模块PFC侧处于关机状态" in m.alarms
    assert "输入过压告警" in m.alarms
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_group_state.py -v
```
Expected: AttributeError or 5 alarms tests fail

- [ ] **Step 3: 在 ModuleState 实现 alarms property**

修改 `group_state.py`，在 `ModuleState` 的 `sleeping` property 后追加：

```python
    @property
    def alarms(self) -> list:
        out = []
        s0, s1, s2 = self.status0, self.status1, self.status2

        if s0 & (1 << 7): out.append("通讯中断告警")
        if s0 & (1 << 6): out.append("风道不畅")
        if s0 & (1 << 5): out.append("模块放电异常")
        if s0 & (1 << 3): out.append("输入或母线异常")

        if s1 & (1 << 7): out.append("模块通信中断告警")
        if s1 & (1 << 6): out.append("Walk-In 使能")
        if s1 & (1 << 5): out.append("输出过压告警")
        if s1 & (1 << 4): out.append("过温告警")
        if s1 & (1 << 3): out.append("风扇故障告警")
        if s1 & (1 << 2): out.append("模块保护告警")
        if s1 & (1 << 1): out.append("模块故障告警")

        if s2 & (1 << 7): out.append("模块PFC侧处于关机状态")
        if s2 & (1 << 6): out.append("输入过压告警")
        if s2 & (1 << 5): out.append("输入欠压告警")
        if s2 & (1 << 4): out.append("三相输入不平衡告警")
        if s2 & (1 << 3): out.append("三相输入缺相告警")
        if s2 & (1 << 2): out.append("模块严重不均流")
        if s2 & (1 << 1): out.append("模块ID重复")

        return out
```

- [ ] **Step 4: 运行确认所有测试通过**

```bash
pytest tests/test_group_state.py -v
```
Expected: 9 passed

- [ ] **Step 5: 提交**

```bash
git add group_state.py tests/test_group_state.py
git commit -m "feat(group_state): ModuleState.alarms 解码协议状态表 0/1/2 全部已定义位"
```

---

## Task 4: 新建 GroupState 聚合数据类

**Files:**
- Modify: `group_state.py`
- Modify: `tests/test_group_state.py`

- [ ] **Step 1: 写失败测试 — GroupState**

追加到 `tests/test_group_state.py`：

```python
def test_group_state_total_power_is_voltage_times_current():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=500.0, total_current=20.0)
    assert g.total_power == 10000.0


def test_group_state_total_power_is_zero_when_voltage_zero():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=0.0, total_current=20.0)
    assert g.total_power == 0.0


def test_group_state_is_on_when_voltage_above_threshold():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=10.0)
    assert g.is_on is True


def test_group_state_is_off_when_voltage_below_threshold():
    from group_state import GroupState
    g = GroupState(group_id=1, voltage=2.0)
    assert g.is_on is False


def test_group_state_modules_starts_empty():
    from group_state import GroupState
    g = GroupState(group_id=2)
    assert g.modules == {}
    assert g.module_count == 0


def test_group_state_module_count_reflects_dict():
    from group_state import GroupState, ModuleState
    g = GroupState(group_id=2)
    g.modules[0x00] = ModuleState(addr=0x00)
    g.modules[0x01] = ModuleState(addr=0x01)
    assert g.module_count == 2
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_group_state.py -v
```
Expected: ImportError or 6 GroupState tests fail

- [ ] **Step 3: 实现 GroupState**

在 `group_state.py` 末尾追加：

```python
@dataclass
class GroupState:
    group_id: int
    voltage: float = 0.0
    total_current: float = 0.0
    modules: dict = field(default_factory=dict)

    @property
    def total_power(self) -> float:
        return self.voltage * self.total_current

    @property
    def is_on(self) -> bool:
        return self.voltage > 5.0

    @property
    def module_count(self) -> int:
        return len(self.modules)
```

- [ ] **Step 4: 运行确认所有测试通过**

```bash
pytest tests/test_group_state.py -v
```
Expected: 15 passed

- [ ] **Step 5: 提交**

```bash
git add group_state.py tests/test_group_state.py
git commit -m "feat(group_state): GroupState 数据类聚合 voltage/current/modules"
```

---

## Task 5: REG1K0100A2 — 所有发送函数加 device_code 参数

**Files:**
- Modify: `REG1K0100A2.py`

> **背景**：现有所有 `REGx_*` 发送函数硬编码 `request.deviceCode = REGx_DEVICE_CODE.SINGLE`。现在改为可选参数，默认 `SINGLE`，向后兼容。
> 影响函数清单：`REGx_ReadStateRequest` / `REGx_ReadInputRequest` / `REGx_ReadOutputRequest` / `REGx_ReadOutputSetRequest` / `REGx_ReadSystemVoltCurrFloat` / `REGx_ReadModuleCount` / `REGx_ReadModuleVoltCurrFloat` / `REGx_ReadSystemVoltCurrFixed` / `REGx_ReadModuleParams` / `REGx_ReadBarcode` / `REGx_ReadExternalVoltCurr` / `REGx_SetOutput` / `REGx_Launch` / `REGx_CloseOutput` / `REGx_SetComprehensive` / `REGx_SetWalkIn` / `REGx_SetGreenLED` / `REGx_SetGroupNumber` / `REGx_SetSleep` / `REGx_SetSystemOutput` / `REGx_SetAddressMode` / `REGx_SetLiquidCoolTemp`

- [ ] **Step 1: 在 `REG1K0100A2.py` 给每个发送函数加可选 device_code 参数**

对每个上述函数：
- 在签名末尾追加 `, device_code=REGx_DEVICE_CODE.SINGLE`
- 把 `request.deviceCode = REGx_DEVICE_CODE.SINGLE` 改为 `request.deviceCode = device_code`

例如 `REGx_SetOutput`：

```python
def REGx_SetOutput(dstAddr, volt, curr, device_code=REGx_DEVICE_CODE.SINGLE):
    volt = max(REGx_OUTPUT_DC_VOLT_MIN, min(volt, REGx_OUTPUT_DC_VOLT_MAX))
    curr = max(REGx_OUTPUT_DC_CURR_MIN, min(curr, REGx_OUTPUT_DC_CURR_MAX))

    request = REGx_Msg_t()
    request.errorCode = REGx_ERROR_CODE.NORMAL
    request.deviceCode = device_code
    request.cmdCode = 0x1C
    request.dstAddr = dstAddr
    request.srcAddr = REGx_MASTER_ADDR
    voltSetValue = int(volt * 1000)
    currSetValue = int(curr * 1000)
    request.data[0] = (voltSetValue >> 24) & 0xFF
    request.data[1] = (voltSetValue >> 16) & 0xFF
    request.data[2] = (voltSetValue >> 8) & 0xFF
    request.data[3] = voltSetValue & 0xFF
    request.data[4] = (currSetValue >> 24) & 0xFF
    request.data[5] = (currSetValue >> 16) & 0xFF
    request.data[6] = (currSetValue >> 8) & 0xFF
    request.data[7] = currSetValue & 0xFF
    REGx_MsgSend(request)
    return 0
```

对其他 21 个发送函数做相同改动（只改签名 + 把 `REGx_DEVICE_CODE.SINGLE` 替换为 `device_code`）。

- [ ] **Step 2: 验证没破坏既有调用**

```bash
pytest tests/ -v
```
Expected: 15 + 3 (旧 config 测试) = 18 passed (新加的测试都不直接调用这些函数，只验证签名与默认行为)

```bash
python -c "from REG1K0100A2 import REGx_SetOutput, REGx_DEVICE_CODE; print(REGx_DEVICE_CODE.GROUP)"
```
Expected: `11`

- [ ] **Step 3: 提交**

```bash
git add REG1K0100A2.py
git commit -m "refactor(REG1K0100A2): 所有发送函数加 device_code 参数（默认 SINGLE，向后兼容）"
```

---

## Task 6: REG1K0100A2 — 新增组级便捷 helper

**Files:**
- Modify: `REG1K0100A2.py`
- Create: `tests/test_reg1k_group_helpers.py`

- [ ] **Step 1: 写失败测试 — 组级 helper 编码正确**

新建 `tests/test_reg1k_group_helpers.py`：

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class _MockCAN:
    def __init__(self):
        self.sent = []   # list of (can_id, bytes)

    def send_data_ch1(self, can_id, data):
        self.sent.append((can_id, bytes(data)))
        return 1


@pytest.fixture
def mock_can(monkeypatch):
    import REG1K0100A2
    mc = _MockCAN()
    REG1K0100A2.REGx_Init(mc)
    monkeypatch.setattr(REG1K0100A2, 'g_log_callback', None)
    return mc


def test_group_set_output_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupSetOutput
    REGx_GroupSetOutput(group_id=2, volt=512.0, total_curr=40.0)
    can_id, data = mock_can.sent[-1]
    # 02 DB 02 F0 — cmd=0x1B(101 1), device=0x0B(1011), dst=0x02, src=0xF0
    assert can_id == 0x02DB02F0
    # voltage = 512.0V → 512000 mV = 0x0007D000
    assert data[0:4] == bytes([0x00, 0x07, 0xD0, 0x00])
    # current = 40.0A → 40000 mA = 0x00009C40
    assert data[4:8] == bytes([0x00, 0x00, 0x9C, 0x40])


def test_group_launch_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupLaunch
    REGx_GroupLaunch(group_id=3)
    can_id, data = mock_can.sent[-1]
    # cmd=0x1A, device=0x0B, dst=0x03, src=0xF0
    assert can_id == 0x02DA03F0
    assert data[0] == 0x00


def test_group_close_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupClose
    REGx_GroupClose(group_id=3)
    can_id, data = mock_can.sent[-1]
    assert can_id == 0x02DA03F0
    assert data[0] == 0x01


def test_group_read_volt_curr_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupReadVoltCurr
    REGx_GroupReadVoltCurr(group_id=1)
    can_id, _ = mock_can.sent[-1]
    # cmd=0x08, device=0x0B, dst=0x01, src=0xF0
    assert can_id == 0x02C801F0


def test_group_discover_modules_encodes_identifier(mock_can):
    from REG1K0100A2 import REGx_GroupReadModulesStatus
    REGx_GroupReadModulesStatus(group_id=1)
    can_id, _ = mock_can.sent[-1]
    # cmd=0x04, device=0x0B, dst=0x01, src=0xF0
    assert can_id == 0x02C401F0
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_reg1k_group_helpers.py -v
```
Expected: ImportError: cannot import name 'REGx_GroupSetOutput'

- [ ] **Step 3: 在 `REG1K0100A2.py` 末尾追加 helper**

```python
# ─── 组级便捷包装 ────────────────────────────────────────
def REGx_GroupSetOutput(group_id, volt, total_curr):
    return REGx_SetSystemOutput(group_id, volt, total_curr,
                                 device_code=REGx_DEVICE_CODE.GROUP)


def REGx_GroupLaunch(group_id):
    return REGx_Launch(group_id, device_code=REGx_DEVICE_CODE.GROUP)


def REGx_GroupClose(group_id):
    return REGx_CloseOutput(group_id, device_code=REGx_DEVICE_CODE.GROUP)


def REGx_GroupReadVoltCurr(group_id):
    return REGx_ReadSystemVoltCurrFixed(group_id,
                                         device_code=REGx_DEVICE_CODE.GROUP)


def REGx_GroupReadModulesStatus(group_id):
    return REGx_ReadStateRequest(group_id, device_code=REGx_DEVICE_CODE.GROUP)
```

- [ ] **Step 4: 运行确认 5 个测试通过**

```bash
pytest tests/test_reg1k_group_helpers.py -v
```
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add REG1K0100A2.py tests/test_reg1k_group_helpers.py
git commit -m "feat(REG1K0100A2): 新增 5 个组级便捷 helper（SetOutput/Launch/Close/ReadVoltCurr/Discover）"
```

---

## Task 7: REG1K0100A2 — RX 监听器分发

**Files:**
- Modify: `REG1K0100A2.py`
- Create: `tests/test_reg1k_listeners.py`

> **目的**：把 `REGx_CAN_ReceviceCallback` 直接修改全局 `CANControllerInfo` 的紧耦合，改造为"解析 → 派 RxEvent → 调每个注册的监听器"。旧 listener 继续填 `CANControllerInfo`，确保 `manual_widget` 不打断。

- [ ] **Step 1: 写失败测试 — listener 注册与回调**

新建 `tests/test_reg1k_listeners.py`：

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class _FakeMsg:
    def __init__(self, can_id, data):
        self.can_id = can_id
        self.data = bytes(data)


def test_register_listener_called_with_rx_event():
    import REG1K0100A2
    REG1K0100A2._rx_listeners.clear()
    captured = []
    REG1K0100A2.REGx_RegisterListener(lambda ev: captured.append(ev))

    # 模块 0 回 0x09：02 89 F0 00 ; data 200V 5A
    msg = _FakeMsg(0x028900F0 | 0x000000F0,  # 占位，下行用真实
                   bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88]))
    msg.can_id = 0x0289F000  # cmd=0x09, device=0x0A, dst=0xF0, src=0x00
    info = REG1K0100A2.CANControllerInfo()
    REG1K0100A2.REGx_CAN_ReceviceCallback(msg, info)

    assert len(captured) == 1
    ev = captured[0]
    assert ev.cmdCode == 0x09
    assert ev.deviceCode == 0x0A
    assert ev.dstAddr == 0xF0
    assert ev.srcAddr == 0x00
    assert ev.data[:8] == bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88])


def test_legacy_listener_still_fills_canController_info():
    """确保旧路径（CANControllerInfo）不被打断 — manual_widget 还在用"""
    import REG1K0100A2
    REG1K0100A2._rx_listeners.clear()  # 清掉前测试残留
    info = REG1K0100A2.CANControllerInfo()
    msg = _FakeMsg(0x0289F000,
                   bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88]))
    REG1K0100A2.REGx_CAN_ReceviceCallback(msg, info)

    assert info.DC_Output_Volt == pytest.approx(200.0)
    assert info.DC_Output_Curr == pytest.approx(5.0)


def test_unregister_listener():
    import REG1K0100A2
    REG1K0100A2._rx_listeners.clear()
    captured = []
    cb = lambda ev: captured.append(ev)
    REG1K0100A2.REGx_RegisterListener(cb)
    REG1K0100A2.REGx_UnregisterListener(cb)

    msg = _FakeMsg(0x0289F000, bytes(8))
    info = REG1K0100A2.CANControllerInfo()
    REG1K0100A2.REGx_CAN_ReceviceCallback(msg, info)
    assert captured == []
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_reg1k_listeners.py -v
```
Expected: AttributeError: module 'REG1K0100A2' has no attribute 'REGx_RegisterListener'

- [ ] **Step 3: 在 `REG1K0100A2.py` 加 listener 基础设施 + RxEvent**

在文件靠近顶部（在 `g_candevice` 定义后）追加：

```python
from dataclasses import dataclass

@dataclass
class RxEvent:
    errorCode: int
    deviceCode: int
    cmdCode: int
    dstAddr: int
    srcAddr: int
    data: bytes  # 8 字节


_rx_listeners = []  # list of callable(RxEvent)

def REGx_RegisterListener(cb):
    if cb not in _rx_listeners:
        _rx_listeners.append(cb)

def REGx_UnregisterListener(cb):
    if cb in _rx_listeners:
        _rx_listeners.remove(cb)
```

在 `REGx_CAN_ReceviceCallback` 函数最末（`pass` 之后）追加：

```python
    # 派发给注册的监听器（旧路径继续填 canController_info，新路径用 RxEvent）
    ev = RxEvent(
        errorCode=response.errorCode,
        deviceCode=response.deviceCode,
        cmdCode=response.cmdCode,
        dstAddr=response.dstAddr,
        srcAddr=response.srcAddr,
        data=bytes(response.data),
    )
    for cb in list(_rx_listeners):
        try:
            cb(ev)
        except Exception as e:
            print(f"[REGx listener exception] {e}")
```

- [ ] **Step 4: 运行确认所有测试通过**

```bash
pytest tests/ -v
```
Expected: all passed (含本任务 3 个新测试)

- [ ] **Step 5: 提交**

```bash
git add REG1K0100A2.py tests/test_reg1k_listeners.py
git commit -m "refactor(REG1K0100A2): RX 回调追加 RxEvent + listener 派发，旧 CANControllerInfo 路径保留"
```

---

## Task 8: GroupPoller 基础类与链式调度

**Files:**
- Create: `group_poller.py`
- Create: `tests/test_group_poller.py`

> **设计要点**：
> - 不绑 `QTimer`，而是接受一个 `schedule_fn(delay_ms, callback)` 注入参数。生产代码传 `lambda d, cb: QTimer.singleShot(d, cb)`，测试传一个手工 step 的假调度器。这样 GroupPoller 可纯 Python 单元测试。
> - 链式发送：`_send_step()` 发一条命令，调度 `poll_interval_ms` 后调用 `_send_next()`，依此类推。
> - 一个完整周期 = ① 组级 0x08 + ② N 个模块的 0x09 + ③ N 个模块的 0x04。
> - 模块 dict 由外部 `GroupState` 持有，poller 不直接持有；poller 用 `state.modules.keys()` 决定 ②③ 要发给谁。

- [ ] **Step 1: 写失败测试 — 周期发送序列**

新建 `tests/test_group_poller.py`：

```python
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class _MockCAN:
    def __init__(self):
        self.sent = []
    def send_data_ch1(self, can_id, data):
        self.sent.append((can_id, bytes(data)))
        return 1


class _StepScheduler:
    """手工 step 的假调度器，记录所有调用"""
    def __init__(self):
        self.queue = []  # list of (delay_ms, callback)
    def __call__(self, delay_ms, cb):
        self.queue.append((delay_ms, cb))
    def step(self):
        if not self.queue:
            return False
        _, cb = self.queue.pop(0)
        cb()
        return True


@pytest.fixture
def setup():
    import REG1K0100A2
    from group_state import GroupState, ModuleState
    REG1K0100A2._rx_listeners.clear()
    can = _MockCAN()
    REG1K0100A2.REGx_Init(can)
    state = GroupState(group_id=1)
    state.modules[0x00] = ModuleState(addr=0x00, last_seen=0.0)
    state.modules[0x01] = ModuleState(addr=0x01, last_seen=0.0)
    sch = _StepScheduler()
    return can, state, sch


def test_poller_sends_group_then_per_module_x9_x4(setup):
    from group_poller import GroupPoller
    can, state, sch = setup
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.start_cycle()

    # 立即发了组 0x08（不等 schedule）
    assert can.sent[0][0] == 0x02C801F0  # cmd=0x08 device=0x0B dst=0x01

    # step 一次 → 发模块 0 的 0x09
    sch.step()
    assert can.sent[1][0] == 0x028900F0  # cmd=0x09 device=0x0A dst=0x00

    # step → 模块 0 的 0x04
    sch.step()
    assert can.sent[2][0] == 0x028400F0  # cmd=0x04 device=0x0A dst=0x00

    # step → 模块 1 的 0x09
    sch.step()
    assert can.sent[3][0] == 0x028901F0

    # step → 模块 1 的 0x04
    sch.step()
    assert can.sent[4][0] == 0x028401F0


def test_poller_loops_back_after_full_cycle(setup):
    from group_poller import GroupPoller
    can, state, sch = setup
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.start_cycle()
    # 一个完整周期 = 1 + 2*2 = 5 条
    while sch.step():
        if len(can.sent) >= 5:
            break

    # 再 step 一次 → 应该回到组 0x08
    sch.step()
    assert can.sent[5][0] == 0x02C801F0


def test_poller_stop_cancels_chain(setup):
    from group_poller import GroupPoller
    can, state, sch = setup
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.start_cycle()
    poller.stop()
    sch.step()  # 已被 cancel，不应再发
    assert len(can.sent) == 1  # 只有起步那一条
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_group_poller.py -v
```
Expected: ModuleNotFoundError: No module named 'group_poller'

- [ ] **Step 3: 实现 `group_poller.py`**

```python
from REG1K0100A2 import (
    REGx_GroupReadVoltCurr,
    REGx_ReadOutputRequest,         # 0x09
    REGx_ReadStateRequest,          # 0x04
    REGx_GroupReadModulesStatus,    # 0x04 + 0x0B
    REGx_DEVICE_CODE,
)


class GroupPoller:
    def __init__(self, state, schedule_fn, poll_interval_ms: int = 100):
        self._state = state
        self._sched = schedule_fn
        self._interval = poll_interval_ms
        self._running = False
        self._step_idx = 0   # 0=group, 1..N=module idx for 0x09, N+1..2N=module idx for 0x04

    def start_cycle(self):
        self._running = True
        self._step_idx = 0
        self._do_current_step()

    def stop(self):
        self._running = False

    def _module_addrs(self):
        return sorted(self._state.modules.keys())

    def _do_current_step(self):
        if not self._running:
            return
        addrs = self._module_addrs()
        N = len(addrs)
        i = self._step_idx
        if i == 0:
            REGx_GroupReadVoltCurr(self._state.group_id)
        elif 1 <= i <= N:
            REGx_ReadOutputRequest(addrs[i - 1])
        elif N + 1 <= i <= 2 * N:
            REGx_ReadStateRequest(addrs[i - N - 1])
        # 准备下一步
        self._step_idx = (i + 1) % (1 + 2 * N) if N > 0 else 0
        self._sched(self._interval, self._next_step_wrapper)

    def _next_step_wrapper(self):
        if self._running:
            self._do_current_step()
```

- [ ] **Step 4: 运行确认 3 个测试通过**

```bash
pytest tests/test_group_poller.py -v
```
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add group_poller.py tests/test_group_poller.py
git commit -m "feat(group_poller): 链式调度 1 组级 + 2N 模块级命令的轮询，schedule_fn 注入便于测试"
```

---

## Task 9: GroupPoller — 初始模块发现

**Files:**
- Modify: `group_poller.py`
- Modify: `tests/test_group_poller.py`

- [ ] **Step 1: 写失败测试 — 发现流程**

追加到 `tests/test_group_poller.py`：

```python
def test_discover_collects_srcAddrs_into_state_modules(setup, monkeypatch):
    import REG1K0100A2
    from group_poller import GroupPoller
    can, state, sch = setup
    state.modules.clear()  # 重置，模拟刚切组
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)

    # 模拟"调度延迟"：当 poller 调用 sch 等 600ms 时，我们手动喂入 RX
    captured_finish = []
    poller.discover_modules(group_id=1, timeout_ms=600,
                             on_finish=lambda found: captured_finish.append(found))

    # 验证发了组级 0x04
    assert can.sent[-1][0] == 0x02C401F0

    # 模拟 3 个模块回复（组级 0x04 回复，srcAddr = 模块地址）
    # 协议示例: 02 C4 F0 00 (cmd=0x04 device=0x0B dst=0xF0=master src=0x00)
    for mod_addr in (0x00, 0x01, 0x02):
        # data: [0,0,group_id_reported, status3, temp, status2, status1, status0]
        msg = REG1K0100A2.RxEvent(errorCode=0, deviceCode=0x0B, cmdCode=0x04,
                                   dstAddr=0xF0, srcAddr=mod_addr,
                                   data=bytes([0, 0, 1, 0, 25, 0, 0, 0]))
        # 直接喂给 poller 的 listener
        poller._on_rx(msg)

    # 模拟 timeout 触发
    sch.step()  # discover 的超时回调

    assert sorted(state.modules.keys()) == [0x00, 0x01, 0x02]
    assert captured_finish == [{0x00, 0x01, 0x02}]


def test_discover_calls_on_finish_with_empty_set_on_timeout(setup):
    from group_poller import GroupPoller
    can, state, sch = setup
    state.modules.clear()
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    captured = []
    poller.discover_modules(group_id=2, timeout_ms=600,
                             on_finish=lambda found: captured.append(found))
    sch.step()
    assert captured == [set()]
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_group_poller.py -v
```
Expected: AttributeError: 'GroupPoller' object has no attribute 'discover_modules'

- [ ] **Step 3: 在 GroupPoller 加 discover_modules + RxEvent listener**

修改 `group_poller.py`，在 import 区追加：

```python
import time
from REG1K0100A2 import REGx_RegisterListener, REGx_UnregisterListener
from group_state import ModuleState
```

在 `GroupPoller` 类中追加：

```python
    def discover_modules(self, group_id: int, timeout_ms: int, on_finish):
        self._state.group_id = group_id
        self._discover_seen = set()
        REGx_RegisterListener(self._on_rx)
        REGx_GroupReadModulesStatus(group_id)

        def _finish():
            REGx_UnregisterListener(self._on_rx)
            for addr in self._discover_seen:
                if addr not in self._state.modules:
                    self._state.modules[addr] = ModuleState(addr=addr, last_seen=time.time())
            on_finish(self._discover_seen)

        self._sched(timeout_ms, _finish)

    def _on_rx(self, ev):
        # 接收组级 0x04 回复用于发现；接收其他用于更新数据
        if ev.cmdCode == 0x04 and ev.deviceCode == 0x0B and ev.srcAddr != 0xF0:
            self._discover_seen.add(ev.srcAddr)
```

- [ ] **Step 4: 运行确认 5 个 group_poller 测试通过**

```bash
pytest tests/test_group_poller.py -v
```
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add group_poller.py tests/test_group_poller.py
git commit -m "feat(group_poller): discover_modules 通过组级 0x04 广播收集组内模块地址"
```

---

## Task 10: GroupPoller — RX 数据 + 离线状态机

**Files:**
- Modify: `group_poller.py`
- Modify: `tests/test_group_poller.py`

- [ ] **Step 1: 写失败测试 — 0x09/0x04 RX 更新 ModuleState**

追加到 `tests/test_group_poller.py`：

```python
def test_rx_x9_updates_module_voltage_current_and_last_seen(setup, monkeypatch):
    import REG1K0100A2, time
    from group_poller import GroupPoller
    can, state, sch = setup
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.attach()  # 注册到 RX 监听

    monkeypatch.setattr(time, 'time', lambda: 1234.5)
    ev = REG1K0100A2.RxEvent(errorCode=0, deviceCode=0x0A, cmdCode=0x09,
                              dstAddr=0xF0, srcAddr=0x00,
                              data=bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88]))
    poller._on_rx(ev)

    m = state.modules[0x00]
    assert m.voltage == pytest.approx(200.0)
    assert m.current == pytest.approx(5.0)
    assert m.last_seen == 1234.5

    poller.detach()


def test_rx_x4_updates_status_and_temperature(setup):
    import REG1K0100A2
    from group_poller import GroupPoller
    can, state, sch = setup
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.attach()

    ev = REG1K0100A2.RxEvent(errorCode=0, deviceCode=0x0A, cmdCode=0x04,
                              dstAddr=0xF0, srcAddr=0x01,
                              data=bytes([0, 0, 1, 0x80, 0x1B, 0x40, 0x10, 0x80]))
    poller._on_rx(ev)
    m = state.modules[0x01]
    assert m.group_id_reported == 1
    assert m.status3 == 0x80
    assert m.temperature == 0x1B  # 27 deg
    assert m.status2 == 0x40
    assert m.status1 == 0x10
    assert m.status0 == 0x80

    poller.detach()


def test_rx_x4_other_group_evicts_module_from_state(setup):
    import REG1K0100A2
    from group_poller import GroupPoller
    can, state, sch = setup
    state.group_id = 1
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.attach()

    # 模块 0x00 报告自己组号 = 5（不再属于本组 1）
    ev = REG1K0100A2.RxEvent(errorCode=0, deviceCode=0x0A, cmdCode=0x04,
                              dstAddr=0xF0, srcAddr=0x00,
                              data=bytes([0, 0, 5, 0, 25, 0, 0, 0]))
    poller._on_rx(ev)
    assert 0x00 not in state.modules

    poller.detach()


def test_rx_x8_group_updates_group_voltage_current(setup):
    import REG1K0100A2
    from group_poller import GroupPoller
    can, state, sch = setup
    state.group_id = 1
    poller = GroupPoller(state=state, schedule_fn=sch, poll_interval_ms=100)
    poller.attach()

    # 协议：0x08 组级回复 srcAddr = 组号
    ev = REG1K0100A2.RxEvent(errorCode=0, deviceCode=0x0B, cmdCode=0x08,
                              dstAddr=0xF0, srcAddr=0x01,
                              data=bytes([0, 3, 0x0D, 0x40, 0, 0, 0x13, 0x88]))
    poller._on_rx(ev)
    assert state.voltage == pytest.approx(200.0)
    assert state.total_current == pytest.approx(5.0)

    poller.detach()
```

- [ ] **Step 2: 运行确认失败**

```bash
pytest tests/test_group_poller.py -v -k "test_rx_"
```
Expected: AttributeError: 'GroupPoller' object has no attribute 'attach'

- [ ] **Step 3: 在 GroupPoller 加 attach/detach 与各 RX 解码**

替换 `_on_rx` + 加 attach/detach：

```python
    def attach(self):
        REGx_RegisterListener(self._on_rx)

    def detach(self):
        REGx_UnregisterListener(self._on_rx)

    def _on_rx(self, ev):
        # 1) 组级 0x04 发现回复（discover_modules 期间）
        if ev.cmdCode == 0x04 and ev.deviceCode == 0x0B and ev.srcAddr != 0xF0:
            self._discover_seen.add(ev.srcAddr)

        # 2) 模块级 0x09 → 更新模块 V/I + last_seen
        if ev.cmdCode == 0x09 and ev.deviceCode == 0x0A:
            addr = ev.srcAddr
            m = self._state.modules.get(addr)
            if m is None:
                return
            d = ev.data
            v_mV = (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]
            i_mA = (d[4] << 24) | (d[5] << 16) | (d[6] << 8) | d[7]
            m.voltage = v_mV / 1000.0
            m.current = i_mA / 1000.0
            m.last_seen = time.time()

        # 3) 模块级 0x04 → 更新状态/温度/组号；若组号 ≠ 本组则踢出
        if ev.cmdCode == 0x04 and ev.deviceCode == 0x0A:
            addr = ev.srcAddr
            m = self._state.modules.get(addr)
            if m is None:
                return
            d = ev.data
            reported_group = d[2]
            if reported_group != self._state.group_id:
                self._state.modules.pop(addr, None)
                return
            m.group_id_reported = reported_group
            m.status3 = d[3]
            # data[4] 是有符号 8bit 温度
            t = d[4]
            m.temperature = t - 256 if t > 127 else t
            m.status2 = d[5]
            m.status1 = d[6]
            m.status0 = d[7]
            m.last_seen = time.time()

        # 4) 组级 0x08 / 0x01 → 更新组聚合 V/I
        if ev.cmdCode == 0x08 and ev.deviceCode == 0x0B and ev.srcAddr == self._state.group_id:
            d = ev.data
            v_mV = (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]
            i_mA = (d[4] << 24) | (d[5] << 16) | (d[6] << 8) | d[7]
            self._state.voltage = v_mV / 1000.0
            self._state.total_current = i_mA / 1000.0
```

> 同时把原来 `_on_rx` 里只处理"discover"的代码删掉（已合并到上面）。
> `discover_modules` 里调 `attach()` 而非 `REGx_RegisterListener` 重复注册：把 `discover_modules` 中的 `REGx_RegisterListener(self._on_rx)` 改为 `self.attach()`，把 `_finish` 里的 `REGx_UnregisterListener(self._on_rx)` 改为 `self.detach()`。

注意：`discover_modules` 不应在 finish 里 detach，否则后续周期的 RX 收不到。改为：discover 期间和周期期间共用同一个 attach；调用方自己控制生命周期。

具体修改 `discover_modules`：

```python
    def discover_modules(self, group_id: int, timeout_ms: int, on_finish):
        self._state.group_id = group_id
        self._discover_seen = set()
        # 监听器若未 attach 则 attach；后续由调用方 detach
        if self._on_rx not in _local_attached(self):
            self.attach()
        REGx_GroupReadModulesStatus(group_id)

        def _finish():
            for addr in self._discover_seen:
                if addr not in self._state.modules:
                    self._state.modules[addr] = ModuleState(addr=addr, last_seen=time.time())
            on_finish(self._discover_seen)

        self._sched(timeout_ms, _finish)
```

> 把 `_local_attached(self)` 简化掉：直接维护一个 bool `_attached` 标志：

```python
    def __init__(self, state, schedule_fn, poll_interval_ms: int = 100):
        self._state = state
        self._sched = schedule_fn
        self._interval = poll_interval_ms
        self._running = False
        self._step_idx = 0
        self._discover_seen = set()
        self._attached = False

    def attach(self):
        if not self._attached:
            REGx_RegisterListener(self._on_rx)
            self._attached = True

    def detach(self):
        if self._attached:
            REGx_UnregisterListener(self._on_rx)
            self._attached = False
```

`discover_modules` 里把 `if self._on_rx not in _local_attached(self): self.attach()` 改为直接 `self.attach()`（attach 内部已有幂等保护）。

- [ ] **Step 4: 运行确认所有测试通过**

```bash
pytest tests/ -v
```
Expected: all passed

- [ ] **Step 5: 提交**

```bash
git add group_poller.py tests/test_group_poller.py
git commit -m "feat(group_poller): RX 解码 0x09/0x04/0x08 → 更新 ModuleState/GroupState；跨组模块自动踢出"
```

---

## Task 11: chart_widget — target 切换 + RX 驱动 push

**Files:**
- Modify: `chart_widget.py`

> **要点**：
> - 现有 `push(volt, curr, power)` 保留向后兼容（兜底），但新增 `push_group/push_module/set_target`。
> - target 切换时清空缓冲区且自动恢复运行（不沿用上一个 target 的暂停态）。
> - 拓扑：`set_target('group')` 或 `set_target(int)`（模块地址）。
> - 增加 `set_module_options(addrs)`：从外部更新 dropdown 选项。

- [ ] **Step 1: 在 `chart_widget.py` 顶部 import 处加 ComboBox**

替换 import 行：

```python
from qfluentwidgets import (CaptionLabel, CheckBox, ComboBox, FluentIcon as FIF,
                             StrongBodyLabel, ToolButton, isDarkTheme)
```

- [ ] **Step 2: 在 `RealtimeChart.__init__` 末尾加 target 状态**

在 `self._build_ui()` 调用前追加：

```python
        self._target = 'group'   # 'group' or int (module addr)
        self._volt_max_group = float(volt_max) if volt_max > 0 else 1000.0
        self._curr_max_group = float(curr_max) if curr_max > 0 else 100.0
        self._pwr_max_group  = float(pwr_max)  if pwr_max  > 0 else 30000.0
```

- [ ] **Step 3: 在 `_build_ui` 的 hdr 行加 target dropdown**

在 `self._pause_btn = ToolButton(...)` 创建之前插入：

```python
        self._target_combo = ComboBox()
        self._target_combo.addItem('整组')
        self._target_combo.setMinimumWidth(110)
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        hdr.addWidget(self._target_combo)
```

- [ ] **Step 4: 加 set_target / set_module_options / push_group / push_module 方法**

在 `RealtimeChart` 类中（`push` 方法之后）追加：

```python
    def set_target(self, target):
        """target = 'group' or int (module addr)"""
        self._target = target
        self._volt_data.clear()
        self._curr_data.clear()
        self._pwr_data.clear()
        self._paused = False
        self._pause_btn.setIcon(FIF.PAUSE)
        # 量程：模块视角时退化
        if target == 'group':
            self._volt_max = self._volt_max_group
            self._curr_max = self._curr_max_group
            self._pwr_max  = self._pwr_max_group
        else:
            self._volt_max = self._volt_max_group   # 单模块电压量程同组
            self._curr_max = self._curr_max_group / max(self._target_combo.count() - 1, 1)
            self._pwr_max  = self._volt_max * self._curr_max
        self._canvas.update()

    def set_module_options(self, addrs):
        """从外部更新 dropdown 选项，保留当前选择若仍存在"""
        cur = self._target_combo.currentText()
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        self._target_combo.addItem('整组')
        for a in sorted(addrs):
            self._target_combo.addItem(f'模块 0x{a:02X}')
        idx = self._target_combo.findText(cur)
        if idx >= 0:
            self._target_combo.setCurrentIndex(idx)
        else:
            self._target_combo.setCurrentIndex(0)
            self._target = 'group'
        self._target_combo.blockSignals(False)

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
        # 'module 0x05' → 5
        try:
            addr = int(text.split('0x')[1], 16)
            self.set_target(addr)
        except (IndexError, ValueError):
            self.set_target('group')
```

- [ ] **Step 5: 手动 sanity check（无自动测试，UI 模块）**

```bash
python -c "from chart_widget import RealtimeChart; print('OK')"
```
Expected: `OK`

> 手动测试留到 Task 16 集成时一起做。

- [ ] **Step 6: 提交**

```bash
git add chart_widget.py
git commit -m "feat(chart_widget): 新增 set_target/push_group/push_module 与 target dropdown，支持 整组/模块N 切换"
```

---

## Task 12: 模块表自定义 Delegate（CheckBox 列 + 告警 Badge）

**Files:**
- Create: `module_table.py`

> **设计**：完全用 `QStyledItemDelegate` 渲染，避免 setCellWidget 的列宽抖动问题（已在 manual_widget 验证过这个模式）。
> - 6 列：地址 / 电压 / 电流 / 温度 / 💤 / 💡
> - 第 5 列（💤）：复选框；状态从 `ModuleState.sleeping` 读，点击发 `0x19`
> - 第 6 列（💡）：复选框；本地 toggle，点击发 `0x14`
> - 地址列旁告警 badge：用 `IconInfoBadge` 通过 `setCellWidget` 配 hover tooltip（这一个仅显示，不参与排序，setCellWidget 抖动可接受）

- [ ] **Step 1: 创建 `module_table.py` 骨架（无测试，UI 类）**

```python
from PyQt5.QtCore import Qt, QRect, QEvent
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (QStyledItemDelegate, QStyle, QStyleOptionButton,
                              QApplication, QHeaderView, QWidget, QHBoxLayout)
from qfluentwidgets import TableWidget, IconInfoBadge, FluentIcon as FIF, InfoLevel


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
        """state: GroupState；now_ms_thresholds: (now_time, pending, offline, gone)"""
        from PyQt5.QtWidgets import QTableWidgetItem
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
            item.setBackground(color if color else QColor(0, 0, 0, 0))

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
```

- [ ] **Step 2: sanity check**

```bash
python -c "from module_table import ModuleTable, COLS; print(COLS)"
```
Expected: `['地址', '电压', '电流', '温度℃', '💤', '💡']`

- [ ] **Step 3: 提交**

```bash
git add module_table.py
git commit -m "feat(module_table): 新建组内模块表格组件，含 💤/💡 自定义 Delegate + 告警 Badge"
```

---

## Task 13: 新建 GroupHomeWidget — 顶部条 + 整体布局骨架

**Files:**
- Create: `home_widget.py`

> 这一节只搭骨架（不接数据）。下一任务接数据。

- [ ] **Step 1: 创建 `home_widget.py` 骨架**

```python
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
```

- [ ] **Step 2: sanity check**

```bash
python -c "from home_widget import GroupHomeWidget; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add home_widget.py
git commit -m "feat(home_widget): 新建 GroupHomeWidget 骨架（顶部条 + 左信息流 + 右组控制）"
```

---

## Task 14: GroupHomeWidget — 接数据 + 信号槽

**Files:**
- Modify: `home_widget.py`

- [ ] **Step 1: 实现 _toggle_can**

替换 `_toggle_can`：

```python
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
                self._poller.attach()
                # 立即对默认组发起一次发现
                self._bind_group(self._cfg.default_group)
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
```

- [ ] **Step 2: 实现 _on_group_changed + _bind_group + _discover_now**

追加 / 替换：

```python
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
        # 停止周期、清空模块、重新发现
        self._poller.stop()
        self._state.modules.clear()
        self.tbl.setRowCount(0)
        self._bind_group(self._state.group_id)
```

- [ ] **Step 3: 实现控件命令下发**

追加 / 替换：

```python
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
```

- [ ] **Step 4: 实现刷新视图 + chart 联动 + 周期 UI 刷新**

在类中追加：

```python
    def _refresh_aggregate_view(self):
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
        import time
        self.tbl.update_modules(self._state, (
            time.time(),
            self._cfg.module_pending_timeout_ms,
            self._cfg.module_offline_timeout_ms,
            self._cfg.module_gone_timeout_ms,
        ))
        # 移除 gone 模块
        gone = [a for a, m in s.modules.items()
                if m.lifecycle(time.time(),
                               self._cfg.module_pending_timeout_ms,
                               self._cfg.module_offline_timeout_ms,
                               self._cfg.module_gone_timeout_ms) == 'gone']
        for a in gone:
            s.modules.pop(a, None)
        # 同步 chart dropdown
        self.chart.set_module_options(s.modules.keys())
```

在 `__init__` 末尾追加 UI 刷新 timer：

```python
        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_aggregate_view)
        self._ui_timer.start(200)
```

- [ ] **Step 5: 在类中加 chart RX 监听 hookup（让 chart 跟着 RX 动）**

在 `__init__` 末尾追加（在 ui_timer 之前）：

```python
        from REG1K0100A2 import REGx_RegisterListener
        REGx_RegisterListener(self._chart_listener)

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
```

- [ ] **Step 6: sanity check**

```bash
python -c "from home_widget import GroupHomeWidget; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: 提交**

```bash
git add home_widget.py
git commit -m "feat(home_widget): 接 GroupPoller + chart RX 监听 + 组控制下发 + 切组 InfoBar 提示"
```

---

## Task 15: 接入 main.py（替换旧 MainWindow）

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 替换 main.py**

```python
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import (QAction, QApplication, QFrame, QHBoxLayout,
                              QMenu, QSystemTrayIcon, QWidget)
from qfluentwidgets import (Action, AvatarWidget, BodyLabel, CaptionLabel,
                             FluentIcon, FluentIcon as FIF, FluentWindow,
                             HyperlinkButton, MessageBox, NavigationAvatarWidget,
                             NavigationItemPosition, SubtitleLabel, SwitchButton,
                             Theme, isDarkTheme, setFont, setTheme, setThemeColor)
from qfluentwidgets.components.material import AcrylicMenu

from config_manager import AppConfig, ConfigManager
from HDL_CAN import CANDev
from home_widget import GroupHomeWidget
from manual_widget import ManualWidget
from REG1K0100A2 import CANControllerInfo, REGx_Init


class SettingWidget(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.switchButton = SwitchButton(self)
        self.switchButton.setOnText('Dark')
        self.switchButton.setOffText('Light')
        self.switchButton.checkedChanged.connect(
            lambda: setTheme(Theme.DARK if self.switchButton.isChecked() else Theme.LIGHT))
        setFont(self.switchButton, 24)
        self.hBoxLayout.addWidget(self.switchButton, 1, Qt.AlignCenter)
        self.setObjectName(text.replace(' ', '-'))


class ProfileCard(QWidget):
    def __init__(self, avatarPath: str, name: str, email: str, parent=None):
        super().__init__(parent=parent)
        self.avatar = AvatarWidget(avatarPath, self)
        self.nameLabel = BodyLabel(name, self)
        self.emailLabel = CaptionLabel(email, self)
        self.logoutButton = HyperlinkButton(
            'https://github.com/MisakaMikoto128', '注销', self)
        color = QColor(206, 206, 206) if isDarkTheme() else QColor(96, 96, 96)
        self.emailLabel.setStyleSheet('QLabel{color: ' + color.name() + '}')
        color = QColor(255, 255, 255) if isDarkTheme() else QColor(0, 0, 0)
        self.nameLabel.setStyleSheet('QLabel{color: ' + color.name() + '}')
        setFont(self.logoutButton, 13)
        self.setFixedSize(307, 82)
        self.avatar.setRadius(24)
        self.avatar.move(2, 6)
        self.nameLabel.move(64, 13)
        self.emailLabel.move(64, 32)
        self.logoutButton.move(52, 48)


class Window(FluentWindow):
    def __init__(self):
        super().__init__()
        setThemeColor('#28afe9')

        self._config = ConfigManager().load()

        self.can_device = CANDev()
        REGx_Init(self.can_device)
        self.canController_info = CANControllerInfo()  # 仅供 manual_widget 使用

        self.homeInterface = GroupHomeWidget(
            can_device=self.can_device,
            config=self._config,
            parent=self,
        )
        self.homeInterface.setObjectName('GroupHomeWidget')
        self.manualInterface = ManualWidget(
            can_device=self.can_device,
            canController_info=self.canController_info,
            config=self._config,
            parent=self,
        )
        self.settingInterface = SettingWidget('Setting Interface', self)

        self.setWindowState(Qt.WindowMaximized)
        self._init_navigation()
        self._init_window()

        # Tray
        exitAction = QAction(QIcon('./img/sp-exit.png'), 'Exit', self)
        exitAction.triggered.connect(self.close)
        trayMenu = QMenu(self)
        trayMenu.addAction(exitAction)
        self.trayIcon = QSystemTrayIcon(self)
        self.trayIcon.setIcon(QIcon('./img/star.png'))
        self.trayIcon.setContextMenu(trayMenu)
        self.trayIcon.show()

    def _init_navigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, '主页')
        self.addSubInterface(self.manualInterface, FIF.EDIT, '手动操作')
        self.navigationInterface.addSeparator()
        self.navigationInterface.addWidget(
            routeKey='avatar',
            widget=NavigationAvatarWidget('Yuanlin-Liu', 'resource/shoko.png'),
            onClick=self._show_about,
            position=NavigationItemPosition.BOTTOM,
        )
        self.addSubInterface(self.settingInterface, FIF.SETTING, 'Settings',
                             NavigationItemPosition.BOTTOM)
        self.navigationInterface.setAcrylicEnabled(True)

    def _init_window(self):
        self.resize(1100, 760)
        self.setWindowTitle(self._config.device_name)
        self.setWindowIcon(QIcon('./img/star.png'))
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

    def _show_about(self):
        MessageBox('支持作者', '🥤🥤🚀', self).exec()

    def contextMenuEvent(self, e) -> None:
        menu = AcrylicMenu(parent=self)
        card = ProfileCard('resource/shoko.png', '刘沅林',
                           'liuyuanlins@outlook.com', menu)
        menu.addWidget(card, selectable=False)
        menu.addSeparator()
        menu.addActions([
            Action(FluentIcon.PEOPLE, '管理账户和设置'),
            Action(FluentIcon.SHOPPING_CART, '支付方式'),
            Action(FluentIcon.CODE, '兑换代码和礼品卡'),
        ])
        menu.addSeparator()
        menu.addAction(Action(FluentIcon.SETTING, '设置'))
        menu.exec(e.globalPos())

    def closeEvent(self, event):
        self.can_device.close_device()
        event.accept()


if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    app.exec_()
```

- [ ] **Step 2: sanity check**

```bash
python -c "import main; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: 提交**

```bash
git add main.py
git commit -m "refactor(main): 主页面切换到 GroupHomeWidget；旧 MainWindow 删除；保留 manual_widget 路径不变"
```

---

## Task 16: 手动联调 + 调整

**Files:** 无（手动测试）

> 此任务**不写代码**，跑起来打开 CAN（如果硬件可用）或者干跑空 CAN，验证 UI 渲染、布局、组切换流程。如果发现 bug，按 superpowers:systematic-debugging 流程修。

- [ ] **Step 1: 跑 debug 模式打包测试启动**

```bash
build_nuitka_debug.bat
```
Expected: 打包成功，CMD 窗口能打开 `release\main.dist\INFY_POWER_debug.exe`，主页加载，组选择器可见，控件初始 disabled。

> 若打包失败，先看 CMD 输出错误，对应修，然后重打。

- [ ] **Step 2: 验收清单（无硬件场景）**

逐项确认：
- [ ] 主页面加载，左侧"组聚合 + 实时曲线 + 模块表"，右侧"组控制"
- [ ] 顶部"打开 CAN"按钮可见，组选择器列出 1~15
- [ ] 没打开 CAN 时，组选择器、设定输入框、3 个按钮全部 disabled
- [ ] 切到"手动操作"页能正常打开（旧 manual_widget 不被打断）
- [ ] 切到"Settings"页能切换 Light/Dark 主题
- [ ] 关闭主窗口能干净退出（无 traceback）

- [ ] **Step 3: 验收清单（有 CAN + 模块场景，可选）**

如果硬件可用：
- [ ] 点"打开 CAN"，按钮文字变"关闭 CAN"，组选择器解锁
- [ ] 选组，600ms 内模块表填充
- [ ] 实时曲线滚动，电压/电流/功率三条线
- [ ] 切到"模块 0x00"，曲线清空重新画该模块的 V/I/P
- [ ] 在右侧改电压/电流，点"设定下发"，模块表数据跟着变
- [ ] 点"启动组输出"弹确认框，确认后组开机
- [ ] 模块表点 💤，对应模块进入休眠状态（电流变 0，下次 0x04 回复显示）
- [ ] 切组到另一个组，旧组开机时弹 InfoBar 提示

- [ ] **Step 4: 提交（即使没改代码也提交一个 chore commit 标记联调完成）**

```bash
git commit --allow-empty -m "chore: 主页面组级控制改造 联调通过"
```

---

## Self-Review

走一遍 spec 的每节，对应到任务：

| Spec 节 | 任务 |
|---|---|
| §1 心智模型 | (架构层面，无单独任务，体现在 §2/§5) |
| §2 用户操作主线 | Task 14 (`_toggle_can`, `_on_group_changed`, `_bind_group`, `_discover_now`) |
| §2.1 切组 InfoBar | Task 14 `_on_group_changed` 里的 `InfoBar.warning` |
| §2.2 三个特殊状态 | Task 13/14 `_set_idle_state` / `_set_active_state` / `_refresh_aggregate_view` 空状态 |
| §3 整体布局 | Task 13 `_build_ui` |
| §4 心跳轮询调度 | Task 8 (`GroupPoller` 链式) |
| §4.3 RX 即 push | Task 14 `_chart_listener` + `_refresh_aggregate_view` UI timer |
| §5.1 初始发现 | Task 9 `discover_modules` |
| §5.2 周期验证 + 跨组踢出 | Task 10 `_on_rx` 0x04 分支 |
| §5.3 离线四态 | Task 2 `lifecycle` + Task 12 `update_modules` 视觉反馈 |
| §5.4 手动刷新 | Task 13 `btn_refresh` + Task 14 `_discover_now` |
| §6.1-6.4 chart 改造 | Task 11 |
| §6.5 main.py 对接 | Task 14 `_chart_listener` |
| §7 组控制 | Task 13 `_build_control_panel` + Task 14 `_on_apply_setpoint` / `_on_group_power` |
| §8 单模块操作 | Task 12 (复选框列) + Task 14 (`_on_sleep_toggled`/`_on_led_toggled`) |
| §8.2 行级告警 | Task 12 `update_modules` 中 IconInfoBadge 分支 |
| §8.3 离线行禁用 | Task 12 `setFlags(Qt.NoItemFlags)` |
| §9 数据模型 | Tasks 2/3/4 |
| §10 CAN 协议层重构 | Tasks 5/6/7 |
| §10.4 GroupPoller | Tasks 8/9/10 |
| §11 配置 | Task 1 |
| §12 错误处理 | Task 14 (idle/active state + 空模块表) |
| §13 协议冲突分析 | (设计依据，体现在 Task 8 仅暴露 0x19/0x14；不需要单独任务) |
| §14 测试策略 | Tasks 1/2/3/4/6/7/8/9/10 各自的 TDD 步骤 |
| §15 实施分支 | (已在 brainstorming 阶段创建) |

**Placeholder scan**：grep 全文 "TBD" / "TODO" / "FIXME" → 0 命中。每个步骤都有完整代码或具体命令。

**类型一致性**：
- `GroupPoller(state=..., schedule_fn=..., poll_interval_ms=...)`：Tasks 8/9/10/14 全部一致
- `state.modules: dict[int, ModuleState]`：Tasks 4/8/10/12 一致
- `RxEvent(errorCode, deviceCode, cmdCode, dstAddr, srcAddr, data)`：Tasks 7/8/10 一致
- `ModuleState.lifecycle(now, pending_ms, offline_ms, gone_ms)`：Tasks 2/12 一致

**潜在歧义**：
- Task 9 测试里引用 `tests.test_reg1k_listeners._FakeMsg`：步骤 4 已注明 sys.path 调整。
- Task 14 `_chart_listener` 与 GroupPoller 的 `_on_rx` 都监听 RX —— 两个 listener 并行注册，互不干扰（一个填 GroupState，一个 push chart），符合 Task 7 设计。

无放置 fix。
